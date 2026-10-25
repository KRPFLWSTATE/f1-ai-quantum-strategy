"""One isolated preflight and, only if every gate passes, the Design R continuation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from f1q.a4.corrected_cost import HISTORICAL_UNDERPREDICTION
from f1q.a4.isolation import (
    HISTORICAL_SIX_HOUR_RUN_ID,
    ISOLATED_AMENDMENT_ID,
    PRESERVED_RUN_IDS,
    child_env,
    scientific_seal_audit,
    snapshot_protected,
)
from f1q.a4.resources import available_ram_bytes, cpu_seconds
from f1q.a4.six_hour import DISK_RESERVE, PREFLIGHT_WALL_S, six_hour_caps
from f1q.hashing import sha256_file, sha256_json

CONTAMINATION = {
    "evidence/stage6_a4/cdd21ec6-9d95-48a5-806b-64fd7e296434",
    "evidence/stage6_a4/eeb03bdd-4fdf-4e1e-baf6-590b54c11d4a",
    "evidence/stage6_a4/engineering_byproducts",
}


def cell_split(units: list[dict[str, Any]], counts: dict[str, Any]) -> dict[str, int]:
    ablation = 0
    offline_unit = 0
    for unit in units:
        plan = int(unit.get("n_planning_worlds") or 0) * max(int(unit.get("portfolio_k") or 0), 1)
        ev = int(unit.get("n_evaluation_worlds") or 0)
        if unit.get("role") == "ablation":
            ablation += plan + ev
        elif unit.get("role") == "offline_all_plan":
            offline_unit += plan + ev
    pooled = int(counts["plan_world_evaluations_k_once"]) + int(counts["evaluation_worlds"]) - ablation - offline_unit
    serial = ablation + int(counts["offline_continuations"])
    if pooled < 0:
        raise RuntimeError("pooled race cells went negative")
    return {"pooled_race_cells": pooled, "serial_race_cells": serial, "ablation_cells": ablation, "offline_unit_cells": offline_unit}


def run_isolated_pytest(root: Path) -> dict[str, Any]:
    """Full suite in a copy that does not contain the scientific outcome registry."""
    before = snapshot_protected(root)
    seal_before = scientific_seal_audit(root)
    tmp = Path(shutil.mkdtemp(prefix="f1q-isolated-suite-"))
    try:
        def _ignore(directory: str, names: list[str]) -> set[str]:
            ignored = {n for n in names if n in {".git", "__pycache__", ".venv", ".venv-fresh"} or n.endswith(".pyc")}
            return ignored

        shutil.copytree(root, tmp, dirs_exist_ok=True, ignore=_ignore)
        for rel in CONTAMINATION:
            target = tmp / rel
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        env = child_env(tmp)
        env["F1Q_PROTECTED_ROOT"] = str(root.resolve())
        env["F1Q_ENGINEERING_ONLY"] = "1"
        env["F1Q_REVIEWED_SOURCE_COMMIT"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=line"], cwd=str(tmp), env=env, capture_output=True, text=True)
        after = snapshot_protected(root)
        seal_after = scientific_seal_audit(root)
        snapshot_ok = before == after
        return {
            "exit_code": 0 if proc.returncode == 0 and snapshot_ok and seal_before.get("ok") and seal_after.get("ok") and before == after else (proc.returncode or 1),
            "pytest_exit_code": proc.returncode,
            "snapshot_unchanged": snapshot_ok,
            "seal_before_ok": bool(seal_before.get("ok")),
            "seal_after_ok": bool(seal_after.get("ok")),
            "seal_before": seal_before,
            "seal_after": seal_after,
            "stdout_tail": (proc.stdout or "")[-4000:],
            "stderr_tail": (proc.stderr or "")[-4000:],
            "isolated_root": str(tmp),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def focused_parity_canary(root: Path) -> dict[str, Any]:
    """Reuse the 3072 receipt when the kernel identity matches, and run a small canary."""
    from f1q.a4.banks import EVALUATION_BANK
    from f1q.a4.backend_select import select_evaluation_backend
    from f1q.a4.loop import evaluate_candidates_on_bank
    from f1q.a4.prepared import prepare_case
    from f1q.a4.six_hour import KERNEL_SHA256, KERNEL_VERSION, kernel_file_ok
    from f1q.simulator.engine import RaceEngine

    kernel = kernel_file_ok(root)
    receipt = json.loads((root / "evidence/stage6_a4" / HISTORICAL_SIX_HOUR_RUN_ID / "parity_panel" / "PARITY_SUMMARY.json").read_text(encoding="utf-8"))
    identity_ok = (
        kernel["ok"]
        and receipt.get("kernel_source_sha256") == KERNEL_SHA256
        and int(receipt.get("rows") or 0) == 3072
        and int(receipt.get("exact_signature_mismatches") or 0) == 0
        and kernel["version"] == KERNEL_VERSION
    )
    calls = {"n": 0}
    real = RaceEngine.continue_to_finish

    def _wrapped(self, *args, **kwargs):
        calls["n"] += 1
        return real(self, *args, **kwargs)

    RaceEngine.continue_to_finish = _wrapped
    try:
        select_evaluation_backend("candidate")
        pc = prepare_case(
            family_id="fam.green_pit_low.tyre_nonlinear.traffic_dense",
            block_id="engfix.parity.canary",
            regime="SC",
            partition="development",
            index=0,
            seed=67003,
            n_planning=2,
            n_evaluation=2,
        )
        plans = [{"plan": row["plan"], "plan_hash": row["plan_hash"]} for row in pc.legal_table[:2]]
        compiled = evaluate_candidates_on_bank(
            pc.spec_with_budget(30),
            pc.checkpoint_blob,
            plans,
            [960001, 960002],
            bank=EVALUATION_BANK,
            arrival_delay_s=0.02,
            commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
            cache={},
            spec_hash=pc.spec_hash,
            checkpoint_hash=pc.checkpoint_hash,
            nominal_budget_s=30.0,
        )
        scalar_calls = calls["n"]
    finally:
        select_evaluation_backend("legacy")
        RaceEngine.continue_to_finish = real
    canary_ok = scalar_calls == 0 and bool(compiled.get("worlds"))
    return {
        "reused_full_panel": identity_ok and canary_ok,
        "renewed_full_panel": False,
        "identity_ok": identity_ok,
        "canary_ok": canary_ok,
        "scalar_continue_calls": scalar_calls,
        "rows": 3072 if identity_ok else 0,
        "exact_signature_mismatches": 0 if identity_ok else None,
        "kernel": kernel,
        "receipt_sha256": sha256_file(root / "evidence/stage6_a4" / HISTORICAL_SIX_HOUR_RUN_ID / "parity_panel" / "PARITY_SUMMARY.json"),
    }


def resolve_runtime_caps(cfg: dict[str, Any]) -> dict[str, float]:
    from f1q.a4.resources import CAMPAIGN_CPU_CAP_S, CAMPAIGN_WALL_CAP_S
    from f1q.a4.six_hour import is_six_hour

    if is_six_hour(cfg):
        return six_hour_caps(cfg)
    return {
        "campaign_wall_cap_s": float(CAMPAIGN_WALL_CAP_S),
        "campaign_cpu_cap_s": float(CAMPAIGN_CPU_CAP_S),
        "admission_wall_limit_s": 11520.0,
    }


def stop_predicate(elapsed_s: float, caps: dict[str, float]) -> bool:
    return float(elapsed_s) >= float(caps["campaign_wall_cap_s"])


def analysis_gate(*, executed_ok: bool, stopped: bool) -> bool:
    return bool(executed_ok) and not bool(stopped)


def _fail(ev: Path, decision: dict[str, Any]) -> dict[str, Any]:
    from f1q.a4.hashing_io import write_json

    decision["decision_sha256"] = sha256_json({k: v for k, v in decision.items() if k != "decision_sha256"})
    write_json(ev / "ADMISSION_DECISION.json", decision)
    write_json(ev / "ADMISSION_RECEIPT.json", decision)
    return {
        "admitted": False,
        "run_id": decision["run_id"],
        "selected_design": "NONE_RESOURCE_LIMIT",
        "status": decision.get("status") or "not_admitted_resource_limit",
        "gates": decision.get("gates") or {},
        "decision_path": str(ev / "ADMISSION_DECISION.json"),
    }


def run_isolated_admission(root: Path, config_rel: str) -> dict[str, Any]:
    from f1q.a4.completion import load_closure_config
    from f1q.a4.qpu_guard import assert_local_only

    assert_local_only()
    t0 = time.perf_counter()
    cpu0 = cpu_seconds()
    cfg, cfg_hash = load_closure_config(root, config_rel)
    if str(cfg.get("amendment_id")) != ISOLATED_AMENDMENT_ID:
        raise RuntimeError("isolated admission requires the isolated amendment id")
    run_id = str(cfg.get("run_id") or "")
    if run_id in PRESERVED_RUN_IDS or not run_id:
        raise RuntimeError("refusing a preserved or empty run id")
    caps = resolve_runtime_caps(cfg)
    ev = root / "evidence" / "stage6_a4" / run_id
    if ev.exists():
        raise RuntimeError("refusing to resume or overwrite an existing run directory")
    ev.mkdir(parents=True)
    try:
        return _run_isolated_body(root, ev, cfg, cfg_hash, run_id, caps, t0, cpu0)
    except Exception as exc:
        return _fail(ev, {
            "run_id": run_id,
            "amendment_id": ISOLATED_AMENDMENT_ID,
            "admitted": False,
            "status": "not_admitted_exception",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "gates": {},
            "phase_7_authorised": False,
            "qpu_jobs": 0,
            "final_test_accessed": False,
            "registered_scientific_parents_executed": 0,
            "continued_to_corpus": False,
        })


def _run_isolated_body(root, ev, cfg, cfg_hash, run_id, caps, t0, cpu0) -> dict[str, Any]:
    from f1q.a4.contracts import FAMILY_DEPTH_KEYS
    from f1q.a4.donors import build_donor_bank_v2
    from f1q.a4.hashing_io import load_jsonl, write_json
    from f1q.a4.partitions_isolated import build_isolated_partitions
    from f1q.a4.six_hour import build_identity_keys, kernel_file_ok, operation_counts, project_resources
    from f1q.a4.storage_account import identity_ledger, measure_representative_bytes, project_storage
    from f1q.a4.storage_check import recount
    from f1q.a4.unit_ledger import DESIGN_R, design_worlds, enumerate_design_units

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()
    exposed = json.loads((root / "configs" / "design_r_exposed_identities.json").read_text(encoding="utf-8"))
    parts = build_isolated_partitions(exposed)
    registry = json.loads((root / "configs" / "design_r_isolated_registry.json").read_text(encoding="utf-8"))
    if parts["registry_sha256"] if False else registry.get("registry_sha256") != sha256_json({k: v for k, v in registry.items() if k != "registry_sha256"}):
        raise RuntimeError("frozen registry hash does not recompute")
    if set(parts["block_ids"]) != set(registry["block_ids"]):
        raise RuntimeError("registry block ids drifted from the generator")
    write_json(ev / "PARTITIONS.json", parts)
    write_json(ev / "EXPOSURE_LEDGER.json", exposed)
    print(json.dumps({"phase": "isolated_pytest"}), flush=True)
    tests = run_isolated_pytest(root)
    if tests["pytest_exit_code"] != 0 or not tests["snapshot_unchanged"] or not tests["seal_before_ok"] or not tests["seal_after_ok"]:
        return _fail(ev, {
            "run_id": run_id,
            "amendment_id": ISOLATED_AMENDMENT_ID,
            "admitted": False,
            "status": "not_admitted_tests",
            "gates": {"tests": False, "snapshot": tests["snapshot_unchanged"], "seal": tests["seal_before_ok"] and tests["seal_after_ok"]},
            "tests": {k: v for k, v in tests.items() if k not in {"stdout_tail", "stderr_tail"}},
            "tests_stdout_tail": tests["stdout_tail"],
            "tests_stderr_tail": tests["stderr_tail"],
            "continued_to_parity": False,
            "continued_to_rates": False,
            "phase_7_authorised": False,
            "qpu_jobs": 0,
            "final_test_accessed": False,
            "registered_scientific_parents_executed": 0,
            "reviewed_source_commit": head,
            "config_hash": cfg_hash,
        })
    print(json.dumps({"phase": "parity_canary"}), flush=True)
    parity = focused_parity_canary(root)
    if not parity["reused_full_panel"]:
        return _fail(ev, {
            "run_id": run_id,
            "admitted": False,
            "status": "not_admitted_parity",
            "gates": {"literal_parity": False},
            "parity": parity,
            "continued_to_rates": False,
            "phase_7_authorised": False,
            "qpu_jobs": 0,
            "final_test_accessed": False,
            "registered_scientific_parents_executed": 0,
            "reviewed_source_commit": head,
            "config_hash": cfg_hash,
        })
    anchor_rel = "evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b/ANCHOR_FITS.jsonl"
    if sha256_file(root / anchor_rel) != "b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a":
        raise RuntimeError("anchor hash mismatch; refusing reuse")
    fits = load_jsonl(root / anchor_rel)
    bank = build_donor_bank_v2(
        fits,
        source_run_id="09806343-f940-4f33-9e0f-eb2855d0714b",
        source_anchor_path=anchor_rel,
        source_anchor_sha256="b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a",
    )
    n_donors = len(bank["family_depths"][FAMILY_DEPTH_KEYS[0]]["donors"])
    enum = enumerate_design_units(design=DESIGN_R, parts=parts, worlds=design_worlds(DESIGN_R, "minimum"), freeze=None, miniature=False)
    keys = build_identity_keys(parts, bank)
    counts = operation_counts(enum["units"], n_legal=100, n_donors=n_donors, unique_parameter_builds=len(set(keys)))
    split = cell_split(enum["units"], counts)
    print(json.dumps({"phase": "storage"}), flush=True)
    measured = measure_representative_bytes(ev)
    identities = identity_ledger(enum["units"])
    storage = project_storage(identities, measured, n_units=int(enum["n_units"]), evaluation_worlds=int(counts["evaluation_worlds"]))
    checked_storage = recount(enum["units"], measured, n_units=int(enum["n_units"]), evaluation_worlds=int(counts["evaluation_worlds"]))
    print(json.dumps({"phase": "resources"}), flush=True)
    from f1q.a4.measured_resources import measure_workload

    workload = measure_workload(root, pooled_race_cells=split["pooled_race_cells"], serial_race_cells=split["serial_race_cells"], counts={**counts, "n_operation_rows": identities["n_operation_rows"]})
    proj = workload["projection"]
    from f1q.a4.resource_check import project_from_raw

    again = project_from_raw(workload["raw"])
    disk = shutil.disk_usage(str(root))
    ram_limit = int(0.60 * available_ram_bytes())
    rss = int(proj.get("simultaneous_rss_max_bytes") or 0)
    preflight_wall = time.perf_counter() - t0
    historical = json.loads((root / "evidence/stage6_a4" / HISTORICAL_SIX_HOUR_RUN_ID / "ADMISSION_DECISION.json").read_text(encoding="utf-8"))
    historical_projection = project_resources(
        counts,
        {
            "scalar_s_per_cell": 1.0,
            "speedup": float(HISTORICAL_UNDERPREDICTION),
            "compiled_s_per_cell": float(proj["schedule_per_cell_wall_s"]),
            "build_cpu_s": 0.0,
            "resample_s": 0.0,
            "optimiser_s": 0.0,
            "prepare_s": 0.0,
            "other_fixed_s": 0.0,
        },
        efficiency=float(historical["capacity"]["efficiency_8"]),
        cold_wall_s=float(historical["capacity"]["cold_start_wall_s"]),
        underprediction=float(HISTORICAL_UNDERPREDICTION),
    )
    gates = {
        "literal_parity": bool(parity["reused_full_panel"]),
        "kernel_hash": bool(kernel_file_ok(root)["ok"]),
        "tests": tests["pytest_exit_code"] == 0,
        "snapshot": bool(tests["snapshot_unchanged"]),
        "seal": bool(tests["seal_before_ok"] and tests["seal_after_ok"]),
        "storage_independent": int(storage["measured_peak_bytes"]) == int(checked_storage["measured_peak_bytes"]),
        "resource_independent": abs(float(again["admission_wall_s"]) - float(proj["admission_wall_s"])) < 1e-6 and abs(float(again["conservative_cpu_s"]) - float(proj["conservative_cpu_s"])) < 1e-6,
        "cpu": float(proj["conservative_cpu_s"]) <= float(caps["campaign_cpu_cap_s"]),
        "admission_wall": float(proj["admission_wall_s"]) <= float(caps["admission_wall_limit_s"]),
        "campaign_wall": float(proj["campaign_wall_s"]) <= float(caps["campaign_wall_cap_s"]),
        "ram": 0 < rss <= ram_limit,
        "disk": int(storage["measured_peak_bytes"]) <= (1.0 - DISK_RESERVE) * disk.free,
        "preflight_wall": preflight_wall <= PREFLIGHT_WALL_S,
        "k_once": bool(counts["k_applied_once"]),
        "parents_120_80_24": parts["n_train"] == 120 and parts["n_tune"] == 80 and parts["n_calib"] == 24,
        "design_f_not_launched": True,
        "no_new_exposure": tests["seal_after"].get("new_split_outcome_files") == [],
    }
    admitted = all(gates.values())
    decision = {
        "run_id": run_id,
        "amendment_id": ISOLATED_AMENDMENT_ID,
        "admitted": admitted,
        "selected_design": DESIGN_R if admitted else "NONE_RESOURCE_LIMIT",
        "status": "admitted" if admitted else "not_admitted_resource_limit",
        "gates": gates,
        "counts": counts,
        "cell_split": split,
        "storage": storage,
        "storage_independent": checked_storage,
        "projection": proj,
        "historical_formula_sensitivity": historical_projection,
        "historical_storage_bytes": storage["historical_formula_bytes"],
        "rates_raw_summary": {k: workload["raw"][k] for k in ("probe_cells", "pool_makespan_s", "pooled_race_cells", "serial_race_cells", "cold_wall_s", "serial_wall_s") if k in workload["raw"]},
        "parity": parity,
        "tests": {k: v for k, v in tests.items() if k not in {"stdout_tail", "stderr_tail", "seal_before", "seal_after"}},
        "preflight_wall_s": preflight_wall,
        "preflight_cpu_s": cpu_seconds() - cpu0,
        "historical_preflight_wall_s": historical.get("preflight_wall_s"),
        "historical_preflight_cpu_s": historical.get("preflight_cpu_s"),
        "ram_limit_bytes": ram_limit,
        "free_disk_bytes": disk.free,
        "caps": caps,
        "config_hash": cfg_hash,
        "partition_sha256": registry.get("registry_sha256"),
        "reviewed_source_commit": head,
        "kernel": kernel_file_ok(root),
        "phase_7_authorised": False,
        "qpu_jobs": 0,
        "final_test_accessed": False,
        "registered_scientific_parents_executed": 0,
        "design_f_launched": False,
        "consumed": False,
        "miniature": False,
        "underprediction": proj.get("underprediction_factor"),
    }
    decision["decision_sha256"] = sha256_json({k: v for k, v in decision.items() if k != "decision_sha256"})
    write_json(ev / "ADMISSION_DECISION.json", decision)
    write_json(ev / "ADMISSION_RECEIPT.json", decision)
    write_json(ev / "OPERATION_COUNTS.json", counts)
    write_json(ev / "STORAGE_ACCOUNT.json", storage)
    write_json(ev / "RESOURCE_PROJECTION.json", proj)
    write_json(ev / "DONOR_BANK_V2.json", bank)
    write_json(ev / "PRODUCTION_KERNEL.json", {"kernel_version": parity["kernel"]["version"], "sha256": parity["kernel"]["sha256"]})
    print(json.dumps({"phase": "admission_done", "admitted": admitted, "wall_s": proj["admission_wall_s"], "cpu_s": proj["conservative_cpu_s"]}), flush=True)
    return {
        "admitted": admitted,
        "run_id": run_id,
        "selected_design": decision["selected_design"],
        "status": decision["status"],
        "gates": gates,
        "projection": proj,
        "storage": storage,
        "decision_path": str(ev / "ADMISSION_DECISION.json"),
        "config_rel": config_rel,
        "decision_sha256": decision["decision_sha256"],
    }
