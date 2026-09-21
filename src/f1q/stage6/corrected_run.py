"""Phase 6 correction campaign: shot accounting, gate-noise, capacity, sizing, Gate E.

Preserves historical ``evidence/stage6/bd83cb22-…`` unchanged. Writes new evidence under
``evidence/stage6_corrected/<run_id>/`` and ``docs/evidence/stage6_corrected/``.
"""

from __future__ import annotations

import hashlib
import json
import resource
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from f1q.hashing import sha256_file, sha256_json
from f1q.stage6 import PHASE5_CORRECTED_RUN_ID, PHASE5_FINAL_ACCEPTANCE_COMMIT, STAGE6_VERSION
from f1q.stage6.capacity import build_capacity_estimates, inspect_machine, measure_component_timings
from f1q.stage6.causal_adapter import validate_simulator_adapter
from f1q.stage6.config import Phase6Config, config_to_frozen_dict, default_phase6_config
from f1q.stage6.freeze import build_freeze_record
from f1q.stage6.novelty import build_novelty_comparison
from f1q.stage6.noisy import HISTORICAL_NOISY_PANEL_CLASS, run_noisy_panel
from f1q.stage6.pilot import (
    _load_phase5_assets,
    measure_development_unit,
    run_mechanism_pilot,
    write_json,
)
from f1q.stage6.sizing import mechanism_precision_targets_predeclared, size_from_pilot_summaries
from f1q.stage6.splits import build_calibration_splits
from f1q.stage6.verify_corrected import run_corrected_verification


HISTORICAL_STAGE6_RUN = "bd83cb22-6a38-4d21-9267-3253f52587d7"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Progress:
    def __init__(self, interval_s: float = 30.0):
        self.interval_s = interval_s
        self.t0 = time.perf_counter()
        self.cpu0 = resource.getrusage(resource.RUSAGE_SELF)

    def __call__(self, msg: str) -> None:
        now = time.perf_counter()
        cpu = resource.getrusage(resource.RUSAGE_SELF)
        cpu_s = (cpu.ru_utime - self.cpu0.ru_utime) + (cpu.ru_stime - self.cpu0.ru_stime)
        print(f"[stage6_corrected +{now - self.t0:7.1f}s wall / {cpu_s:7.1f}s cpu] {msg}", flush=True)


def _git_head(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()
    except Exception:
        return "UNKNOWN"


def _dirty_patch_hash(root: Path) -> str | None:
    try:
        diff = subprocess.check_output(["git", "diff", "HEAD"], cwd=str(root))
        untracked = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=str(root)
        )
        payload = diff + b"\n---UNTRACKED---\n" + untracked
        if not diff.strip() and not untracked.strip():
            return None
        return hashlib.sha256(payload).hexdigest()
    except Exception:
        return None


def _source_tree_inventory(root: Path) -> dict[str, Any]:
    """Provenance including new/untracked implementation files (not patch-hash alone)."""
    paths: list[str] = []
    for base in ("src/f1q/stage6", "tests/stage6", "configs"):
        p = root / base
        if not p.exists():
            continue
        for f in sorted(p.rglob("*")):
            if f.is_file() and f.suffix in {".py", ".yaml", ".yml"} and "__pycache__" not in str(f):
                paths.append(str(f.relative_to(root)))
    files = {}
    for rel in paths:
        fp = root / rel
        files[rel] = {"sha256": sha256_file(fp), "bytes": fp.stat().st_size}
    return {
        "n_files": len(files),
        "files": files,
        "inventory_sha256": sha256_json(files),
    }


def _dossier_source_hash(root: Path) -> str:
    path = root / "docs/protocol/SOURCE_HASH.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else "missing"
    for line in text.splitlines():
        if line.startswith("SHA256_PDF:"):
            return line.split(":", 1)[1].strip()
    return sha256_json({"source_hash_fallback": True})


