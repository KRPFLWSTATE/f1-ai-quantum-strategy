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
                "pit_entry_event_index": 5,
                "service_complete_event_index": 7,
                "evidence_source": "pit_entry.detail.pit_entry_completed_laps",
                "entry_lap_provenance": "post_checkpoint_pit_entry_paired",
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
                "pit_entry_event_index": 5,
                "service_complete_event_index": 7,
                "evidence_source": "pit_entry.detail.pit_entry_completed_laps",
                "entry_lap_provenance": "post_checkpoint_pit_entry_paired",
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
                "pit_entry_event_index": 5,
                "service_complete_event_index": 7,
                "evidence_source": "pit_entry.detail.pit_entry_completed_laps",
                "entry_lap_provenance": "post_checkpoint_pit_entry_paired",
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


def test_timing_provenance_named_episode_delay_laps_entry_lap_32():
    from f1q.formulation.actions import build_joint_plan, simulator_plan_payload
    from f1q.formulation.evaluator import evaluate_joint_plan_from_checkpoint_sim, executed_stops_from_events

    cfg, _ = load_simulator_config(ROOT)
    spec = next(s for s in load_preview_specs(ROOT) if s["episode_id"].endswith("/0000/episode/00/SC"))
    selected = list(spec["selected_car_ids"])
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    cxi = len(list(sim.engine.state.get("events") or []))
    public = _physics(cfg, spec)
    am = generate_action_model(sim.observe(), public, selected_car_ids=selected)
    a = next(x for x in am["menus"][selected[0]] if x["kind"] == "delay_laps" and x.get("delay_laps") == 2)
    b = next(x for x in am["menus"][selected[1]] if x["kind"] == "delay_laps" and x.get("delay_laps") == 2)
    ev = evaluate_joint_plan_from_checkpoint_sim(
        checkpoint_sim=sim,
        spec=spec,
        action_a=a,
        action_b=b,
        checkpoint_event_index=cxi,
        decision_time=float(sim.engine.state["t"]),
    )
    assert ev["checkpoint_event_index"] == cxi
    assert ev["semantic_legal"] is True
    clone = sim.clone()
    clone.apply_plan(
        simulator_plan_payload(
            build_joint_plan(CarAction.model_validate(a), CarAction.model_validate(b), selected)
        )
    )
    clone.continue_to_finish()
    events = list(clone.engine.state.get("events") or [])
    for cid in selected:
        stops = executed_stops_from_events(events, cid, checkpoint_event_index=cxi)
        assert len(stops) >= 1
        assert stops[0]["pit_entry_completed_laps"] == 32
        assert stops[0]["pit_entry_event_index"] is not None
        assert stops[0]["pit_entry_event_index"] >= cxi
        assert stops[0]["service_complete_event_index"] > stops[0]["pit_entry_event_index"]
        pe = events[stops[0]["pit_entry_event_index"]]["detail"]["pit_entry_completed_laps"]
        sc = events[stops[0]["service_complete_event_index"]]["detail"]["pit_entry_completed_laps"]
        assert pe == sc == 32
        assert ev["instructed_versus_executed"][cid]["timing_reason"] == "delay_laps_exact_entry_lap"


def test_timing_provenance_fail_closed_on_missing_and_mismatch_and_contradiction():
    action = _action(
        action_id="c|delay_laps|2|soft|s1",
        car_id="c",
        kind="delay_laps",
        compound="soft",
        set_id="s1",
        delay_laps=2,
    )
    good = {
        "set_id": "s1",
        "compound": "soft",
        "pit_lap_index": 32,
        "pit_entry_completed_laps": 32,
        "pit_entry_event_index": 10,
        "service_complete_event_index": 12,
        "evidence_source": "pit_entry.detail.pit_entry_completed_laps",
        "entry_lap_provenance": "post_checkpoint_pit_entry_paired",
    }
    ok = check_action_semantics(
        action=action,
        executed=[good],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=30,
        pit_entry_completed_laps=32,
        terminal_car={"mounted_set_id": "s1"},
    )
    assert ok["timing_ok"] is True
    assert ok["timing_reason"] == "delay_laps_exact_entry_lap"

    missing = dict(good)
    missing["pit_entry_completed_laps"] = None
    missing["pit_lap_index"] = None
    bad_missing = check_action_semantics(
        action=action,
        executed=[missing],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=30,
        pit_entry_completed_laps=None,
        terminal_car={"mounted_set_id": "s1"},
    )
    assert bad_missing["timing_ok"] is False
    assert bad_missing["timing_reason"] == "missing_pit_entry_completed_laps"

    for wrong in (31, 33):
        mismatched = dict(good, pit_entry_completed_laps=wrong, pit_lap_index=wrong)
        bad = check_action_semantics(
            action=action,
            executed=[mismatched],
            expected=[],
            decision_time=100.0,
            checkpoint_completed_laps=30,
            pit_entry_completed_laps=wrong,
            terminal_car={"mounted_set_id": "s1"},
        )
        assert bad["timing_ok"] is False
        assert bad["timing_reason"] == "delay_laps_entry_lap_mismatch"

    contra = dict(good, evidence_source="contradictory_pit_entry_and_service_complete", pit_entry_completed_laps=None)
    bad_c = check_action_semantics(
        action=action,
        executed=[contra],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=30,
        pit_entry_completed_laps=None,
        terminal_car={"mounted_set_id": "s1"},
    )
    assert bad_c["timing_ok"] is False
    assert bad_c["timing_reason"] == "contradictory_pit_entry_and_service_complete"


