from __future__ import annotations

import pytest

from f1q.causal import PRIVATE_SOLVER_EXCLUSIONS, PrivateSimState, Quantity, SimulatorState
from f1q.errors import RejectionError, SchemaError
from f1q.generator.observation import project_decision_observation
from f1q.generator.stage3 import SimulatorAdapter


def _state(**private_extra):
    private = dict(
        block_stream_seed=1,
        episode_stream_seed=2,
        sampled_future_regime_duration_s=14.5,
        rival_eventual_pit_laps={"car.fictional.harbour.a": 33},
        evaluator_bank_key="secret-eval",
    )
    private.update(private_extra)
    return SimulatorState(
        episode_id="ep-1",
        spec_id="spec-1",
        public={
            "cars": [
                {
                    "car_id": "car.fictional.northshore.a",
                    "classified_position": 4,
                    "gap_ahead_s": 1.2,
                    "lap_deficit": 0,
                    "pit_entry_commitment_cutoff_race_s": 90.0,
                }
            ],
            "completed_laps": 20,
            "remaining_laps": 15,
            "selected_team_id": "team.fictional.northshore",
            "forecasts": [
                Quantity(
                    value=3,
                    unit="laps",
                    source="weather desk fictional",
                    availability_time="race_s:80",
                    status="forecast",
                    forecast_issuance_time="race_s:80",
                    forecast_uncertainty={"kind": "interval", "low": 2, "high": 5},
                ).model_dump(mode="python")
            ],
        },
        private=PrivateSimState(**private),
        stream_key_ids={"episode": "abc"},
    )


def test_projection_excludes_private_and_future_duration():
    spec = {
        "spec_id": "spec-1",
        "block_id": "block-1",
        "episode_id": "ep-1",
        "family_id": "fam.green_pit_low.tyre_near_linear.traffic_sparse",
        "partition": "development",
        "selected_team_id": "team.fictional.northshore",
        "race_horizon_laps": 35,
        "checkpoint_request": {"completed_laps": 20, "remaining_laps": 15},
        "clock": {"communication_margin_s": 1.0},
        "deadline_interface": {"primary_nominal_budget_s": 30},
        "compound_obligation": {},
        "pit_lane": {},
        "team_service": {},
        "field": [{"car_id": "car.fictional.northshore.a"}],
    }
    obs = project_decision_observation(
        _state(), decision_time_race_s=100.0, revealed_regime="SC", spec=spec
    )
    dumped = obs.model_dump(mode="python")
    blob = str(dumped)
    assert "14.5" not in blob
    assert "secret-eval" not in blob
    assert "rival_eventual_pit_laps" not in blob
    assert dumped["safety_regime"]["value"] == "SC"
    assert dumped["safety_regime_duration"]["status"] == "unknown"
    assert dumped["forecasts"][0]["status"] == "forecast"
    for key in PRIVATE_SOLVER_EXCLUSIONS:
        assert key not in dumped


def test_future_availability_rejected_for_known_quantity():
    state = _state()
    state.public["forecasts"] = [
        Quantity(
            value=1,
            unit="laps",
            source="leak",
            availability_time="race_s:500",
            status="known",
        ).model_dump(mode="python")
    ]
    with pytest.raises((RejectionError, SchemaError)):
        project_decision_observation(
            state,
            decision_time_race_s=100.0,
            revealed_regime="VSC",
            spec={
                "spec_id": "s",
                "block_id": "b",
                "episode_id": "ep-1",
                "family_id": "f",
                "partition": "development",
                "selected_team_id": "t",
                "race_horizon_laps": 40,
                "checkpoint_request": {"completed_laps": 20, "remaining_laps": 20},
                "clock": {"communication_margin_s": 1.0},
                "deadline_interface": {},
                "field": [],
            },
        )


def test_labeled_forecast_issued_before_checkpoint_is_permitted():
    obs = project_decision_observation(
        _state(),
        decision_time_race_s=100.0,
        revealed_regime="SC",
        spec={
            "spec_id": "s",
            "block_id": "b",
            "episode_id": "ep-1",
            "family_id": "f",
            "partition": "development",
            "selected_team_id": "t",
            "race_horizon_laps": 40,
            "checkpoint_request": {"completed_laps": 20, "remaining_laps": 20},
            "clock": {"communication_margin_s": 1.0},
            "deadline_interface": {},
            "field": [{"car_id": "x"}],
        },
    )
    assert obs.forecasts[0].forecast_issuance_time == "race_s:80"


def test_expired_pit_is_not_relabeled():
    state = _state()
    state.public["cars"][0]["pit_entry_commitment_cutoff_race_s"] = 50.0
    obs = project_decision_observation(
        state,
        decision_time_race_s=100.0,
        revealed_regime="SC",
        spec={
            "spec_id": "s",
            "block_id": "b",
            "episode_id": "ep-1",
            "family_id": "f",
            "partition": "development",
            "selected_team_id": "t",
            "race_horizon_laps": 40,
            "checkpoint_request": {"completed_laps": 20, "remaining_laps": 20},
            "clock": {"communication_margin_s": 1.0},
            "deadline_interface": {},
            "field": [{"car_id": "car.fictional.northshore.a"}],
        },
    )
    assert obs.expired_actions[0].reason_code == "PIT_WINDOW_CLOSED"
    assert obs.expired_actions[0].not_relabeled_as == "pit_next_lap"


def test_relabeled_missed_pit_is_rejected():
    state = _state()
    state.public["cars"][0]["pit_entry_commitment_cutoff_race_s"] = 50.0
    state.public["cars"][0]["missed_pit_relabeled_as"] = "pit_next_lap"
    with pytest.raises(RejectionError, match="MISSED_PIT_RELABELED"):
        project_decision_observation(
            state,
            decision_time_race_s=100.0,
            revealed_regime="SC",
            spec={
                "spec_id": "s",
                "block_id": "b",
                "episode_id": "ep-1",
                "family_id": "f",
                "partition": "development",
                "selected_team_id": "t",
                "race_horizon_laps": 40,
                "checkpoint_request": {"completed_laps": 20, "remaining_laps": 20},
                "clock": {"communication_margin_s": 1.0},
                "deadline_interface": {},
                "field": [],
            },
        )


def test_simulator_adapter_evolves_without_placeholders():
    from pathlib import Path

    from f1q.simulator.hand_specs import build_hand_spec
    from f1q.simulator.interface import SimulatorAdapter

    adapter = SimulatorAdapter(project_root=Path(__file__).resolve().parents[1])
    spec = build_hand_spec(obligation=1)
    from f1q.causal import parse_scenario_spec

    parsed = parse_scenario_spec(spec)
    state = adapter.initialize(parsed)
    assert state.private.engine_state is not None
    adapter.validate_checkpoint  # real method exists
    checkpoint = adapter.run_to_checkpoint(parsed)
    assert checkpoint.public.get("checkpoint_reached") is True
