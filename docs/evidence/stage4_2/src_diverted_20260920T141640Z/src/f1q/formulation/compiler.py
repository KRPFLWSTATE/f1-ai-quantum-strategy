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
    residual_components: dict[str, Any] | None = None
    action_compound = action.compound
    action_set = action.set_id

    commitment = car.get("committed_pit_service")
    # In-pit continuation: residual committed stop from the decision instant (not zero, not a full new stop).
    if action.kind == "continuation" and car.get("in_pit_lane") and commitment:
        residual = float(commitment["residual_pit_time_s"])
        total += residual
        compound = str(commitment["target_compound"])
        action_compound = compound
        action_set = str(commitment["set_id"])
        already_done = bool(
            commitment.get("service_already_completed") or commitment.get("pit_phase") == "transit_out"
        )
        if already_done:
            # Preserve already-mounted compound/set and current tyre age; residual is exit only.
            age = float(car["tyre_age_laps"])
            used.add(compound)
            obligation_needed = len(used) < int(public.distinct_compounds_required)
            forced_pit_done = True
            residual_components = {
                "remaining_current_phase_s": commitment["remaining_current_phase_s"],
                "remaining_wait_s": 0.0,
                "remaining_service_s": 0.0,
                "remaining_transit_out_s": commitment["remaining_transit_out_s"],
                "residual_pit_time_s": residual,
                "units": "seconds",
                "no_elapsed_double_charge": True,
                "pit_phase_at_decision": commitment["pit_phase"],
                "service_already_completed": True,
                "age_reset": False,
                "expect_new_service_complete": False,
            }
            planned_stops.append(
                normalize_stop_record(
                    car_id=action.car_id,
                    source="service_already_completed",
                    kind="transit_out",
                    compound=compound,
                    set_id=action_set,
                    pit_lap_index=commitment.get("pit_entry_completed_laps"),
                    reason="service_already_completed_residual_exit",
                )
            )
        else:
            age = 0.0
            used.add(compound)
            obligation_needed = len(used) < int(public.distinct_compounds_required)
            forced_pit_done = True
            residual_components = {
                "remaining_current_phase_s": commitment["remaining_current_phase_s"],
                "remaining_wait_s": commitment["remaining_wait_s"],
                "remaining_service_s": commitment["remaining_service_s"],
                "remaining_transit_out_s": commitment["remaining_transit_out_s"],
                "residual_pit_time_s": residual,
                "units": "seconds",
                "no_elapsed_double_charge": True,
                "pit_phase_at_decision": commitment["pit_phase"],
                "service_already_completed": False,
                "age_reset": True,
                "expect_new_service_complete": True,
            }
            planned_stops.append(
                normalize_stop_record(
                    car_id=action.car_id,
                    source="in_progress_commitment",
                    kind="pit",
                    compound=compound,
                    set_id=action_set,
                    pit_lap_index=commitment.get("pit_entry_completed_laps"),
                    reason="in_progress_commitment",
                )
            )
    elif action.kind == "continuation" and obligation_needed and not car.get("in_pit_lane"):
        # Continuation under compound_obligation.v1: immediate alternate stop when unmet.
        choice = _select_obligation_inventory(car, inventory, used)
        if choice is not None:
            pit_at = 0
            action_compound = str(choice["compound"])
            action_set = str(choice["set_id"])
        else:
            action_compound = None
            action_set = None

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
    pit_loss_applied = 0.0
    if residual_components is not None:
        pit_loss_applied = float(residual_components["residual_pit_time_s"])
    elif forced_pit_done or (pit_at is not None and action.kind != "continuation"):
        pit_loss_applied = float(pit_loss)
    return {
        "unary_s": float(total),
        "pit_loss_applied_s": pit_loss_applied,
        "n_laps": n,
        "final_compound": compound,
        "planned_stops": planned_stops,
        "residual_in_pit_components": residual_components,
        "units": COEFFICIENT_UNITS,
    }


