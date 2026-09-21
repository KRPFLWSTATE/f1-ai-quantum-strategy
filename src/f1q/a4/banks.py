"""Planning vs evaluation banks. Disjoint, committed before outcomes, fail-closed leakage."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from f1q.hashing import sha256_json
from f1q.simulator.interface import RaceSimulator

PLANNING_BANK = "planning_bank"
EVALUATION_BANK = "evaluation_bank"
OFFLINE_PLANNING_BANK = "offline_planning_bank"
OFFLINE_EVALUATION_BANK = "offline_evaluation_bank"


def stream_seed(key: str, domain: str) -> int:
    h = hashlib.sha256(f"a4.{domain}:{key}".encode()).hexdigest()
    return int(h[:16], 16) % (2**31 - 1)


def bank_world_seeds(block_id: str, regime: str, bank: str, n: int) -> list[int]:
    return [stream_seed(f"{bank}:{block_id}:{regime}:{i}", bank) for i in range(n)]


def banks_disjoint(planning: list[int], evaluation: list[int]) -> bool:
    return set(planning).isdisjoint(set(evaluation))


def apply_hidden_world(sim: RaceSimulator, world_seed: int) -> dict[str, Any]:
    """Event-keyed CRN on supported hidden-future mechanisms.

    Varied: sampled_future_regime_duration_s / regime_end_s.
    Not independently varied (simulator has no per-world RNG for them): traffic density
    (a spec family factor) and service duration (deterministic from pit parts + crew wait).
    """
    eng = sim.engine
    assert eng is not None
    rng = np.random.default_rng(world_seed)
    extra = float(rng.uniform(-4.0, 18.0))
    base = float(eng.state.get("sampled_future_regime_duration_s") or 8.0)
    eng.state["sampled_future_regime_duration_s"] = max(1.5, base + extra)
    t = float(eng.state["t"])
    if eng.state.get("regime") in {"SC", "VSC"}:
        eng.state["regime_end_s"] = t + float(eng.state["sampled_future_regime_duration_s"])
    return {
        "varied": ["sampled_future_regime_duration_s", "regime_end_s"],
        "not_varied": [
            "traffic_density_is_spec_family_factor",
            "service_duration_deterministic_from_pit_parts_and_crew_wait",
        ],
        "world_seed": int(world_seed),
    }


def cache_key(
    *,
    spec_hash: str,
    checkpoint_hash: str,
    plan_hash: str,
    bank: str,
    world_seed: int,
) -> str:
    return sha256_json(
        {
            "spec_hash": spec_hash,
            "checkpoint_hash": checkpoint_hash,
            "plan_hash": plan_hash,
            "bank": bank,
            "world_seed": int(world_seed),
        }
    )


def reject_evaluation_in_planning(bank: str) -> None:
    from f1q.errors import RejectionError

    if bank in {EVALUATION_BANK, OFFLINE_EVALUATION_BANK, "calibration_outcomes", "final_test"}:
        raise RejectionError("BANK_LEAKAGE", f"planning path cannot use {bank}")
