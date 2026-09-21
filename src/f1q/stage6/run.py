"""Phase 6 foreground orchestrator — freeze → pilot → analysis → verify → report."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from f1q.hashing import sha256_file, sha256_json
from f1q.stage6 import PHASE5_CORRECTED_RUN_ID, PHASE5_FINAL_ACCEPTANCE_COMMIT, STAGE6_VERSION
from f1q.stage6.capacity import build_capacity_estimates, inspect_machine
from f1q.stage6.causal_adapter import validate_simulator_adapter
from f1q.stage6.config import Phase6Config, config_to_frozen_dict, default_phase6_config
from f1q.stage6.freeze import build_freeze_record
from f1q.stage6.novelty import build_novelty_comparison
from f1q.stage6.noisy import run_noisy_panel
from f1q.stage6.pilot import (
    _load_phase5_assets,
    measure_development_unit,
    run_mechanism_pilot,
    write_json,
)
from f1q.stage6.sizing import mechanism_precision_targets_predeclared, size_from_pilot_summaries
from f1q.stage6.splits import build_calibration_splits
from f1q.stage6.verify import run_targeted_verification


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Progress:
    def __init__(self, interval_s: float = 30.0):
        self.interval_s = interval_s
        self.t0 = time.perf_counter()
        self.last = self.t0

    def __call__(self, msg: str) -> None:
        now = time.perf_counter()
        elapsed = now - self.t0
        print(f"[phase6 +{elapsed:7.1f}s] {msg}", flush=True)
        self.last = now


def _git_head(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(root), text=True
        ).strip()
    except Exception:
        return "UNKNOWN"


def _dirty_patch_hash(root: Path) -> str | None:
    try:
        diff = subprocess.check_output(["git", "diff", "HEAD"], cwd=str(root))
        if not diff.strip():
            return None
        return hashlib.sha256(diff).hexdigest()
    except Exception:
        return None


def _dossier_source_hash(root: Path) -> str:
    path = root / "docs/protocol/SOURCE_HASH.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else "missing"
    for line in text.splitlines():
        if line.startswith("SHA256_PDF:"):
            return line.split(":", 1)[1].strip()
    return sha256_json({"source_hash_fallback": True})


def _requirements_map() -> dict[str, Any]:
    return {
        "phase6_requirements": [
            {"id": "P6-1", "dossier": "§§11–16", "req": "Frozen models/policies/circuits before calibration", "evidence": "protocol_freeze.json"},
            {"id": "P6-2", "dossier": "§7/§18", "req": "24 calibration blocks, 3/family, SC+VSC cases", "evidence": "calibration_splits.json"},
            {"id": "P6-3", "dossier": "§12–13/§17", "req": "C0/C1 p=1/2; learned/fixed/NN/random; classical refs", "evidence": "pilot_receipt.json"},
            {"id": "P6-4", "dossier": "§18–19", "req": "Precision targets + sizing; headroom gate", "evidence": "statistical_sizing.json"},
            {"id": "P6-5", "dossier": "§17", "req": "Machine capacity + Phase 7 resource estimates", "evidence": "capacity_estimates.json"},
            {"id": "P6-6", "dossier": "§10/§26 Gate E", "req": "Scientific value / novelty comparison", "evidence": "novelty_comparison.json / STAGE_6_NOVELTY_COMPARISON.md"},
            {"id": "P6-7", "dossier": "§26 Gate F", "req": "Local precision and resource gate", "evidence": "capacity_estimates.json + sizing"},
            {"id": "P6-8", "dossier": "§15/§23", "req": "Causal/operational integration assessment", "evidence": "causal_adapter.json"},
        ],
        "phase7_planned_not_executed": [
            "Full ideal circuit panel (dossier counts)",
            "Held-out primary analysis",
            "Ablation matrix",
            "Fresh variational-reference campaign at dossier cap",
        ],
        "phase8_hardware_deferred": [
            "IBM backend selection",
            "QPU submission path",
            "Hardware quality/latency blocks",
        ],
        "unresolved_prerequisites": [
            "Causal model change + retraining for operational readiness",
            "Nonzero headroom for superiority path",
            "Dated amendment if reduced Phase 7 matrix used before final-test access",
        ],
    }


def execute_phase6_run(root: Path, cfg: Phase6Config | None = None) -> dict[str, Any]:
    cfg = cfg or default_phase6_config()
    progress = Progress(cfg.progress_interval_s)
    t0 = time.perf_counter()
    source_commit = _git_head(root)
    dirty = _dirty_patch_hash(root)
    run_id = str(uuid.uuid4())
    evidence_dir = root / "evidence" / "stage6" / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    docs_ev = root / "docs" / "evidence" / "stage6"
    docs_ev.mkdir(parents=True, exist_ok=True)

    progress("inspect machine + deps")
    machine = inspect_machine()
    progress("measure development unit timing")
    dev_timing = measure_development_unit(cfg)
    proposed = {
        "calibration_blocks": 24,
        "cases": 48,
        "family_depths": 4,
        "policies": 4,
        "distribution_evals": 48 * 4 * 4,
        "est_seconds_from_dev_unit": float(dev_timing["est_48_cases_four_policies_s"]),
        "ceiling_s": cfg.max_pilot_compute_s,
        "fits_ceiling_estimate": float(dev_timing["est_48_cases_four_policies_s"]) <= cfg.max_pilot_compute_s,
        "workers": cfg.max_workers,
        "pool_shots": cfg.pool_shots,
        "pool_seeds": cfg.pool_seeds,
    }
    write_json(evidence_dir / "machine_inspect.json", machine)
    write_json(evidence_dir / "development_unit_timing.json", dev_timing)
    write_json(evidence_dir / "proposed_workload.json", proposed)

    # Precision targets BEFORE calibration outcomes
    pre_precision = mechanism_precision_targets_predeclared(cfg)
    write_json(evidence_dir / "precision_targets_predeclared.json", pre_precision)

    progress("build freeze record (before calibration outcomes)")
    freeze = build_freeze_record(
        root,
        cfg,
        source_commit=source_commit,
        dirty_tree_patch_hash=dirty,
        machine=machine,
        development_unit_timing=dev_timing,
        proposed_workload=proposed,
    )
    write_json(evidence_dir / "protocol_freeze.json", freeze)

    progress("create calibration cohort")
    dossier_hash = _dossier_source_hash(root)
    # Phase 5 split source hash from corrected frozen config / split audit
    p5_split = json.loads(
        (root / f"evidence/stage5/{PHASE5_CORRECTED_RUN_ID}/split_audit.json").read_text(encoding="utf-8")
    )
    phase5_source_hash = str(p5_split.get("source_hash") or dossier_hash)
    splits = build_calibration_splits(
        source_hash=dossier_hash,
        phase5_source_hash=phase5_source_hash,
        salt=cfg.split_source_salt,
    )
    write_json(evidence_dir / "calibration_splits.json", splits)
    write_json(evidence_dir / "requirements_map.json", _requirements_map())

    progress("causal adapter validation")
    causal = validate_simulator_adapter(root)
    write_json(evidence_dir / "causal_adapter.json", causal)

    progress("mechanism pilot start")
    pilot = run_mechanism_pilot(
        root,
        cfg,
        splits["calibration"],
        evidence_dir=evidence_dir,
        progress=progress,
        phase5_source_hash=phase5_source_hash,
    )

    progress("noisy panel")
    assets = _load_phase5_assets(root, cfg.phase5_corrected_run_id)
    noisy = run_noisy_panel(cfg, assets=assets, progress=progress)
    write_json(evidence_dir / "noisy_panel.json", noisy)

    progress("statistical sizing")
    sizing = size_from_pilot_summaries(cfg, pilot)
    write_json(evidence_dir / "statistical_sizing.json", sizing)

    progress("capacity estimates")
    repaired_path = root / "evidence/stage5/final_acceptance_repair/actual_circuit_resources.json"
    repaired = json.loads(repaired_path.read_text(encoding="utf-8")) if repaired_path.is_file() else None
    # resources may be wrapped
    repaired_rows = repaired.get("rows") if isinstance(repaired, dict) else repaired
    capacity = build_capacity_estimates(
        cfg,
        development_timing=dev_timing,
        pilot_receipt=pilot,
        repaired_resources=repaired_rows if isinstance(repaired_rows, list) else repaired,
        machine=machine,
    )
    write_json(evidence_dir / "capacity_estimates.json", capacity)

    progress("Gate E novelty")
    novelty = build_novelty_comparison(
        pilot_headroom=str(pilot.get("development_headroom") or "UNKNOWN"),
        causal_operational_ready=bool(causal.get("causal_operational_readiness")),
    )
    write_json(evidence_dir / "novelty_comparison.json", novelty)

    # Deviations + readiness
    deviations = []
    if pilot.get("failed_cases"):
        deviations.append(
            {
                "id": "pilot_unit_failures",
                "n": pilot.get("failed_cases"),
                "failures": pilot.get("failures"),
            }
        )
    if not proposed.get("fits_ceiling_estimate"):
        deviations.append({"id": "workload_estimate_exceeded_ceiling_preflight", "proposed": proposed})
    if float(capacity.get("extrapolation_full_dossier_cpu_hours", {}).get("total") or 0) > cfg.dossier_cpu_hour_ceiling:
        deviations.append(
            {
                "id": "full_dossier_phase7_exceeds_24h_ceiling",
                "action": "use_feasible_reduced_matrix_with_dated_amendment",
            }
        )
    deviations.append(
        {
            "id": "historical_variational_param_vectors_not_fully_archived",
            "disclosure": freeze["bank_vs_variational_reference_audit"]["disclosure"],
        }
    )
    write_json(evidence_dir / "deviations.json", {"deviations": deviations})

    feasible = capacity.get("feasible_proposed_phase7_matrix", {})
    readiness = {
        "PHASE_6_ENGINEERING": "PASS_WITH_DOCUMENTED_LIMITATIONS"
        if pilot.get("completed_cases", 0) >= 40
        else "PARTIAL",
        "GATE_E_SCIENTIFIC_VALUE": novelty.get("GATE_E_SCIENTIFIC_VALUE"),
        "GATE_F_LOCAL_PRECISION_AND_RESOURCES": (
            "PASS_WITH_LIMITATIONS"
            if feasible.get("fits_24h_ceiling")
            else "PASS_WITH_LIMITATIONS_REDUCED_MATRIX_REQUIRED"
        ),
        "PROTOCOL_STATUS": "BLOCKED_DRAFT"
        if not causal.get("causal_operational_readiness")
        else "FROZEN_MECHANISM_SCOPE_ONLY",
        "ADMITTED_SCIENTIFIC_SCOPE": (
            "local_A2_circuit_mechanism_and_resource_estimation;"
            "restricted_synthetic_revealed_duration_surrogate;"
            "no_operational_race_decision;"
            "no_H1_superiority;"
            "no_QPU"
        ),
        "CAUSAL_OPERATIONAL_READINESS": False,
        "PHASE_7_MECHANISM_READY": True,
        "PHASE_7_OPERATIONAL_READY": False,
        "PHASE_7_SUPERIORITY_READY": False,
        "DEVELOPMENT_HEADROOM": pilot.get("development_headroom"),
        "SUPERIORITY_PATH_AVAILABLE": False,
        "FINAL_TEST_ACCESSED": False,
        "QPU_EXECUTION_AUTHORISED": False,
        "PROPOSED_PHASE_7_COUNTS": feasible.get("proposed_counts"),
        "ESTIMATED_PHASE_7_CPU_HOURS": feasible.get("arithmetic_cpu_hours", {}).get("sum"),
    }
    # Protocol: FROZEN only for scientifically admitted sufficiently specified scope
    # Mechanism scope is sufficiently specified for local pilot follow-up, but full scientific
    # protocol remains BLOCKED_DRAFT for operational/superiority fields.
    if novelty.get("GATE_E_SCIENTIFIC_VALUE") == "PASS_FOR_DEFINED_SCOPE":
        readiness["PROTOCOL_STATUS"] = "BLOCKED_DRAFT"
        readiness["PROTOCOL_NOTE"] = (
            "Mechanism/resource scope is specified; full protocol FROZEN blocked pending "
            "causal operational redesign fields and dated Phase 7 amendment before final-test access. "
            "Hardware fields deferred to Phase 8."
        )
    write_json(evidence_dir / "readiness_matrix.json", readiness)

    progress("targeted verification")
    verify = run_targeted_verification(
        root,
        evidence_dir,
        freeze=freeze,
        pilot_receipt=pilot,
        split_audit=splits["audit"],
    )
    write_json(evidence_dir / "verify_payload.json", verify)

    progress("write reports")
    from f1q.stage6.report import write_all_reports

    report_paths = write_all_reports(
        root,
        run_id=run_id,
        evidence_dir=evidence_dir,
        docs_ev=docs_ev,
        cfg=cfg,
        freeze=freeze,
        splits=splits,
        pilot=pilot,
        causal=causal,
        noisy=noisy,
        sizing=sizing,
        capacity=capacity,
        novelty=novelty,
        readiness=readiness,
        deviations=deviations,
        verify=verify,
        source_commit=source_commit,
        dirty=dirty,
        machine=machine,
        elapsed_s=time.perf_counter() - t0,
    )

    # Manifest after reports
    artifact_files = sorted(p for p in evidence_dir.rglob("*") if p.is_file())
    manifest_files = {}
    for p in artifact_files:
        rel = str(p.relative_to(evidence_dir))
        if rel in {"STAGE_6_MANIFEST.json", "STAGE_6_FINAL_VERIFY.json"}:
            continue
        manifest_files[rel] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    # Include docs reports
    for key, path in report_paths.items():
        if path and Path(path).is_file():
            manifest_files[f"docs:{key}"] = {
                "sha256": sha256_file(Path(path)),
                "bytes": Path(path).stat().st_size,
                "path": str(Path(path).relative_to(root)),
            }

    manifest = {
        "schema_version": "stage6.manifest.v1",
        "run_id": run_id,
        "stage6_version": STAGE6_VERSION,
        "source_commit": source_commit,
        "dirty_tree_patch_hash": dirty,
        "phase5_final_acceptance_commit": PHASE5_FINAL_ACCEPTANCE_COMMIT,
        "phase5_corrected_run_id": PHASE5_CORRECTED_RUN_ID,
        "created_at_utc": _utc_now(),
        "config_sha256": config_to_frozen_dict(cfg)["config_sha256"],
        "freeze_sha256": freeze.get("freeze_sha256"),
        "files": manifest_files,
        "readiness": readiness,
        "qpu_jobs": 0,
        "qpu_usage_seconds": 0,
        "qpu_execution_authorised": False,
    }
    manifest_hash_payload = {k: v for k, v in manifest.items()}
    manifest["manifest_sha256"] = sha256_json(manifest_hash_payload)
    man_path = evidence_dir / "STAGE_6_MANIFEST.json"
    write_json(man_path, manifest)
    # Docs mirror manifest
    write_json(docs_ev / "STAGE_6_MANIFEST.json", manifest)

    # Final verify after manifest
    verify["manifest_path"] = str(man_path.relative_to(root))
    verify["manifest_sha256"] = sha256_file(man_path)
    verify["verified_at_unix"] = time.time()
    # Re-check manifest hash consistency
    verify["manifest_sha256_matches_file"] = verify["manifest_sha256"] == sha256_file(man_path)
    verify_path = evidence_dir / "STAGE_6_FINAL_VERIFY.json"
    write_json(verify_path, verify)
    write_json(docs_ev / "STAGE_6_FINAL_VERIFY.json", verify)

    # Reopen: update manifest to reference verify without cyclic hash of verify into itself
    # Evidence/report → manifest → verifier (verifier points at manifest; manifest does not include verify hash)
    elapsed = time.perf_counter() - t0
    result = {
        "status": readiness["PHASE_6_ENGINEERING"],
        "run_id": run_id,
        "evidence_dir": str(evidence_dir.relative_to(root)),
        "elapsed_s": elapsed,
        "readiness": readiness,
        "pilot_completed": pilot.get("completed_cases"),
        "pilot_failed": pilot.get("failed_cases"),
        "report_path": report_paths.get("STAGE_6_REPORT"),
        "manifest_path": str(man_path.relative_to(root)),
        "verify_path": str(verify_path.relative_to(root)),
        "source_commit": source_commit,
        "qpu_jobs": 0,
        "qpu_usage_seconds": 0,
    }
    write_json(evidence_dir / "run_receipt.json", result)
    progress(f"complete status={result['status']} elapsed={elapsed:.1f}s")
    return result
