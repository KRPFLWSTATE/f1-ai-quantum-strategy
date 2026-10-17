"""Engineering measurement driver for the compiled continuation.

This is not a scientific plan and it does not execute registered parents.
Invoke slices explicitly. Each process is foreground and bounded.
"""

from __future__ import annotations

import argparse
import gzip
import json
import multiprocessing as mp
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from f1q.hashing import sha256_json

EVIDENCE = Path("evidence/performance_feasibility/3c44b59e-7065-4899-9977-1fae0cb9d88f")
FAMILIES_NOTE = "cartesian eight families"


def _rows_path(kind: str) -> Path:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    return EVIDENCE / kind


def parity_one_checkpoint(task: dict[str, Any]) -> dict[str, Any]:
    """Scalar versus candidate on one synthetic checkpoint. No registered parents."""
    from f1q.a4.backend_select import select_evaluation_backend
    from f1q.a4.banks import EVALUATION_BANK
    from f1q.a4.batched import simulate_plan_world_scalar
    from f1q.a4.loop import evaluate_candidates_on_bank, family_spec
    from f1q.a4.problem import (
        build_menu_and_instance,
        enumerate_legal_policies,
        extract_causal_view,
        plan_fingerprint,
    )
    from f1q.generator.config import cartesian_family_ids
    from f1q.simulator.interface import RaceSimulator

    fam = cartesian_family_ids()[int(task["family_index"])]
    regime = task["regime"]
    replicate = int(task["replicate"])
    spec = family_spec(
        family_id=fam,
        block_id=f"engperf.corr.{fam}.r{replicate}",
        regime=regime,
        partition="development",
        index=replicate,
        seed=41000 + replicate,
    )
    sim = RaceSimulator()
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    blob = sim.serialize()
    obs = sim.observe()
    view = extract_causal_view(obs.model_dump(mode="python"))
    inst = build_menu_and_instance(view)
    legal = enumerate_legal_policies(inst)
    cands = []
    for row in legal[:3]:
        plan = row["wrapped"]["plan"]
        cands.append({"plan": plan, "plan_hash": plan_fingerprint(plan)})
    worlds = [810000 + i for i in range(int(task["n_worlds"]))]
    epoch = float(blob["t"]) + 0.05
    sh = sha256_json({"family": fam, "regime": regime, "replicate": replicate, "panel": "correctness"})
    ch = sha256_json({"t": blob["t"], "regime": regime})
    t0 = time.perf_counter()
    cpu0 = time.process_time()
    scalar: dict[str, list] = {}
    for cand in cands:
        scalar[cand["plan_hash"]] = [
            simulate_plan_world_scalar(
                spec,
                blob,
                cand["plan"],
                w,
                arrival_delay_s=0.02,
                commitment_epoch_race_s=epoch,
                cache={},
                spec_hash=sh,
                checkpoint_hash=ch,
                bank=EVALUATION_BANK,
                nominal_budget_s=30.0,
                parity=True,
            )
            for w in worlds
        ]
    scalar_s = time.perf_counter() - t0
    select_evaluation_backend("candidate")
    t1 = time.perf_counter()
    out = evaluate_candidates_on_bank(
        spec,
        blob,
        cands,
        worlds,
        bank=EVALUATION_BANK,
        arrival_delay_s=0.02,
        commitment_epoch_race_s=epoch,
        cache={},
        spec_hash=sh,
        checkpoint_hash=ch,
        nominal_budget_s=30.0,
    )
    cand_s = time.perf_counter() - t1
    select_evaluation_backend("legacy")
    rows = []
    mismatches = 0
    for cand in cands:
        ph = cand["plan_hash"]
        for i, w in enumerate(worlds):
            a = scalar[ph][i]
            b = out["worlds"][ph][i]
            match = (
                a.get("commitment_classification") == b.get("commitment_classification")
                and a.get("event_ordering") == b.get("event_ordering")
                and abs(float(a["loss"]) - float(b["loss"])) <= 1e-12
                and bool(a.get("fallback")) == bool(b.get("fallback"))
            )
            if not match:
                mismatches += 1
            rows.append(
                {
                    "checkpoint_id": f"engperf.corr.{fam}.{regime}.r{replicate}",
                    "family_id": fam,
                    "regime": regime,
                    "plan_index": cands.index(cand),
                    "world_seed": w,
                    "match": match,
                    "loss_scalar": a["loss"],
                    "loss_candidate": b["loss"],
                    "commitment": b.get("commitment_classification"),
                    "n_events": len(b["event_ordering"]),
                    "event_sha256": sha256_json(b["event_ordering"]),
                    "scalar_event_sha256": sha256_json(a["event_ordering"]),
                }
            )
    return {
        "checkpoint_id": rows[0]["checkpoint_id"] if rows else task,
        "n_rows": len(rows),
        "mismatches": mismatches,
        "scalar_s": scalar_s,
        "candidate_s": cand_s,
        "cpu_s": time.process_time() - cpu0,
        "rows": rows,
    }


def _tasks(n_worlds: int) -> list[dict[str, Any]]:
    tasks = []
    for family_index in range(8):
        for regime in ("SC", "VSC"):
            for replicate in (0, 1):
                tasks.append(
                    {
                        "family_index": family_index,
                        "regime": regime,
                        "replicate": replicate,
                        "n_worlds": n_worlds,
                    }
                )
    return tasks


def run_parity(offset: int, limit: int, workers: int, n_worlds: int) -> None:
    tasks = _tasks(n_worlds)[offset : offset + limit]
    dest = _rows_path("parity")
    dest.mkdir(exist_ok=True)
    done = {p.name for p in dest.glob("*.json.gz")}
    pending = []
    for task in tasks:
        name = f"w{task['n_worlds']}_{task['family_index']}_{task['regime']}_r{task['replicate']}.json.gz"
        if name not in done:
            task["out_name"] = name
            pending.append(task)
    if not pending:
        print(json.dumps({"skipped": len(tasks), "reason": "already_present"}))
        return
    ctx_workers = max(1, int(workers))
    results = []
    if ctx_workers == 1:
        for task in pending:
            results.append(parity_one_checkpoint(task))
    else:
        with ProcessPoolExecutor(max_workers=ctx_workers, mp_context=mp.get_context("spawn")) as pool:
            results = list(pool.map(parity_one_checkpoint, pending))
    for task, result in zip(pending, results):
        blob = json.dumps(result).encode()
        with gzip.open(dest / task["out_name"], "wb") as fh:
            fh.write(blob)
        print(
            json.dumps(
                {
                    "checkpoint": result["checkpoint_id"],
                    "rows": result["n_rows"],
                    "mismatches": result["mismatches"],
                    "scalar_s": result["scalar_s"],
                    "candidate_s": result["candidate_s"],
                }
            ),
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("parity")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--limit", type=int, default=4)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--worlds", type=int, default=32)
    args = parser.parse_args()
    t0 = time.perf_counter()
    try:
        if args.cmd == "parity":
            run_parity(args.offset, args.limit, args.workers, args.worlds)
    except Exception:
        traceback.print_exc()
        raise
    finally:
        ledger = EVIDENCE / "COMMAND_LEDGER.jsonl"
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        with ledger.open("a") as fh:
            fh.write(
                json.dumps(
                    {
                        "cmd": args.cmd,
                        "args": vars(args),
                        "wall_s": time.perf_counter() - t0,
                        "pid": os.getpid(),
                    }
                )
                + "\n"
            )


if __name__ == "__main__":
    main()