def test_continuation_pre_checkpoint_entry_provenance_still_valid():
    action = _action(
        action_id="c|continuation|pol",
        car_id="c",
        kind="continuation",
        compound=None,
        set_id=None,
    )
    executed = [
        {
            "set_id": "s1",
            "compound": "soft",
            "pit_lap_index": 29,
            "pit_entry_completed_laps": 29,
            "pit_entry_event_index": None,
            "service_complete_event_index": 50,
            "evidence_source": "continuation_pre_checkpoint_entry_via_service_complete.detail.pit_entry_completed_laps",
            "entry_lap_provenance": "continuation_pre_checkpoint_service_complete",
        }
    ]
    expected = [
        {
            "set_id": "s1",
            "compound": "soft",
            "pit_lap_index": 29,
            "source": "commitment",
            "kind": "committed_service",
        }
    ]
    check = check_action_semantics(
        action=action,
        executed=executed,
        expected=expected,
        decision_time=100.0,
        checkpoint_completed_laps=30,
        pit_entry_completed_laps=29,
        terminal_car={"mounted_set_id": "s1", "compound": "soft"},
    )
    assert check["timing_ok"] is True
    assert "continuation" in check["timing_reason"]


def test_checkpoint_event_index_captured_before_plan_application():
    cfg, _ = load_simulator_config(ROOT)
    spec = next(s for s in load_preview_specs(ROOT) if s["episode_id"].endswith("/0000/episode/00/SC"))
    selected = list(spec["selected_car_ids"])
    public = _physics(cfg, spec)
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    before = len(list(sim.engine.state.get("events") or []))
    am = generate_action_model(sim.observe(), public, selected_car_ids=selected)
    a = am["menus"][selected[0]][0]
    b = am["menus"][selected[1]][0]
    ev = evaluate_joint_plan_on_checkpoint(cfg=cfg, spec=spec, action_a=a, action_b=b)
    assert ev["checkpoint_event_index"] == before


def test_version_provenance_package_yaml_engine_agree():
    from f1q import INTERFACE_VERSION as PKG_IFACE
    from f1q import SIMULATOR_VERSION as PKG_SIM
    from f1q.simulator.config import INTERFACE_VERSION, SIMULATOR_VERSION, load_simulator_config

    assert PKG_SIM == SIMULATOR_VERSION == "1.0.4"
    assert PKG_IFACE == INTERFACE_VERSION == "3.1.0"
    cfg, _ = load_simulator_config(ROOT)
    assert cfg["simulator_version"] == "1.0.4"
    assert cfg["interface_version"] == "3.1.0"
    spec = load_preview_specs(ROOT)[0]
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    assert sim.engine.state["simulator_version"] == "1.0.4"
    assert sim.engine.state["interface_version"] == "3.1.0"


def test_real_json_round_trip_is_not_rebuild_twice():
    from f1q.formulation.round_trip import real_plan_round_trip

    cfg, _ = load_simulator_config(ROOT)
    spec = load_preview_specs(ROOT)[0]
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    obs = sim.observe()
    public = _physics(cfg, spec)
    cars = list(spec["selected_car_ids"])
    am = generate_action_model(obs, public, selected_car_ids=cars)
    a = CarAction.model_validate(am["menus"][cars[0]][0])
    b = CarAction.model_validate(am["menus"][cars[1]][0])
    rt = real_plan_round_trip(sim, a, b, cars)
    assert rt["ok"] is True
    assert "canonical_json" in rt["method"]


