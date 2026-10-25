"""Eight-worker CPU and wall observations. Solo cost is recorded and not reused as a divisor."""

from __future__ import annotations

import json
import os
import resource
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from f1q.a4.corrected_cost import HISTORICAL_UNDERPREDICTION
from f1q.a4.resource_check import project_from_raw
from f1q.generator.config import cartesian_family_ids

_CPU0 = 0.0


def _cpu_now() -> float:
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return float(ru.ru_utime + ru.ru_stime)


def _rss_self() -> int:
    ru = resource.getrusage(resource.RUSAGE_SELF)
    rss = int(ru.ru_maxrss)
    if os.uname().sysname != "Darwin" and rss < 10**10:
        return rss * 1024
    return rss


def _init_worker() -> None:
    global _CPU0
    from f1q.a4 import worker_init

    worker_init.apply()
    _CPU0 = _cpu_now()


def _race_task(payload: dict[str, Any]) -> dict[str, Any]:
    from f1q.a4.backend_select import select_evaluation_backend
    from f1q.a4.banks import EVALUATION_BANK
    from f1q.a4.loop import evaluate_candidates_on_bank
    from f1q.a4.prepared import prepare_case

    t0 = time.perf_counter()
    select_evaluation_backend("candidate")
    pc = prepare_case(
        family_id=payload["family_id"],
        block_id=f"engfix.race.{payload['family_index']}.{payload['regime']}",
        regime=payload["regime"],
        partition="development",
        index=int(payload["family_index"]),
        seed=62000 + int(payload["family_index"]),
        n_planning=2,
        n_evaluation=2,
    )
    plans = [{"plan": row["plan"], "plan_hash": row["plan_hash"]} for row in pc.legal_table[: int(payload["n_plans"])]]
    warm_seeds = [930000]
    t_warm = time.perf_counter()
    evaluate_candidates_on_bank(
        pc.spec_with_budget(30),
        pc.checkpoint_blob,
        plans[:1],
        warm_seeds,
        bank=EVALUATION_BANK,
        arrival_delay_s=0.02,
        commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
        cache={},
        spec_hash=pc.spec_hash,
        checkpoint_hash=pc.checkpoint_hash,
        nominal_budget_s=30.0,
    )
    warm_s = time.perf_counter() - t_warm
    worlds = [940000 + i for i in range(int(payload["n_worlds"]))]
    t1 = time.perf_counter()
    evaluate_candidates_on_bank(
        pc.spec_with_budget(30),
        pc.checkpoint_blob,
        plans,
        worlds,
        bank=EVALUATION_BANK,
        arrival_delay_s=0.02,
        commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
        cache={},
        spec_hash=pc.spec_hash,
        checkpoint_hash=pc.checkpoint_hash,
        nominal_budget_s=30.0,
    )
    steady = time.perf_counter() - t1
    cells = len(plans) * len(worlds)
    select_evaluation_backend("legacy")
    return {
        "pid": os.getpid(),
        "cpu_s": _cpu_now() - _CPU0,
        "rss_max_bytes": _rss_self(),
        "warm_s": warm_s,
        "steady_s": steady,
        "cells": cells,
        "per_cell_wall_s": steady / cells if cells else 0.0,
        "wall_s": time.perf_counter() - t0,
        "family_id": payload["family_id"],
        "regime": payload["regime"],
    }