def service_interval_from_commitment(commitment: dict[str, Any] | None) -> tuple[float, float] | None:
    """Return [service_start, service_end] absolute race-seconds, or None."""
    if not commitment:
        return None
    if commitment.get("service_already_completed") or commitment.get("pit_phase") == "transit_out":
        return None
    t0 = float(commitment["decision_time_race_s"])
    phase = commitment["pit_phase"]
    remain_phase = float(commitment["remaining_current_phase_s"])
    remain_wait = float(commitment["remaining_wait_s"])
    remain_service = float(commitment["remaining_service_s"])
    if phase == "service":
        start = 0.0
        end = remain_service
    elif phase == "waiting":
        start = remain_wait
        end = remain_wait + remain_service
    else:
        start = remain_phase + remain_wait
        end = start + remain_service
    return (t0 + start, t0 + end)


def _public_pit_parts(obs: dict[str, Any]) -> dict[str, float] | None:
    lane = obs.get("pit_lane") or {}
    parts = lane.get("public_pit_parts_s")
    if not isinstance(parts, dict):
        return None
    if parts.get("t_in_s") is None or parts.get("t_service_s") is None:
        return None
    return {
        "t_in_s": float(parts["t_in_s"]),
        "t_service_s": float(parts["t_service_s"]),
        "t_out_s": float(parts.get("t_out_s") or 0.0),
    }


def _decision_time_s(obs: dict[str, Any]) -> float:
    dt = obs.get("decision_time")
    if isinstance(dt, dict) and "value" in dt:
        return float(dt["value"])
    if dt is not None:
        try:
            return float(dt)
        except (TypeError, ValueError):
            pass
    return 0.0


def time_to_pit_entry_s(
    obs: dict[str, Any],
    public: PublicPhysicsConfig,
    action: CarAction,
) -> float | None:
    """On-track seconds from decision to pit-entry frac (not service start)."""
    car = _car_row(obs, action.car_id)
    if action.kind == "continuation":
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
    if car.get("in_pit_lane"):
        return None
    if car.get("frac") is None:
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
    frac = float(car["frac"])
    entry = float(public.pit_entry_frac)
    if delay == 0:
        if frac <= entry + 1e-12:
            return (entry - frac) * lt
        return None
    to_sf = (1.0 - frac) * lt
    return to_sf + float(delay - 1) * lt + entry * lt


def predicted_service_interval(
    obs: dict[str, Any],
    public: PublicPhysicsConfig,
    action: CarAction,
) -> dict[str, Any]:
    """One declared coordinate: absolute [service_start, service_end] race-seconds.

    On-track arrivals add public entry-to-box transit (t_in_s) after pit entry.
    In-pit actions use remaining service duration from the commitment.
    Committed wait already counted in unary residual is reported separately so
    pair interaction adds only incremental shared-crew wait.
    """
    car = _car_row(obs, action.car_id)
    commitment = car.get("committed_pit_service")
    t0 = _decision_time_s(obs)
    service = float(public.service_stationary_s)
    parts = _public_pit_parts(obs)

    if action.kind == "continuation" and car.get("in_pit_lane") and commitment:
        interval = service_interval_from_commitment(commitment)
        if interval is None:
            return {
                "ok": True,
                "interval": None,
                "reason": "service_already_completed_or_no_remaining_service",
                "committed_wait_already_counted_s": float(commitment.get("remaining_wait_s") or 0.0),
            }
        return {
            "ok": True,
            "interval": list(interval),
            "reason": "committed_remaining_service",
            "committed_wait_already_counted_s": float(commitment.get("remaining_wait_s") or 0.0),
            "coordinate": "service_interval_absolute_race_s",
        }

    entry_rel = time_to_pit_entry_s(obs, public, action)
    if entry_rel is None:
        return {
            "ok": True,
            "interval": None,
            "reason": "no_scheduled_stop_or_in_pit_without_commitment",
            "committed_wait_already_counted_s": 0.0,
        }
    if parts is None:
        return {
            "ok": False,
            "interval": None,
            "reason": "public_entry_to_box_transit_absent",
            "limitation": "obs.pit_lane.public_pit_parts_s.t_in_s required; not inventing a coefficient",
            "committed_wait_already_counted_s": 0.0,
            "time_to_pit_entry_s": entry_rel,
        }
    t_in = float(parts["t_in_s"])
    start = t0 + float(entry_rel) + t_in
    end = start + float(parts.get("t_service_s") or service)
    return {
        "ok": True,
        "interval": [start, end],
        "reason": "on_track_entry_plus_public_t_in",
        "time_to_pit_entry_s": entry_rel,
        "t_in_s": t_in,
        "committed_wait_already_counted_s": 0.0,
        "coordinate": "service_interval_absolute_race_s",
    }


