"""Restricted proxy objective compiler (analytical seconds). Independent of the simulator evaluator."""

from __future__ import annotations

from typing import Any

from f1q.formulation.actions import CarAction
from f1q.formulation.boundaries import SpyMapping, reject_private_payload
from f1q.formulation.downstream_policy import normalize_stop_record
from f1q.formulation.public_config import PublicPhysicsConfig
from f1q.formulation.versions import (
    COMPILER_VERSION,
    COEFFICIENT_UNITS,
    DOWNSTREAM_POLICY_ID,
    DOWNSTREAM_POLICY_VERSION,
    PAIR_ARRIVAL_TOLERANCE_S,
    RISK_WEIGHT,
    TOLERANCE_S,
)
from f1q.hashing import sha256_json
from f1q.schemas import reject_non_finite

# Explicit architectural note: this module must not import the evaluator or engine.
_SEPARATION_GUARD = True


def _qty_value(q: Any) -> Any:
    if isinstance(q, dict) and "value" in q:
        return q["value"]
    return q


def _obs_dict(observation: Any) -> dict[str, Any]:
    if hasattr(observation, "model_dump"):
        data = observation.model_dump(mode="python")
    else:
        data = dict(observation)
    reject_private_payload(data)
    reject_non_finite(data)
    return SpyMapping(data)


def _car_row(obs: dict[str, Any], car_id: str) -> dict[str, Any]:
    for row in obs["cars"]:
        if row["car_id"] == car_id:
            return row
    raise KeyError(car_id)


def _lap_time(
    public: PublicPhysicsConfig,
    *,
    compound: str,
    age_laps: float,
    fuel_kg: float,
    regime: str | None,
) -> float:
    offset = float(public.compound_offset_s[compound])
    linear = float(public.tyre_wear_per_lap) * float(public.time_scale_s) * float(age_laps)
    if public.tyre_form == "near_linear":
        tyre = linear
    else:
        tyre = linear + float(public.tyre_curvature or 0.0) * float(public.curve_scale_s) * float(age_laps) ** 2
    fuel = float(public.time_per_kg_s) * float(fuel_kg)
    base = float(public.green_lap_s) + offset + tyre + fuel
    return base * public.regime_pace_factor(regime)


def _select_obligation_inventory(car: dict[str, Any], inventory: list[dict[str, Any]], used: set[str]) -> dict[str, Any] | None:
    for item in inventory:
        if item.get("used"):
            continue
        if item.get("set_id") == car.get("mounted_set_id"):
            continue
        if item["compound"] not in used:
            return item
    for item in inventory:
        if not item.get("used") and item.get("set_id") != car.get("mounted_set_id"):
            return item
    return None


def _simulate_unary(
    obs: dict[str, Any],
    public: PublicPhysicsConfig,
    action: CarAction,
) -> dict[str, Any]:
    car = _car_row(obs, action.car_id)
    remaining = float(_qty_value(obs["remaining_laps"]))
    regime_q = obs.get("safety_regime")
    regime = _qty_value(regime_q) if regime_q is not None else None
    if isinstance(regime, dict):
        regime = regime.get("value")
    compound = car["compound"]
    age = float(car["tyre_age_laps"])
    fuel = float(car["fuel_kg_estimated"])
    total = 0.0
    pit_loss = public.effective_pit_loss_s(regime if isinstance(regime, str) else None)
    pit_at: int | None = None
    if action.kind == "pit_now":
        pit_at = 0
    elif action.kind == "delay_laps":
        pit_at = int(action.delay_laps or 0)

    n = max(0, int(round(remaining)))
    used = set(car.get("used_compounds") or [])
    used.add(compound)
    obligation_needed = len(used) < int(public.distinct_compounds_required)
    forced_pit_done = False
    planned_stops: list[dict[str, Any]] = []
    inventory = (obs.get("inventories") or {}).get(action.car_id) or []

    # Continuation under compound_obligation.v1@1.1.0: immediate alternate stop when unmet
    # (matches simulator continuation_intent / continuation_stop_intent).
    if action.kind == "continuation" and obligation_needed and not car.get("in_pit_lane"):
        choice = _select_obligation_inventory(car, inventory, used)
        if choice is not None:
            pit_at = 0
            action_compound = str(choice["compound"])
            action_set = str(choice["set_id"])
        else:
            action_compound = None
            action_set = None
    else:
        action_compound = action.compound
        action_set = action.set_id

    for lap in range(n):
        if pit_at is not None and lap == pit_at and action_compound and action_set and not forced_pit_done:
            total += pit_loss
            compound = str(action_compound)
            age = 0.0
            used.add(compound)
            obligation_needed = len(used) < int(public.distinct_compounds_required)
            forced_pit_done = True
            planned_stops.append(
                normalize_stop_record(
                    car_id=action.car_id,
                    source="compiler",
                    kind="pit",
                    compound=compound,
                    set_id=action_set,
                    pit_lap_index=lap,
                    reason=(
                        "compound_obligation"
                        if action.kind == "continuation"
                        else action.kind
                    ),
                )
            )

        lt = _lap_time(
            public,
            compound=compound,
            age_laps=age,
            fuel_kg=fuel,
            regime=regime if isinstance(regime, str) else None,
        )
        total += lt
        age += 1.0
        fuel = max(0.0, fuel - float(public.kg_per_lap))
    return {
        "unary_s": float(total),
        "pit_loss_applied_s": float(pit_loss if forced_pit_done or (pit_at is not None and action.kind != "continuation") else 0.0),
        "n_laps": n,
        "final_compound": compound,
        "planned_stops": planned_stops,
        "units": COEFFICIENT_UNITS,
    }