def _poll_rss(stop: threading.Event, samples: list[int]) -> None:
    parent = os.getpid()
    while not stop.is_set():
        proc = subprocess.run(["ps", "-ax", "-o", "pid=,ppid=,rss="], capture_output=True, text=True)
        rows = []
        for line in (proc.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
                rows.append((int(parts[0]), int(parts[1]), int(parts[2])))
        children = {pid for pid, ppid, _rss in rows if ppid == parent}
        total = 0
        for pid, ppid, rss in rows:
            if pid == parent or ppid == parent or ppid in children:
                total += rss * 1024
        if total:
            samples.append(total)
        stop.wait(0.25)


def _serial_cpu_wall(fn) -> dict[str, float]:
    cpu0 = _cpu_now()
    t0 = time.perf_counter()
    fn()
    return {"wall_s": time.perf_counter() - t0, "cpu_s": _cpu_now() - cpu0}


def measure_workload(
    root: Path,
    *,
    pooled_race_cells: int,
    serial_race_cells: int,
    counts: dict[str, Any],
) -> dict[str, Any]:
    """Predeclared strata: 8 families × SC/VSC, 4 plans × 8 worlds, eight workers."""
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor, as_completed

    from f1q.a4.backend_select import select_evaluation_backend
    from f1q.a4.distributions import build_ideal_distribution, resample_pool
    from f1q.a4.donor_labels import per_instance_variational_reference
    from f1q.a4.loop import decide_and_evaluate
    from f1q.a4.prepared import prepare_case
    from f1q.a4.contracts import FAMILY_DEPTH_KEYS, POOL_DRAWS
    from f1q.a4.unit_ledger import ablation_specs

    families = cartesian_family_ids()
    tasks = []
    for i, fam in enumerate(families):
        for regime in ("SC", "VSC"):
            tasks.append({"family_id": fam, "family_index": i, "regime": regime, "n_plans": 4, "n_worlds": 8})
    print(json.dumps({"phase": "resource_probe", "tasks": len(tasks), "workers": 8}), flush=True)
    cpu0 = _cpu_now()
    t0 = time.perf_counter()
    samples: list[int] = []
    stop = threading.Event()
    poll = threading.Thread(target=_poll_rss, args=(stop, samples), daemon=True)
    poll.start()
    results = []
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=8, mp_context=ctx, initializer=_init_worker) as pool:
        futures = [pool.submit(_race_task, task) for task in tasks]
        for fut in as_completed(futures):
            results.append(fut.result())
            print(json.dumps({"phase": "resource_task", "done": len(results), "total": len(tasks)}), flush=True)
    stop.set()
    poll.join(timeout=2)
    pool_makespan = time.perf_counter() - t0
    coordinator_cpu = _cpu_now() - cpu0
    probe_cells = sum(int(row["cells"]) for row in results)
    per_cell = [float(row["per_cell_wall_s"]) for row in results]
    cold_wall = max(float(row["warm_s"]) for row in results)
    cold_cpu = max(float(row["cpu_s"]) for row in results) * (1.0 / max(probe_cells, 1))

    def _solo() -> None:
        select_evaluation_backend("candidate")
        pc = prepare_case(
            family_id=families[0],
            block_id="engfix.solo.probe",
            regime="SC",
            partition="development",
            index=0,
            seed=63001,
            n_planning=2,
            n_evaluation=2,
        )
        from f1q.a4.banks import EVALUATION_BANK
        from f1q.a4.loop import evaluate_candidates_on_bank

        evaluate_candidates_on_bank(
            pc.spec_with_budget(30),
            pc.checkpoint_blob,
            [{"plan": pc.legal_table[0]["plan"], "plan_hash": pc.legal_table[0]["plan_hash"]}],
            [950000, 950001],
            bank=EVALUATION_BANK,
            arrival_delay_s=0.02,
            commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
            cache={},
            spec_hash=pc.spec_hash,
            checkpoint_hash=pc.checkpoint_hash,
            nominal_budget_s=30.0,
        )
        select_evaluation_backend("legacy")

    solo = _serial_cpu_wall(_solo)

    pc = prepare_case(
        family_id="fam.green_pit_low.tyre_nonlinear.traffic_dense",
        block_id="engfix.serial.probe",
        regime="SC",
        partition="development",
        index=1,
        seed=64002,
        n_planning=2,
        n_evaluation=2,
    )
    serial_wall = 0.0
    serial_cpu = 0.0
    components: dict[str, Any] = {}

    def _charge(name: str, repeats: int, fn) -> None:
        nonlocal serial_wall, serial_cpu
        obs = [_serial_cpu_wall(fn) for _ in range(repeats)]
        wall = max(row["wall_s"] for row in obs)
        cpu = max(row["cpu_s"] for row in obs)
        components[name] = {"repeats": repeats, "max_wall_s": wall, "max_cpu_s": cpu, "observations": obs}
        return wall, cpu

    build_times = []
    for depth, family in ((1, "C0"), (2, "C0"), (1, "C1"), (2, "C1")):
        def _build(depth=depth, family=family) -> None:
            build_ideal_distribution(
                instance=pc.instance,
                qubo=pc.qubo,
                family=family,
                depth=depth,
                gammas=[0.1] * depth,
                betas=[0.2] * depth,
                prepared_case_hash=pc.prepared_case_hash + f".{family}.{depth}",
                cache={},
                legal_table=pc.legal_table,
            )
        obs = [_serial_cpu_wall(_build) for _ in range(2)]
        build_times.append(max(row["wall_s"] for row in obs))
        serial_wall += max(row["wall_s"] for row in obs)
        serial_cpu += max(row["cpu_s"] for row in obs)
    n_builds = int(counts.get("unique_parameter_builds") or 0)
    # The two observations are per depth. Scale the slowest depth across every unique build.
    slow_build = max(build_times) if build_times else 0.0
    build_scale_wall = slow_build * max(n_builds - 4, 0)
    build_scale_cpu = build_scale_wall
    components["builds"] = {"slowest_s": slow_build, "scaled_wall_s": build_scale_wall, "n_builds": n_builds}

    dist = build_ideal_distribution(
        instance=pc.instance,
        qubo=pc.qubo,
        family="C0",
        depth=1,
        gammas=[0.15],
        betas=[0.25],
        prepared_case_hash=pc.prepared_case_hash + ".resample",
        cache={},
        legal_table=pc.legal_table,
    )
    resample_obs = []
    for i in range(8):
        resample_obs.append(_serial_cpu_wall(lambda i=i: resample_pool(dist, pool_draws=POOL_DRAWS, seed=6500 + i)))
    slow_resample = max(row["wall_s"] for row in resample_obs)
    n_resample = int(counts.get("charged_resamples") or 0)
    resample_wall = slow_resample * n_resample
    components["resamples"] = {"slowest_s": slow_resample, "n": n_resample, "scaled_wall_s": resample_wall, "observations": resample_obs}

    fit_obs = []
    for depth, family in ((1, "C0"), (2, "C1")):
        fit_obs.append(
            _serial_cpu_wall(
                lambda depth=depth, family=family: per_instance_variational_reference(
                    instance=pc.instance,
                    qubo=pc.qubo,
                    family=family,
                    depth=depth,
                    seed=6600 + depth,
                    legal_table=pc.legal_table,
                    max_evals=40,
                )
            )
        )
    slow_fit = max(row["wall_s"] for row in fit_obs)
    n_fits = int(counts.get("best_found_fits") or 0)
    fit_wall = slow_fit * n_fits
    components["donor_fits"] = {"slowest_s": slow_fit, "n": n_fits, "scaled_wall_s": fit_wall, "observations": fit_obs}

    from f1q.a4.allocator import dispatch_choice

    alloc_obs = [
        _serial_cpu_wall(
            lambda: dispatch_choice(
                {"pred_marginal_utility": 0.2, "uncertainty": 0.01},
                deadline_s=30.0,
                pred_latency_s=0.1,
                margin=0.001,
                mode="frozen_allocator",
                conservative_residual=0.0,
                allowed_options=["classical_only", "C0_p1", "C1_p1"],
            )
        )
        for _ in range(8)
    ]
    slow_alloc = max(row["wall_s"] for row in alloc_obs)
    alloc_wall = slow_alloc * int(counts.get("n_operation_rows") or n_builds or 1)
    components["allocator"] = {"slowest_s": slow_alloc, "scaled_wall_s": alloc_wall}

    ab_obs = []
    bank = json.loads((root / "evidence" / "stage6_a4" / "09806343-f940-4f33-9e0f-eb2855d0714b" / "DONOR_BANK_V2.json").read_text(encoding="utf-8")) if False else None
    from f1q.a4.donors import build_donor_bank_v2
    from f1q.a4.hashing_io import load_jsonl

    fits = load_jsonl(root / "evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b/ANCHOR_FITS.jsonl")
    bank = build_donor_bank_v2(
        fits,
        source_run_id="09806343-f940-4f33-9e0f-eb2855d0714b",
        source_anchor_path="evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b/ANCHOR_FITS.jsonl",
        source_anchor_sha256="b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a",
    )
    for spec in ablation_specs():
        mode = spec["mode"] if spec["mode"] != "frozen_allocator" else "always_classical"
        ab_obs.append(
            _serial_cpu_wall(
                lambda mode=mode: decide_and_evaluate(
                    pc.spec_with_budget(30),
                    mode=mode,
                    runtime=None,
                    donor_bank=bank,
                    donor_policy="fixed",
                    planning_seeds=pc.planning_bank_keys[:2],
                    evaluation_seeds=pc.evaluation_bank_keys[:2],
                    online_seed=1,
                    cache={},
                    pool_size=32,
                    equal_k=4,
                    deadline_s=30.0,
                    margin=0.001,
                    conservative_residual=0.0,
                    family_depth=("C0", 1),
                    n_stochastic_seeds=1,
                    legal_table=pc.legal_table,
                    prepared=pc,
                    dist_cache={},
                    policy_seed=0,
                )
            )
        )
    slow_ab = max(row["wall_s"] for row in ab_obs) if ab_obs else 0.0
    components["ablations"] = {
        "slowest_case_s": slow_ab,
        "n_specifications_probed": len(ablation_specs()),
        "scaled_in_serial_race_cells": True,
        "not_added_again_as_case_wall": True,
    }
    components["offline_all_plan"] = {
        "schedule": "serial_for_loop_of_eight",
        "charged_as": "serial_race_cells",
    }
    # Builds run inside the eight-worker case pool. Wall uses that schedule once.
    build_wall = slow_build * max(n_builds, 0) / 8.0
    build_cpu = slow_build * max(n_builds, 0)
    components["builds"]["schedule"] = "eight_worker_pool"
    components["builds"]["scaled_wall_s"] = build_wall
    components["builds"]["scaled_cpu_s"] = build_cpu
    # Resamples and variational fits in the coordinator donor loop are serial.
    serial_wall = resample_wall + fit_wall + alloc_wall
    serial_cpu = resample_wall + fit_wall + alloc_wall + build_cpu
    serial_wall += build_wall

    raw = {
        "probe_cells": probe_cells,
        "per_cell_wall_s": per_cell,
        "processes": [{"pid": int(row["pid"]), "cpu_s": float(row["cpu_s"])} for row in results],
        "coordinator_cpu_s": coordinator_cpu,
        "solo_wall_s": solo["wall_s"],
        "solo_cpu_s": solo["cpu_s"],
        "cold_wall_s": cold_wall,
        "cold_cpu_s": cold_cpu,
        "serial_wall_s": serial_wall,
        "serial_cpu_s": serial_cpu,
        "pool_makespan_s": pool_makespan,
        "pooled_race_cells": int(pooled_race_cells),
        "serial_race_cells": int(serial_race_cells),
        "underprediction_historical": float(HISTORICAL_UNDERPREDICTION),
        "simultaneous_rss_max_bytes": max(samples) if samples else max(int(row["rss_max_bytes"]) for row in results),
        "components": components,
        "family_depths_measured": list(FAMILY_DEPTH_KEYS),
        "schedule": "eight_worker_spawn",
        "probe_map": "configs/design_r_isolated_probe_map.json",
    }
    projection = project_from_raw(raw)
    projection["simultaneous_rss_max_bytes"] = raw["simultaneous_rss_max_bytes"]
    raw_public = {k: v for k, v in raw.items() if k != "components"}
    raw_public["components"] = {
        key: {ik: iv for ik, iv in val.items() if ik != "observations"} if isinstance(val, dict) else val
        for key, val in components.items()
    }
    return {"raw": raw_public, "projection": projection, "probe_wall_s": time.perf_counter() - t0}
