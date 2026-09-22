"""Exact batched continuation kernel for paired world evaluation.

Production evaluation must call ``evaluate_candidates_batched``. The scalar
``_simulate_plan_world`` path is retained only for parity diagnostics.
Causal semantics match ``RaceSimulator.consider_recommendation`` +
``continue_to_finish``; outputs are compared at 1e-12.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from f1q.a4.banks import (
    EVALUATION_BANK,
    PLANNING_BANK,
    apply_hidden_world,
    cache_key,
    forbid_evaluation_payload,
    reject_evaluation_in_planning,
)
from f1q.a4.cache import ByteBoundedCache
from f1q.a4.problem import plan_fingerprint
from f1q.hashing import sha256_json
from f1q.simulator.engine import event_signature
from f1q.simulator.interface import RaceSimulator

PARITY_TOL = 1e-12

_KERNEL_COUNTERS: dict[str, int] = {
    "batched_calls": 0,
    "batched_worlds": 0,
    "scalar_calls": 0,
    "parity_scalar_calls": 0,
}


def reset_kernel_counters() -> None:
    for k in list(_KERNEL_COUNTERS):
        _KERNEL_COUNTERS[k] = 0


def kernel_counters() -> dict[str, int]:
    return dict(_KERNEL_COUNTERS)


def _cache_get(cache: Any, key: str) -> Any | None:
    if cache is None:
        return None
    if isinstance(cache, ByteBoundedCache):
        return cache.get(key)
    return cache.get(key)


def _cache_put(cache: Any, key: str, value: dict[str, Any], *, klass: str = "continuation") -> None:
    if cache is None:
        return
    stored = {k: v for k, v in value.items() if k != "cache_hit"}
    if isinstance(cache, ByteBoundedCache):
        cache.put(key, stored, klass=klass)
    else:
        cache[key] = stored


def _run_committed(
    sim: RaceSimulator,
    plan: dict[str, Any],
    *,
    world_seed: int,
    bank: str,
    ck: str,
    nominal_budget_s: float,
    arrival_delay_s: float,
    common_commit_delay_s: float | None,
    commitment_epoch_race_s: float | None,
) -> dict[str, Any]:
    rec_commit = sim.consider_recommendation(
        plan,
        arrival_delay_s=float(arrival_delay_s),
        common_commit_delay_s=common_commit_delay_s,
        commitment_epoch_race_s=commitment_epoch_race_s,
    )
    _state, outcome = sim.continue_to_finish()
    loss = float(outcome["team_loss"]["normalized_team_rank_loss"])
    is_fb = rec_commit.get("selected_plan") != "recommendation"
    events = []
    if sim.engine is not None:
        events = event_signature(list(sim.engine.state.get("events") or []))
    selected_plan_obj = plan if not is_fb else {"fallback": True}
    rec = {
        "loss": loss,
        "timely": bool(rec_commit.get("timely")),
        "fallback": bool(is_fb),
        "commit": rec_commit.get("selected_plan"),
        "commitment_classification": rec_commit.get("selected_plan"),
        "legality": rec_commit.get("legality"),
        "selected_plan": rec_commit.get("selected_plan"),
        "fallback_plan": rec_commit.get("selected_plan") == "fallback_continuation",
        "event_ordering": events,
        "team_loss": loss,
        "plan_hash": plan_fingerprint(plan),
        "world_seed": int(world_seed),
        "bank": bank,
        "cache_hit": False,
        "evaluator": "simulator.team_rank_loss",
        "not_proxy_qubo": True,
        "trace_id": ck[:16],
        "nominal_budget_s": float(nominal_budget_s),
        "arrival_delay_s": float(arrival_delay_s),
        "registered_commitment_epoch_race_s": rec_commit.get("registered_commitment_epoch_race_s"),
        "late_vs_registered_epoch": rec_commit.get("late_vs_registered_epoch"),
        "late_vs_effective_end": rec_commit.get("late_vs_effective_end"),
        "fallback_reason": rec_commit.get("fallback_reason"),
        "commitment_race_s": rec_commit.get("commitment_race_s"),
        "checkpoint_time_race_s": rec_commit.get("checkpoint_time_race_s"),
        "stale": bool(
            rec_commit.get("fallback_reason") in {"PIT_WINDOW_CLOSED", "EXPIRED_PIT_NOW"}
            or rec_commit.get("late_vs_effective_end")
        ),
        "changed_state": float(rec_commit.get("commitment_race_s") or 0.0)
        > float(rec_commit.get("checkpoint_time_race_s") or 0.0) + 1e-12,
        "selected_or_fallback_plan": selected_plan_obj,
    }
    return rec


def simulate_plan_world_scalar(
    spec: dict[str, Any],
    base_blob: dict[str, Any],
    plan: dict[str, Any],
    world_seed: int,
    *,
    arrival_delay_s: float,
    common_commit_delay_s: float | None = None,
    commitment_epoch_race_s: float | None = None,
    cache: dict[str, Any] | ByteBoundedCache | None = None,
    spec_hash: str,
    checkpoint_hash: str,
    bank: str,
    nominal_budget_s: float,
    parity: bool = False,
) -> dict[str, Any]:
    """Scalar RaceSimulator path. Production campaign must not call this."""
    _KERNEL_COUNTERS["scalar_calls"] += 1
    if parity:
        _KERNEL_COUNTERS["parity_scalar_calls"] += 1
    if bank in {PLANNING_BANK, "offline_planning_bank"}:
        reject_evaluation_in_planning(bank)
    ph = plan_fingerprint(plan)
    epoch = commitment_epoch_race_s
    if epoch is None and common_commit_delay_s is not None:
        epoch = float(common_commit_delay_s)
    ck = cache_key(
        spec_hash=spec_hash,
        checkpoint_hash=checkpoint_hash,
        plan_hash=ph,
        bank=bank,
        world_seed=world_seed,
        nominal_budget_s=float(nominal_budget_s),
        arrival_delay_s=float(arrival_delay_s),
        commitment_epoch_race_s=float(epoch if epoch is not None else nominal_budget_s),
    )
    hit = _cache_get(cache, ck)
    if hit is not None:
        rec = dict(hit)
        rec["cache_hit"] = True
        return rec
    world = RaceSimulator()
    world.restore(copy.deepcopy(base_blob), spec)
    apply_hidden_world(world, world_seed)
    rec = _run_committed(
        world,
        plan,
        world_seed=world_seed,
        bank=bank,
        ck=ck,
        nominal_budget_s=nominal_budget_s,
        arrival_delay_s=arrival_delay_s,
        common_commit_delay_s=common_commit_delay_s,
        commitment_epoch_race_s=commitment_epoch_race_s,
    )
    rec["plan_hash"] = ph
    _cache_put(cache, ck, rec, klass="continuation")
    return rec


def evaluate_candidates_batched(
    spec: dict[str, Any],
    base_blob: dict[str, Any],
    candidates: list[dict[str, Any]],
    world_seeds: list[int],
    *,
    bank: str,
    arrival_delay_s: float,
    common_commit_delay_s: float | None = None,
    commitment_epoch_race_s: float | None = None,
    cache: dict[str, Any] | ByteBoundedCache | None = None,
    spec_hash: str,
    checkpoint_hash: str,
    nominal_budget_s: float,
) -> dict[str, Any]:
    """Production paired-world kernel.

    Restores the checkpoint once per world seed, applies the hidden-world draw,
    snapshots that state, then evaluates every candidate plan from the snapshot.
    Cache hits skip both restore and continuation.
    """
    from f1q.a4.banks import EVALUATION_BANK as _EB  # noqa: F401 — leakage guard import

    _KERNEL_COUNTERS["batched_calls"] += 1
    if bank in {PLANNING_BANK, "offline_planning_bank"}:
        forbid_evaluation_payload({"bank": bank}, path="evaluate_candidates_batched")
        reject_evaluation_in_planning(bank)
    means: dict[str, float] = {}
    worlds: dict[str, list[dict[str, Any]]] = {}
    epoch = commitment_epoch_race_s
    if epoch is None and common_commit_delay_s is not None:
        epoch = float(common_commit_delay_s)
    epoch_f = float(epoch if epoch is not None else nominal_budget_s)

    pending_by_seed: dict[int, list[dict[str, Any]]] = {}
    for cand in candidates:
        ph = cand.get("plan_hash") or plan_fingerprint(cand["plan"])
        recs: list[dict[str, Any] | None] = [None] * len(world_seeds)
        worlds[ph] = recs  # type: ignore[assignment]
        for i, w in enumerate(world_seeds):
            ck = cache_key(
                spec_hash=spec_hash,
                checkpoint_hash=checkpoint_hash,
                plan_hash=ph,
                bank=bank,
                world_seed=int(w),
                nominal_budget_s=float(nominal_budget_s),
                arrival_delay_s=float(arrival_delay_s),
                commitment_epoch_race_s=epoch_f,
            )
            hit = _cache_get(cache, ck)
            if hit is not None:
                rec = dict(hit)
                rec["cache_hit"] = True
                recs[i] = rec
            else:
                pending_by_seed.setdefault(int(w), []).append(
                    {"cand": cand, "ph": ph, "index": i, "ck": ck, "recs": recs}
                )

    engine = RaceSimulator()
    for seed, jobs in pending_by_seed.items():
        engine.restore(copy.deepcopy(base_blob), spec)
        apply_hidden_world(engine, int(seed))
        hidden_blob = engine.serialize()
        for job in jobs:
            engine.restore(copy.deepcopy(hidden_blob), spec)
            rec = _run_committed(
                engine,
                job["cand"]["plan"],
                world_seed=int(seed),
                bank=bank,
                ck=job["ck"],
                nominal_budget_s=nominal_budget_s,
                arrival_delay_s=arrival_delay_s,
                common_commit_delay_s=common_commit_delay_s,
                commitment_epoch_race_s=commitment_epoch_race_s,
            )
            rec["plan_hash"] = job["ph"]
            _KERNEL_COUNTERS["batched_worlds"] += 1
            _cache_put(cache, job["ck"], rec, klass="continuation")
            job["recs"][job["index"]] = rec

    out_worlds: dict[str, list[dict[str, Any]]] = {}
    for ph, recs in worlds.items():
        filled = [r for r in recs if r is not None]
        if len(filled) != len(world_seeds):
            raise RuntimeError(f"batched kernel missing worlds for {ph}: {len(filled)}/{len(world_seeds)}")
        out_worlds[ph] = filled
        losses = [float(r["loss"]) for r in filled]
        means[ph] = float(np.mean(losses)) if losses else float("inf")
    return {"means": means, "worlds": out_worlds, "kernel": "batched"}


def parity_rows(
    spec: dict[str, Any],
    base_blob: dict[str, Any],
    candidates: list[dict[str, Any]],
    world_seeds: list[int],
    *,
    bank: str,
    arrival_delay_s: float,
    commitment_epoch_race_s: float,
    spec_hash: str,
    checkpoint_hash: str,
    nominal_budget_s: float,
) -> dict[str, Any]:
    """Compare scalar vs batched on every cell. Not a production path."""
    scalar_cache: dict[str, Any] = {}
    batched_cache: dict[str, Any] = {}
    scalar_worlds: dict[str, list[dict[str, Any]]] = {}
    for cand in candidates:
        ph = cand.get("plan_hash") or plan_fingerprint(cand["plan"])
        recs = [
            simulate_plan_world_scalar(
                spec,
                base_blob,
                cand["plan"],
                w,
                arrival_delay_s=arrival_delay_s,
                commitment_epoch_race_s=commitment_epoch_race_s,
                cache=scalar_cache,
                spec_hash=spec_hash,
                checkpoint_hash=checkpoint_hash,
                bank=bank,
                nominal_budget_s=nominal_budget_s,
                parity=True,
            )
            for w in world_seeds
        ]
        scalar_worlds[ph] = recs
    batched = evaluate_candidates_batched(
        spec,
        base_blob,
        candidates,
        world_seeds,
        bank=bank,
        arrival_delay_s=arrival_delay_s,
        commitment_epoch_race_s=commitment_epoch_race_s,
        cache=batched_cache,
        spec_hash=spec_hash,
        checkpoint_hash=checkpoint_hash,
        nominal_budget_s=nominal_budget_s,
    )
    rows = []
    ok = True
    for cand in candidates:
        ph = cand.get("plan_hash") or plan_fingerprint(cand["plan"])
        for i, w in enumerate(world_seeds):
            s = scalar_worlds[ph][i]
            b = batched["worlds"][ph][i]
            cell_ok = (
                s.get("commitment_classification") == b.get("commitment_classification")
                and s.get("selected_plan") == b.get("selected_plan")
                and bool(s.get("fallback")) == bool(b.get("fallback"))
                and s.get("legality") == b.get("legality")
                and s.get("event_ordering") == b.get("event_ordering")
                and abs(float(s["loss"]) - float(b["loss"])) <= PARITY_TOL
            )
            ok = ok and cell_ok
            rows.append(
                {
                    "plan_hash": ph,
                    "world_seed": int(w),
                    "ok": cell_ok,
                    "scalar_loss": s["loss"],
                    "batched_loss": b["loss"],
                    "scalar_commit": s.get("commitment_classification"),
                    "batched_commit": b.get("commitment_classification"),
                    "scalar_legality": s.get("legality"),
                    "batched_legality": b.get("legality"),
                    "event_ordering_equal": s.get("event_ordering") == b.get("event_ordering"),
                }
            )
    return {
        "ok": ok,
        "n_cells": len(rows),
        "rows": rows,
        "rows_hash": sha256_json(rows),
        "tolerance": PARITY_TOL,
        "kernel": "batched",
    }
