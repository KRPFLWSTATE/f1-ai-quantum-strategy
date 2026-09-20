"""Stage 4 Final Closure regression tests (A–C + bounded gate fixtures)."""

from __future__ import annotations

from pathlib import Path

import pytest

from f1q.formulation.actions import CarAction, generate_action_model
from f1q.formulation.compiler import compile_action_costs, predicted_service_interval
from f1q.formulation.evaluator import check_action_semantics, evaluate_joint_plan_on_checkpoint
from f1q.formulation.public_config import public_physics_from_sources
from f1q.simulator.commitment import project_committed_pit_service
from f1q.simulator.config import load_simulator_config
from f1q.simulator.interface import RaceSimulator
from f1q.simulator.matrix import load_preview_specs

ROOT = Path(__file__).resolve().parents[2]


def _physics(cfg, spec):
    return public_physics_from_sources(
        simulator_cfg=cfg,
        block_parameters=spec["block_parameters"],
        compound_obligation=spec.get("compound_obligation"),
    )


def _action(**kwargs):
    base = {
        "commitment": {"expires": "test", "kind": "test"},
        "description": "test action",
        "observable_admission_facts": {},
    }
    base.update(kwargs)
    return CarAction.model_validate(base)


def test_timing_rejects_late_service_complete_as_pit_now_window():
    action = _action(
        action_id="c|pit_now|soft|s1",
        car_id="c",
        kind="pit_now",
        compound="soft",
        set_id="s1",
    )
    # Decision at t=100 lap 10; service at 99999 lap 99 must fail exact entry-lap check.
    check = check_action_semantics(
        action=action,
        executed=[
            {
                "set_id": "s1",
                "compound": "soft",
                "pit_lap_index": 99,
                "pit_entry_completed_laps": 99,
                "event_time_race_s": 99999.0,
            }
        ],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=10,
        pit_entry_completed_laps=99,
        terminal_car={"mounted_set_id": "s1"},
    )
    assert check["timing_ok"] is False
    assert "pit_now_entry_lap_mismatch" in check["timing_reason"]


def test_delay_laps_exact_boundary_not_lower_bound():
    action = _action(
        action_id="c|delay_laps|2|soft|s1",
        car_id="c",
        kind="delay_laps",
        compound="soft",
        set_id="s1",
        delay_laps=2,
    )
    # Expected entry lap = 10+2=12; lap 99 must not pass as a lower bound.
    check = check_action_semantics(
        action=action,
        executed=[
            {
                "set_id": "s1",
                "compound": "soft",
                "pit_lap_index": 99,
                "pit_entry_completed_laps": 99,
                "event_time_race_s": 99999.0,
            }
        ],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=10,
        pit_entry_completed_laps=99,
        terminal_car={"mounted_set_id": "s1"},
    )
    assert check["timing_ok"] is False
    exact = check_action_semantics(
        action=action,
        executed=[
            {
                "set_id": "s1",
                "compound": "soft",
                "pit_lap_index": 12,
                "pit_entry_completed_laps": 12,
                "event_time_race_s": 200.0,
            }
        ],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=10,
        pit_entry_completed_laps=12,
        terminal_car={"mounted_set_id": "s1"},
    )
    assert exact["timing_ok"] is True


