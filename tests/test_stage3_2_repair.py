"""Stage 3.2 independent regressions for R1–R6. Development fixtures, not experimental observations."""

from __future__ import annotations

import copy
import math
from pathlib import Path

import pytest

from f1q.errors import RejectionError
from f1q.simulator.classification import classify
from f1q.simulator.config import load_simulator_config
from f1q.simulator.engine import OVERTAKE_ORDER_SNAP_LAPS, distance
from f1q.simulator.followup import evaluate_resolution_row
from f1q.simulator.hand_specs import build_hand_spec
from f1q.simulator.interface import RaceSimulator

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cfg():
    return load_simulator_config(ROOT)[0]


def _fresh(cfg):
    sim = RaceSimulator(cfg)
    sim.initialize(build_hand_spec(obligation=1))
    return sim


def test_r1_pit_box_progress_uses_configured_geometry(cfg):
    entry = float(cfg["track"]["pit_entry_frac"])
    box = float(cfg["track"]["pit_box_frac"])
    exit_f = float(cfg["track"]["pit_exit_frac"])
    sim = _fresh(cfg)
    e = sim.engine
    car = next(iter(e.state["cars"].values()))
    cid = car["car_id"]
    car.update(
        completed_laps=10,
        frac=entry,
        pit_this_lap=True,
        pending_compound="medium",
        pending_set_id=f"{cid}.set.medium.0",
    )
    e.fire([("pit_entry", cid, {})])
    assert abs(distance(car) - (10.0 + entry)) < 1e-12
    progress = [distance(car)]
    while car["in_pit"]:
        e.state["t"] = car["pit_phase_end"]
        car["pit_clock_t"] = e.state["t"]
        e._advance_pit(car)
        progress.append(distance(car))
    # Nondecreasing racing-line progress
    assert all(progress[i + 1] + 1e-12 >= progress[i] for i in range(len(progress) - 1))
    # Box phases at ℓ+1 + box_frac (configured geometry)
    assert abs(progress[1] - (11.0 + box)) < 1e-9
    assert abs(progress[-1] - (11.0 + exit_f)) < 1e-9
    # Must not report phantom ℓ + entry after S/F cross
    assert progress[1] < 11.0 + entry - 0.5


def test_r1_queued_stop_box_not_leader_via_phantom_frac(cfg):
    sim = _fresh(cfg)
    e = sim.engine
    cars = list(e.state["cars"].values())
    leader = max(cars, key=distance)
    pitter = min(cars, key=distance)
    entry = float(cfg["track"]["pit_entry_frac"])
    pitter.update(
        completed_laps=int(leader["completed_laps"]),
        frac=entry,
        pit_this_lap=True,
        pending_compound="medium",
        pending_set_id=f"{pitter['car_id']}.set.medium.0",
    )
    e.fire([("pit_entry", pitter["car_id"], {})])
    e.state["t"] = pitter["pit_phase_end"]
    pitter["pit_clock_t"] = e.state["t"]
    e._advance_pit(pitter)
    assert pitter["pit_phase"] in {"service", "waiting"}
    assert distance(pitter) <= distance(leader) + 1.0 + 1e-9
    assert e.leader()["car_id"] != pitter["car_id"] or distance(pitter) >= distance(leader) - 1e-9


def test_r2_individual_finish_times_not_leader_stamp(cfg):
    from f1q.simulator.stage3_3_diagnostic import (
        assert_r2_individual_finish_invariants,
        historical_shared_leader_stamp_would_fail,
    )

    sim = _fresh(cfg)
    sim.advance_to_checkpoint()
    _, out = sim.continue_to_finish()
    summary = assert_r2_individual_finish_invariants(out, field_size=20)
    assert summary["n_defined"] == 1
    assert summary["n_absent"] == 19
    assert summary["classification_consistent"] is True
    assert out.get("classification_model") == (
        "leader_triggered_end_progress_primary_individual_finish_when_crossed"
    )
    # Historical all-cars/shared-leader-time shape must fail the same invariant.
    assert historical_shared_leader_stamp_would_fail(float(out["leader_finish_t"]), field_size=20)