def test_mixed_crew_real_checkpoint_and_positive_overlap_fixture():
    from f1q.formulation.compiler import _incremental_pair_wait

    cfg, _ = load_simulator_config(ROOT)
    spec = next(s for s in load_preview_specs(ROOT) if s["episode_id"].endswith("/0001/episode/02/SC"))
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    obs = sim.observe()
    d = obs.model_dump(mode="python")
    public = _physics(cfg, spec)
    cars = list(spec["selected_car_ids"])
    in_pit = [c for c in d["cars"] if c["car_id"] in cars and c.get("in_pit_lane")]
    on_track = [c for c in d["cars"] if c["car_id"] in cars and not c.get("in_pit_lane")]
    assert len(in_pit) == 1 and len(on_track) == 1
    am = generate_action_model(obs, public, selected_car_ids=cars)
    stop = next(a for a in am["menus"][on_track[0]["car_id"]] if a["kind"] in {"pit_now", "delay_laps"})
    cont = next(a for a in am["menus"][in_pit[0]["car_id"]] if a["kind"] == "continuation")
    pred_a = predicted_service_interval(d, public, CarAction.model_validate(stop))
    pred_b = predicted_service_interval(d, public, CarAction.model_validate(cont))
    reasons = {pred_a["reason"], pred_b["reason"]}
    assert pred_a["coordinate"] == pred_b["coordinate"] == "service_interval_absolute_race_s"
    assert "on_track_entry_plus_public_t_in" in reasons
    assert "committed_remaining_service" in reasons
    costs = compile_action_costs(
        obs, public, menus={on_track[0]["car_id"]: [stop], in_pit[0]["car_id"]: [cont]}, selected_car_ids=cars
    )
    pair = costs["pair_details"][0][0]
    expected, _ = _incremental_pair_wait(
        pred_a["interval"],
        pred_b["interval"],
        committed_wait_a=float(pred_a.get("committed_wait_already_counted_s") or 0.0),
        committed_wait_b=float(pred_b.get("committed_wait_already_counted_s") or 0.0),
    )
    assert abs(float(pair["pair_s"]) - expected) <= 1e-12
    synth, _ = _incremental_pair_wait([100.0, 102.5], [101.0, 103.5], committed_wait_a=0.0, committed_wait_b=0.5)
    assert abs(synth - 1.0) <= 1e-12 and synth > 0.0


def test_historical_panel_recompute_requires_reversal_and_tie_loss():
    import json
    from collections import Counter

    from f1q.formulation.panel import EVALUATOR_RANK_TOLERANCE, TOLERANCE_S, classify_order_relation
    from f1q.hashing import sha256_file

    panel_path = (
        ROOT
        / "evidence/formulation/artifacts/e85ee977-8a35-40c1-b690-02724dea3228"
        / "formulation.evaluator_separation_panel/evaluator_panel.json"
    )
    assert panel_path.is_file()
    panel = json.loads(panel_path.read_text(encoding="utf-8"))
    digest = sha256_file(panel_path)
    assert len(digest) == 64
    recomputed: Counter[str] = Counter()
    for case in panel["cases"]:
        paired = []
        for entry in case.get("evaluations") or []:
            ev = entry.get("evaluator") or {}
            if ev.get("semantic_legal") and "team_rank_loss_L" in ev:
                paired.append((float(entry["proxy_value"]), float(ev["team_rank_loss_L"])))
        if len(paired) < 2:
            recomputed["insufficient_unique_plans"] += 1
            continue
        rel = classify_order_relation(
            [p for p, _ in paired],
            [e for _, e in paired],
            proxy_tol=TOLERANCE_S,
            eval_tol=EVALUATOR_RANK_TOLERANCE,
        )
        recomputed[str(rel["relation"])] += 1
    assert recomputed["reversal"] >= 1
    assert recomputed["tie_loss_of_discrimination"] >= 1


def test_legacy_counts_from_git_tracked_records():
    from f1q.formulation.legacy_counts import count_committed_record_json, legacy_archive_summary

    assert count_committed_record_json(ROOT, "e85ee977-8a35-40c1-b690-02724dea3228") == 40
    assert count_committed_record_json(ROOT, "41c28597-0ce0-428f-8230-ba2ca973c5b7") == 21
    summary = legacy_archive_summary(ROOT)
    assert summary["legacy_gate_action"] == "ARCHIVED_DO_NOT_RESUME"
    assert "21 archived" in summary["41c28597"]["description"]


def test_status_does_not_suggest_resume_for_archived_legacy():
    from f1q.status import run_status

    st = run_status(ROOT)
    assert st["LEGACY_GATE_ACTION"] == "ARCHIVED_DO_NOT_RESUME"
    assert st["LEGACY_EXHAUSTIVE_GATE"] == "PARTIAL"
    assert st["QPU_EXECUTION_AUTHORISED"] is False
    nxt = st.get("next_permitted_work") or ""
    for rid in ("e85ee977-8a35-40c1-b690-02724dea3228", "41c28597-0ce0-428f-8230-ba2ca973c5b7"):
        assert f"resume --run-id {rid}" not in nxt