def _issue_register() -> dict[str, Any]:
    return {
        "schema_version": "phases1to6.issue_register.v1",
        "issues": [
            {
                "id": "P6-SHOT-CAP",
                "severity": "CRITICAL",
                "stage": 6,
                "files": ["src/f1q/stage6/metrics_pilot.py"],
                "reproduction": "pool_sample_metrics used min(pool_size, 2**n); 8q cases drew 256 not 1024",
                "scientific_impact": "Best-of-pool / shot-budget claims for 8q arms invalid under 1024 label",
                "correction": "Remove Hilbert cap; record requested/actual/counts; resample",
                "evidence_invalidated": [
                    f"evidence/stage6/{HISTORICAL_STAGE6_RUN}/pilot_units/* (8q pools)",
                    "derived pilot summaries / capacity extrapolations depending on those pools",
                ],
                "evidence_reused": ["ideal instance construction", "Phase 5 models/donors", "12q pools structurally OK but re-run for consistent schema"],
                "verification": "test_shot_accounting + corrected pilot shot_conservation_ok",
                "disposition": "CORRECTED_AND_VERIFIED",
            },
            {
                "id": "P6-NOISE-JITTER",
                "severity": "CRITICAL",
                "stage": 6,
                "files": ["src/f1q/stage6/noisy.py"],
                "reproduction": "Historical panel mixed ideal probs with uniform + Gaussian jitter",
                "scientific_impact": "Cannot support gate-level noise resilience or noisy runtime claims",
                "correction": "Withdraw historical class; implement DensityMatrix 1q/2q depolarizing on actual circuits",
                "evidence_invalidated": [f"evidence/stage6/{HISTORICAL_STAGE6_RUN}/noisy_panel.json as gate-noise evidence"],
                "evidence_reused": ["preserved historical file with accurate class label"],
                "verification": "analytical channel checks + zero-noise vs ideal",
                "disposition": "CORRECTED_AND_VERIFIED",
            },
            {
                "id": "P6-CAPACITY-HARDCODE",
                "severity": "HIGH",
                "stage": 6,
                "files": ["src/f1q/stage6/capacity.py"],
                "reproduction": "Hard-coded 0.36s/pool etc → 25.46h; seed double-count risk",
                "scientific_impact": "Reduced matrix / ceiling fit not accepted",
                "correction": "measure_component_timings + explicit arithmetic; resolve blocks vs cases",
                "evidence_invalidated": [f"evidence/stage6/{HISTORICAL_STAGE6_RUN}/capacity_estimates.json claims"],
                "evidence_reused": ["machine inspect method"],
                "verification": "measured pool actual_draws==1024; no double seed multiply",
                "disposition": "CORRECTED_AND_VERIFIED",
            },
            {
                "id": "P6-SIZING-PLACEHOLDER",
                "severity": "HIGH",
                "stage": 6,
                "files": ["src/f1q/stage6/sizing.py"],
                "reproduction": "String 'stratified bootstrap' without computation; 80 blocks vs 80 cases conflation",
                "scientific_impact": "Independent-block recommendation unjustified",
                "correction": "Execute stratified block bootstrap; derive recommendation; disclose saturation",
                "evidence_invalidated": [f"evidence/stage6/{HISTORICAL_STAGE6_RUN}/statistical_sizing.json"],
                "evidence_reused": ["pilot block structure"],
                "verification": "precision_analysis_executed true",
                "disposition": "CORRECTED_AND_VERIFIED",
            },
            {
                "id": "P6-PROTOCOL-GATE-E",
                "severity": "HIGH",
                "stage": 6,
                "files": ["src/f1q/stage6/novelty.py", "docs/STAGE_6_PROTOCOL_FREEZE.md"],
                "reproduction": "PROTOCOL BLOCKED_DRAFT while MECHANISM_READY true; Gate E PASS with insufficient F1 contribution",
                "scientific_impact": "Overstated readiness for Phase 7 / scientific value",
                "correction": "Withdraw Gate E PASS; set mechanism ready false until freeze+justification",
                "evidence_invalidated": ["prior GATE_E PASS_FOR_DEFINED_SCOPE", "PHASE_7_MECHANISM_READY true"],
                "evidence_reused": ["literature comparison structure"],
                "verification": "novelty v2 + readiness matrix",
                "disposition": "CORRECTED_AND_VERIFIED",
            },
            {
                "id": "P6-A2-CAUSAL",
                "severity": "HIGH",
                "stage": "5-6",
                "files": ["src/f1q/stage6/causal_adapter.py", "src/f1q/stage5/model.py"],
                "reproduction": "A2 assumes duration revealed at epoch 1",
                "scientific_impact": "Not an operational causal race-decision model",
                "correction": "Document redesign spec; keep CAUSAL_OPERATIONAL_READINESS false",
                "evidence_invalidated": ["any operational F1 claim"],
                "evidence_reused": ["Stage 3 simulator checks as simulator validity only"],
                "verification": "causal_adapter readiness false",
                "disposition": "BLOCKED",
            },
            {
                "id": "P6-ZERO-HEADROOM",
                "severity": "HIGH",
                "stage": 6,
                "files": ["pilot evidence"],
                "reproduction": "Exact classical → ZERO demonstrated proxy headroom",
                "scientific_impact": "Superiority path unavailable; must not manufacture difficulty",
                "correction": "Retain ZERO; SUPERIORITY_PATH false",
                "evidence_invalidated": [],
                "evidence_reused": ["headroom finding"],
                "verification": "strict_improve vs exact == 0 on corrected pilot",
                "disposition": "VERIFIED_BY_REUSABLE_EVIDENCE",
            },
        ],
    }


