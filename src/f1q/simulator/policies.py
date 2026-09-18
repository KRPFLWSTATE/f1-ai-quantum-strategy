from __future__ import annotations

from typing import Any

from f1q.errors import RejectionError


def compounds_used(car: dict[str, Any]) -> set[str]:
    used = {car["compound"]}
    for item in car.get("inventory") or []:
        if item.get("used"):
            used.add(item["compound"])
    used.update(car.get("used_compounds") or [])
    return set(used)


def obligation_met(car: dict[str, Any], required: int) -> bool:
    return len(compounds_used(car)) >= int(required)


def select_obligation_set(car: dict[str, Any]) -> tuple[str, str]:
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


def continuation_intent(car: dict[str, Any], *, required_compounds: int, remaining_laps: float) -> dict[str, Any]:
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