def test_r2_historical_shared_leader_stamp_fails_invariant():
    from f1q.simulator.stage3_3_diagnostic import assert_r2_individual_finish_invariants

    # Synthetic engineering fixture mirroring the pre-repair defect shape.
    field_size = 20
    stamp = 3755.732088
    progress = {f"car.{i:02d}": float(field_size - i) for i in range(field_size)}
    fts = {cid: stamp for cid in progress}
    out = {
        "finish_time": fts,
        "progress": progress,
        "leader_finish_t": stamp,
        "leader_finish_car_id": "car.00",
        "ranking": classify(progress, fts),
        "classification_model": "historical_shared_leader_stamp_fixture",
    }
    with pytest.raises(AssertionError, match="exactly one defined"):
        assert_r2_individual_finish_invariants(out, field_size=field_size)


def test_r3_overtake_no_free_distance_on_finite_gap(cfg):
    sim = _fresh(cfg)
    e = sim.engine
    ids = list(e.state["cars"])
    ahead, passer = e.state["cars"][ids[0]], e.state["cars"][ids[1]]
    ahead.update(completed_laps=10, frac=0.5, tyre_age_laps=20.0)
    passer.update(completed_laps=10, frac=0.4999, tyre_age_laps=0.0)
    old = (distance(passer), passer["fuel_actual"], passer["tyre_age_laps"], e.state["t"])
    e.fire([("catch_or_pass", ids[1], {"ahead": ids[0]})])
    new = (distance(passer), passer["fuel_actual"], passer["tyre_age_laps"], e.state["t"])
    deltas = [v - u for u, v in zip(old, new)]
    assert deltas[0] == 0.0
    assert deltas[1] == 0.0 and deltas[2] == 0.0 and deltas[3] == 0.0


def test_r3_overtake_order_snap_only_at_crossing(cfg):
    sim = _fresh(cfg)
    e = sim.engine
    ids = list(e.state["cars"])
    ahead, passer = e.state["cars"][ids[0]], e.state["cars"][ids[1]]
    ahead.update(completed_laps=10, frac=0.5, tyre_age_laps=20.0)
    passer.update(completed_laps=10, frac=0.5 - OVERTAKE_ORDER_SNAP_LAPS / 2, tyre_age_laps=0.0)
    old_d, old_fuel, old_age, old_t = distance(passer), passer["fuel_actual"], passer["tyre_age_laps"], e.state["t"]
    e.fire([("catch_or_pass", ids[1], {"ahead": ids[0]})])
    assert passer["fuel_actual"] == old_fuel
    assert passer["tyre_age_laps"] == old_age
    assert e.state["t"] == old_t
    assert distance(passer) - old_d <= OVERTAKE_ORDER_SNAP_LAPS * 2 + 1e-15
    assert distance(passer) > distance(ahead)


def test_r4_late_vs_registered_epoch_keeps_fallback(cfg):
    sim = _fresh(cfg)
    ids = list(sim.engine.state["cars"])
    sim.advance_to_checkpoint()
    t0 = float(sim.engine.state["t"])
    early = sim.clone().consider_recommendation(
        {ids[0]: {"kind": "continuation"}},
        arrival_delay_s=0.05,
        commitment_epoch_race_s=t0 + 0.1,
    )
    late = sim.clone().consider_recommendation(
        {ids[0]: {"kind": "continuation"}},
        arrival_delay_s=0.2,
        commitment_epoch_race_s=t0 + 0.1,
    )
    assert early["timely"] is True
    assert early["selected_plan"] == "recommendation"
    assert abs(early["commitment_race_s"] - (t0 + 0.1)) < 1e-9
    assert late["timely"] is False
    assert late["late_vs_registered_epoch"] is True
    assert late["selected_plan"] == "fallback_continuation"
    assert abs(late["commitment_race_s"] - (t0 + 0.1)) < 1e-9
    assert late["registered_commitment_epoch_race_s"] == early["registered_commitment_epoch_race_s"]


def test_r4_rejects_nonfinite_and_out_of_window_epoch(cfg):
    sim = _fresh(cfg)
    ids = list(sim.engine.state["cars"])
    sim.advance_to_checkpoint()
    t0 = float(sim.engine.state["t"])
    with pytest.raises(RejectionError) as exc:
        sim.clone().consider_recommendation(
            {ids[0]: {"kind": "continuation"}},
            arrival_delay_s=float("nan"),
        )
    assert exc.value.code == "INVALID_COMMITMENT_PROTOCOL"
    with pytest.raises(RejectionError):
        sim.clone().consider_recommendation(
            {ids[0]: {"kind": "continuation"}},
            arrival_delay_s=-1.0,
        )
    with pytest.raises(RejectionError):
        sim.clone().consider_recommendation(
            {ids[0]: {"kind": "continuation"}},
            arrival_delay_s=0.0,
            commitment_epoch_race_s=t0 - 10.0,
        )


