"""Authoritative Stage 4.1 downstream-policy semantics (versioned, shared).

Frozen means a versioned deterministic policy shared by the action generator,
compiler, simulator adapter/engine, evaluator, and tests — not an undocumented
behaviour change between modules.

Stage 4.1 supported action language is intentionally limited to **one**
solver-visible future stop (`pit_now` / `delay_laps` / `continuation`).
Therefore:

- Same-compound pit/delay while the two-compound obligation is unmet is
  **rejected** at admission (the plan cannot promise a second alternate stop).
- `continuation` always invokes this policy: if the obligation is unmet and
  remaining horizon permits, schedule an alternate-compound `pit_now`; otherwise
  stay out.
- After a one-shot pit/delay is consumed at pit entry, the stored policy becomes
  `continuation`, which re-invokes this policy on subsequent intent updates
  (not an inert permanent stay-out).
- In-pit continuation preserves the already-committed service target; it does
  not invent an unrelated extra stop.
- Applying a new on-track plan clears stale `pit_this_lap` / pending fields
  atomically; continuing an in-progress service preserves the active commitment.

Normalized stop records use the schema in `normalize_stop_record`.

This module must not import the simulator package (avoids formulation↔simulator
import cycles). Helpers here are intentionally duplicated with
`f1q.simulator.policies` and kept in lockstep by tests.
"""

from __future__ import annotations

from typing import Any, Mapping

from f1q.errors import RejectionError
from f1q.formulation.versions import DOWNSTREAM_POLICY_ID, DOWNSTREAM_POLICY_VERSION

POLICY_SPEC = {
    "policy_id": DOWNSTREAM_POLICY_ID,
    "policy_version": DOWNSTREAM_POLICY_VERSION,
    "one_solver_visible_stop": True,
    "same_compound_while_unmet": "rejected_at_admission",
    "continuation": "invoke_obligation_alternate_compound_pit_when_unmet",
    "post_one_shot": "store_continuation_then_reinvoke_policy",
    "in_pit_continuation": "preserve_committed_service_target",
}


def compounds_used(car: Mapping[str, Any]) -> set[str]:
    used = {car["compound"]}
    for item in car.get("inventory") or []:
        if item.get("used"):
            used.add(item["compound"])
    used.update(car.get("used_compounds") or [])
    return set(used)


def obligation_met(car: Mapping[str, Any], required: int) -> bool:
    return len(compounds_used(car)) >= int(required)


def select_obligation_set(car: Mapping[str, Any]) -> tuple[str, str]:
    used = compounds_used(car)
    for item in car["inventory"]:
        if item["used"]:
            continue
        if item["compound"] not in used:
            return item["compound"], item["set_id"]
    for item in car["inventory"]:
        if not item["used"]:
            return item["compound"], item["set_id"]
    raise RejectionError("NO_LEGAL_TYRE_SET", f"{car.get('car_id', '?')} has no unused set")


def normalize_stop_record(
    *,
    car_id: str,
    source: str,
    kind: str,
    compound: str | None,
    set_id: str | None,
    pit_lap_index: int | None,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "car_id": car_id,
        "source": source,
        "kind": kind,
        "compound": compound,
        "set_id": set_id,
        "pit_lap_index": pit_lap_index,
        "reason": reason,
        "downstream_policy_id": DOWNSTREAM_POLICY_ID,
        "downstream_policy_version": DOWNSTREAM_POLICY_VERSION,
    }


def continuation_stop_intent(
    car_view: dict[str, Any],
    *,
    required_compounds: int,
    remaining_laps: float,
) -> dict[str, Any]:
    """Executable continuation under compound_obligation.v1 / 1.1.0."""
    if remaining_laps <= 1e-9:
        return {"kind": "continuation", "reason": "horizon_exhausted"}
    if obligation_met(car_view, required_compounds):
        return {"kind": "continuation", "reason": "obligation_met"}
    compound, set_id = select_obligation_set(car_view)
    return {
        "kind": "pit_now",
        "compound": compound,
        "set_id": set_id,
        "reason": "compound_obligation",
        "downstream_policy_id": DOWNSTREAM_POLICY_ID,
        "downstream_policy_version": DOWNSTREAM_POLICY_VERSION,
    }


def compounds_after_mount(car: dict[str, Any], inventory: list[dict[str, Any]], after: str | None) -> set[str]:
    used = compounds_used(
        {
            "compound": car["compound"],
            "used_compounds": car.get("used_compounds") or [],
            "inventory": inventory,
        }
    )
    if after is not None:
        used = set(used)
        used.add(after)
    return used
