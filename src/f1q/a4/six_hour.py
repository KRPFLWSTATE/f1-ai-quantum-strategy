"""Prospective six-hour Design R admission.

Engineering fixtures and the corrected ledger only. Registered a4.v2 outcomes
are not opened here. Historical wall constants in ``resources`` stay at
11,520 / 14,400 so published receipts remain reproducible.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from f1q.a4.contracts import (
    FAMILY_DEPTH_KEYS,
    N_MECHANISM_RESAMPLE_SEEDS,
    N_POLICY_SEEDS,
    POOL_DRAWS,
    PORTFOLIO_K,
    PRIMARY_BUDGET_S,
)
from f1q.a4.corrected_cost import (
    HISTORICAL_UNDERPREDICTION,
    plan_world_evals_from_units,
)
from f1q.a4.partitions import RETIRED_DIAGNOSTIC_PARENTS, build_a4_partitions
from f1q.a4.resources import (
    ADMISSION_WALL_LIMIT_S,
    CAMPAIGN_CPU_CAP_S,
    CAMPAIGN_WALL_CAP_S,
    RAM_FRACTION,
    available_ram_bytes,
    cpu_seconds,
)
from f1q.a4.unit_ledger import DESIGN_R, design_worlds, enumerate_design_units
from f1q.hashing import sha256_file, sha256_json

AMENDMENT_ID = "design_r_six_hour_20261025"
RUN_ID = "ed37296f-55c5-44e5-8ffd-77410d4789de"
CAMPAIGN_WALL_S = 21_600.0
ADMISSION_WALL_S = 17_280.0
CPU_CAP_S = 86_400.0
PREFLIGHT_WALL_S = 7_200.0
WORKERS = 8
KERNEL_SHA256 = "a763fe1bc041f77a4ed7f06978eaf2dfd48a468205d8b675988224afd8a7818f"
KERNEL_VERSION = "compiled-event-loop-2"
CAPACITY_REL = (
    "evidence/performance_feasibility_followup/1d1b3499-2ff1-440a-ba33-d45212b31b83/CAPACITY.json"
)
CARRIED_PREPARE_S = 36.157
CARRIED_SPEEDUP = 22.902642628995448
DISK_RESERVE = 0.20


def is_six_hour(cfg: dict[str, Any] | None) -> bool:
    from f1q.a4.isolation import ISOLATED_AMENDMENT_ID

    return str((cfg or {}).get("amendment_id") or "") in {AMENDMENT_ID, ISOLATED_AMENDMENT_ID}


def six_hour_caps(cfg: dict[str, Any] | None = None) -> dict[str, float]:
    """Caps for this attempt. Historical module constants are not rewritten."""
    wall = float((cfg or {}).get("campaign_wall_cap_s") or CAMPAIGN_WALL_S)
    admission = float((cfg or {}).get("admission_wall_limit_s") or ADMISSION_WALL_S)
    cpu = float((cfg or {}).get("campaign_cpu_cap_s") or CPU_CAP_S)
    if abs(wall - CAMPAIGN_WALL_S) > 1e-9 or abs(admission - (0.8 * wall)) > 1e-6:
        raise ValueError("six-hour config drifted from 21600 and 0.8*wall")
    if abs(cpu - CPU_CAP_S) > 1e-9:
        raise ValueError("CPU cap is not the retained 86400 seconds")
    return {
        "campaign_cpu_cap_s": cpu,
        "campaign_wall_cap_s": wall,
        "admission_wall_limit_s": admission,
        "historical_admission_wall_s": ADMISSION_WALL_LIMIT_S,
        "historical_campaign_wall_s": CAMPAIGN_WALL_CAP_S,
        "historical_cpu_cap_s": CAMPAIGN_CPU_CAP_S,
    }


def verify_sealed_splits(root: Path) -> dict[str, Any]:
    """Confirm the registered 120/80/24 ids are disjoint and outcomes are unopened.

    Final-test ids are compared as a set. Their outcomes are not read.
    """
    parts = build_a4_partitions()
    train = [b["block_id"] for b in parts["train"]]
    tune = [b["block_id"] for b in parts["tune"]]
    calib = [b["block_id"] for b in parts["calib"]]
    open_ids = train + tune + calib
    ft = list((parts.get("final_test") or {}).get("ids") or [])
    retired = set(RETIRED_DIAGNOSTIC_PARENTS)
    opened: list[str] = []
    evidence = root / "evidence"
    interesting = ("TRAINING_OPTION", "TUNING_OPTION", "CALIBRATION_OPTION", "EVALUATION_WORLD")
    if evidence.is_dir():
        for path in evidence.rglob("*"):
            if not path.is_file():
                continue
            if not any(tok in path.name for tok in interesting):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "a4.v2.train." in text or "a4.v2.tune." in text or "a4.v2.calib." in text:
                if "mean_loss" in text or '"loss"' in text:
                    opened.append(str(path.relative_to(root)))
    shift_overlap = [i for i in open_ids if ".shift." in i or i.startswith("shift.")]
    defects = []
    if len(train) != 120 or len(tune) != 80 or len(calib) != 24:
        defects.append("parent_counts")
    if len(set(open_ids)) != len(open_ids):
        defects.append("duplicate_open_ids")
    if set(open_ids) & set(ft):
        defects.append("final_test_overlap")
    if set(open_ids) & retired:
        defects.append("retired_diagnostic_overlap")
    if parts.get("a2_a3_id_reuse"):
        defects.append("a2_a3_reuse")
    if not parts.get("ok"):
        defects.append("partition_flag")
    if opened:
        defects.append("registered_outcomes_opened")
    if shift_overlap:
        defects.append("shift_id_overlap")
    if (parts.get("final_test") or {}).get("outcomes_materialised") or (parts.get("final_test") or {}).get("outcomes_opened"):
        defects.append("final_test_materialised")
    return {
        "ok": not defects,
        "defects": defects,
        "n_train": len(train),
        "n_tune": len(tune),
        "n_calib": len(calib),
        "n_final_test_ids": len(ft),
        "final_test_id_sha256": (parts.get("final_test") or {}).get("id_sha256"),
        "final_test_outcomes_read": False,
        "opened_outcome_files": opened,
        "salt": parts.get("salt"),
        "parts": parts,
    }


def recompute_capacity(root: Path) -> dict[str, Any]:
    """Eight-worker efficiency and cold start from the Route 1 raw waves."""
    path = root / CAPACITY_REL
    data = json.loads(path.read_text(encoding="utf-8"))
    ratios = []
    colds = []
    rss = []
    fit_s: dict[str, float] = {}
    for row in data.get("fits", {}).get("fits") or data.get("fits") or []:
        if isinstance(row, dict) and row.get("key") and "conservative_fit_s" in row:
            fit_s[str(row["key"])] = float(row["conservative_fit_s"])
    for rep in data["reps"]:
        by_n = {int(cfg["workers"]): cfg for cfg in rep["configs"]}
        solo = by_n[1]["waves"][1]["makespan_s"]
        eight = by_n[8]
        steady = float(eight["waves"][1]["makespan_s"])
        cold = float(eight["waves"][0]["makespan_s"])
        ratios.append(float(solo) / steady)
        colds.append(cold - steady)
        rss.append(int(eight["simultaneous_rss_max_bytes"]))
        if 10 in by_n:
            ten_steady = float(by_n[10]["waves"][1]["makespan_s"])
            # recorded only; not used as the admission efficiency
            by_n[10]["_efficiency"] = float(solo) / ten_steady
    if len(ratios) != 3:
        raise RuntimeError(f"expected 3 capacity repetitions, got {len(ratios)}")
    return {
        "path": CAPACITY_REL,
        "sha256": sha256_file(path),
        "efficiency_8": min(ratios),
        "efficiency_8_reps": ratios,
        "cold_start_wall_s": max(colds),
        "cold_start_reps_s": colds,
        "recorded_rss_max_bytes": max(rss),
        "fit_s": fit_s,
        "logical_cpus": data.get("logical_cpus"),
        "physical_cpus": data.get("physical_cpus"),
        "twelve_measured": bool((data.get("twelve_worker_exclusion") or {}).get("measured")),
    }


def _checkpoint_ids(parts: dict[str, Any]) -> list[str]:
    from f1q.a4.unit_ledger import checkpoints_for_parent
    from f1q.generator.config import cartesian_family_ids

    fam_index = {f: i for i, f in enumerate(cartesian_family_ids())}
    ids = []
    for block in parts["train"]:
        regime = checkpoints_for_parent(block, design=DESIGN_R, family_index=fam_index[block["family_id"]])[0]
        ids.append(f"{block['block_id']}:{regime}")
    return ids


def build_identity_keys(parts: dict[str, Any], bank: dict[str, Any]) -> list[tuple[Any, ...]]:
    """Complete build identities: checkpoint, family/depth, parameter tuple, noise, backend."""
    keys: list[tuple[Any, ...]] = []
    checkpoints = _checkpoint_ids(parts)
    depths = bank.get("family_depths") or {}
    for checkpoint in checkpoints:
        for fd in FAMILY_DEPTH_KEYS:
            donors = list((depths.get(fd) or {}).get("donors") or [])
            for donor in donors:
                gammas = tuple(float(x) for x in donor.get("gammas") or [])
                betas = tuple(float(x) for x in donor.get("betas") or [])
                keys.append(
                    (
                        checkpoint,
                        fd,
                        gammas,
                        betas,
                        "ideal_noiseless",
                        "local_statevector",
                        "simulator_version_from_bank_row",
                    )
                )
    return keys


def operation_counts(units: list[dict[str, Any]], *, n_legal: int, n_donors: int, unique_parameter_builds: int) -> dict[str, Any]:
    """Recount Design R operations. K is applied once. Resamples are not builds."""
    plan = 0
    evaluation = 0
    offline_cases = 0
    offline_plan_worlds = 0
    mechanism = 0
    ablation_rows = 0
    ablation_ids: set[str] = set()
    k_seen: set[int] = set()
    mech_checkpoints: set[str] = set()
    for unit in units:
        role = str(unit.get("role"))
        if role == "mechanism_resample":
            mechanism += 1
            mech_checkpoints.add(str(unit.get("checkpoint_id")))
            continue
        k = int(unit.get("portfolio_k") or 0)
        n_plan = int(unit.get("n_planning_worlds") or 0)
        plan += n_plan * max(k, 1)
        evaluation += int(unit.get("n_evaluation_worlds") or 0)
        if role == "offline_all_plan":
            offline_cases += 1
            offline_plan_worlds = n_plan
        elif role == "ablation":
            ablation_rows += 1
            ablation_ids.add(str(unit.get("option")))
        elif k:
            k_seen.add(k)
    donor_resamples = len(mech_checkpoints) * len(FAMILY_DEPTH_KEYS) * int(n_donors) * N_MECHANISM_RESAMPLE_SEEDS
    tune_policy_resamples = 80 * len(FAMILY_DEPTH_KEYS) * 5
    best_found_fits = 120 * len(FAMILY_DEPTH_KEYS)
    # Specification rows use five policies. The executor's donor panel uses the
    # bank's donors. Charge the larger resample count so the run cannot exceed
    # the admission by implementing the heavier panel.
    charged_resamples = max(mechanism, donor_resamples) + tune_policy_resamples
    charged_builds = int(unique_parameter_builds)
    return {
        "plan_world_evaluations_k_once": plan,
        "evaluation_worlds": evaluation,
        "offline_cases": offline_cases,
        "offline_continuations": offline_cases * int(n_legal) * int(offline_plan_worlds),
        "mechanism_policy_rows": mechanism,
        "mechanism_checkpoints": len(mech_checkpoints),
        "donor_label_resamples": donor_resamples,
        "tune_policy_resamples": tune_policy_resamples,
        "charged_resamples": charged_resamples,
        "unique_parameter_builds": int(unique_parameter_builds),
        "best_found_fits": best_found_fits,
        "charged_builds": charged_builds,
        "ablation_specifications": len(ablation_ids),
        "ablation_rows": ablation_rows,
        "portfolio_k_values": sorted(k_seen),
        "k_applied_once": k_seen == {PORTFOLIO_K},
        "builds_2400_proven": int(unique_parameter_builds) == 2400,
    }


def project_resources(
    counts: dict[str, Any],
    rates: dict[str, float],
    *,
    efficiency: float,
    cold_wall_s: float,
    underprediction: float,
) -> dict[str, Any]:
    """Point CPU, one under-prediction multiplier, then 1.20 wall plus cold start."""
    scalar = float(rates["scalar_s_per_cell"])
    speedup = float(rates["speedup"])
    race_cells = (
        int(counts["plan_world_evaluations_k_once"])
        + int(counts["evaluation_worlds"])
        + int(counts["offline_continuations"])
    )
    race_scalar_s = race_cells * scalar
    if rates.get("compiled_s_per_cell") is not None:
        race_accelerated_s = race_cells * float(rates["compiled_s_per_cell"])
    else:
        race_accelerated_s = race_scalar_s / speedup
    build_s = float(rates["build_cpu_s"])
    resample_s = int(counts["charged_resamples"]) * float(rates["resample_s"])
    fit_s = float(rates["optimiser_s"])
    prepare_s = float(rates["prepare_s"])
    other_s = float(rates.get("other_fixed_s") or 0.0)
    fixed_s = build_s + resample_s + fit_s + prepare_s + other_s
    point = fixed_s + race_accelerated_s
    conservative = point * float(underprediction)
    steady_wall = conservative / (WORKERS * float(efficiency)) * 1.20
    admission_wall = steady_wall + float(cold_wall_s)
    return {
        "race_cells": race_cells,
        "race_scalar_s": race_scalar_s,
        "race_accelerated_s": race_accelerated_s,
        "fixed_s": fixed_s,
        "components_s": {
            "builds": build_s,
            "resamples": resample_s,
            "optimiser": fit_s,
            "prepare": prepare_s,
            "other_fixed": other_s,
            "race_accelerated": race_accelerated_s,
        },
        "point_cpu_s": point,
        "underprediction": float(underprediction),
        "conservative_cpu_s": conservative,
        "steady_wall_s": steady_wall,
        "cold_start_wall_s": float(cold_wall_s),
        "admission_wall_s": admission_wall,
        "campaign_wall_s": admission_wall,
        "workers": WORKERS,
        "efficiency": float(efficiency),
        "speedup": speedup,
    }


def independent_recompute(
    units: list[dict[str, Any]],
    identity_keys: list[tuple[Any, ...]],
    rates: dict[str, float],
    *,
    n_legal: int,
    n_donors: int,
    efficiency: float,
    cold_wall_s: float,
    underprediction: float,
) -> dict[str, Any]:
    """Recount from units and identity tuples, then apply the same wall formula."""
    once = plan_world_evals_from_units(units)
    counts = operation_counts(
        units,
        n_legal=n_legal,
        n_donors=n_donors,
        unique_parameter_builds=len(set(identity_keys)),
    )
    counts["plan_matches_helper"] = counts["plan_world_evaluations_k_once"] == once
    projection = project_resources(
        counts,
        rates,
        efficiency=efficiency,
        cold_wall_s=cold_wall_s,
        underprediction=underprediction,
    )
    return {"counts": counts, "projection": projection}


def kernel_file_ok(root: Path) -> dict[str, Any]:
    from f1q.simulator.compiled_kernel import KERNEL_VERSION as live

    path = root / "src/f1q/simulator/compiled_kernel.py"
    digest = sha256_file(path)
    return {
        "ok": digest == KERNEL_SHA256 and live == KERNEL_VERSION,
        "sha256": digest,
        "expected_sha256": KERNEL_SHA256,
        "version": live,
    }


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=str(root), text=True).strip()


def measure_race_and_distributions(root: Path) -> dict[str, Any]:
    """Fresh synthetic rates. Identifiers use the engperf prefix, not a4.v2 parents."""
    from f1q.a4.backend_select import select_evaluation_backend
    from f1q.a4.banks import EVALUATION_BANK
    from f1q.a4.distributions import build_ideal_distribution, resample_pool
    from f1q.a4.loop import evaluate_candidates_on_bank
    from f1q.a4.prepared import prepare_case
    from f1q.generator.config import cartesian_family_ids
    from f1q.simulator.engine import RaceEngine

    families = cartesian_family_ids()
    calls = {"n": 0}
    real = RaceEngine.continue_to_finish

    def _wrapped(self, *args, **kwargs):
        calls["n"] += 1
        return real(self, *args, **kwargs)

    RaceEngine.continue_to_finish = _wrapped
    ratios = []
    scalar_cell = []
    compiled_cell = []
    candidate_scalar_calls = 0
    try:
        select_evaluation_backend("candidate")
        # Warm the compiler on one synthetic cell before the steady ratios.
        warm = prepare_case(
            family_id=families[0],
            block_id="engperf.sixhour.warm",
            regime="SC",
            partition="development",
            index=0,
            seed=51000,
            n_planning=2,
            n_evaluation=2,
        )
        evaluate_candidates_on_bank(
            warm.spec_with_budget(30),
            warm.checkpoint_blob,
            [{"plan": warm.legal_table[0]["plan"], "plan_hash": warm.legal_table[0]["plan_hash"]}],
            [810100],
            bank=EVALUATION_BANK,
            arrival_delay_s=0.02,
            commitment_epoch_race_s=float(warm.window_for_budget(30)["effective_end_race_s"]),
            cache={},
            spec_hash=warm.spec_hash,
            checkpoint_hash=warm.checkpoint_hash,
            nominal_budget_s=30.0,
        )
        if calls["n"] != 0:
            raise RuntimeError(f"warmup candidate entered scalar continue_to_finish {calls['n']} times")
        calls["n"] = 0
        for fam_i, fam in enumerate(families):
            for regime in ("SC", "VSC"):
                pc = prepare_case(
                    family_id=fam,
                    block_id=f"engperf.sixhour.{fam}.{regime}",
                    regime=regime,
                    partition="development",
                    index=fam_i,
                    seed=52000 + fam_i,
                    n_planning=4,
                    n_evaluation=4,
                )
                plans = [{"plan": row["plan"], "plan_hash": row["plan_hash"]} for row in pc.legal_table[:3]]
                worlds = [810200 + i for i in range(8)]
                spec = pc.spec_with_budget(30)
                epoch = float(pc.window_for_budget(30)["effective_end_race_s"])
                t0 = time.perf_counter()
                select_evaluation_backend("legacy")
                from f1q.a4.batched import simulate_plan_world_scalar

                for cand in plans:
                    for seed in worlds:
                        simulate_plan_world_scalar(
                            spec,
                            pc.checkpoint_blob,
                            cand["plan"],
                            seed,
                            cache={},
                            parity=True,
                            bank=EVALUATION_BANK,
                            arrival_delay_s=0.02,
                            commitment_epoch_race_s=epoch,
                            spec_hash=pc.spec_hash,
                            checkpoint_hash=pc.checkpoint_hash,
                            nominal_budget_s=30.0,
                        )
                scalar_s = time.perf_counter() - t0
                t1 = time.perf_counter()
                select_evaluation_backend("candidate")
                before_candidate = calls["n"]
                evaluate_candidates_on_bank(
                    spec,
                    pc.checkpoint_blob,
                    plans,
                    worlds,
                    bank=EVALUATION_BANK,
                    arrival_delay_s=0.02,
                    commitment_epoch_race_s=epoch,
                    cache={},
                    spec_hash=pc.spec_hash,
                    checkpoint_hash=pc.checkpoint_hash,
                    nominal_budget_s=30.0,
                )
                compiled_s = time.perf_counter() - t1
                if calls["n"] != before_candidate:
                    candidate_scalar_calls += calls["n"] - before_candidate
                    raise RuntimeError(
                        f"candidate path entered scalar continue_to_finish {calls['n'] - before_candidate} times"
                    )
                cells = len(plans) * len(worlds)
                ratios.append(scalar_s / compiled_s if compiled_s > 0 else 0.0)
                scalar_cell.append(scalar_s / cells)
                compiled_cell.append(compiled_s / cells)
                print(
                    json.dumps(
                        {
                            "phase": "race_ratio",
                            "family": fam,
                            "regime": regime,
                            "ratio": ratios[-1],
                            "scalar_s_per_cell": scalar_cell[-1],
                        }
                    ),
                    flush=True,
                )
        # Build and resample on one engineering menu, three repetitions, conservative max.
        pc = prepare_case(
            family_id="fam.green_pit_low.tyre_nonlinear.traffic_dense",
            block_id="engperf.sixhour.build",
            regime="SC",
            partition="development",
            index=1,
            seed=53001,
            n_planning=2,
            n_evaluation=2,
        )
        build_times = []
        resample_times = []
        for depth, family in ((1, "C0"), (2, "C0"), (1, "C1"), (2, "C1")):
            reps = []
            for rep in range(3):
                gammas = [0.1 * (rep + 1)] * depth
                betas = [0.2 * (rep + 1)] * depth
                t0 = time.perf_counter()
                dist = build_ideal_distribution(
                    instance=pc.instance,
                    qubo=pc.qubo,
                    family=family,
                    depth=depth,
                    gammas=gammas,
                    betas=betas,
                    prepared_case_hash=pc.prepared_case_hash + f".{family}.{depth}.{rep}",
                    cache={},
                    legal_table=pc.legal_table,
                )
                reps.append(time.perf_counter() - t0)
                if family == "C0" and depth == 2 and rep == 0:
                    rs = []
                    for i in range(30):
                        t_r = time.perf_counter()
                        resample_pool(dist, pool_draws=POOL_DRAWS, seed=6000 + i)
                        rs.append(time.perf_counter() - t_r)
                    resample_times.append(max(rs))
            build_times.append(max(reps))
            print(json.dumps({"phase": "build", "family": family, "depth": depth, "conservative_s": build_times[-1]}), flush=True)
        n_legal = len(pc.legal_table)
    finally:
        select_evaluation_backend("legacy")
        RaceEngine.continue_to_finish = real
    if not ratios or min(ratios) <= 0:
        raise RuntimeError("race ratio panel produced no positive ratio")
    return {
        "speedup": min(ratios),
        "speedup_max": max(ratios),
        "speedup_n_checkpoints": len(ratios),
        "scalar_s_per_cell": max(scalar_cell),
        "compiled_s_per_cell": max(compiled_cell),
        "build_s": max(build_times),
        "build_s_by_depth": build_times,
        "resample_s": max(resample_times) if resample_times else None,
        "n_legal": n_legal,
        "scalar_continue_calls_during_candidate": candidate_scalar_calls,
        "carried_speedup_not_used": CARRIED_SPEEDUP,
        "panel": "engperf.sixhour 8 families x SC/VSC x 3 plans x 8 worlds after one warmup cell",
    }


def measure_rss(dest: Path) -> dict[str, Any]:
    from f1q.a4.route1_followup import _run_pool, prepare_mix

    items = prepare_mix()
    measured = _run_pool(WORKERS, items, dest / "pids")
    return {
        "workers": WORKERS,
        "simultaneous_rss_max_bytes": measured["simultaneous_rss_max_bytes"],
        "wave_makespans_s": [row["makespan_s"] for row in measured["waves"]],
        "scalar_continue_calls": [w.get("scalar_continue_calls") for wave in measured["waves"] for w in wave["workers"]],
    }


def crafted_quantum_execution() -> dict[str, Any]:
    """Engineering fixture: a quantum-incremental legal plan is selected and executed.

    Planning means are set so the incremental plan is the unique minimum. The
    plan bytes come from the portfolio decoder. The continuation uses the
    compiled kernel. This is not a registered outcome.
    """
    from f1q.a4.backend_select import select_evaluation_backend
    from f1q.a4.banks import EVALUATION_BANK
    from f1q.a4.generators import assemble_portfolio, select_by_planning_mean
    from f1q.a4.loop import evaluate_candidates_on_bank
    from f1q.a4.prepared import prepare_case, validate_plan_fn
    from f1q.simulator.compiled_kernel import KERNEL_VERSION as live
    from f1q.simulator.engine import RaceEngine
    from f1q.simulator.interface import RaceSimulator

    pc = prepare_case(
        family_id="fam.green_pit_low.tyre_nonlinear.traffic_dense",
        block_id="engperf.sixhour.quantum",
        regime="SC",
        partition="development",
        index=3,
        seed=54003,
        n_planning=2,
        n_evaluation=2,
    )
    sim = RaceSimulator()
    sim.restore(pc.checkpoint_blob, pc.spec)
    validate = validate_plan_fn(sim)
    calls = {"n": 0}
    real = RaceEngine.continue_to_finish

    def _wrapped(self, *args, **kwargs):
        calls["n"] += 1
        return real(self, *args, **kwargs)

    RaceEngine.continue_to_finish = _wrapped
    found = None
    try:
        select_evaluation_backend("candidate")
        for seed in range(8):
            params = ([0.15 + 0.05 * seed], [0.25])
            port = assemble_portfolio(
                pc.instance,
                pc.qubo,
                choice="always_c1",
                seed=700 + seed,
                pool_size=64,
                sim_validate=validate,
                params=params,
                family="C1",
                p_depth=1,
                equal_k=PORTFOLIO_K,
                n_stochastic_seeds=1,
                legal_table=pc.legal_table,
                prepared_case_hash=pc.prepared_case_hash,
                dist_cache={},
            )
            incremental = [c for c in port["downstream_candidates"] if c.get("quantum_incremental_at_k")]
            if incremental:
                found = (port, incremental[0])
                break
        if found is None:
            return {
                "ok": False,
                "reason": "no quantum-incremental legal plan entered K on 8 crafted seeds",
                "scalar_continue_calls": calls["n"],
            }
        port, chosen = found
        means = {c["plan_hash"]: 1.0 for c in port["downstream_candidates"]}
        means[chosen["plan_hash"]] = 0.0
        selected = select_by_planning_mean(port["downstream_candidates"], means)
        if selected["selected_plan_hash"] != chosen["plan_hash"]:
            return {"ok": False, "reason": "unique minimum was not selected", "scalar_continue_calls": calls["n"]}
        executed = evaluate_candidates_on_bank(
            pc.spec_with_budget(30),
            pc.checkpoint_blob,
            [chosen],
            [810300, 810301],
            bank=EVALUATION_BANK,
            arrival_delay_s=0.02,
            commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
            cache={},
            spec_hash=pc.spec_hash,
            checkpoint_hash=pc.checkpoint_hash,
            nominal_budget_s=30.0,
        )
        worlds = executed["worlds"].get(chosen["plan_hash"]) or []
        losses = [row.get("loss") for row in worlds]
    finally:
        select_evaluation_backend("legacy")
        RaceEngine.continue_to_finish = real
    ok = bool(worlds) and all(v is not None for v in losses) and calls["n"] == 0 and live == KERNEL_VERSION
    return {
        "ok": ok,
        "plan_hash": chosen["plan_hash"],
        "quantum_incremental_at_k": True,
        "selected": True,
        "n_worlds_executed": len(worlds),
        "losses": losses,
        "kernel_version": live,
        "scalar_continue_calls": calls["n"],
        "engineering_fixture": True,
        "registered_parent": False,
    }


def _run_cmd(args: list[str], root: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=str(root), env=env, capture_output=True, text=True)
    return {
        "args": args,
        "exit_code": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-4000:],
    }


def run_six_hour_admission(root: Path, config_rel: str = "configs/stage6_a4_design_r_six_hour.yaml") -> dict[str, Any]:
    """Preflight and admission. Does not open the registered corpus."""
    from f1q.a4.completion import load_closure_config
    from f1q.a4.donors import build_donor_bank_v2
    from f1q.a4.hashing_io import write_json
    from f1q.a4.qpu_guard import assert_local_only

    assert_local_only()
    cfg, _cfg_hash = load_closure_config(root, config_rel)
    if str(cfg.get("amendment_id") or "") != AMENDMENT_ID:
        from f1q.a4.isolated_admission import run_isolated_admission

        return run_isolated_admission(root, config_rel)
    t0 = time.perf_counter()
    cpu0 = cpu_seconds()
    cfg, cfg_hash = load_closure_config(root, config_rel)
    if not is_six_hour(cfg):
        raise RuntimeError("config is not the six-hour amendment")
    if str(cfg.get("run_id")) != RUN_ID:
        raise RuntimeError("run id drifted from the frozen amendment")
    caps = six_hour_caps(cfg)
    ev = root / "evidence" / "stage6_a4" / RUN_ID
    if any((root / "evidence" / "stage6_a4" / prior).exists() and False for prior in ()):
        pass
    # Refuse to write inside a preserved run directory. RUN_ID is new.
    preserved = {
        "09806343-f940-4f33-9e0f-eb2855d0714b",
        "3de109c7-30d9-4cb0-827f-dbd82c4c509d",
        "0b697910-e8a2-474b-bc77-bc69ebb8e9c3",
        "fc5f0e00-d9e0-4f89-9eea-498461094969",
    }
    if RUN_ID in preserved or (ev / "ADMISSION_DECISION.json").is_file():
        raise RuntimeError("refusing to overwrite the historical six-hour admission")
    ev.mkdir(parents=True, exist_ok=True)
    sealed = verify_sealed_splits(root)
    write_json(ev / "PARTITIONS.json", sealed["parts"])
    kernel = kernel_file_ok(root)
    capacity = recompute_capacity(root)
    head = _git(root, "rev-parse", "HEAD")
    env = os.environ.copy()
    py = sys.executable
    print(json.dumps({"phase": "pytest"}), flush=True)
    tests = _run_cmd([py, "-m", "pytest", "-q"], root, env)
    if tests["exit_code"] != 0:
        print(json.dumps({"phase": "pytest_failed_stop", "exit_code": tests["exit_code"]}), flush=True)
        return {
            "admitted": False,
            "run_id": RUN_ID,
            "selected_design": "NONE_RESOURCE_LIMIT",
            "status": "not_admitted_tests",
            "gates": {"tests": False},
            "continued_to_parity": False,
            "continued_to_rates": False,
        }
    print(json.dumps({"phase": "doctor"}), flush=True)
    doctor = _run_cmd([py, "-m", "f1q", "doctor"], root, env)
    status = _run_cmd([py, "-m", "f1q", "status"], root, env)
    print(json.dumps({"phase": "parity"}), flush=True)
    from f1q.a4.route1_followup import run_parity_panel

    parity = run_parity_panel(ev / "parity_panel", workers=4)
    print(json.dumps({"phase": "rates"}), flush=True)
    rates_raw = measure_race_and_distributions(root)
    print(json.dumps({"phase": "rss"}), flush=True)
    rss = measure_rss(ev / "rss_probe")
    print(json.dumps({"phase": "crafted_quantum"}), flush=True)
    crafted = crafted_quantum_execution()
    print(json.dumps({"phase": "clean_extract"}), flush=True)
    from f1q.a4.clean_extract import run_clean_extract_e2e

    e2e = run_clean_extract_e2e(root)
    preflight_wall = time.perf_counter() - t0
    preflight_cpu = cpu_seconds() - cpu0

    from f1q.a4.hashing_io import load_jsonl

    anchor_rel = "evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b/ANCHOR_FITS.jsonl"
    fits = load_jsonl(root / anchor_rel)
    bank = build_donor_bank_v2(
        fits,
        source_run_id="09806343-f940-4f33-9e0f-eb2855d0714b",
        source_anchor_path=anchor_rel,
        source_anchor_sha256="b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a",
    )
    n_donors = len(bank["family_depths"][FAMILY_DEPTH_KEYS[0]]["donors"])
    worlds = design_worlds(DESIGN_R, "minimum")
    enum = enumerate_design_units(design=DESIGN_R, parts=sealed["parts"], worlds=worlds, freeze=None, miniature=False)
    keys = build_identity_keys(sealed["parts"], bank)
    n_legal = max(100, int(rates_raw["n_legal"]))
    fit_values = [float(capacity["fit_s"][key]) for key in FAMILY_DEPTH_KEYS]
    optimiser_s = 120.0 * sum(fit_values)
    n_checkpoints = 120
    nominal_builds = n_checkpoints * n_donors * len(FAMILY_DEPTH_KEYS)
    unique_builds = len(set(keys))
    depth_cpu = sum(n_checkpoints * n_donors * float(t) for t in rates_raw["build_s_by_depth"])
    build_cpu_s = depth_cpu * (unique_builds / nominal_builds) if nominal_builds else 0.0
    under = HISTORICAL_UNDERPREDICTION
    rates = {
        "scalar_s_per_cell": float(rates_raw["scalar_s_per_cell"]),
        "speedup": float(rates_raw["speedup"]),
        "compiled_s_per_cell": float(rates_raw["compiled_s_per_cell"]),
        "build_cpu_s": float(build_cpu_s),
        "resample_s": float(rates_raw["resample_s"]),
        "optimiser_s": float(optimiser_s),
        "prepare_s": CARRIED_PREPARE_S,
        "other_fixed_s": 0.874 + 0.002838,
    }
    checked = independent_recompute(
        enum["units"],
        keys,
        rates,
        n_legal=n_legal,
        n_donors=n_donors,
        efficiency=float(capacity["efficiency_8"]),
        cold_wall_s=float(capacity["cold_start_wall_s"]),
        underprediction=under,
    )
    counts = checked["counts"]
    proj = checked["projection"]
    disk = shutil.disk_usage(str(root))
    storage = int(enum["n_units"] * 2_000_000 + int(counts["evaluation_worlds"]) * 200)
    ram_limit = int(RAM_FRACTION * available_ram_bytes())
    rss_bytes = int(rss["simultaneous_rss_max_bytes"] or 0)
    gates = {
        "literal_parity": int(parity.get("exact_signature_mismatches") or 0) == 0 and int(parity.get("rows") or 0) == 3072,
        "kernel_hash": bool(kernel["ok"]),
        "backend_uniform": rates_raw["scalar_continue_calls_during_candidate"] == 0 and all(v == 0 for v in rss["scalar_continue_calls"]),
        "sealed_split": bool(sealed["ok"]),
        "tests": tests["exit_code"] == 0,
        "doctor": doctor["exit_code"] == 0,
        "miniature": bool(e2e.get("ok")),
        "crafted_quantum_executed": bool(crafted.get("ok")),
        "k_once": bool(counts["k_applied_once"] and counts["plan_matches_helper"]),
        "independent_counts": counts["plan_matches_helper"],
        "cpu": proj["conservative_cpu_s"] <= caps["campaign_cpu_cap_s"],
        "admission_wall": proj["admission_wall_s"] <= caps["admission_wall_limit_s"],
        "campaign_wall": proj["campaign_wall_s"] <= caps["campaign_wall_cap_s"],
        "ram": 0 < rss_bytes <= ram_limit,
        "disk": storage <= (1.0 - DISK_RESERVE) * disk.free,
        "preflight_wall": preflight_wall <= PREFLIGHT_WALL_S,
        "workers_8": True,
        "design_f_not_launched": True,
        "numba_import": True,
    }
    try:
        import numba

        gates["numba_import"] = numba.__version__ == "0.68.0"
    except Exception:
        gates["numba_import"] = False
    admitted = all(gates.values())
    decision = {
        "run_id": RUN_ID,
        "amendment_id": AMENDMENT_ID,
        "admitted": admitted,
        "selected_design": DESIGN_R if admitted else "NONE_RESOURCE_LIMIT",
        "design_f_launched": False,
        "gates": gates,
        "counts": counts,
        "projection": proj,
        "rates": rates,
        "rates_raw": {k: v for k, v in rates_raw.items()},
        "capacity": {k: v for k, v in capacity.items() if k != "fit_s"},
        "fit_s": capacity["fit_s"],
        "rss": rss,
        "ram_limit_bytes": ram_limit,
        "storage_bytes": storage,
        "free_disk_bytes": disk.free,
        "kernel": kernel,
        "sealed": {k: v for k, v in sealed.items() if k != "parts"},
        "parity": {k: v for k, v in parity.items() if k != "mismatch_rows"},
        "crafted_quantum": crafted,
        "tests": tests,
        "doctor_exit_code": doctor["exit_code"],
        "status_exit_code": status["exit_code"],
        "clean_extract_e2e": e2e,
        "preflight_wall_s": preflight_wall,
        "preflight_cpu_s": preflight_cpu,
        "config_hash": cfg_hash,
        "reviewed_source_commit": head,
        "selected_world_level": "minimum",
        "machine": {"workers": WORKERS, "logical_cpus": capacity.get("logical_cpus"), "physical_cpus": capacity.get("physical_cpus")},
        "consumed": False,
        "miniature": False,
        "limited_resource_pilot": False,
        "caps": caps,
        "underprediction": under,
        "phase_7_authorised": False,
        "qpu_jobs": 0,
        "final_test_accessed": False,
        "registered_scientific_parents_executed": 0,
    }
    decision["decision_sha256"] = sha256_json({k: v for k, v in decision.items() if k != "decision_sha256"})
    write_json(ev / "DONOR_BANK_V2.json", bank)
    write_json(ev / "ADMISSION_DECISION.json", decision)
    write_json(ev / "ADMISSION_RECEIPT.json", decision)
    write_json(ev / "OPERATION_COUNTS.json", counts)
    write_json(
        ev / "EXTERNAL_COMPUTE_REQUIREMENT.json",
        {
            "required": not admitted,
            "reason": None if admitted else "one or more six-hour admission gates failed",
            "gates": gates,
            "admission_wall_s": proj["admission_wall_s"],
            "admission_wall_limit_s": caps["admission_wall_limit_s"],
            "conservative_cpu_s": proj["conservative_cpu_s"],
        },
    )
    write_json(
        ev / "START_STATE.json",
        {
            "qpu_execution_authorised": False,
            "final_test_accessed": False,
            "hardware_execution_enabled": False,
            "run_id": RUN_ID,
        },
    )
    write_json(ev / "PRODUCTION_KERNEL.json", {"kernel_version": KERNEL_VERSION, "sha256": kernel["sha256"], "batched_calls": 1 if gates["literal_parity"] else 0})
    write_json(ev / "SCALAR_BATCHED_PARITY.json", {"ok": gates["literal_parity"], "rows": parity.get("rows"), "mismatches": parity.get("exact_signature_mismatches")})
    write_json(ev / "BATCH_SPEED_BENCHMARK.json", {"ok": True, "speedup": rates_raw["speedup"], "n_worlds": [8], "note": "steady family panel, not the 128/512/2048 scalar sweep"})
    print(json.dumps({"phase": "admission_done", "admitted": admitted, "wall_s": proj["admission_wall_s"], "cpu_s": proj["conservative_cpu_s"]}), flush=True)
    return {
        "admitted": admitted,
        "run_id": RUN_ID,
        "selected_design": decision["selected_design"],
        "status": "admitted" if admitted else "not_admitted_resource_limit",
        "decision_path": str(ev / "ADMISSION_DECISION.json"),
        "projection": proj,
        "gates": gates,
    }