def test_mutate_executed_rejects_wrong_extra_omitted_mount():
    action = _action(
        action_id="c|pit_now|soft|s1",
        car_id="c",
        kind="pit_now",
        compound="soft",
        set_id="s1",
    )
    wrong = check_action_semantics(
        action=action,
        executed=[{"set_id": "WRONG", "compound": "soft", "pit_lap_index": 10, "pit_entry_completed_laps": 10}],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=10,
        pit_entry_completed_laps=10,
        terminal_car={"mounted_set_id": "WRONG"},
    )
    assert wrong["instructed_set_compound_ok"] is False
    extra = check_action_semantics(
        action=action,
        executed=[
            {"set_id": "s1", "compound": "soft", "pit_lap_index": 10, "pit_entry_completed_laps": 10},
            {"set_id": "s2", "compound": "hard", "pit_lap_index": 11, "pit_entry_completed_laps": 11},
        ],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=10,
        pit_entry_completed_laps=10,
        terminal_car={"mounted_set_id": "s1"},
    )
    assert extra["stop_sequence_ok"] is False
    assert any("extra_unplanned" in c for c in extra["reason_codes"])
    omitted = check_action_semantics(
        action=action,
        executed=[],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=10,
        pit_entry_completed_laps=None,
        terminal_car={"mounted_set_id": "s1"},
    )
    assert omitted["stop_sequence_ok"] is False


def test_transit_out_commitment_uses_mounted_set():
    car = {
        "car_id": "c1",
        "team_id": "t1",
        "in_pit": True,
        "pit_phase": "transit_out",
        "pit_phase_end": 110.0,
        "pending_compound": None,
        "pending_set_id": None,
        "compound": "soft",
        "mounted_set_id": "set.soft.1",
        "tyre_age_laps": 3.0,
        "pit_entry_completed_laps": 10,
    }
    proj = project_committed_pit_service(
        car=car,
        decision_time_race_s=100.0,
        pit_parts={"t_in_s": 20.0, "t_service_s": 2.5, "t_out_s": 8.0},
        crew_free_at_race_s=100.0,
        selected_team_id="t1",
    )
    assert proj is not None
    assert proj["service_already_completed"] is True
    assert proj["set_id"] == "set.soft.1"
    assert proj["target_compound"] == "soft"
    assert proj["remaining_service_s"] == 0.0
    assert proj["residual_pit_time_s"] == pytest.approx(10.0)


def test_mixed_service_interval_coordinate_on_track():
    cfg, _ = load_simulator_config(ROOT)
    spec = next(s for s in load_preview_specs(ROOT) if s["episode_id"].endswith("/0000/episode/00/SC"))
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    obs = sim.observe()
    public = _physics(cfg, spec)
    cars = list(spec["selected_car_ids"])
    am = generate_action_model(obs, public, selected_car_ids=cars)
    a0 = next(a for a in am["menus"][cars[0]] if a["kind"] in {"pit_now", "delay_laps"})
    a1 = next(a for a in am["menus"][cars[1]] if a["kind"] in {"pit_now", "delay_laps"})
    pred_a = predicted_service_interval(obs.model_dump(mode="python"), public, CarAction.model_validate(a0))
    pred_b = predicted_service_interval(obs.model_dump(mode="python"), public, CarAction.model_validate(a1))
    assert pred_a["ok"] and pred_b["ok"]
    assert pred_a["interval"] and pred_b["interval"]
    assert pred_a["reason"] == "on_track_entry_plus_public_t_in"
    costs = compile_action_costs(
        obs, public, menus={cars[0]: [a0], cars[1]: [a1]}, selected_car_ids=cars
    )
    assert costs["pair_details"][0][0]["pair_s"] is not None
    assert costs["pair_details"][0][0].get("coordinate") or costs["pair_details"][0][0].get("pred_a")


def test_in_pit_continuation_still_semantic_legal():
    cfg, _ = load_simulator_config(ROOT)
    spec = next(s for s in load_preview_specs(ROOT) if s["episode_id"].endswith("/0000/episode/02/SC"))
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    obs = sim.observe()
    cars = list(spec["selected_car_ids"])
    public = _physics(cfg, spec)
    am = generate_action_model(obs, public, selected_car_ids=cars)
    ev = evaluate_joint_plan_on_checkpoint(
        cfg=cfg,
        spec=spec,
        action_a=CarAction.model_validate(am["menus"][cars[0]][0]),
        action_b=CarAction.model_validate(am["menus"][cars[1]][0]),
    )
    assert ev["semantic_legal"] is True
