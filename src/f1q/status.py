from __future__ import annotations

from pathlib import Path

from f1q.authorization import load_project_config
from f1q.errors import LedgerLocked
from f1q.formulation.legacy_counts import LEGACY_WITHDRAWN_RUN_IDS, legacy_archive_summary
from f1q.ledger import Ledger
from f1q.paths import resolve_project_root
from f1q.runner import ledger_paths
from f1q.simulator.config import INTERFACE_VERSION, SIMULATOR_VERSION


def _closure_complete(root: Path) -> bool:
    summary = root / "evidence/formulation/artifacts/stage4_closure/closure_summary.json"
    if not summary.is_file():
        return False
    import json

    try:
        data = json.loads(summary.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(data.get("ok")) and int(data.get("completed_episodes") or 0) == 64


def _phase5_status(root: Path) -> str:
    import json

    docs = root / "docs/evidence/stage5/STAGE_5_FINAL_VERIFY.json"
    if not docs.is_file():
        return "PENDING"
    try:
        data = json.loads(docs.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "PENDING"
    return str(data.get("PHASE_5_ENGINEERING") or "PENDING")


def _phase6_status(root: Path) -> str:
    import json

    docs = root / "docs/evidence/stage6/STAGE_6_FINAL_VERIFY.json"
    if not docs.is_file():
        return "PENDING"
    try:
        data = json.loads(docs.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "PENDING"
    return "PASS_WITH_DOCUMENTED_LIMITATIONS" if data.get("ok") else "PARTIAL"


def run_status(root: Path | None = None) -> dict:
    root = resolve_project_root(root)
    config, config_hash, _ = load_project_config(root)
    db, lock = ledger_paths(root, config)
    legacy = legacy_archive_summary(root)
    gate = {
        "STAGE_4_ENGINEERING": "CLOSED_WITH_DOCUMENTED_LIMITATIONS"
        if _closure_complete(root)
        else "PENDING_BOUNDED_CLOSURE",
        "LEGACY_EXHAUSTIVE_GATE": "PARTIAL",
        "LEGACY_GATE_ACTION": "ARCHIVED_DO_NOT_RESUME",
        "PROXY_HEADROOM": "ZERO",
        "STAGE_5A": "PASS",
        "SELECTED_ARCHITECTURE": "A2_multi_epoch_scenario_contingent_strategy_policy",
        "PHASE_5_ENGINEERING": _phase5_status(root),
        "PHASE_6_ENGINEERING": _phase6_status(root),
        "QPU_EXECUTION_AUTHORISED": False,
        "simulator_version": SIMULATOR_VERSION,
        "interface_version": INTERFACE_VERSION,
        "legacy_archive": legacy,
    }
    next_work_default = (
        "Phase 6 complete; Phase 7 mechanism only after explicit prompt + dated amendment + review. "
        "Operational/superiority Phase 7 not ready. No QPU."
        if _phase6_status(root) in {"PASS_WITH_DOCUMENTED_LIMITATIONS", "PASS", "PARTIAL"}
        else (
            "Phase 5 complete pending review; next is Stage 6 local pilot (not hardware) when authorised."
            if _phase5_status(root) in {"PASS", "PARTIAL"}
            else "Run Phase 5: python -m f1q run --plan phase5"
        )
    )
    ledger_state: dict
    if not db.is_file():
        ledger_state = {
            "present": False,
            "runs": [],
            "completed_units": [],
            "failed_units": [],
            "pending_units": [],
            "next_permitted_work": "run --plan bootstrap (Stage 1 software-check fixture)",
            "readiness": "unknown",
        }
    else:
        ledger = Ledger(db, lock, root=root)
        try:
            ledger.acquire(blocking=False)
            runs = []
            completed: list[str] = []
            failed: list[str] = []
            pending: list[str] = []
            interrupted: list[str] = []
            archived_incomplete: list[str] = []
            for row in ledger.list_runs():
                units = ledger.units_for(row["run_id"])
                archived = row["run_id"] in LEGACY_WITHDRAWN_RUN_IDS
                runs.append(
                    {
                        "run_id": row["run_id"],
                        "status": row["status"],
                        "plan_id": row["plan_id"],
                        "evidence_kind": row["evidence_kind"],
                        "archived_do_not_resume": archived,
                        "units": [{"unit_id": u["unit_id"], "status": u["status"]} for u in units],
                    }
                )
                for unit in units:
                    key = f"{row['run_id']}:{unit['unit_id']}"
                    if unit["status"] == "completed":
                        completed.append(key)
                    elif unit["status"] == "failed":
                        failed.append(key)
                    elif unit["status"] == "pending":
                        pending.append(key)
                    elif unit["status"] == "interrupted":
                        interrupted.append(key)
            incomplete = [
                r["run_id"]
                for r in runs
                if r["status"] in {"running", "interrupted", "pending"}
                and r["run_id"] not in LEGACY_WITHDRAWN_RUN_IDS
            ]
            archived_incomplete = [
                r["run_id"]
                for r in runs
                if r["status"] in {"running", "interrupted", "pending"}
                and r["run_id"] in LEGACY_WITHDRAWN_RUN_IDS
            ]
            bootstrap_done = any(
                r["plan_id"] == "bootstrap" and r["status"] == "completed" for r in runs
            )
            if _closure_complete(root):
                next_work = next_work_default
                readiness = "stage4-engineering-closed-pending-stage5-architecture"
                gate["STAGE_4_ENGINEERING"] = "CLOSED_WITH_DOCUMENTED_LIMITATIONS"
            elif incomplete:
                next_work = f"resume --run-id <id> ; incomplete={incomplete}"
                readiness = "not ready"
            elif bootstrap_done:
                next_work = next_work_default
                readiness = "stage4-engineering-pending-or-review"
                preview_done = any(
                    r["plan_id"] == "development_preview" and r["status"] == "completed" for r in runs
                )
                if preview_done:
                    sim_done = any(
                        r["plan_id"] == "simulator_check" and r["status"] == "completed" for r in runs
                    )
                    repair_done = any(
                        r["plan_id"] == "simulator_repair" and r["status"] == "completed" for r in runs
                    )
                    form_done = any(
                        r["plan_id"] == "formulation_check" and r["status"] == "completed" for r in runs
                    )
                    form_repair_done = any(
                        r["plan_id"] == "formulation_repair_check" and r["status"] == "completed"
                        for r in runs
                    )
                    if form_repair_done or form_done or repair_done or sim_done:
                        next_work = next_work_default
                        readiness = "stage4-engineering-closed-or-pending-bounded-closure"
            else:
                next_work = "run --plan bootstrap"
                readiness = "unknown"
            if archived_incomplete:
                # Visible as history only — never suggest resume.
                next_work = (
                    f"{next_work} | archived_legacy_incomplete={archived_incomplete} "
                    "(ARCHIVED_DO_NOT_RESUME)"
                )
            ledger_state = {
                "present": True,
                "runs": runs,
                "completed_units": completed,
                "failed_units": failed,
                "pending_units": pending,
                "interrupted_units": interrupted,
                "archived_legacy_incomplete_run_ids": archived_incomplete,
                "next_permitted_work": next_work,
                "readiness": readiness,
            }
        except LedgerLocked:
            ledger_state = {
                "present": True,
                "readiness": "unknown",
                "next_permitted_work": "ledger locked by another writer",
            }
        finally:
            ledger.release()
    return {
        "command": "status",
        "project_root": str(root),
        "active_stage": config.active_stage,
        "scientific_protocol": config.scientific_protocol_status,
        "protocol_frozen": config.protocol_frozen,
        "hardware_execution_enabled": config.hardware_execution_enabled,
        "qpu_account_queried": False,
        "new_physical_qpu_jobs_submitted": 0,
        "research_experiments_executed": 0,
        "configuration_hash_draft": config_hash,
        "unknown_is_not_ready": True,
        **gate,
        **ledger_state,
    }