def predicted_box_arrival_s(
    obs: dict[str, Any],
    public: PublicPhysicsConfig,
    action: CarAction,
) -> float | None:
    """Predict box-arrival race-seconds from public observables (restricted model).

    Units: seconds from the decision checkpoint. Uses current estimated lap time and
    public pit_entry_frac. Returns None when the action has no scheduled stop.
    """
    car = _car_row(obs, action.car_id)
    if action.kind == "continuation":
        # Obligation continuation may schedule an immediate stop; treat as pit_now for timing.
        used = set(car.get("used_compounds") or [])
        used.add(car["compound"])
        if len(used) >= int(public.distinct_compounds_required) or car.get("in_pit_lane"):
            return None
        delay = 0
    elif action.kind == "pit_now":
        delay = 0
    elif action.kind == "delay_laps":
        delay = int(action.delay_laps or 0)
    else:
        return None

    regime_q = obs.get("safety_regime")
    regime = _qty_value(regime_q) if regime_q is not None else None
    if isinstance(regime, dict):
        regime = regime.get("value")
    lt = _lap_time(
        public,
        compound=car["compound"],
        age_laps=float(car["tyre_age_laps"]),
        fuel_kg=float(car["fuel_kg_estimated"]),
        regime=regime if isinstance(regime, str) else None,
    )
    frac = float(car.get("frac") or 0.0)
    entry = float(public.pit_entry_frac)
    # Time to complete current lap to entry, then delay whole laps, then to entry frac.
    if delay == 0:
        if frac <= entry + 1e-12:
            return (entry - frac) * lt
        # Past entry: cannot pit this lap under admission rules; treat as unreachable.
        return None
    # delay >= 1: finish current lap, then (delay-1) full laps, then to entry.
    to_sf = (1.0 - frac) * lt
    return to_sf + float(delay - 1) * lt + entry * lt


def service_interval_overlap_wait_s(
    arrival_a: float,
    arrival_b: float,
    *,
    service_s: float,
) -> float:
    """Shared-crew wait: later car waits until earlier service completes, if overlapping.

    Intervals are [arrival, arrival + service_s]. Wait equals
    max(0, earlier_end - later_arrival). Same nominal pit lap is not automatically
    a full service wait unless arrivals overlap under this calculation.
    Adjacent-lap schedules with non-overlapping intervals yield zero.
    """
    if arrival_a <= arrival_b:
        earlier, later = arrival_a, arrival_b
    else:
        earlier, later = arrival_b, arrival_a
    earlier_end = earlier + float(service_s)
    return float(max(0.0, earlier_end - later))


def _pair_interaction(
    obs: dict[str, Any],
    public: PublicPhysicsConfig,
    action_a: CarAction,
    action_b: CarAction,
) -> dict[str, Any]:
    """Derived shared-crew wait from predicted box-arrival intervals, or zero if unknown."""
    arr_a = predicted_box_arrival_s(obs, public, action_a)
    arr_b = predicted_box_arrival_s(obs, public, action_b)
    service = float(public.service_stationary_s)
    if arr_a is None or arr_b is None:
        return {
            "pair_s": 0.0,
            "reason": "insufficient_public_timing_or_no_scheduled_stop",
            "arrival_a_s": arr_a,
            "arrival_b_s": arr_b,
            "service_stationary_s": service,
            "equation": "wait = max(0, min_arrival + service - max_arrival); zero if either arrival unknown",
        }
    wait = service_interval_overlap_wait_s(arr_a, arr_b, service_s=service)
    if wait <= PAIR_ARRIVAL_TOLERANCE_S:
        wait = 0.0
    return {
        "pair_s": float(wait),
        "reason": "service_interval_overlap" if wait > 0 else "no_overlap",
        "arrival_a_s": arr_a,
        "arrival_b_s": arr_b,
        "service_stationary_s": service,
        "equation": "wait = max(0, earlier_arrival + service_stationary_s - later_arrival)",
        "units": "seconds",
        "no_double_counting": "unary costs exclude shared-crew wait; pair adds wait once",
        "adjacent_lap_arbitrary_half_service": False,
    }