def test_r5_rejects_mismatch_and_rival_and_is_atomic(cfg):
    sim = _fresh(cfg)
    ids = list(sim.engine.state["cars"])
    selected = list(sim.engine.state["selected_car_ids"])
    prior = copy.deepcopy(sim.engine.state["policies"])
    with pytest.raises(RejectionError) as exc:
        sim.validate_plan(
            {selected[0]: {"kind": "pit_now", "compound": "hard", "set_id": f"{selected[0]}.set.medium.0"}}
        )
    assert "mismatch" in exc.value.reason
    rival = next(c for c in ids if c not in selected)
    with pytest.raises(RejectionError) as exc2:
        sim.validate_plan({rival: {"kind": "continuation"}})
    assert "selected_car_ids" in exc2.value.reason
    # Atomicity: rejected second car must not leave first mutated
    bad = {
        selected[0]: {"kind": "continuation"},
        selected[1]: {"kind": "pit_now", "compound": "hard", "set_id": f"{selected[1]}.set.medium.0"},
    }
    try:
        sim.apply_plan(bad)
        raised = False
    except RejectionError:
        raised = True
    assert raised
    assert sim.engine.state["policies"] == prior


def test_r6_injected_checker_failures():
    def base_row():
        events = {("pit_entry", "car.a"): [100.0], ("pit_exit", "car.a"): [110.0]}
        return {
            "finish_times": {"car.a": 200.0, "car.b": 201.0},
            "progress": {"car.a": 34.0, "car.b": 33.5},
            "ranks": {"car.a": 1, "car.b": 2},
            "events": events,
            "classification_order": ["car.a", "car.b"],
            "legality_ok": True,
        }

    h = base_row()
    h2 = copy.deepcopy(h)
    h4 = copy.deepcopy(h)
    ok = evaluate_resolution_row(
        episode_id="inj.ok", family_id="inj", regime="SC", h=h, h2=h2, h4=h4
    )
    assert ok["row_status"] == "PASS"
    assert ok["pit_gate"] == "PASS"

    missing = copy.deepcopy(h4)
    missing["events"] = {("pit_entry", "car.a"): [100.0]}  # exit missing
    bad_missing = evaluate_resolution_row(
        episode_id="inj.missing", family_id="inj", regime="SC", h=h, h2=h2, h4=missing
    )
    assert bad_missing["pit_gate"] == "FAIL"
    assert bad_missing["row_status"] == "FAIL"

    count = copy.deepcopy(h4)
    count["events"] = {
        ("pit_entry", "car.a"): [100.0, 100.5],
        ("pit_exit", "car.a"): [110.0],
    }
    bad_count = evaluate_resolution_row(
        episode_id="inj.count", family_id="inj", regime="SC", h=h, h2=h2, h4=count
    )
    assert bad_count["pit_gate"] == "FAIL"

    illegal = copy.deepcopy(h4)
    illegal["legality_ok"] = False
    bad_leg = evaluate_resolution_row(
        episode_id="inj.leg", family_id="inj", regime="SC", h=h, h2=h2, h4=illegal
    )
    assert bad_leg["legality_stable"] is False
    assert bad_leg["row_status"] == "FAIL"

    flip = copy.deepcopy(h4)
    flip["ranks"] = {"car.a": 2, "car.b": 1}
    flip["classification_order"] = ["car.b", "car.a"]
    flip["progress"] = {"car.a": 33.0, "car.b": 34.0}  # well separated
    flip["finish_times"] = {"car.a": 210.0, "car.b": 200.0}
    bad_rank = evaluate_resolution_row(
        episode_id="inj.rank", family_id="inj", regime="SC", h=h, h2=h2, h4=flip
    )
    assert bad_rank["rank_flip_h_h2_h4"] is True
    assert bad_rank["row_status"] != "PASS"
    assert bad_rank["near_tie_from_same_run_gap"] is False
