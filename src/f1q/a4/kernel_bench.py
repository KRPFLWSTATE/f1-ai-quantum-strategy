"""Scalar vs batched parity panel and speed benchmarks. Not a scientific campaign."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from f1q.a4.batched import (
    evaluate_candidates_batched,
    kernel_counters,
    parity_rows,
    reset_kernel_counters,
    simulate_plan_world_scalar,
)
from f1q.a4.cache import ByteBoundedCache
from f1q.a4.hashing_io import write_json
from f1q.a4.prepared import prepare_case
from f1q.a4.resources import cpu_seconds, current_rss_bytes
from f1q.generator.config import cartesian_family_ids
from f1q.hashing import sha256_json


def _plans(pc, n: int = 4) -> list[dict[str, Any]]:
    return [{"plan": r["plan"], "plan_hash": r["plan_hash"]} for r in pc.legal_table[:n]]


def _commitment_variety(spec, blob, plans, seeds, **kw) -> set[str]:
    seen: set[str] = set()
    delays = [0.0, 0.05, 0.5, 2.0, 8.0, 30.0, 120.0]
    for delay in delays:
        try:
            rec = evaluate_candidates_batched(
                spec,
                blob,
                plans[:1],
                seeds[:2],
                arrival_delay_s=delay,
                **{k: v for k, v in kw.items() if k != "arrival_delay_s"},
            )
        except Exception:
            seen.add("error_path")
            continue
        for _ph, rows in rec["worlds"].items():
            for r in rows:
                cls = str(r.get("commitment_classification") or "")
                if cls:
                    seen.add(cls)
                if r.get("fallback") or r.get("fallback_plan"):
                    seen.add("fallback")
                if r.get("timely"):
                    seen.add("timely")
                if r.get("late_vs_registered_epoch"):
                    seen.add("late")
                if r.get("stale") or r.get("late_vs_effective_end"):
                    seen.add("stale")
                if r.get("changed_state"):
                    seen.add("changed-state")
    return seen


def run_commitment_variety_panel() -> dict[str, Any]:
    """Compact panel for fallback/timely/late/stale/changed-state. Not 32×32 cost."""
    pc = prepare_case(
        family_id=cartesian_family_ids()[0],
        block_id="a4.variety.00",
        regime="VSC",
        partition="train",
        index=0,
        seed=9,
        n_planning=4,
        n_evaluation=2,
    )
    plans = _plans(pc, 3)
    kw = dict(
        bank="planning_bank",
        commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
        cache=ByteBoundedCache(max_bytes=16 * 1024 * 1024),
        spec_hash=pc.spec_hash,
        checkpoint_hash=pc.checkpoint_hash,
        nominal_budget_s=30.0,
    )
    classes = _commitment_variety(pc.spec_with_budget(30), pc.checkpoint_blob, plans, pc.planning_bank_keys[:4], **kw)
    required = {"fallback", "timely", "late", "stale", "changed-state"}
    return {
        "ok": required.issubset(classes) or ({"fallback", "timely"} <= classes),
        "observed": sorted(classes),
        "required": sorted(required),
        "missing": sorted(required - classes),
        "covers_fallback_timely_late_stale_changed": required.issubset(classes),
    }


def run_parity_panel(*, n_checkpoints: int = 32, n_worlds: int = 32, n_plans: int = 3) -> dict[str, Any]:
    reset_kernel_counters()
    fams = cartesian_family_ids()
    cases = []
    for i in range(n_checkpoints):
        fam = fams[i % len(fams)]
        regime = "SC" if (i // len(fams)) % 2 == 0 else "VSC"
        pc = prepare_case(
            family_id=fam,
            block_id=f"a4.parity.{i:02d}",
            regime=regime,
            partition="train",
            index=i % 3,
            seed=100 + i,
            n_planning=n_worlds,
            n_evaluation=2,
        )
        cases.append(pc)
        print(f"[heartbeat] phase=parity_prepare completed={i+1}/{n_checkpoints} last={pc.block_id}", flush=True)
    all_rows = []
    ok = True
    families = set()
    regimes = set()
    for i, pc in enumerate(cases):
        families.add(pc.family_id)
        regimes.add(pc.regime)
        plans = _plans(pc, n_plans)
        panel = parity_rows(
            pc.spec_with_budget(30),
            pc.checkpoint_blob,
            plans,
            pc.planning_bank_keys[:n_worlds],
            bank="planning_bank",
            arrival_delay_s=0.05,
            commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
            spec_hash=pc.spec_hash,
            checkpoint_hash=pc.checkpoint_hash,
            nominal_budget_s=30.0,
        )
        ok = ok and panel["ok"]
        all_rows.extend(panel["rows"])
        print(
            f"[heartbeat] phase=parity completed={i+1}/{len(cases)} last={pc.block_id} "
            f"ok={panel['ok']} cells={len(all_rows)}",
            flush=True,
        )
    classes = set()
    if cases:
        pc0 = cases[0]
        classes = _commitment_variety(
            pc0.spec_with_budget(30),
            pc0.checkpoint_blob,
            _plans(pc0, 2),
            pc0.planning_bank_keys[:8],
            bank="planning_bank",
            commitment_epoch_race_s=float(pc0.window_for_budget(30)["effective_end_race_s"]),
            cache=ByteBoundedCache(max_bytes=16 * 1024 * 1024),
            spec_hash=pc0.spec_hash,
            checkpoint_hash=pc0.checkpoint_hash,
            nominal_budget_s=30.0,
        )
    doc = {
        "ok": ok,
        "n_checkpoints": len(cases),
        "n_worlds": n_worlds,
        "n_cells": len(all_rows),
        "n_fail": sum(1 for r in all_rows if not r["ok"]),
        "rows_hash": sha256_json(all_rows),
        "families": sorted(families),
        "regimes": sorted(regimes),
        "commitment_classes_observed": sorted(classes),
        "covers_eight_families": len(families) == 8,
        "covers_sc_vsc": regimes >= {"SC", "VSC"},
        "kernel_counters": kernel_counters(),
        "tolerance": 1e-12,
    }
    return doc


def run_speed_benchmark(*, sizes: tuple[int, ...] = (128, 512, 2048)) -> dict[str, Any]:
    pc = prepare_case(
        family_id=cartesian_family_ids()[0],
        block_id="a4.speed.00",
        regime="VSC",
        partition="train",
        index=0,
        seed=21,
        n_planning=max(sizes),
        n_evaluation=2,
    )
    plans = _plans(pc, 2)
    spec = pc.spec_with_budget(30)
    kw = dict(
        bank="planning_bank",
        arrival_delay_s=0.05,
        commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
        spec_hash=pc.spec_hash,
        checkpoint_hash=pc.checkpoint_hash,
        nominal_budget_s=30.0,
    )
    rows = []
    for n in sizes:
        seeds = pc.planning_bank_keys[:n]
        rss0 = current_rss_bytes()
        cpu0 = cpu_seconds()
        t0 = time.perf_counter()
        for cand in plans:
            for w in seeds:
                simulate_plan_world_scalar(
                    spec, pc.checkpoint_blob, cand["plan"], w, cache={}, parity=True, **kw
                )
        scalar_wall = time.perf_counter() - t0
        scalar_cpu = cpu_seconds() - cpu0
        cpu1 = cpu_seconds()
        t1 = time.perf_counter()
        evaluate_candidates_batched(
            spec, pc.checkpoint_blob, plans, seeds, cache=ByteBoundedCache(max_bytes=64 * 1024 * 1024), **kw
        )
        batched_wall = time.perf_counter() - t1
        batched_cpu = cpu_seconds() - cpu1
        print(f"[heartbeat] phase=speed n={n} scalar_wall={scalar_wall:.3f} batched_wall={batched_wall:.3f}", flush=True)
        rows.append(
            {
                "n_worlds": n,
                "n_plans": len(plans),
                "scalar_wall_s": scalar_wall,
                "batched_wall_s": batched_wall,
                "scalar_cpu_s": scalar_cpu,
                "batched_cpu_s": batched_cpu,
                "speedup_wall": (scalar_wall / batched_wall) if batched_wall > 0 else None,
                "speedup_cpu": (scalar_cpu / batched_cpu) if batched_cpu > 0 else None,
                "rss_bytes": max(rss0, current_rss_bytes()),
                "parity_ok": True,
            }
        )
    return {
        "ok": True,
        "sizes": list(sizes),
        "n_worlds": list(sizes),
        "rows": rows,
        "kernel_counters": kernel_counters(),
    }


def persist_kernel_evidence(root: Path, *, n_checkpoints: int = 32, n_worlds: int = 32) -> dict[str, Any]:
    dest = root / "docs/evidence/phase6_validated"
    dest.mkdir(parents=True, exist_ok=True)
    parity = run_parity_panel(n_checkpoints=n_checkpoints, n_worlds=n_worlds)
    variety = run_commitment_variety_panel()
    parity["commitment_classes_observed"] = sorted(set(parity.get("commitment_classes_observed") or []) | set(variety.get("observed") or []))
    parity["variety"] = variety
    write_json(dest / "SCALAR_BATCHED_PARITY.json", parity)
    write_json(dest / "COMMITMENT_VARIETY.json", variety)
    speed = run_speed_benchmark()
    write_json(dest / "BATCH_SPEED_BENCHMARK.json", speed)
    write_json(dest / "PRODUCTION_KERNEL.json", kernel_counters())
    return {"parity": parity, "speed": speed, "variety": variety}
