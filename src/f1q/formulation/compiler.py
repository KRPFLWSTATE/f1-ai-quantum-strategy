"""Restricted proxy objective compiler (analytical seconds). Independent of the simulator evaluator."""

from __future__ import annotations

from typing import Any

from f1q.formulation.actions import CarAction
from f1q.formulation.boundaries import SpyMapping, reject_private_payload
from f1q.formulation.public_config import PublicPhysicsConfig
from f1q.formulation.versions import COMPILER_VERSION, COEFFICIENT_UNITS, RISK_WEIGHT, TOLERANCE_S
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

    # Discrete remaining whole laps under restricted analytical model.
    n = max(0, int(round(remaining)))
    used = set(car.get("used_compounds") or [])
    used.add(compound)
    obligation_needed = len(used) < int(public.distinct_compounds_required)
    forced_pit_done = False

    for lap in range(n):
        # Apply scheduled stop at the beginning of the designated lap.
        if pit_at is not None and lap == pit_at and action.compound and action.set_id:
            total += pit_loss
            compound = str(action.compound)
            age = 0.0
            used.add(compound)
            obligation_needed = len(used) < int(public.distinct_compounds_required)
            forced_pit_done = True
        elif (
            action.kind == "continuation"
            and obligation_needed
            and not forced_pit_done
            and lap == max(0, n - 2)
        ):
            # Frozen downstream obligation policy: pit two laps before horizon if still unmet.
            inventory = (obs.get("inventories") or {}).get(action.car_id) or []
            choice = None
            for item in inventory:
                if item.get("used"):
                    continue
                if item.get("set_id") == car.get("mounted_set_id"):
                    continue
                if item["compound"] not in used:
                    choice = item
                    break
            if choice is None:
                for item in inventory:
                    if not item.get("used") and item.get("set_id") != car.get("mounted_set_id"):
                        choice = item
                        break
            if choice is not None:
                total += pit_loss
                compound = str(choice["compound"])
                age = 0.0
                used.add(compound)
                obligation_needed = len(used) < int(public.distinct_compounds_required)
                forced_pit_done = True

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
        "pit_loss_applied_s": float(pit_loss if pit_at is not None or forced_pit_done else 0.0),
        "n_laps": n,
        "final_compound": compound,
        "units": COEFFICIENT_UNITS,
    }


def _pair_interaction(
    obs: dict[str, Any],
    public: PublicPhysicsConfig,
    action_a: CarAction,
    action_b: CarAction,
) -> float:
    """Additional shared-crew / rejoin interaction not already in unaries.

    Shared-crew double stacking is a finite delay, not a hard prohibition.
    If both cars pit at the same scheduled lap index, add one service wait once.
    """
    del obs  # pair term uses only action timing + public service constant
    def pit_lap(action: CarAction) -> int | None:
        if action.kind == "pit_now":
            return 0
        if action.kind == "delay_laps":
            return int(action.delay_laps or 0)
        return None

    la, lb = pit_lap(action_a), pit_lap(action_b)
    if la is None or lb is None:
        return 0.0
    if la == lb:
        return float(public.service_stationary_s)
    # Adjacent-lap stack: partial wait (half service) as restricted rejoin interaction.
    if abs(la - lb) == 1:
        return 0.5 * float(public.service_stationary_s)
    return 0.0


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
    for i, a in enumerate(actions1):
        row = []
        for j, b in enumerate(actions2):
            v = _pair_interaction(obs, public, a, b)
            row.append(float(v))
        pair.append(row)

    C = 0.0  # baseline absorbed into unaries; reported for schema completeness
    m1 = min(u1) if u1 else 0.0
    m2 = min(u2) if u2 else 0.0
    u1c = [x - m1 for x in u1]
    u2c = [x - m2 for x in u2]
    Cc = C + m1 + m2

    # Verify centring preserves physical objectives on the legal table.
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
        "assumptions": {
            "fuel_uses_estimated_kg": True,
            "no_private_fuel": True,
            "no_continue_to_finish": True,
            "regime_pit_loss": "green_pit_loss_s / pace_factor",
            "pair_term": "shared_crew_service_wait_on_same_or_adjacent_pit_lap",
            "downstream_policy": "compound_obligation.v1 pit near horizon if unmet",
            "double_counting": "pair excludes unary remaining-time components",
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
