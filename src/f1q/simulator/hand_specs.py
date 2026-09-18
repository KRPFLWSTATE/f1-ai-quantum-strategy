from __future__ import annotations

from typing import Any

from f1q.causal import parse_scenario_spec

TEAMS = [
    ("team.fictional.northshore", "northshore"),
    ("team.fictional.harbour", "harbour"),
    ("team.fictional.cedarline", "cedarline"),
    ("team.fictional.ironbridge", "ironbridge"),
    ("team.fictional.silverfen", "silverfen"),
    ("team.fictional.redcliff", "redcliff"),
    ("team.fictional.bluehaven", "bluehaven"),
    ("team.fictional.stoneford", "stoneford"),
    ("team.fictional.lakemere", "lakemere"),
    ("team.fictional.windrow", "windrow"),
]


def _inventory(car_id: str, compound: str, age: float) -> list[dict[str, Any]]:
    items = []
    counts = {"soft": 2, "medium": 3, "hard": 3}
    for name, n in counts.items():
        for i in range(n):
            mounted = name == compound and i == 0
            items.append(
                {
                    "set_id": f"{car_id}.set.{name}.{i}",
                    "compound": name,
                    "used": mounted,
                    "age_laps": age if mounted else 0.0,
                }
            )
    return items


def build_hand_spec(
    *,
    spec_id: str = "hand.free_track.v1",
    episode_id: str = "hand.free_track.v1/episode/00/SC",
    regime: str = "SC",
    green_lap_s: float = 90.0,
    green_pit_loss_s: float = 20.0,
    tyre_form: str = "near_linear",
    tyre_wear: float = 0.05,
    tyre_curvature: float | None = None,
    mean_gap_ahead_s: float = 8.0,
    completed_init: int = 10,
    laps_until_checkpoint: int = 2,
    remaining_at_checkpoint: int = 12,
    selected_positions: tuple[int, int] = (1, 2),
    gap_overrides: dict[int, float] | None = None,
    fuel_kg: float | None = None,
    compound: str = "soft",
    tyre_age: float = 0.0,
    cutoff_leader_s: float = 20.0,
    obligation: int = 1,
    requested_note: str = "hand-constructed fixture; not a historical race",
) -> dict[str, Any]:
    completed_cp = completed_init + laps_until_checkpoint
    remaining_init = remaining_at_checkpoint + laps_until_checkpoint
    horizon = completed_init + remaining_init
    fuel = fuel_kg if fuel_kg is not None else remaining_init * 1.8 + 2.0
    field = []
    pos = 1
    selected_ids = []
    selected_team = None
    for team_id, slug in TEAMS:
        for suffix in ("a", "b"):
            car_id = f"car.fictional.{slug}.{suffix}"
            gap = 0.0 if pos == 1 else float((gap_overrides or {}).get(pos, mean_gap_ahead_s))
            if pos in selected_positions:
                selected_ids.append(car_id)
                selected_team = team_id
            field.append(
                {
                    "car_id": car_id,
                    "team_id": team_id,
                    "classified_position": pos,
                    "gap_ahead_s": gap,
                    "lap_deficit": 0,
                    "compound": compound,
                    "tyre_age_laps": tyre_age,
                    "mounted_set_id": f"{car_id}.set.{compound}.0",
                    "inventory": _inventory(car_id, compound, tyre_age),
                    "fuel_kg": round(float(fuel), 3),
                    "fuel_uncertainty_kg": 2.0,
                    "pit_entry_commitment_cutoff_remaining_s": cutoff_leader_s if pos == 1 else cutoff_leader_s + 5.0,
                    "in_pit_lane": False,
                    "service_state": "on_track",
                }
            )
            pos += 1
    spec = {
        "schema_version": "2.0.0",
        "kind": "scenario_spec",
        "spec_id": spec_id,
        "block_id": "hand.block",
        "episode_id": episode_id,
        "family_id": "fam.green_pit_low.tyre_near_linear.traffic_sparse",
        "partition": "development",
        "namespace": "development",
        "generator_version": "2.0.0",
        "evidence_kind": "development",
        "awaiting_simulator_validation": True,
        "not_a_validated_race_checkpoint": True,
        "not_a_scientific_split_member": True,
        "factors": {"green_pit_loss": "low", "tyre_degradation": tyre_form, "traffic": "sparse"},
        "block_parameters": {
            "green_pit_loss_s": green_pit_loss_s,
            "green_pit_loss_includes_service_and_transit": True,
            "green_lap_s": green_lap_s,
            "mean_gap_ahead_s": mean_gap_ahead_s,
            "tyre_form": tyre_form,
            "tyre_wear_per_lap": tyre_wear,
            "tyre_curvature": tyre_curvature,
            "tyre_mapping_status": "stage3_declared",
            "remaining_laps_at_checkpoint": remaining_at_checkpoint,
            "completed_laps_at_init": completed_init,
            "track_archetype": "hand-constructed",
            "field_size": 20,
            "weather": "dry",
        },
        "race_horizon_laps": horizon,
        "initialization": {
            "kind": "green_running",
            "completed_laps": completed_init,
            "remaining_laps": remaining_init,
            "laps_until_checkpoint": laps_until_checkpoint,
            "weather": "dry",
            "init_race_time_s": {
                "value": completed_init * green_lap_s,
                "unit": "s",
                "source": "hand fixture assumed completed * green_lap; fictional pre-checkpoint",
                "availability_time": "initialization",
                "status": "assumed",
            },
        },
        "checkpoint_request": {
            "rule": "completed_laps_equals",
            "completed_laps": completed_cp,
            "remaining_laps": remaining_at_checkpoint,
            "requested_regime": regime,
            "race_time_s": {
                "value": None,
                "unit": "s",
                "source": "pending evolution",
                "availability_time": "checkpoint_request",
                "status": "unknown",
                "unknown_reason": "hand fixture awaits simulator evolution",
            },
            "note": requested_note,
        },
        "selected_team_id": selected_team,
        "selected_car_ids": selected_ids,
        "field": field,
        "weather": "dry",
        "compound_obligation": {
            "distinct_compounds_required": obligation,
            "double_stacking": "delay_cost_not_prohibition",
            "kind": "model_configuration",
            "not_an_invented_fia_rule": True,
        },
        "pit_lane": {"occupied": False, "physics": "simulator.v1", "status": "hand_fixture"},
        "team_service": {"shared_service": True, "stacking_policy": "delay_cost_not_prohibition", "state": "crew_available"},
        "rival_policy_ref": {"id": "rival.policy.frozen_nonreactive.v1", "status": "stage3_executed"},
        "clock": {
            "race_clock_unit": "s",
            "race_clock_origin": "race_start",
            "monotonic_client_clock": "separate_from_race_clock",
            "communication_margin_s": 1.0,
        },
        "deadline_interface": {
            "communication_margin_s": 1.0,
            "primary_nominal_budget_s": 30,
            "nominal_budgets_s": [5, 10, 30, 60, 120],
            "effective_deadline_rule": "min(nominal, earliest_team_pit_cutoff - communication_margin)",
        },
        "stream_key_ids": {
            "block_params": "0" * 64,
            "episode": "1" * 64,
            "evaluation": "2" * 64,
            "fitting": "3" * 64,
            "online_scoring": "4" * 64,
        },
        "assumptions": [{"field": "hand_fixture", "status": "assumed", "note": "independent mechanism check"}],
        "exclusions": [
            "wet_transitions",
            "red_flags",
            "sprint_specific_rules",
            "tyre_damage",
            "detailed_energy_deployment",
        ],
        "provenance": {"attempt": 1, "kind": "hand_constructed_fixture", "not_historical": True},
    }
    parse_scenario_spec(spec)
    return spec
