"""Phase 6 A4 completion orchestrator: admission → campaign → analysis → verify.

`campaign_raw_complete` is not Phase 6 completion.
"""

from __future__ import annotations

import json
import math
import os
import resource
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from f1q import INTERFACE_VERSION, SIMULATOR_VERSION, __version__ as PACKAGE_VERSION
from f1q.a4.analysis import (
    choose_mc_world_target,
    claims_ledger,
    derive_gate_e,
    derive_gate_f,
    finite_sample_q,
    mc_allowance,
    stage7_block_sizing,
    stratified_block_bootstrap,
)
from f1q.a4.banks import (
    EVALUATION_BANK,
    OFFLINE_EVALUATION_BANK,
    OFFLINE_PLANNING_BANK,
    PLANNING_BANK,
    bank_world_seeds,
    banks_disjoint,
)
from f1q.a4.cache import ByteBoundedCache
from f1q.a4.contracts import (
    ALLOCATOR_OPTIONS,
    FAMILY_DEPTH_KEYS,
    N_POLICY_SEEDS,
    NOMINAL_BUDGETS_S,
    POOL_DRAWS,
    PORTFOLIO_K,
    PRIMARY_BUDGET_S,
    SEED_HIERARCHY,
    WORLD_LADDERS,
    StructuralError,
    circuit_resample_seed,
)
from f1q.a4.distributions import distribution_counters, reset_distribution_counters
from f1q.a4.donors import (
    DonorRanker,
    build_donor_bank_v2,
    donor_features_from_case,
    selected_donors,
    select_donor_policy,
)
from f1q.a4.hashing_io import append_jsonl, load_jsonl, write_json
from f1q.a4.loop import decide_and_evaluate, evaluate_offline_reference
from f1q.a4.partitions import build_a4_partitions
from f1q.a4.pool import run_pool
from f1q.a4.prepared import prepare_case, prepare_counters, reset_prepare_counters
from f1q.a4.qpu_guard import assert_local_only
from f1q.a4.resources import (
    ADMISSION_WALL_LIMIT_S,
    CAMPAIGN_CPU_CAP_S,
    CAMPAIGN_WALL_CAP_S,
    available_ram_bytes,
    choose_workers,
    cpu_seconds,
    current_rss_bytes,
    projection_fits,
)
from f1q.generator.config import cartesian_family_ids
from f1q.hashing import sha256_file, sha256_json
from f1q.paths import resolve_project_root
from f1q.stage5.metrics import normalised_regret

PRIOR_FAILED = "09806343-f940-4f33-9e0f-eb2855d0714b"
PRIOR_ADMISSION = "3de109c7-30d9-4cb0-827f-dbd82c4c509d"
START_COMMIT_EXPECTED = "443c6365777965438e1cd57439a58770227ae513"
REUSED = {
    "MANIFEST.json": "8f620c8fc9048cf27c304847efe7fa79a3eb00aac2f7af6a7b5f0c97db0be70e",
    "ANCHOR_FITS.jsonl": "b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a",
    "NATIVE_NOISE_CORRECTION.json": "5daa9944fe0bbc0e8c837d5002bf0e0bb271db559901480501d1fd57b3adb84d",
    "A3_INVALIDATION.json": "4b9743aea6273eee511133b12e0fde130103aae10c5ec1002484f9a642cd277d",
    "PARTITIONS.json": "31f4b985b15face11752de1094282441d837acd362941c0e2c66e2686602c9f5",
    "PROTOCOL_AMENDMENT_A4.json": "7ee7d9af1e7371c193c32eb4a03751127ed9c7004e6d391957c0e508b5aca9c3",
}