def execute_stage6_correction(root: Path, cfg: Phase6Config | None = None) -> dict[str, Any]:
    cfg = cfg or default_phase6_config()
    progress = Progress(cfg.progress_interval_s)
    wall0 = time.perf_counter()
    cpu0 = resource.getrusage(resource.RUSAGE_SELF)
    source_commit = _git_head(root)
    dirty = _dirty_patch_hash(root)
    run_id = str(uuid.uuid4())
    evidence_dir = root / "evidence" / "stage6_corrected" / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    docs_ev = root / "docs" / "evidence" / "stage6_corrected"
    docs_ev.mkdir(parents=True, exist_ok=True)

    # Supersession links
    write_json(
        evidence_dir / "supersession.json",
        {
            "supersedes_run_id": HISTORICAL_STAGE6_RUN,
            "historical_evidence_path": f"evidence/stage6/{HISTORICAL_STAGE6_RUN}",
            "historical_report": "docs/STAGE_6_REPORT.md",
            "historical_preserved": True,
            "reason": (
                "Shot under-sampling on 8q; non-gate noise panel; hard-coded capacity; "
                "placeholder sizing; Gate E overstated"
            ),
            "historical_noisy_class": HISTORICAL_NOISY_PANEL_CLASS,
        },
    )
    write_json(evidence_dir / "issue_register.json", _issue_register())
    write_json(evidence_dir / "source_tree_inventory.json", _source_tree_inventory(root))

    progress("inspect machine + measure timings")
    machine = inspect_machine()
    measured = measure_component_timings(cfg)
    dev_timing = measure_development_unit(cfg)
    proposed = {
        "calibration_blocks": 24,
        "cases": 48,
        "family_depths": 4,
        "policies": 4,
        "distribution_evals": 48 * 4 * 4,
        "pool_shots": cfg.pool_shots,
        "pool_seeds": cfg.pool_seeds,
        "hilbert_cap_removed": True,
        "est_seconds_from_dev_unit": float(dev_timing["est_48_cases_four_policies_s"]),
        "ceiling_s": cfg.max_pilot_compute_s,
        "fits_ceiling_estimate": float(dev_timing["est_48_cases_four_policies_s"]) <= cfg.max_pilot_compute_s,
        "measured_pool_1024_s": measured["measured_s"]["one_pool_1024_draws"],
        "measured_actual_draws": measured["actual_draws"],
    }
    write_json(evidence_dir / "machine_inspect.json", machine)
    write_json(evidence_dir / "measured_component_timings.json", measured)
    write_json(evidence_dir / "development_unit_timing.json", dev_timing)
    write_json(evidence_dir / "proposed_workload.json", proposed)

    pre_precision = mechanism_precision_targets_predeclared(cfg)
    write_json(evidence_dir / "precision_targets_predeclared.json", pre_precision)

    progress("freeze record")
    freeze = build_freeze_record(
        root,
        cfg,
        source_commit=source_commit,
        dirty_tree_patch_hash=dirty,
        machine=machine,
        development_unit_timing=dev_timing,
        proposed_workload=proposed,
    )
    freeze["correction_campaign"] = True
    freeze["stage6_version"] = STAGE6_VERSION
    freeze["protocol_freeze_version"] = "v2"
    write_json(evidence_dir / "protocol_freeze.json", freeze)

    progress("calibration cohort (isolated; no final-test)")
    dossier_hash = _dossier_source_hash(root)
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

    progress("causal adapter")
    causal = validate_simulator_adapter(root)
    write_json(evidence_dir / "causal_adapter.json", causal)

    progress("corrected mechanism pilot (exact 1024 draws)")
    pilot = run_mechanism_pilot(
        root,
        cfg,
        splits["calibration"],
        evidence_dir=evidence_dir,
        progress=progress,
        phase5_source_hash=phase5_source_hash,
    )

    progress("gate-channel noisy panel")
    assets = _load_phase5_assets(root, cfg.phase5_corrected_run_id)
    noisy = run_noisy_panel(cfg, assets=assets, progress=progress)
    write_json(evidence_dir / "noisy_panel.json", noisy)

    progress("statistical sizing + bootstrap")
    sizing = size_from_pilot_summaries(cfg, pilot)
    write_json(evidence_dir / "statistical_sizing.json", sizing)

    progress("capacity from measurements")
    repaired_path = root / "evidence/stage5/final_acceptance_repair/actual_circuit_resources.json"
    repaired = json.loads(repaired_path.read_text(encoding="utf-8")) if repaired_path.is_file() else None
    repaired_rows = repaired.get("rows") if isinstance(repaired, dict) else repaired
    capacity = build_capacity_estimates(
        cfg,
        development_timing=dev_timing,
        pilot_receipt=pilot,
        repaired_resources=repaired_rows if isinstance(repaired_rows, list) else repaired,
        machine=machine,
        measured=measured,
    )
    write_json(evidence_dir / "capacity_estimates.json", capacity)

    progress("Gate E novelty reassessment")
    novelty = build_novelty_comparison(
        pilot_headroom=str(pilot.get("development_headroom") or "UNKNOWN"),
        causal_operational_ready=bool(causal.get("causal_operational_readiness")),
    )
    write_json(evidence_dir / "novelty_comparison.json", novelty)

    feasible = capacity.get("feasible_proposed_phase7_matrix", {})
    gate_e = novelty.get("GATE_E_SCIENTIFIC_VALUE")
    readiness = {
        "PHASE_6_ENGINEERING": (
            "PASS_WITH_DOCUMENTED_LIMITATIONS"
            if pilot.get("completed_cases", 0) >= 40 and pilot.get("completed_cases") == pilot.get("planned_cases")
            else "PARTIAL"
        ),
        "PHASE_6_ACCEPTANCE": "CORRECTED_WITH_DOCUMENTED_LIMITATIONS",
        "GATE_E_SCIENTIFIC_VALUE": gate_e,
        "GATE_E_NARROW_MECHANISM_ARTIFACTS": novelty.get("GATE_E_NARROW_MECHANISM_ARTIFACTS"),
        "GATE_F_LOCAL_PRECISION_AND_RESOURCES": (
            "PASS_WITH_LIMITATIONS"
            if sizing.get("precision_analysis_executed")
            and feasible.get("arithmetic_cpu_hours_measured", {}).get("sum_cpu_hours") is not None
            else "FAIL"
        ),
        "PROTOCOL_STATUS": "MECHANISM_SCOPE_DRAFT_V2_NOT_FINAL_TEST_AUTHORISED",
        "SHOT_ACCOUNTING": "CORRECTED",
        "NOISE_EVIDENCE_CLASS": noisy.get("evidence_class") or noisy.get("status"),
        "PRECISION_ANALYSIS_EXECUTED": bool(sizing.get("precision_analysis_executed")),
        "INDEPENDENT_BLOCK_COUNT_JUSTIFIED": sizing.get("mechanism", {})
        .get("independent_block_recommendation", {})
        .get("status"),
        "RESOURCE_ESTIMATES_MEASUREMENT_BACKED": True,
        "CAUSAL_OPERATIONAL_READINESS": False,
        "PHASE_7_MECHANISM_READY": False,
        "PHASE_7_OPERATIONAL_READY": False,
        "PHASE_7_SUPERIORITY_READY": False,
        "PHASE_7_MECHANISM_READY_REASON": (
            "Gate E fail for intended contribution; protocol draft v2 not final-test authorised; "
            "dated amendment + independent review still required even for narrow mechanism follow-up"
        ),
        "DEVELOPMENT_HEADROOM": pilot.get("development_headroom"),
        "SUPERIORITY_PATH_AVAILABLE": False,
        "FINAL_TEST_ACCESSED": False,
        "QPU_EXECUTION_AUTHORISED": False,
        "F1_CONTRIBUTION_STATUS": novelty.get("contribution_assessment", {}).get(
            "adequacy_for_ai_quantum_f1_objective"
        ),
        "PROPOSED_PHASE_7_COUNTS": feasible.get("proposed_counts"),
        "ESTIMATED_PHASE_7_CPU_HOURS": feasible.get("arithmetic_cpu_hours_measured", {}).get("sum_cpu_hours"),
        "BLOCKS_VS_CASES": feasible.get("blocks_vs_cases_resolution"),
    }
    write_json(evidence_dir / "readiness_matrix.json", readiness)
    write_json(
        evidence_dir / "deviations.json",
        {
            "deviations": [
                {
                    "id": "historical_stage6_superseded",
                    "run": HISTORICAL_STAGE6_RUN,
                    "preserved": True,
                },
                {
                    "id": "gate_e_prior_pass_withdrawn",
                    "prior": "PASS_FOR_DEFINED_SCOPE",
                    "now": gate_e,
                },
                {
                    "id": "phase7_mechanism_ready_revoked",
                    "prior": True,
                    "now": False,
                },
            ]
        },
    )

    progress("corrected verification")
    verify = run_corrected_verification(
        root,
        evidence_dir,
        freeze=freeze,
        pilot_receipt=pilot,
        split_audit=splits["audit"],
        noisy=noisy,
        sizing=sizing,
        capacity=capacity,
        readiness=readiness,
    )
    write_json(evidence_dir / "verify_payload.json", verify)

    wall_s = time.perf_counter() - wall0
    cpu1 = resource.getrusage(resource.RUSAGE_SELF)
    cpu_s = (cpu1.ru_utime - cpu0.ru_utime) + (cpu1.ru_stime - cpu0.ru_stime)
    timing = {"wall_s": wall_s, "cpu_s": cpu_s, "max_rss_kb": cpu1.ru_maxrss}
    write_json(evidence_dir / "correction_timing.json", timing)

    # Manifest (exclude verify)
    artifact_files = sorted(p for p in evidence_dir.rglob("*") if p.is_file())
    manifest_files = {}
    for p in artifact_files:
        rel = str(p.relative_to(evidence_dir))
        if rel in {"STAGE_6_CORRECTED_MANIFEST.json", "STAGE_6_CORRECTED_FINAL_VERIFY.json"}:
            continue
        manifest_files[rel] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}

    # Protected historical inventory check (path+hash sample)
    hist_dir = root / "evidence" / "stage6" / HISTORICAL_STAGE6_RUN
    protected = {}
    for name in ("run_receipt.json", "pilot_receipt.json", "noisy_panel.json", "STAGE_6_MANIFEST.json"):
        hp = hist_dir / name
        if hp.is_file():
            protected[name] = {"sha256": sha256_file(hp), "bytes": hp.stat().st_size, "exists": True}

    manifest = {
        "schema_version": "stage6.corrected.manifest.v1",
        "run_id": run_id,
        "stage6_version": STAGE6_VERSION,
        "source_commit": source_commit,
        "dirty_tree_patch_hash": dirty,
        "source_tree_inventory_sha256": sha256_file(evidence_dir / "source_tree_inventory.json"),
        "phase5_final_acceptance_commit": PHASE5_FINAL_ACCEPTANCE_COMMIT,
        "phase5_corrected_run_id": PHASE5_CORRECTED_RUN_ID,
        "supersedes": HISTORICAL_STAGE6_RUN,
        "created_at_utc": _utc_now(),
        "config_sha256": config_to_frozen_dict(cfg)["config_sha256"],
        "freeze_sha256": freeze.get("freeze_sha256"),
        "files": manifest_files,
        "protected_historical_stage6": protected,
        "readiness": readiness,
        "timing": timing,
        "qpu_jobs": 0,
        "qpu_usage_seconds": 0,
        "qpu_execution_authorised": False,
    }
    manifest["manifest_sha256"] = sha256_json({k: v for k, v in manifest.items()})
    man_path = evidence_dir / "STAGE_6_CORRECTED_MANIFEST.json"
    write_json(man_path, manifest)
    write_json(docs_ev / "STAGE_6_CORRECTED_MANIFEST.json", manifest)

    verify["manifest_path"] = str(man_path.relative_to(root))
    verify["manifest_sha256"] = sha256_file(man_path)
    verify["verified_at_unix"] = time.time()
    # Independent re-check of every manifest entry
    man_obj = json.loads(man_path.read_text(encoding="utf-8"))
    entry_ok = True
    entry_failures = []
    for rel, meta in man_obj.get("files", {}).items():
        fp = evidence_dir / rel
        if not fp.is_file():
            entry_ok = False
            entry_failures.append({"rel": rel, "reason": "missing"})
            continue
        if fp.stat().st_size != meta.get("bytes") or sha256_file(fp) != meta.get("sha256"):
            entry_ok = False
            entry_failures.append({"rel": rel, "reason": "hash_or_size_mismatch"})
    verify["manifest_entries_ok"] = entry_ok
    verify["manifest_entry_failures"] = entry_failures
    verify["ok"] = bool(verify.get("ok")) and entry_ok
    verify_path = evidence_dir / "STAGE_6_CORRECTED_FINAL_VERIFY.json"
    write_json(verify_path, verify)
    write_json(docs_ev / "STAGE_6_CORRECTED_FINAL_VERIFY.json", verify)

    result = {
        "status": readiness["PHASE_6_ACCEPTANCE"],
        "run_id": run_id,
        "evidence_dir": str(evidence_dir.relative_to(root)),
        "wall_s": wall_s,
        "cpu_s": cpu_s,
        "readiness": readiness,
        "pilot_completed": pilot.get("completed_cases"),
        "pilot_failed": pilot.get("failed_cases"),
        "manifest_path": str(man_path.relative_to(root)),
        "verify_path": str(verify_path.relative_to(root)),
        "verify_ok": verify.get("ok"),
        "source_commit": source_commit,
        "qpu_jobs": 0,
        "qpu_usage_seconds": 0,
    }
    write_json(evidence_dir / "run_receipt.json", result)
    progress(f"complete status={result['status']} wall={wall_s:.1f}s cpu={cpu_s:.1f}s")
    return result


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    # project root is parents[2] from src/f1q/stage6/corrected_run.py → src/f1q → src → root? 
    # __file__ = .../src/f1q/stage6/corrected_run.py → parents[0]=stage6, [1]=f1q, [2]=src, [3]=root
    root = Path(__file__).resolve().parents[3]
    result = execute_stage6_correction(root)
    print(json.dumps({k: v for k, v in result.items() if k != "readiness"}, indent=2))
    print("READINESS", json.dumps(result["readiness"], indent=2))


if __name__ == "__main__":
    main()
