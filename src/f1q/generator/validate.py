from __future__ import annotations

from typing import Any

from f1q.errors import RejectionError

REJECTION_CODES = (
    "DUPLICATE_CAR_ID",
    "DUPLICATE_POSITION",
    "TEAM_MEMBERSHIP_INVALID",
    "NEGATIVE_DURATION",
    "NEGATIVE_TYRE_AGE",
    "NEGATIVE_INVENTORY",
    "HORIZON_INCONSISTENT",
    "RANGE_VIOLATION",
    "TYRE_SET_INCONSISTENT",
    "WET_EXCLUDED",
    "RED_FLAG_EXCLUDED",
    "SPRINT_EXCLUDED",
    "TYRE_DAMAGE_EXCLUDED",
    "ENERGY_DEPLOYMENT_EXCLUDED",
    "FUTURE_AVAILABILITY",
    "IMPOSSIBLE_TIME_ORDER",
    "PARTITION_REASSIGNMENT",
    "DUPLICATE_IDENTITY",
    "DEVELOPMENT_IN_SCIENTIFIC_SPLIT",
    "PRIVATE_FIELD_IN_OBSERVATION",
    "REALIZED_FUTURE_DURATION",
    "MISSED_PIT_RELABELED",
    "FIELD_SIZE_INVALID",
    "UNKNOWN_WITHOUT_REASON",
    "NAN_OR_INF",
)


def structural_errors(spec: dict[str, Any]) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    field = spec.get("field") or []
    if len(field) != 20:
        errors.append(("FIELD_SIZE_INVALID", f"expected 20 cars, got {len(field)}"))
    car_ids = [car.get("car_id") for car in field]
    if len(car_ids) != len(set(car_ids)):
        errors.append(("DUPLICATE_CAR_ID", "car_id values are not unique"))
    positions = [car.get("classified_position") for car in field]
    if len(positions) != len(set(positions)):
        errors.append(("DUPLICATE_POSITION", "classified positions are not unique"))
    if any(isinstance(pos, int) and (pos < 1 or pos > 20) for pos in positions):
        errors.append(("RANGE_VIOLATION", "classified positions must be in 1..20"))
    selected = spec.get("selected_car_ids") or []
    team_id = spec.get("selected_team_id")
    selected_cars = [car for car in field if car.get("car_id") in selected]
    if len(selected) != 2 or len(selected_cars) != 2:
        errors.append(("TEAM_MEMBERSHIP_INVALID", "selected team must be two cars present in the field"))
    elif any(car.get("team_id") != team_id for car in selected_cars):
        errors.append(("TEAM_MEMBERSHIP_INVALID", "selected cars are not members of selected_team_id"))
    init = spec.get("initialization") or {}
    request = spec.get("checkpoint_request") or {}
    init_completed = init.get("completed_laps")
    init_remaining = init.get("remaining_laps")
    horizon = spec.get("race_horizon_laps")
    if None not in {init_completed, init_remaining, horizon}:
        if init_completed + init_remaining != horizon:
            errors.append(("HORIZON_INCONSISTENT", "initialization remaining+completed must equal horizon"))
    req_completed = request.get("completed_laps")
    req_remaining = request.get("remaining_laps")
    if None not in {req_completed, req_remaining, horizon}:
        if req_completed + req_remaining != horizon:
            errors.append(("HORIZON_INCONSISTENT", "checkpoint remaining+completed must equal horizon"))
    if isinstance(init_completed, int) and isinstance(req_completed, int) and req_completed <= init_completed:
        errors.append(("HORIZON_INCONSISTENT", "checkpoint completed_laps must be after initialization"))
    weather = spec.get("weather")
    if weather and weather != "dry":
        errors.append(("WET_EXCLUDED", "wet transitions are excluded from the primary experiment"))
    for flag, code in (
        ("red_flag", "RED_FLAG_EXCLUDED"),
        ("sprint", "SPRINT_EXCLUDED"),
        ("tyre_damage", "TYRE_DAMAGE_EXCLUDED"),
        ("energy_deployment", "ENERGY_DEPLOYMENT_EXCLUDED"),
    ):
        if spec.get(flag) or init.get(flag):
            errors.append((code, f"{flag} is excluded from the primary experiment"))
    for car in field:
        if car.get("tyre_age_laps", 0) < 0:
            errors.append(("NEGATIVE_TYRE_AGE", f"{car.get('car_id')} tyre age is negative"))
        if car.get("gap_ahead_s", 0) < 0 or car.get("fuel_kg", 0) < 0:
            errors.append(("NEGATIVE_DURATION", f"{car.get('car_id')} has a negative duration or fuel"))
        mounted = car.get("mounted_set_id")
        inventory = car.get("inventory") or []
        set_ids = [item.get("set_id") for item in inventory]
        if mounted not in set_ids:
            errors.append(("TYRE_SET_INCONSISTENT", f"{car.get('car_id')} mounted set is not in inventory"))
        if len(set_ids) != len(set(set_ids)):
            errors.append(("TYRE_SET_INCONSISTENT", f"{car.get('car_id')} inventory set ids are not unique"))
        for item in inventory:
            if item.get("age_laps", 0) < 0:
                errors.append(("NEGATIVE_INVENTORY", f"{car.get('car_id')} has a negative tyre-set age"))
    if spec.get("partition") in {"training", "tuning", "calibration", "test", "shift"}:
        errors.append(("DEVELOPMENT_IN_SCIENTIFIC_SPLIT", "Stage 2 preview must not use a scientific partition"))
    pit = spec.get("green_pit_loss_s") or (spec.get("block_parameters") or {}).get("green_pit_loss_s")
    if isinstance(pit, (int, float)) and (pit < 18 or pit > 28):
        errors.append(("RANGE_VIOLATION", "green pit loss is outside the declared 18-28 s assumption"))
    remaining = request.get("remaining_laps")
    if isinstance(remaining, int) and (remaining < 12 or remaining > 45):
        errors.append(("RANGE_VIOLATION", "checkpoint remaining laps outside 12-45"))
    return errors


def assert_structural(spec: dict[str, Any]) -> None:
    errors = structural_errors(spec)
    if errors:
        code, reason = errors[0]
        raise RejectionError(code, reason)


def race_clock_seconds(label: str) -> float | None:
    if label.startswith("race_s:"):
        return float(label.split(":", 1)[1])
    if label in {"initialization", "generator", "checkpoint_request"}:
        return None
    return None
