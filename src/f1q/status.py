from __future__ import annotations

from pathlib import Path

from f1q.authorization import load_project_config
from f1q.errors import LedgerLocked
from f1q.ledger import Ledger
from f1q.paths import resolve_project_root
from f1q.runner import ledger_paths


def run_status(root: Path | None = None) -> dict:
    root = resolve_project_root(root)
    config, config_hash, _ = load_project_config(root)
    db, lock = ledger_paths(root, config)
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
            for row in ledger.list_runs():
                units = ledger.units_for(row["run_id"])
                runs.append(
                    {
                        "run_id": row["run_id"],
                        "status": row["status"],
                        "plan_id": row["plan_id"],
                        "evidence_kind": row["evidence_kind"],
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
            incomplete = [r["run_id"] for r in runs if r["status"] in {"running", "interrupted", "pending"}]
            bootstrap_done = any(
                r["plan_id"] == "bootstrap" and r["status"] == "completed" for r in runs
            )
            if incomplete:
                next_work = f"resume --run-id <id> ; incomplete={incomplete}"
                readiness = "not ready"
            elif bootstrap_done:
                next_work = "Stage 2 -- scenario generator and causal checkpoint schema (awaiting implementation prompt)"
                readiness = "stage1-complete-pending-stage2"
                preview_done = any(
                    r["plan_id"] == "development_preview" and r["status"] == "completed" for r in runs
                )
                if preview_done:
                    next_work = "Stage 3 -- simulator-check plan (python -m f1q run --plan simulator_check)"
                    readiness = "stage2-complete-pending-stage3"
                    sim_done = any(
                        r["plan_id"] == "simulator_check" and r["status"] == "completed" for r in runs
                    )
                    if sim_done:
                        next_work = "Stage 4 -- action model, QUBO and independent classical references (awaiting implementation prompt)"
                        readiness = "stage3-complete-pending-stage4"
            else:
                next_work = "run --plan bootstrap"
                readiness = "unknown"
            ledger_state = {
                "present": True,
                "runs": runs,
                "completed_units": completed,
                "failed_units": failed,
                "pending_units": pending,
                "interrupted_units": interrupted,
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
        **ledger_state,
    }
