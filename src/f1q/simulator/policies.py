from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from f1q.errors import RejectionError

PRIVATE_CAR_KEYS = frozenset(
    {
        "fuel_actual",
        "fuel_floor_applied",
        "sampled_future_regime_duration_s",
        "regime_end_s",
        "engine",
        "engine_state",
        "rng",
        "private",
    }
)

PUBLIC_CAR_KEYS = frozenset(
    {
        "car_id",
        "team_id",
        "completed_laps",
        "frac",
        "in_pit",
        "pit_phase",
        "compound",
        "mounted_set_id",
        "tyre_age_laps",
        "inventory",
        "used_compounds",
        "fuel_estimated",
        "fuel_uncertainty_kg",
        "classified_position_init",
        "pit_this_lap",
        "pending_compound",
        "pending_set_id",
        "retired",
        "finish_time",
        "service_wait_s",
        "lap_deficit_init",
    }
)


class SpyCar(dict):
    """Adversarial mapping: accessing a private key fails conspicuously."""

    def __getitem__(self, key):  # type: ignore[override]
        if key in PRIVATE_CAR_KEYS:
            raise AssertionError(f"policy accessed private field {key!r}")
        return super().__getitem__(key)

    def get(self, key, default=None):  # type: ignore[override]
        if key in PRIVATE_CAR_KEYS:
            raise AssertionError(f"policy accessed private field {key!r}")
        return super().get(key, default)

    def __contains__(self, key):  # type: ignore[override]
        if key in PRIVATE_CAR_KEYS:
            raise AssertionError(f"policy accessed private field {key!r}")
        return super().__contains__(key)


def public_car_view(car: Mapping[str, Any], *, spy: bool = False) -> dict[str, Any]:
    view: dict[str, Any] = {}
    for key in PUBLIC_CAR_KEYS:
        if key in car:
            value = car[key]
            if isinstance(value, list):
                view[key] = [dict(item) if isinstance(item, dict) else item for item in value]
            else:
                view[key] = value
    return SpyCar(view) if spy else view


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
    raise RejectionError("NO_LEGAL_TYRE_SET", f"{car['car_id']} has no unused set")


def continuation_intent(car: Mapping[str, Any], *, required_compounds: int, remaining_laps: float) -> dict[str, Any]:
    if remaining_laps <= 1e-9:
        return {"kind": "continuation"}
    if obligation_met(car, required_compounds):
        return {"kind": "continuation"}
    compound, set_id = select_obligation_set(car)
    return {"kind": "pit_now", "compound": compound, "set_id": set_id, "reason": "compound_obligation"}


def delay_to_pit_now(plan: dict[str, Any], *, completed_laps: int) -> dict[str, Any]:
    kind = plan.get("kind")
    if kind == "pit_now":
        return plan
    if kind == "delay_laps":
        delay = int(plan.get("delay_laps") or 0)
        if delay not in {1, 2}:
            raise RejectionError("ILLEGAL_PLAN", "delay_laps must be 1 or 2")
        reference = int(plan.get("reference_completed", completed_laps))
        if completed_laps - reference >= delay:
            return {
                "kind": "pit_now",
                "compound": plan.get("compound"),
                "set_id": plan.get("set_id"),
                "reason": "delay_elapsed",
            }
        return {"kind": "continuation", "reason": "waiting_delay"}
    return {"kind": "continuation"}


def decide_from_observation(
    observation: Any,
    *,
    car_id: str,
    required_compounds: int,
    policy_seed: int = 0,
) -> dict[str, Any]:
    """Baseline policy: DecisionObservation only. policy_seed is recorded and unused (deterministic)."""
    del policy_seed  # reserved; baseline has no private RNG
    if hasattr(observation, "model_dump"):
        data = observation.model_dump(mode="python")
    else:
        data = dict(observation)
    cars = {row["car_id"]: row for row in data.get("cars") or []}
    if car_id not in cars:
        raise RejectionError("ILLEGAL_PLAN", f"unknown car {car_id} in observation")
    row = cars[car_id]
    remaining_q = data.get("remaining_laps") or {}
    remaining = float(remaining_q["value"] if isinstance(remaining_q, dict) else remaining_q.value)
    inventories = data.get("inventories") or {}
    view = public_car_view(
        {
            "car_id": car_id,
            "compound": row.get("compound"),
            "inventory": inventories.get(car_id) or [],
            "used_compounds": row.get("used_compounds") or [row.get("compound")],
            "completed_laps": row.get("completed_laps"),
            "fuel_estimated": row.get("fuel_kg_estimated"),
            "fuel_uncertainty_kg": row.get("fuel_uncertainty_kg"),
            "in_pit": row.get("in_pit_lane"),
            "mounted_set_id": row.get("mounted_set_id"),
            "tyre_age_laps": row.get("tyre_age_laps"),
        },
        spy=True,
    )
    required = int(required_compounds)
    obligations = data.get("compound_obligations") or {}
    if obligations.get("distinct_compounds_required") is not None:
        required = int(obligations["distinct_compounds_required"])
    return continuation_intent(view, required_compounds=required, remaining_laps=remaining)