COMPLETED_STATES = {
    "CLOSED_READY_FOR_PHASE7_BOUNDARY",
    "CLOSED_NOT_READY_FOR_PHASE7",
    "INCOMPLETE_ENGINEERING",
    "INCOMPLETE_ENGINEERING_RESOURCE_LIMIT",
}


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_head(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()


def load_closure_config(root: Path, rel: str = "configs/stage6_a4_closure.yaml") -> tuple[dict[str, Any], str]:
    path = root / rel
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data, sha256_file(path)


def amendment_record() -> dict[str, Any]:
    return {
        "schema": "f1q.a4.implementation_resource_amendment.v1",
        "prospective": True,
        "outcomes_opened": False,
        "prior_75min_and_60min_were_implementation_added": True,
        "dossier_constraints": {
            "ram_fraction": 0.60,
            "checkpoint_bounded_units": True,
            "provisional_cpu_hour_ceiling": 24,
        },
        "user_protection_wall_s": CAMPAIGN_WALL_CAP_S,
        "admission_wall_limit_s": ADMISSION_WALL_LIMIT_S,
        "campaign_cpu_cap_s": CAMPAIGN_CPU_CAP_S,
        "world_ladders": WORLD_LADDERS,
        "calibration_evaluation_starts_at": 2048,
        "seed_hierarchy": SEED_HIERARCHY,
        "prior_admission_run": PRIOR_ADMISSION,
        "prior_admission_disposition": "SUPERSEDED_RESOURCE_MODEL_ONLY",
        "may_not_drop_denominators": True,
        "last_resort": "INCOMPLETE_ENGINEERING_RESOURCE_LIMIT",
    }


def lineage_record(*, new_run: str, source_commit: str) -> dict[str, Any]:
    return {
        "new_run_id": new_run,
        "reviewed_source_commit": source_commit,
        "start_commit": START_COMMIT_EXPECTED,
        "prior_admission_run": PRIOR_ADMISSION,
        "prior_admission_disposition": "SUPERSEDED_RESOURCE_MODEL_ONLY",
        "prior_failed_run": PRIOR_FAILED,
        "prior_failed_disposition": "PRESERVED_ANCHOR_SOURCE",
        "a3_run": "a5fdb488-9a90-47f9-a4f5-7f77a74180a6",
        "a3_disposition": "SUPERSEDED_INVALID_IMPLEMENTATION",
        "do_not_modify_historical_files": True,
        "qpu_execution_authorised": False,
        "phase_7_authorised": False,
        "final_test_accessed": False,
    }


def verify_reused_evidence(root: Path) -> dict[str, Any]:
    prior = root / "evidence" / "stage6_a4" / PRIOR_FAILED
    items = []
    for name, expected in REUSED.items():
        path = prior / name
        if not path.is_file():
            raise StructuralError("MISSING_ARTIFACT", "required reused artifact missing", path=str(path))
        got = sha256_file(path)
        rec = {
            "artifact": name,
            "source_run": PRIOR_FAILED,
            "source_path": str(path.relative_to(root)),
            "expected_hash": expected,
            "observed_hash": got,
            "reuse": got == expected,
        }
        if name == "ANCHOR_FITS.jsonl":
            rows = load_jsonl(path)
            rec["n_rows"] = len(rows)
            rec["n_success"] = sum(1 for r in rows if r.get("success"))
            rec["n_unique_anchors"] = len({r.get("block_id") for r in rows})
            rec["schema_ok"] = rec["n_success"] == 288 and rec["n_unique_anchors"] == 24
            rec["reuse"] = rec["reuse"] and rec["schema_ok"]
        if not rec["reuse"]:
            raise StructuralError("INTEGRITY", "reused artifact failed hash/schema/count", path=name, value=rec)
        items.append(rec)
    return {"ok": True, "items": items, "do_not_rerun_anchors": True, "do_not_rerun_native_noise": True}


def copy_reused(root: Path, dest: Path) -> None:
    prior = root / "evidence" / "stage6_a4" / PRIOR_FAILED
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("ANCHOR_FITS.jsonl", "NATIVE_NOISE_CORRECTION.json", "A3_INVALIDATION.json", "PROTOCOL_AMENDMENT_A4.json"):
        shutil.copy2(prior / name, dest / name)


MINIATURE_WORLDS = {
    "training": {"planning": 2, "evaluation": 4},
    "tuning": {"planning": 2, "evaluation": 4},
    "calibration": {"planning": 2, "evaluation": 8},
    "offline": {"planning": 2, "evaluation": 4},
}


def operation_ledger(*, ladder: str, worlds: dict[str, Any], miniature: bool = False, n_legal: int = 100) -> dict[str, Any]:
    n_train_p, n_tune_p, n_cal_p = (2, 2, 2) if miniature else (120, 80, 24)
    n_train_c, n_tune_c, n_cal_c = n_train_p * 2, n_tune_p * 2, n_cal_p * 2
    n_mech = 8 if miniature else 120
    n_noisy = 0 if miniature else 40
    n_off = 2 if miniature else 8
    n_lat = 2 if miniature else 6
    w = worlds
    seeds = 1 if miniature else N_POLICY_SEEDS
    budgets = 2 if miniature else len(NOMINAL_BUDGETS_S)
    options = 3 if miniature else (1 + 4)  # classical + 4 circuits before freeze
    n_legal = max(1, int(n_legal))
    prepared = n_train_c + n_tune_c + n_cal_c + n_off + n_lat + n_mech
    distributions = n_mech * len(FAMILY_DEPTH_KEYS) * 8  # per donor
    pools = n_mech * len(FAMILY_DEPTH_KEYS) * 5 * (3 if miniature else 30)
    portfolios = (n_train_c + n_tune_c + n_cal_c) * budgets * options * seeds
    distinct_plan_eval = portfolios  # upper bound; reuse reduces realised
    planning_worlds = (
        n_train_c * w["training"]["planning"] * budgets * options
        + n_tune_c * w["tuning"]["planning"] * budgets * options
        + n_cal_c * w["calibration"]["planning"] * budgets * options
    )
    eval_worlds = (
        n_train_c * w["training"]["evaluation"] * budgets * options
        + n_tune_c * w["tuning"]["evaluation"] * budgets * options
        + n_cal_c * w["calibration"]["evaluation"] * budgets * options
    )
    offline_all = n_off * n_legal * int(w["offline"]["planning"]) + n_off * int(w["offline"]["evaluation"])
    return {
        "ladder": ladder,
        "miniature": miniature,
        "seed_hierarchy": SEED_HIERARCHY,
        "counts": {
            "prepared_cases": prepared,
            "distributions": distributions,
            "parameter_policies": 5,
            "pools_1024": pools,
            "optimiser_expectation_evaluations": n_mech * 8 * 4,
            "portfolios": portfolios,
            "distinct_plan_evaluations_upper": distinct_plan_eval,
            "planning_worlds_upper": planning_worlds,
            "evaluation_worlds_upper": eval_worlds,
            "offline_all_plan_evaluations": offline_all,
            "model_fits": 4 + 1,
            "bootstrap_passes": 1,
            "report_verifier_passes": 2,
        },
        "denominators_intact": {
            "train_parents": n_train_p,
            "tune_parents": n_tune_p,
            "calib_parents": n_cal_p,
            "family_depths": list(FAMILY_DEPTH_KEYS),
            "budgets": list(NOMINAL_BUDGETS_S) if not miniature else [5, 30],
            "policy_seeds": seeds,
            "pool_draws": POOL_DRAWS,
            "portfolio_k": PORTFOLIO_K,
            "calibration_eval_worlds": w["calibration"]["evaluation"],
        },
        "row_arithmetic_note": "policy_seed=3; circuit_resample_seed derived 1:1; not 3x3",
    }


def _heartbeat(ev: Path, **fields: Any) -> None:
    rec = {"ts": _utc(), **fields}
    append_jsonl(ev / "HEARTBEATS.jsonl", rec)
    print(
        f"[heartbeat] phase={fields.get('phase')} {fields.get('completed')}/{fields.get('total')} "
        f"last={fields.get('last_case')} workers={fields.get('active_workers')} "
        f"wall={fields.get('elapsed_wall_s')} cpu={fields.get('elapsed_cpu_s')} "
        f"rss={fields.get('aggregate_rss')} eta={fields.get('eta_s')} bytes={fields.get('evidence_bytes')}",
        flush=True,
    )


def process_case_unit(payload: dict[str, Any]) -> dict[str, Any]:
    """Checkpoint-bounded worker: one case, all requested options/budgets/seeds."""
    from f1q.a4 import worker_init

    worker_init.apply()
    t0 = time.perf_counter()
    reset_prepare_counters()
    reset_distribution_counters()
    pc = prepare_case(
        family_id=payload["family_id"],
        block_id=payload["block_id"],
        regime=payload["regime"],
        partition=payload["partition"],
        index=int(payload["index"]),
        seed=int(payload["seed"]),
        n_planning=int(payload["n_planning"]),
        n_evaluation=int(payload["n_evaluation"]),
    )
    if prepare_counters()["prepare_case_calls"] != 1:
        raise StructuralError("PREPARE", "worker prepared more than once", path=pc.case_id)
    bank = payload["donor_bank"]
    cache: dict[str, Any] = {}
    dist_cache: dict[str, Any] = {}
    rows = []
    p_seeds = bank_world_seeds(pc.block_id, pc.regime, PLANNING_BANK, int(payload["n_planning"]))
    e_seeds = bank_world_seeds(pc.block_id, pc.regime, EVALUATION_BANK, int(payload["n_evaluation"]))
    if not banks_disjoint(p_seeds, e_seeds):
        raise StructuralError("BANKS", "planning/evaluation overlap", path=pc.case_id)
    n_seeds = int(payload.get("n_policy_seeds") or 1)
    pool_draws = int(payload.get("pool_draws") or POOL_DRAWS)
    for budget in payload["budgets"]:
        for option, mode, fd in payload["option_specs"]:
            key = None if fd is None else f"{fd[0]}_p{fd[1]}"
            dpol = payload.get("donor_policy_by_fd", {}).get(key or "classical", {}).get("policy", "fixed")
            for s_i in range(n_seeds):
                rec = decide_and_evaluate(
                    pc.spec_with_budget(budget),
                    mode=mode,
                    runtime=None,
                    donor_bank=bank,
                    donor_policy=dpol if fd else "fixed",
                    planning_seeds=p_seeds,
                    evaluation_seeds=e_seeds,
                    online_seed=circuit_resample_seed(policy_seed=s_i, case_id=pc.case_id, family_depth=key or "classical"),
                    cache=cache,
                    pool_size=pool_draws,
                    equal_k=PORTFOLIO_K,
                    deadline_s=float(budget),
                    margin=0.001,
                    conservative_residual=0.0,
                    family_depth=tuple(fd) if fd else None,
                    n_stochastic_seeds=1,
                    legal_table=pc.legal_table,
                    prepared=pc,
                    dist_cache=dist_cache,
                    policy_seed=s_i,
                )
                rows.append(
                    {
                        "block_id": pc.block_id,
                        "family_id": pc.family_id,
                        "regime": pc.regime,
                        "split": pc.split,
                        "option": option,
                        "budget_s": budget,
                        "policy_seed": s_i,
                        "mean_loss": rec["mean_loss"],
                        "plan_hash": rec["plan_hash"],
                        "choice": rec["choice"],
                        "family_depth": rec.get("family_depth"),
                        "portfolio_budget_matched": rec["portfolio"]["portfolio_budget_matched"],
                        "n_downstream": rec["portfolio"]["n_downstream"],
                        "n_unique_hashes": rec["portfolio"].get("n_unique_hashes") or rec["portfolio"]["n_downstream"],
                        "found_by": rec["portfolio"].get("candidate_found_by"),
                        "quantum_incremental_generated": rec.get("quantum_incremental_generated"),
                        "quantum_incremental_evaluated_in_k": rec.get("quantum_incremental_evaluated_in_k"),
                        "quantum_incremental_selected": rec.get("quantum_incremental_selected"),
                        "classical_k_hashes": rec["portfolio"].get("classical_k_hashes"),
                        "hybrid_hashes": rec["portfolio"].get("candidate_plan_hashes"),
                        "precommit_s": rec["timings"]["precommit_s"],
                        "frozen_scenario_latency_s": rec["timings"].get("frozen_scenario_latency_s"),
                        "measured_compute_s": rec["timings"].get("measured_compute_s"),
                        "pool_draws": rec.get("pool_draws"),
                        "prepared_case_hash": rec.get("prepared_case_hash"),
                        "eval_worlds": rec["eval_worlds"] if payload.get("persist_worlds") else None,
                        "success": rec["mean_loss"] is not None,
                        "config_hash": payload.get("config_hash"),
                        "source_commit": payload.get("source_commit"),
                    }
                )
    return {
        "ok": True,
        "unit_id": payload["unit_id"],
        "case_id": pc.case_id,
        "prepared_case_hash": pc.prepared_case_hash,
        "n_legal": len(pc.legal_table),
        "n_qubits": pc.qubo["n"],
        "features": pc.features,
        "prepare_counters": prepare_counters(),
        "distribution_counters": distribution_counters(),
        "rows": rows,
        "prepared_summary": {
            "case_id": pc.case_id,
            "split": pc.split,
            "block_id": pc.block_id,
            "family_id": pc.family_id,
            "regime": pc.regime,
            "prepared_case_hash": pc.prepared_case_hash,
            "n_legal": len(pc.legal_table),
            "n_qubits": pc.qubo["n"],
            "spec_hash": pc.spec_hash,
            "checkpoint_hash": pc.checkpoint_hash,
        },
        "wall_s": time.perf_counter() - t0,
        "rss": current_rss_bytes(),
        "worker_pid": os.getpid(),
    }


def option_specs_all() -> list[tuple[str, str, tuple[str, int] | None]]:
    return [
        ("classical_only", "always_classical", None),
        ("C0_p1", "always_c0", ("C0", 1)),
        ("C0_p2", "always_c0", ("C0", 2)),
        ("C1_p1", "always_c1", ("C1", 1)),
        ("C1_p2", "always_c1", ("C1", 2)),
    ]


def _project_from_probes(ledger: dict[str, Any], probes: list[dict[str, Any]], workers: dict[str, Any], efficiency: float) -> dict[str, Any]:
    by_kind: dict[str, list[float]] = {}
    for p in probes:
        by_kind.setdefault(p["kind"], []).append(float(p["wall_s"]))

    def _summ(vals: list[float]) -> dict[str, float]:
        a = np.asarray(vals, dtype=float)
        if a.size == 0:
            return {"point": 0.0, "p50": 0.0, "p95": 0.0, "conservative": 0.0, "n": 0}
        return {
            "point": float(a.mean()),
            "p50": float(np.quantile(a, 0.50)),
            "p95": float(np.quantile(a, 0.95)),
            "conservative": float(np.quantile(a, 0.95)),
            "n": int(a.size),
        }

    def _get(kind: str) -> dict[str, Any] | None:
        for p in probes:
            if p.get("kind") == kind:
                return p
        return None

    prepare = _summ(by_kind.get("prepare", []))
    fd = _summ(by_kind.get("family_depth", []))
    classical = _summ(by_kind.get("budget", []))
    case_u = _summ(by_kind.get("case_unit", []))
    off = _get("offline") or {"wall_s": 0.0, "n_legal": 100}
    cal = _get("calib_2048") or {"wall_s": 0.0, "n_eval": 1}
    n_legal = max(1, int(off.get("n_legal") or 100))
    off_denom = max(1.0, n_legal * 4.0 + 8.0)
    per_world_s = float(off.get("wall_s") or 0.0) / off_denom
    cal_n = max(1, int(cal.get("n_eval") or 1))
    per_eval_world_s = float(cal.get("wall_s") or 0.0) / cal_n
    circuit_s = max(0.0, fd["conservative"] - classical["conservative"]) if classical["n"] else fd["conservative"]
    counts = ledger["counts"]
    n_units = int(counts["prepared_cases"])
    cpu_prep = prepare["conservative"] * n_units
    cpu_dist = circuit_s * int(counts["distributions"])
    cpu_plan = per_world_s * int(counts["planning_worlds_upper"]) * PORTFOLIO_K
    cpu_eval = per_eval_world_s * int(counts["evaluation_worlds_upper"])
    cpu_off = per_world_s * int(counts["offline_all_plan_evaluations"])
    serial_point = cpu_prep + cpu_dist + cpu_plan + cpu_eval + cpu_off
    serial = serial_point * 1.15
    n_w = max(1, int(workers["workers"]))
    eff = max(float(efficiency), 0.05)
    wall_point = serial_point / max(n_w * eff, 1.0)
    conservative_wall = (serial / max(n_w * eff, 1.0)) * 1.20
    rss = int(workers.get("per_worker_rss_budget_bytes") or 0) * n_w
    storage = int(n_units * 2_000_000 + int(counts["evaluation_worlds_upper"]) * 200)
    payload = {
        "serial": serial,
        "wall": conservative_wall,
        "n": n_units,
        "eff": eff,
        "workers": n_w,
        "per_world_s": per_world_s,
        "per_eval_world_s": per_eval_world_s,
    }
    return {
        "unit_s": case_u,
        "n_units": n_units,
        "components_s": {
            "prepare": cpu_prep,
            "distributions": cpu_dist,
            "planning_worlds": cpu_plan,
            "evaluation_worlds": cpu_eval,
            "offline": cpu_off,
            "per_world_s": per_world_s,
            "per_eval_world_s": per_eval_world_s,
            "n_legal_measured": n_legal,
            "circuit_s": circuit_s,
        },
        "serial_cpu_s": {"point": serial_point, "p50": serial_point, "p95": serial, "conservative": serial},
        "parallel_wall_s": {
            "point": wall_point,
            "p50": wall_point,
            "p95": conservative_wall,
            "conservative": conservative_wall,
        },
        "efficiency_used": eff,
        "assumed_0_55_forbidden": True,
        "peak_aggregate_rss_bytes": rss,
        "storage_bytes": storage,
        "workers": n_w,
        "checksum": sha256_json(payload),
        "checksum_payload": payload,
    }


def independent_projection_checksum(proj: dict[str, Any]) -> str:
    payload = proj.get("checksum_payload")
    if isinstance(payload, dict):
        return sha256_json(payload)
    n = int(proj["n_units"])
    serial = float(proj["serial_cpu_s"]["conservative"])
    w = int(proj["workers"])
    eff = float(proj["efficiency_used"])
    wall = (serial / max(w * max(eff, 0.05), 1.0)) * 1.20
    return sha256_json({"serial": serial, "wall": wall, "n": n, "eff": eff, "workers": w})