def compile_action_costs(
    observation: Any,
    public: PublicPhysicsConfig,
    *,
    menus: dict[str, list[dict[str, Any]]] | list[CarAction],
    selected_car_ids: list[str],
) -> dict[str, Any]:
    """Build uncentred/centred unary and pair tables. Does not call continue_to_finish."""
    if RISK_WEIGHT != 0.0:
        raise ValueError("Stage 4 risk weight must remain exactly zero")
    obs = _obs_dict(observation)
    car1, car2 = selected_car_ids
    actions1 = [_as_action(a, car1) for a in _menu_list(menus, car1)]
    actions2 = [_as_action(a, car2) for a in _menu_list(menus, car2)]
    actions1.sort(key=lambda a: a.action_id)
    actions2.sort(key=lambda a: a.action_id)

    u1 = []
    u2 = []
    details1 = []
    details2 = []
    for a in actions1:
        d = _simulate_unary(obs, public, a)
        u1.append(d["unary_s"])
        details1.append({"action_id": a.action_id, **d})
    for b in actions2:
        d = _simulate_unary(obs, public, b)
        u2.append(d["unary_s"])
        details2.append({"action_id": b.action_id, **d})

    pair = []
    pair_details = []
    for i, a in enumerate(actions1):
        row = []
        detail_row = []
        for j, b in enumerate(actions2):
            info = _pair_interaction(obs, public, a, b)
            row.append(float(info["pair_s"]))
            detail_row.append(info)
        pair.append(row)
        pair_details.append(detail_row)

    C = 0.0
    m1 = min(u1) if u1 else 0.0
    m2 = min(u2) if u2 else 0.0
    u1c = [x - m1 for x in u1]
    u2c = [x - m2 for x in u2]
    Cc = C + m1 + m2

    for i in range(len(u1)):
        for j in range(len(u2)):
            raw = C + u1[i] + u2[j] + pair[i][j]
            cen = Cc + u1c[i] + u2c[j] + pair[i][j]
            if abs(raw - cen) > TOLERANCE_S:
                raise AssertionError("centring changed physical objective")

    record = {
        "compiler_version": COMPILER_VERSION,
        "units": COEFFICIENT_UNITS,
        "risk_weight": RISK_WEIGHT,
        "downstream_policy_id": DOWNSTREAM_POLICY_ID,
        "downstream_policy_version": DOWNSTREAM_POLICY_VERSION,
        "assumptions": {
            "fuel_uses_estimated_kg": True,
            "no_private_fuel": True,
            "no_continue_to_finish": True,
            "regime_pit_loss": "green_pit_loss_s / pace_factor",
            "pair_term": "shared_crew_service_interval_overlap_from_predicted_box_arrival",
            "pair_zero_when": "either arrival unknown or intervals do not overlap",
            "downstream_policy": f"{DOWNSTREAM_POLICY_ID}@{DOWNSTREAM_POLICY_VERSION} immediate alternate stop on continuation when unmet",
            "one_solver_visible_stop": True,
            "double_counting": "pair excludes unary remaining-time components; wait charged once",
        },
        "selected_car_ids": list(selected_car_ids),
        "action_ids": {
            car1: [a.action_id for a in actions1],
            car2: [a.action_id for a in actions2],
        },
        "C": C,
        "u1": u1,
        "u2": u2,
        "v": pair,
        "pair_details": pair_details,
        "m1": m1,
        "m2": m2,
        "C_centered": Cc,
        "u1_centered": u1c,
        "u2_centered": u2c,
        "unary_details": {car1: details1, car2: details2},
        "tolerance_s": TOLERANCE_S,
    }
    record["coefficient_hash"] = sha256_json(
        {
            "C": C,
            "u1": u1,
            "u2": u2,
            "v": pair,
            "C_centered": Cc,
            "u1_centered": u1c,
            "u2_centered": u2c,
            "action_ids": record["action_ids"],
        }
    )
    return record


def score_joint_direct(
    costs: dict[str, Any],
    *,
    index_a: int,
    index_b: int,
    centred: bool = False,
) -> float:
    """Direct legal-plan scorer from the action-cost table. Does not import QUBO."""
    if centred:
        return float(costs["C_centered"] + costs["u1_centered"][index_a] + costs["u2_centered"][index_b] + costs["v"][index_a][index_b])
    return float(costs["C"] + costs["u1"][index_a] + costs["u2"][index_b] + costs["v"][index_a][index_b])


def _menu_list(menus: Any, car_id: str) -> list[Any]:
    if isinstance(menus, dict):
        return list(menus[car_id])
    return [a for a in menus if (a["car_id"] if isinstance(a, dict) else a.car_id) == car_id]


def _as_action(obj: Any, car_id: str) -> CarAction:
    if isinstance(obj, CarAction):
        return obj
    data = dict(obj)
    data.setdefault("car_id", car_id)
    return CarAction.model_validate(data)