def predicted_box_arrival_s(
    obs: dict[str, Any],
    public: PublicPhysicsConfig,
    action: CarAction,
) -> float | None:
    """Deprecated alias: relative seconds from decision to service start (same coordinate)."""
    pred = predicted_service_interval(obs, public, action)
    interval = pred.get("interval")
    if not interval:
        return None
    return float(interval[0] - _decision_time_s(obs))


def service_interval_overlap_wait_s(
    arrival_a: float,
    arrival_b: float,
    *,
    service_s: float,
) -> float:
    """Shared-crew wait: later car waits until earlier service completes, if overlapping."""
    if arrival_a <= arrival_b:
        earlier, later = arrival_a, arrival_b
    else:
        earlier, later = arrival_b, arrival_a
    earlier_end = earlier + float(service_s)
    return float(max(0.0, earlier_end - later))


def _incremental_pair_wait(
    interval_a: list[float] | tuple[float, float],
    interval_b: list[float] | tuple[float, float],
    *,
    committed_wait_a: float,
    committed_wait_b: float,
) -> tuple[float, str]:
    """Overlap wait minus wait already counted in unary residuals."""
    a0, a1 = float(interval_a[0]), float(interval_a[1])
    b0, b1 = float(interval_b[0]), float(interval_b[1])
    if a0 <= b0:
        raw = max(0.0, a1 - b0)
    else:
        raw = max(0.0, b1 - a0)
    # Own committed waits are already in unary residual; pair adds only incremental overlap.
    already = float(committed_wait_a) + float(committed_wait_b)
    incr = max(0.0, raw - already)
    return incr, "incremental_overlap_minus_committed_wait"


def _pair_interaction(
    obs: dict[str, Any],
    public: PublicPhysicsConfig,
    action_a: CarAction,
    action_b: CarAction,
) -> dict[str, Any]:
    """Derived shared-crew wait from one service-interval coordinate, or zero if unknown."""
    service = float(public.service_stationary_s)
    pred_a = predicted_service_interval(obs, public, action_a)
    pred_b = predicted_service_interval(obs, public, action_b)
    if not pred_a.get("ok") or not pred_b.get("ok"):
        return {
            "pair_s": 0.0,
            "reason": "public_timing_limitation",
            "limitation": pred_a.get("limitation") or pred_b.get("limitation"),
            "pred_a": pred_a,
            "pred_b": pred_b,
            "service_stationary_s": service,
            "adjacent_lap_arbitrary_half_service": False,
            "deterministic_proxy_not_full_race_prediction": True,
        }
    abs_a = pred_a.get("interval")
    abs_b = pred_b.get("interval")
    if abs_a is None or abs_b is None:
        return {
            "pair_s": 0.0,
            "reason": "insufficient_public_timing_or_no_scheduled_stop",
            "pred_a": pred_a,
            "pred_b": pred_b,
            "service_stationary_s": service,
            "adjacent_lap_arbitrary_half_service": False,
            "deterministic_proxy_not_full_race_prediction": True,
        }
    wait, wait_reason = _incremental_pair_wait(
        abs_a,
        abs_b,
        committed_wait_a=float(pred_a.get("committed_wait_already_counted_s") or 0.0),
        committed_wait_b=float(pred_b.get("committed_wait_already_counted_s") or 0.0),
    )
    if wait <= PAIR_ARRIVAL_TOLERANCE_S:
        wait = 0.0
    return {
        "pair_s": float(wait),
        "reason": "service_interval_overlap" if wait > 0 else "no_overlap",
        "wait_accounting": wait_reason,
        "service_interval_a": list(abs_a),
        "service_interval_b": list(abs_b),
        "pred_a": pred_a,
        "pred_b": pred_b,
        "service_stationary_s": service,
        "equation": (
            "wait = max(0, earlier_service_end - later_service_start) "
            "- committed_wait_already_in_unary; coordinate=service_interval_absolute_race_s"
        ),
        "units": "seconds",
        "no_double_counting": "unary residual includes own committed wait once; pair adds incremental overlap only",
        "adjacent_lap_arbitrary_half_service": False,
        "deterministic_proxy_not_full_race_prediction": True,
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
