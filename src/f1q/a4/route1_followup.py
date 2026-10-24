"""Route 1 parity panel and capacity measurements.

Engineering fixtures only. Does not execute registered scientific parents and
does not write the preserved feasibility directory.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import threading
import time
import traceback
from pathlib import Path
from typing import Any

from f1q.a4.performance_feasibility import _tasks, parity_one_checkpoint
from f1q.hashing import sha256_file


def run_parity_panel(dest: Path, workers: int) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    rows_dir = dest / "parity"
    rows_dir.mkdir(exist_ok=True)
    tasks = _tasks(32)
    pending = []
    for task in tasks:
        name = f"w{task['n_worlds']}_{task['family_index']}_{task['regime']}_r{task['replicate']}.json.gz"
        task = dict(task)
        task["out_name"] = name
        if not (rows_dir / name).is_file():
            pending.append(task)
    t0 = time.perf_counter()
    cpu0 = time.process_time()
    print(
        json.dumps({"phase": "parity_panel", "pending": len(pending), "workers": workers, "checkpoints": len(tasks)}),
        flush=True,
    )
    results = []
    if pending:
        if workers <= 1:
            for i, task in enumerate(pending, start=1):
                results.append((task, parity_one_checkpoint(task)))
                print(json.dumps({"phase": "parity_checkpoint", "completed": i, "total": len(pending)}), flush=True)
        else:
            import multiprocessing as mp
            from concurrent.futures import ProcessPoolExecutor

            with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as pool:
                futures = {pool.submit(parity_one_checkpoint, task): task for task in pending}
                done = 0
                from concurrent.futures import wait, FIRST_COMPLETED

                waiting = set(futures)
                while waiting:
                    finished, waiting = wait(waiting, timeout=30, return_when=FIRST_COMPLETED)
                    if not finished:
                        print(
                            json.dumps(
                                {
                                    "phase": "parity_heartbeat",
                                    "completed": done,
                                    "total": len(pending),
                                    "wall_s": time.perf_counter() - t0,
                                }
                            ),
                            flush=True,
                        )
                        continue
                    for fut in finished:
                        task = futures[fut]
                        result = fut.result()
                        blob = json.dumps(result).encode()
                        with gzip.open(rows_dir / task["out_name"], "wb") as fh:
                            fh.write(blob)
                        done += 1
                        results.append((task, result))
                        print(
                            json.dumps(
                                {
                                    "phase": "parity_checkpoint",
                                    "completed": done,
                                    "total": len(pending),
                                    "checkpoint": result["checkpoint_id"],
                                    "mismatches": result["mismatches"],
                                    "wall_s": time.perf_counter() - t0,
                                }
                            ),
                            flush=True,
                        )
    summary = _summarize(rows_dir)
    summary["wall_s"] = time.perf_counter() - t0
    summary["parent_cpu_process_time_s"] = time.process_time() - cpu0
    summary["kernel_source_sha256"] = sha256_file(Path("src/f1q/simulator/compiled_kernel.py"))
    (dest / "PARITY_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def _summarize(rows_dir: Path) -> dict:
    files = sorted(rows_dir.glob("*.json.gz"))
    rows = 0
    mismatches = 0
    mismatch_rows = []
    ratios = []
    for path in files:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        rows += int(payload["n_rows"])
        mismatches += int(payload["mismatches"])
        scalar_s = float(payload["scalar_s"])
        cand_s = float(payload["candidate_s"])
        if cand_s > 0:
            ratios.append(scalar_s / cand_s)
        for row in payload["rows"]:
            if not row["match"]:
                mismatch_rows.append(
                    {
                        "checkpoint_id": row["checkpoint_id"],
                        "plan_index": row["plan_index"],
                        "world_seed": row["world_seed"],
                        "loss_scalar": row["loss_scalar"],
                        "loss_candidate": row["loss_candidate"],
                    }
                )
    steady = sorted(ratios)
    return {
        "files": len(files),
        "rows": rows,
        "exact_signature_mismatches": mismatches,
        "mismatch_rows": mismatch_rows,
        "paired_checkpoint_ratios": {
            "n": len(steady),
            "min": steady[0] if steady else None,
            "max": steady[-1] if steady else None,
        },
    }


def _rss_of(pids: list[int]) -> int:
    if not pids:
        return 0
    proc = subprocess.run(
        ["ps", "-o", "pid=,rss=", "-p", ",".join(str(p) for p in pids)],
        check=False,
        capture_output=True,
        text=True,
    )
    total = 0
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit():
            total += int(parts[1]) * 1024
    return total


def _watch_rss(pid_dir: Path, stop: threading.Event, samples: list[int]) -> None:
    while not stop.is_set():
        pids = []
        if pid_dir.is_dir():
            for path in pid_dir.glob("*.pid"):
                try:
                    pids.append(int(path.read_text(encoding="utf-8").strip()))
                except ValueError:
                    continue
        pids.append(os.getpid())
        samples.append(_rss_of(pids))
        stop.wait(0.5)


def prepare_mix() -> list[dict[str, Any]]:
    from f1q.a4.loop import family_spec
    from f1q.a4.problem import (
        build_menu_and_instance,
        enumerate_legal_policies,
        extract_causal_view,
        plan_fingerprint,
    )
    from f1q.generator.config import cartesian_family_ids
    from f1q.hashing import sha256_json
    from f1q.simulator.interface import RaceSimulator

    items = []
    families = cartesian_family_ids()
    for fam in families:
        for regime in ("SC", "VSC"):
            spec = family_spec(
                family_id=fam,
                block_id=f"engperf.cap.{fam}.{regime}",
                regime=regime,
                partition="development",
                index=0,
                seed=41000,
            )
            sim = RaceSimulator()
            sim.initialize(spec)
            sim.advance_to_checkpoint()
            blob = sim.serialize()
            view = extract_causal_view(sim.observe().model_dump(mode="python"))
            legal = enumerate_legal_policies(build_menu_and_instance(view))
            cands = []
            for row in legal[:3]:
                plan = row["wrapped"]["plan"]
                cands.append({"plan": plan, "plan_hash": plan_fingerprint(plan)})
            items.append(
                {
                    "spec": spec,
                    "blob": blob,
                    "cands": cands,
                    "worlds": [810000, 810001, 810002, 810003],
                    "epoch": float(blob["t"]) + 0.05,
                    "spec_hash": sha256_json({"family": fam, "regime": regime, "panel": "capacity"}),
                    "checkpoint_hash": sha256_json({"t": blob["t"], "regime": regime}),
                }
            )
            print(json.dumps({"phase": "prepare_checkpoint", "family": fam, "regime": regime, "plans": len(cands)}), flush=True)
    cells = sum(len(item["cands"]) * len(item["worlds"]) for item in items)
    if cells != 192:
        raise RuntimeError(f"capacity mix is {cells} cells, expected 192")
    return items


def _run_pool(n_workers: int, items: list[dict[str, Any]], pid_dir: Path, waves: int = 2) -> dict[str, Any]:
    import multiprocessing as mp
    import shutil
    from concurrent.futures import ProcessPoolExecutor

    from f1q.a4.route1_worker import candidate_wave

    if pid_dir.exists():
        shutil.rmtree(pid_dir)
    pid_dir.mkdir(parents=True)
    samples: list[int] = []
    stop = threading.Event()
    watcher = threading.Thread(target=_watch_rss, args=(pid_dir, stop, samples), daemon=True)
    watcher.start()
    t0 = time.perf_counter()
    cpu0 = time.process_time()
    wave_rows = []
    try:
        ctx = mp.get_context("spawn")
        with ProcessPoolExecutor(max_workers=n_workers, mp_context=ctx) as pool:
            for wave in range(waves):
                payloads = []
                for slot in range(n_workers):
                    payloads.append(
                        {
                            "items": items,
                            "pid_path": str(pid_dir / f"w{wave}_{slot}.pid"),
                        }
                    )
                tw = time.perf_counter()
                rows = list(pool.map(candidate_wave, payloads))
                wave_rows.append(
                    {
                        "wave": wave,
                        "makespan_s": time.perf_counter() - tw,
                        "workers": rows,
                    }
                )
                print(
                    json.dumps(
                        {
                            "phase": "capacity_wave",
                            "workers": n_workers,
                            "wave": wave,
                            "makespan_s": wave_rows[-1]["makespan_s"],
                            "max_worker_wall_s": max(r["wall_s"] for r in rows),
                        }
                    ),
                    flush=True,
                )
    finally:
        stop.set()
        watcher.join(timeout=2)
    return {
        "workers": n_workers,
        "waves": wave_rows,
        "pool_wall_s": time.perf_counter() - t0,
        "parent_process_time_s": time.process_time() - cpu0,
        "simultaneous_rss_samples": len(samples),
        "simultaneous_rss_max_bytes": max(samples) if samples else None,
        "simultaneous_rss_median_bytes": sorted(samples)[len(samples) // 2] if samples else None,
    }


def time_fits() -> dict[str, Any]:
    from f1q.a4.donor_labels import per_instance_variational_reference
    from f1q.a4.donors import DonorRanker, select_donor_policy
    from f1q.a4.loop import family_spec
    from f1q.a4.problem import build_a4_qubo, build_menu_and_instance, extract_causal_view
    from f1q.simulator.interface import RaceSimulator

    spec = family_spec(
        family_id="fam.green_pit_low.tyre_nonlinear.traffic_dense",
        block_id="engperf.fit.fam.green_pit_low.tyre_nonlinear.traffic_dense",
        regime="SC",
        partition="development",
        index=1,
        seed=41001,
    )
    sim = RaceSimulator()
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    view = extract_causal_view(sim.observe().model_dump(mode="python"))
    inst = build_menu_and_instance(view)
    qubo = build_a4_qubo(inst)
    from f1q.a4.problem import enumerate_legal_policies

    legal = enumerate_legal_policies(inst)
    fits = []
    for family, depth in (("C0", 1), ("C0", 2), ("C1", 1), ("C1", 2)):
        reps = []
        for rep in range(3):
            t0 = time.perf_counter()
            cpu0 = time.process_time()
            rec = per_instance_variational_reference(
                instance=inst,
                qubo=qubo,
                family=family,
                depth=depth,
                seed=7000 + rep,
                legal_table=legal,
                max_evals=40,
            )
            reps.append(
                {
                    "rep": rep,
                    "wall_s": time.perf_counter() - t0,
                    "cpu_s": time.process_time() - cpu0,
                    "fit_s": rec["donor"]["fit_s"],
                    "n_evals": rec["n_evals"],
                }
            )
            print(json.dumps({"phase": "fit", "family": family, "depth": depth, **reps[-1]}), flush=True)
        fits.append(
            {
                "family": family,
                "depth": depth,
                "key": f"{family}_p{depth}",
                "reps": reps,
                "conservative_wall_s": max(r["wall_s"] for r in reps),
                "conservative_fit_s": max(r["fit_s"] for r in reps),
            }
        )
    donors = []
    for row in fits:
        donors.append(
            {
                "donor_id": row["key"],
                "features": {"n_logical_vars": 8.0, "remaining_laps": 20.0},
                "best_value_scaled": row["conservative_fit_s"],
            }
        )
    feats = {"n_logical_vars": 8.0, "remaining_laps": 21.0}
    ranker = DonorRanker()
    import numpy as np

    x = np.ones((4, len(ranker.feature_keys)))
    y = np.ones((4, len(donors)))
    t_rank = time.perf_counter()
    ranker.fit(x, y, [d["donor_id"] for d in donors], family_depth="C0_p1")
    ranker_fit_s = time.perf_counter() - t_rank
    rng = np.random.default_rng(0)
    selections = []
    for policy in ("fixed", "nn", "random", "learned", "best_found"):
        t0 = time.perf_counter()
        for _ in range(100):
            select_donor_policy(policy=policy, donors=donors, feats=feats, ranker=ranker, rng=rng, identity_seed=1)
        selections.append({"policy": policy, "per_call_s": (time.perf_counter() - t0) / 100.0, "calls_timed": 100})
    return {"fits": fits, "ranker_fit_s": ranker_fit_s, "selections": selections, "n_legal": len(legal)}


def run_capacity(dest: Path, *, prior_wall: float, prior_cpu: float) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    logical = os.cpu_count() or 1
    physical = logical
    try:
        import subprocess as sp

        physical = int(sp.check_output(["sysctl", "-n", "hw.physicalcpu"], text=True).strip())
        logical = int(sp.check_output(["sysctl", "-n", "hw.logicalcpu"], text=True).strip())
    except Exception:
        pass
    exclusion = {
        "workers": 12,
        "measured": False,
        "reason": f"12 workers exceed {logical} logical and {physical} physical CPUs",
    }
    print(json.dumps({"phase": "fits_start"}), flush=True)
    fits = time_fits()
    if prior_wall + (time.perf_counter() - t0) > 6800:
        raise RuntimeError("engineering wall allowance too small to start worker measurements")
    print(json.dumps({"phase": "prepare_mix"}), flush=True)
    items = prepare_mix()
    reps = []
    for rep in range(3):
        if prior_wall + (time.perf_counter() - t0) > 6800:
            print(json.dumps({"phase": "stop", "reason": "wall_allowance", "completed_reps": rep}), flush=True)
            break
        rep_row = {"rep": rep, "configs": []}
        for n in (1, 8, 10):
            if n > logical:
                continue
            print(json.dumps({"phase": "capacity_config", "rep": rep, "workers": n}), flush=True)
            measured = _run_pool(n, items, dest / "pids" / f"r{rep}_w{n}")
            rep_row["configs"].append(measured)
        reps.append(rep_row)
    out = {
        "logical_cpus": logical,
        "physical_cpus": physical,
        "twelve_worker_exclusion": exclusion,
        "fits": fits,
        "reps": reps,
        "wall_s": time.perf_counter() - t0,
        "cells_per_task": 192,
        "waves": 2,
        "repetitions_completed": len(reps),
    }
    (dest / "CAPACITY.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("parity")
    p.add_argument("--dest", type=Path, required=True)
    p.add_argument("--workers", type=int, default=4)
    c = sub.add_parser("capacity")
    c.add_argument("--dest", type=Path, required=True)
    c.add_argument("--prior-wall", type=float, required=True)
    c.add_argument("--prior-cpu", type=float, required=True)
    args = parser.parse_args()
    t0 = time.perf_counter()
    try:
        if args.cmd == "parity":
            summary = run_parity_panel(args.dest, args.workers)
            print(json.dumps({"phase": "parity_done", "summary": summary}), flush=True)
        elif args.cmd == "capacity":
            summary = run_capacity(args.dest, prior_wall=args.prior_wall, prior_cpu=args.prior_cpu)
            print(json.dumps({"phase": "capacity_done", "wall_s": summary["wall_s"], "reps": summary["repetitions_completed"]}), flush=True)
    except Exception:
        traceback.print_exc()
        raise
    finally:
        ledger = args.dest / "COMMAND_LEDGER.jsonl"
        args.dest.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "cmd": args.cmd,
                        "wall_s": time.perf_counter() - t0,
                        "pid": os.getpid(),
                    }
                )
                + "\n"
            )


if __name__ == "__main__":
    main()
