from __future__ import annotations

from typing import Any

from f1q import GENERATOR_VERSION
from f1q.causal import CheckpointRequest, ClockContract, Quantity, ScenarioSpec, TyreSet, parse_scenario_spec
from f1q.errors import RejectionError
from f1q.generator.config import FamilyRecord, GeneratorConfigFile
from f1q.generator.sampling import StreamRNG, sample_distribution
from f1q.generator.streams import block_id, episode_id, spec_id, stream_hex, stream_seed
from f1q.generator.validate import assert_structural, structural_errors
from f1q.hashing import sha256_json

COMPOUNDS = ("soft", "medium", "hard")
SETS_PER_COMPOUND = {"soft": 2, "medium": 3, "hard": 3}
VOLATILE_KEYS = frozenset({"generated_at_utc", "run_id", "attempt_id", "written_at_utc", "unit_attempt_id"})


def strip_volatile(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {key: strip_volatile(value) for key, value in obj.items() if key not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [strip_volatile(item) for item in obj]
    return obj


def substantive_fingerprint(payload: Any) -> str:
    return sha256_json(strip_volatile(payload))


def _qty(value: Any, unit: str, source: str, availability: str, status: str, **extra: Any) -> dict[str, Any]:
    body = {
        "value": value,
        "unit": unit,
        "source": source,
        "availability_time": availability,
        "status": status,
    }
    body.update({key: val for key, val in extra.items() if val is not None})
    return body


def generate_block(
    config: GeneratorConfigFile,
    family: FamilyRecord,
    *,
    namespace: str,
    block_index: int,
    declared_unit_seed: int,
    family_iteration_tag: str | None = None,
) -> dict[str, Any]:
    """family_iteration_tag is ignored for sampling so iteration order cannot change payloads."""
    del family_iteration_tag
    partition = "development" if namespace == "development" else "forbidden"
    if partition != "development":
        raise RejectionError("DEVELOPMENT_IN_SCIENTIFIC_SPLIT", "Stage 2 may only emit the development namespace")
    ident = block_id(namespace=namespace, partition=partition, family_id=family.id, index=block_index)
    block_ctx = {
        "generator_version": config.generator_version,
        "namespace": namespace,
        "family_id": family.id,
        "block_index": block_index,
        "declared_unit_seed": declared_unit_seed,
    }
    block_seed = stream_seed("block_params", block_ctx)
    rng = StreamRNG(block_seed)
    pit_spec = config.factors["green_pit_loss"][family.green_pit_loss]
    traffic_spec = config.factors["traffic"][family.traffic]["mean_gap_ahead_s"]
    tyre_spec = config.factors["tyre_degradation"][family.tyre_degradation]
    remaining_at_checkpoint = sample_distribution(rng, config.domain["remaining_laps"])
    completed_at_init = sample_distribution(rng, config.domain["completed_laps_at_init"])
    green_lap_s = sample_distribution(rng, config.domain["green_lap_s"])
    green_pit_loss_s = rng.uniform(pit_spec["low"], pit_spec["high"])
    mean_gap = rng.uniform(traffic_spec["low"], traffic_spec["high"])
    wear = rng.uniform(tyre_spec["wear_per_lap"]["low"], tyre_spec["wear_per_lap"]["high"])
    curvature = None
    if family.tyre_degradation == "nonlinear":
        curvature = rng.uniform(tyre_spec["curvature"]["low"], tyre_spec["curvature"]["high"])
    track = rng.choice(config.provisional_quantities[-1]["value"] if False else [
        item["value"] for item in config.provisional_quantities if item["field"] == "track_archetypes"
    ][0])
    block_parameters = {
        "green_pit_loss_s": round(float(green_pit_loss_s), 4),
        "green_pit_loss_includes_service_and_transit": True,
        "green_lap_s": round(float(green_lap_s), 4),
        "mean_gap_ahead_s": round(float(mean_gap), 4),
        "tyre_form": family.tyre_degradation,
        "tyre_wear_per_lap": round(float(wear), 5),
        "tyre_curvature": None if curvature is None else round(float(curvature), 5),
        "tyre_mapping_status": "pending_stage3_physics",
        "remaining_laps_at_checkpoint": int(remaining_at_checkpoint),
        "completed_laps_at_init": int(completed_at_init),
        "track_archetype": track,
        "field_size": 20,
        "weather": "dry",
    }
    episodes = []
    rejections: list[dict[str, Any]] = []
    max_attempts = int(config.retry_policy["max_attempts_per_episode"])
    for episode_index in range(8):
        regime = "SC" if episode_index < 4 else "VSC"
        spec = None
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                spec = generate_episode(
                    config,
                    family,
                    block_id_value=ident,
                    block_parameters=block_parameters,
                    episode_index=episode_index,
                    regime=regime,
                    declared_unit_seed=declared_unit_seed,
                    attempt=attempt,
                )
                break
            except RejectionError as exc:
                last_error = exc
                rejections.append(
                    {
                        "episode_index": episode_index,
                        "attempt": attempt,
                        "code": exc.code,
                        "reason": exc.reason,
                    }
                )
                if attempt >= max_attempts:
                    raise
        assert spec is not None
        episodes.append(spec)
        del last_error
    sc = sum(1 for ep in episodes if ep["checkpoint_request"]["requested_regime"] == "SC")
    vsc = sum(1 for ep in episodes if ep["checkpoint_request"]["requested_regime"] == "VSC")
    if sc != 4 or vsc != 4:
        raise RejectionError("RANGE_VIOLATION", "each block must request four SC and four VSC checkpoints")
    return {
        "kind": "development_block",
        "block_id": ident,
        "family_id": family.id,
        "partition": "development",
        "namespace": namespace,
        "block_index": block_index,
        "block_parameters": block_parameters,
        "stream_key_ids": {
            "block_params": stream_hex("block_params", block_ctx),
            "fitting": stream_hex("fitting", {"generator_version": config.generator_version, "purpose": "unused_in_stage2"}),
        },
        "episodes": episodes,
        "rejections": rejections,
        "substantive_fingerprint": substantive_fingerprint(
            {"block_id": ident, "block_parameters": block_parameters, "episodes": episodes}
        ),
        "inferential_unit": "block",
        "awaiting_simulator_validation": True,
        "not_a_scientific_split_member": True,
    }


def generate_episode(
    config: GeneratorConfigFile,
    family: FamilyRecord,
    *,
    block_id_value: str,
    block_parameters: dict[str, Any],
    episode_index: int,
    regime: str,
    declared_unit_seed: int,
    attempt: int,
) -> dict[str, Any]:
    ep_ctx = {
        "generator_version": config.generator_version,
        "block_id": block_id_value,
        "episode_index": episode_index,
        "attempt": attempt,
        "declared_unit_seed": declared_unit_seed,
    }
    seed = stream_seed("episode", ep_ctx)
    rng = StreamRNG(seed)
    teams = list(config.fictional_teams)
    team = rng.choice(teams)
    team_id = team["id"]
    slug = team_id.rsplit(".", 1)[-1]
    selected_ids = [f"car.fictional.{slug}.a", f"car.fictional.{slug}.b"]
    offset = rng.choice([1, 2, 3])
    remaining_cp = int(block_parameters["remaining_laps_at_checkpoint"])
    completed_init = int(block_parameters["completed_laps_at_init"])
    completed_cp = completed_init + offset
    remaining_init = remaining_cp + offset
    horizon = completed_init + remaining_init
    if completed_cp + remaining_cp != horizon:
        raise RejectionError("HORIZON_INCONSISTENT", "episode horizon construction failed")
    positions = rng.sample(list(range(1, 21)), 2)
    field = _build_field(
        rng,
        teams=teams,
        selected_team_id=team_id,
        selected_ids=selected_ids,
        selected_positions=positions,
        mean_gap=float(block_parameters["mean_gap_ahead_s"]),
        dense=family.traffic == "dense",
        remaining_laps=remaining_init,
    )
    ep_id = episode_id(block_id_value, episode_index, regime)
    clock = ClockContract(communication_margin_s=float(config.clock["communication_margin_s"]))
    spec = {
        "schema_version": "2.0.0",
        "kind": "scenario_spec",
        "spec_id": spec_id(ep_id),
        "block_id": block_id_value,
        "episode_id": ep_id,
        "family_id": family.id,
        "partition": "development",
        "namespace": "development",
        "generator_version": config.generator_version,
        "evidence_kind": "development",
        "awaiting_simulator_validation": True,
        "not_a_validated_race_checkpoint": True,
        "not_a_scientific_split_member": True,
        "factors": {
            "green_pit_loss": family.green_pit_loss,
            "tyre_degradation": family.tyre_degradation,
            "traffic": family.traffic,
        },
        "block_parameters": block_parameters,
        "race_horizon_laps": horizon,
        "initialization": {
            "kind": "green_running",
            "completed_laps": completed_init,
            "remaining_laps": remaining_init,
            "laps_until_checkpoint": offset,
            "weather": "dry",
            "init_race_time_s": {
                "value": round(completed_init * float(block_parameters["green_lap_s"]), 3),
                "unit": "s",
                "source": "assumed completed_laps * sampled green_lap_s; not Stage 3 physics",
                "availability_time": "initialization",
                "status": "assumed",
            },
        },
        "checkpoint_request": CheckpointRequest(
            rule="completed_laps_equals",
            completed_laps=completed_cp,
            remaining_laps=remaining_cp,
            requested_regime=regime,  # type: ignore[arg-type]
            race_time_s=Quantity(
                value=None,
                unit="s",
                source="race clock at the checkpoint depends on Stage 3 evolution",
                availability_time="checkpoint_request",
                status="unknown",
                unknown_reason="pending Stage 3 advance from initialization to the prescribed completed_laps",
            ),
        ).model_dump(mode="python"),
        "selected_team_id": team_id,
        "selected_car_ids": selected_ids,
        "field": field,
        "weather": "dry",
        "compound_obligation": {
            "kind": "model_configuration",
            "not_an_invented_fia_rule": True,
            "distinct_compounds_required": 2,
            "double_stacking": "delay_cost_not_prohibition",
        },
        "pit_lane": {
            "occupied": False,
            "status": "assumed_at_initialization",
            "physics": "pending_stage3",
        },
        "team_service": {
            "state": "crew_available",
            "shared_service": True,
            "stacking_policy": "delay_cost_not_prohibition",
        },
        "rival_policy_ref": dict(config.rival_policy_ref),
        "clock": clock.model_dump(mode="python"),
        "deadline_interface": {
            "nominal_budgets_s": list(config.nominal_decision_budgets_s),
            "primary_nominal_budget_s": config.primary_nominal_budget_s,
            "communication_margin_s": config.clock["communication_margin_s"],
            "effective_deadline_rule": "min(nominal, earliest_team_pit_cutoff - communication_margin) at the decision epoch",
            "effective_deadline_s": {
                "value": None,
                "unit": "s",
                "source": "requires Stage 3 race clock and cutoffs",
                "availability_time": "checkpoint_request",
                "status": "unknown",
                "unknown_reason": "pending Stage 3",
            },
            "nominal_budgets_are_not_effective_cutoffs": True,
        },
        "stream_key_ids": {
            "block_params": stream_hex(
                "block_params",
                {
                    "generator_version": config.generator_version,
                    "namespace": "development",
                    "family_id": family.id,
                    "block_index": int(block_id_value.rsplit("/", 1)[-1]),
                    "declared_unit_seed": declared_unit_seed,
                },
            ),
            "episode": stream_hex("episode", ep_ctx),
            "fitting": stream_hex("fitting", {"generator_version": config.generator_version, "purpose": "unused_in_stage2"}),
            "online_scoring": stream_hex("online_scoring", {"generator_version": config.generator_version, "purpose": "unused_in_stage2"}),
            "evaluation": stream_hex(
                "evaluation",
                {
                    "generator_version": config.generator_version,
                    "episode_id": ep_id,
                    "driver_id": selected_ids[0],
                    "lap": completed_cp,
                    "event_type": "checkpoint_request",
                    "replication": 0,
                },
            ),
        },
        "assumptions": [
            {"field": "green_pit_loss_s", "status": "assumed", "note": "combined transit and service; not F1 calibration"},
            {"field": "tyre_wear", "status": "assumed", "note": "form plus scale only; lap-time map is Stage 3"},
            {"field": "fuel_model", "status": "assumed", "note": "1.8 kg per remaining lap plus 2 kg uncertainty"},
        ],
        "exclusions": list(config.domain["exclusions"]),
        "provenance": {
            "generator_version": GENERATOR_VERSION,
            "attempt": attempt,
            "declared_unit_seed": declared_unit_seed,
            "dossier_sections": config.dossier.get("sections"),
        },
    }
    assert_structural(spec)
    parse_scenario_spec(spec)
    spec["substantive_fingerprint"] = substantive_fingerprint(spec)
    return spec


def _build_field(
    rng: StreamRNG,
    *,
    teams: list[dict[str, str]],
    selected_team_id: str,
    selected_ids: list[str],
    selected_positions: list[int],
    mean_gap: float,
    dense: bool,
    remaining_laps: int,
) -> list[dict[str, Any]]:
    cars: list[dict[str, Any]] = []
    used_positions = set(selected_positions)
    others = [pos for pos in range(1, 21) if pos not in used_positions]
    team_by_pos: dict[int, tuple[str, str]] = {
        selected_positions[0]: (selected_team_id, selected_ids[0]),
        selected_positions[1]: (selected_team_id, selected_ids[1]),
    }
    remaining_teams = [team for team in teams if team["id"] != selected_team_id]
    for team in remaining_teams:
        slug = team["id"].rsplit(".", 1)[-1]
        pos_a = others.pop(0)
        pos_b = others.pop(0)
        team_by_pos[pos_a] = (team["id"], f"car.fictional.{slug}.a")
        team_by_pos[pos_b] = (team["id"], f"car.fictional.{slug}.b")
    for position in range(1, 21):
        team_id, car_id = team_by_pos[position]
        compound = rng.choice(COMPOUNDS)
        age = rng.uniform(0.0, 18.0)
        inventory = _inventory(car_id, compound, age)
        gap = 0.0 if position == 1 else max(0.05, rng.uniform(mean_gap * 0.5, mean_gap * 1.5))
        lap_deficit = 1 if dense and position >= 19 else 0
        fuel = max(5.0, remaining_laps * 1.8 + rng.uniform(-2.0, 2.0))
        cutoff = rng.uniform(8.0, 40.0)
        cars.append(
            {
                "car_id": car_id,
                "team_id": team_id,
                "classified_position": position,
                "gap_ahead_s": round(gap, 4),
                "lap_deficit": lap_deficit,
                "compound": compound,
                "tyre_age_laps": round(age, 3),
                "mounted_set_id": f"{car_id}.set.{compound}.0",
                "inventory": inventory,
                "fuel_kg": round(fuel, 3),
                "fuel_uncertainty_kg": 2.0,
                "pit_entry_commitment_cutoff_remaining_s": round(cutoff, 3),
                "in_pit_lane": False,
                "service_state": "on_track",
            }
        )
    return cars


def _inventory(car_id: str, mounted_compound: str, mounted_age: float) -> list[dict[str, Any]]:
    items: list[TyreSet] = []
    for compound, count in SETS_PER_COMPOUND.items():
        for index in range(count):
            mounted = compound == mounted_compound and index == 0
            items.append(
                TyreSet(
                    set_id=f"{car_id}.set.{compound}.{index}",
                    compound=compound,  # type: ignore[arg-type]
                    used=mounted,
                    age_laps=round(mounted_age, 3) if mounted else 0.0,
                )
            )
    return [item.model_dump(mode="python") for item in items]
