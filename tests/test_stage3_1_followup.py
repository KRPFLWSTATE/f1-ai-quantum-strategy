from __future__ import annotations

from pathlib import Path

import pytest

from f1q.errors import RejectionError
from f1q.hashing import canonical_json
from f1q.simulator.checks import check_causal, check_deadline, check_free_track, check_sc_vsc
from f1q.simulator.config import load_simulator_config
from f1q.simulator.fuel import realize_initial_fuel
from f1q.simulator.hand_specs import build_hand_spec
from f1q.simulator.interface import RaceSimulator
from f1q.simulator.policies import SpyCar, continuation_intent, public_car_view

ROOT = Path(__file__).resolve().parents[1]


def test_fuel_floor_is_conditioned_atom_not_uniform():
    got = realize_initial_fuel(estimate_kg=18.0, uncertainty_kg=2.0, offset_kg=-1.5, need_kg=18.0)
    assert got.floor_applied is True
    assert abs(got.actual_kg - 18.0) <= 1e-12
    assert got.unbiased_uniform_error is False
    with pytest.raises(RejectionError, match="IMPOSSIBLE_INITIAL_FUEL"):
        realize_initial_fuel(estimate_kg=15.0, uncertainty_kg=2.0, offset_kg=0.0, need_kg=18.0)
    interior = realize_initial_fuel(estimate_kg=20.0, uncertainty_kg=2.0, offset_kg=-1.0, need_kg=18.0)
    assert interior.floor_applied is False
    assert abs(interior.actual_kg - 19.0) <= 1e-12


def test_policy_spy_rejects_private_access():
    spec = build_hand_spec(obligation=1)
    cfg, _ = load_simulator_config(ROOT)
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    car = next(iter(sim.engine.state["cars"].values()))
    spy = public_car_view(car, spy=True)
    assert isinstance(spy, SpyCar)
    continuation_intent(spy, required_compounds=1, remaining_laps=8)
    with pytest.raises(AssertionError, match="private field"):
        _ = spy["fuel_actual"]


def test_paired_future_isolation_and_divergence():
    cfg, _ = load_simulator_config(ROOT)
    result = check_causal(cfg)
    assert result["pass"], result
    assert result["identical_observations_before_reveal"]
    assert result["identical_decisions_before_reveal"]
    assert result["after_reveal_diverged"]
    assert result["spy_private_access_failed"]


def test_free_track_uses_analytic_tolerance():
    cfg, _ = load_simulator_config(ROOT)
    result = check_free_track(cfg)
    assert result["tolerance_s"] == 1e-6
    assert result["pass"], result


def test_common_commitment_and_exclusive_boundary():
    cfg, _ = load_simulator_config(ROOT)
    result = check_deadline(cfg)
    assert result["pass"], result["cases"]
    assert result["cases"]["boundary"] is True
    assert result["cases"]["just_before"] is True
    assert result["cases"]["just_after"] is True
    assert result["cases"]["common_commitment_epoch"] is True
    assert result["cases"]["missed_pit_now_not_next_lap"] is True


def test_sc_targeted_mechanics():
    cfg, _ = load_simulator_config(ROOT)
    result = check_sc_vsc(cfg)
    assert result["pass"], result
    assert result["no_on_track_sc_pass"] is True
    assert result["pit_exit_into_sc_train"] is True


def test_observation_canonical_equality_is_bytewise():
    cfg, _ = load_simulator_config(ROOT)
    spec = build_hand_spec(regime="SC", obligation=1)
    a = RaceSimulator(cfg)
    a.initialize(spec)
    a.advance_to_checkpoint()
    b = a.clone()
    assert canonical_json(a.observe().model_dump(mode="python")) == canonical_json(b.observe().model_dump(mode="python"))
