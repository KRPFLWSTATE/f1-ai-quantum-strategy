"""A3 causal path, QUBO agreement, partitions, inexpensive E2E smoke."""

from __future__ import annotations

from f1q.a3.loop import adversarial_validation, family_spec
from f1q.a3.partitions import build_a3_partitions
from f1q.a3.problem import (
    build_a3_qubo,
    build_menu_and_instance,
    extract_causal_view,
    verify_direct_cost_qubo_agreement,
)
from f1q.simulator.interface import RaceSimulator


def test_partitions_isolated_and_final_test_sealed():
    p = build_a3_partitions()
    assert p["ok"] is True
    assert p["planned"]["anchors"] == 24
    assert p["planned"]["training"] == 120
    assert p["planned"]["tuning"] == 80
    assert p["planned"]["calibration"] == 24
    assert p["final_test"]["n_blocks"] == 80
    assert p["final_test"]["outcomes_materialised"] is False
    assert p["final_test"]["outcomes_opened"] is False
    assert not p["overlap_open_vs_finaltest"]
    assert not p["a2_id_reuse"]


def test_adversarial_causal_fixtures():
    r = adversarial_validation()
    assert r["not_flag_only_wrapper"] is True
    assert r["cases"]["identical_observables_different_hidden_same_policy"]
    assert r["cases"]["future_duration_leakage_rejected"]
    assert r["cases"]["late_results_frozen_classical_fallback"]
    assert r["cases"]["accepted_actions_use_actual_simulator_continuation"]
    assert r["cases"]["evaluator_from_continuation_not_proxy_qubo"]
    assert r["ok"] is True


def test_qubo_direct_cost_agreement_and_e2e_smoke():
    spec = family_spec(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a3.smoke.block",
        regime="SC",
        partition="development",
        index=0,
        seed=7,
    )
    sim = RaceSimulator()
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    obs = sim.observe()
    view = extract_causal_view(obs)
    inst = build_menu_and_instance(view)
    qubo = build_a3_qubo(inst)
    agr = verify_direct_cost_qubo_agreement(inst, qubo)
    assert agr["ok"] is True
    assert qubo["n"] == inst.n_logical_vars()
    plan = {cid: {"kind": "continuation"} for cid in spec["selected_car_ids"]}
    rec = sim.consider_recommendation(plan, arrival_delay_s=0.01, common_commit_delay_s=0.05)
    _st, outcome = sim.continue_to_finish()
    assert rec["selected_plan"] in {"recommendation", "fallback_continuation"}
    assert "normalized_team_rank_loss" in outcome["team_loss"]
    assert outcome["team_loss"]["not_proxy_objective"] is True
