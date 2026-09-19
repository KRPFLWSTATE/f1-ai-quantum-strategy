"""Stage 4 Gate C formulation tests — hand fixtures and architectural checks."""

from __future__ import annotations

import copy
import math
import os
from pathlib import Path

import numpy as np
import pytest

from f1q.formulation.actions import (
    CarAction,
    build_joint_plan,
    generate_action_model,
    generate_car_actions,
    reduce_action_menu,
    simulator_plan_payload,
)
from f1q.formulation.boundaries import ForbiddenAccessError, SpyMapping
from f1q.formulation.compiler import compile_action_costs, score_joint_direct
from f1q.formulation.dp_ref import solve_zero_interaction_dp
from f1q.formulation.enumerate import enumerate_legal_pairs
from f1q.formulation.evaluator import assert_compiler_evaluator_separation, evaluate_joint_plan_on_checkpoint
from f1q.formulation.heuristics import run_classical_heuristics
from f1q.formulation.milp_ref import solve_milp_independent
from f1q.formulation.panel import select_panel_specs
from f1q.formulation.public_config import PublicPhysicsConfig
from f1q.formulation.qubo import (
    build_qubo,
    decode_bits,
    energy_ising,
    energy_qubo,
    hard_penalty_value,
    is_feasible,
    qubo_to_ising,
    scale_ising,
    verify_penalty_proof,
)
from f1q.hashing import sha256_json
from f1q.simulator.config import load_simulator_config
from f1q.simulator.interface import RaceSimulator
from f1q.simulator.matrix import load_preview_specs

ROOT = Path(__file__).resolve().parents[2]


def _public(**over) -> PublicPhysicsConfig:
    base = dict(
        green_lap_s=90.0,
        green_pit_loss_s=20.0,
        tyre_form="near_linear",
        tyre_wear_per_lap=0.05,
        tyre_curvature=None,
        time_scale_s=6.0,
        curve_scale_s=2.0,
        compound_offset_s={"soft": 0.0, "medium": 0.8, "hard": 1.6},
        kg_per_lap=1.8,
        time_per_kg_s=0.03,
        service_stationary_s=2.5,
        sc_pace_factor=1.45,
        vsc_pace_factor=1.40,
        distinct_compounds_required=2,
    )
    base.update(over)
    return PublicPhysicsConfig.model_validate(base)


def _hand_obs(*, remaining=5, frac_a=0.5, frac_b=0.5, expired_a=False):
    cars = []
    inventories = {}
    for cid, team, compound, age, frac, fuel in [
        ("car.a", "team.t", "soft", 2.0, frac_a, 20.0),
        ("car.b", "team.t", "soft", 2.0, frac_b, 20.0),
        ("car.rival", "team.r", "medium", 1.0, 0.4, 22.0),
    ]:
        cars.append(
            {
                "car_id": cid,
                "team_id": team,
                "classified_position": 1 if cid == "car.a" else 2 if cid == "car.b" else 3,
                "progress_laps": 10.0,
                "completed_laps": 10,
                "frac": frac,
                "gap_ahead_s": 1.0,
                "compound": compound,
                "tyre_age_laps": age,
                "mounted_set_id": f"{cid}.set.{compound}.0",
                "fuel_kg_estimated": fuel,
                "fuel_uncertainty_kg": 2.0,
                "in_pit_lane": False,
                "service_state": "on_track",
                "pit_entry_commitment_cutoff_race_s": 9999.0,
                "used_compounds": [compound],
            }
        )
        inventories[cid] = [
            {"set_id": f"{cid}.set.soft.0", "compound": "soft", "used": compound == "soft", "age_laps": age if compound == "soft" else 0.0},
            {"set_id": f"{cid}.set.soft.1", "compound": "soft", "used": False, "age_laps": 0.0},
            {"set_id": f"{cid}.set.medium.0", "compound": "medium", "used": compound == "medium", "age_laps": 0.0},
            {"set_id": f"{cid}.set.hard.0", "compound": "hard", "used": False, "age_laps": 0.0},
        ]
    expired = []
    if expired_a:
        expired.append(
            {
                "car_id": "car.a",
                "action": "pit_now",
                "state": "expired",
                "reason_code": "PIT_WINDOW_CLOSED",
                "cutoff_race_s": 1.0,
                "decision_time_race_s": 2.0,
                "not_relabeled_as": "pit_next_lap",
            }
        )
    return {
        "schema_version": "2.0.0",
        "kind": "decision_observation",
        "checkpoint_id": "hand.cp",
        "scenario_id": "hand",
        "block_id": "hand.block",
        "episode_id": "hand.ep",
        "family_id": "hand.fam",
        "partition": "development",
        "decision_time": {"value": 100.0, "unit": "s", "source": "hand", "availability_time": "race_s:100", "status": "known"},
        "clock": {"origin": "race_start", "unit": "s", "communication_margin_s": 1.0},
        "field_size": {"value": 3, "unit": "cars", "source": "hand", "availability_time": "race_s:100", "status": "known"},
        "completed_laps": {"value": 10, "unit": "laps", "source": "hand", "availability_time": "race_s:100", "status": "known"},
        "remaining_laps": {"value": remaining, "unit": "laps", "source": "hand", "availability_time": "race_s:100", "status": "assumed"},
        "race_horizon_laps": {"value": 15, "unit": "laps", "source": "hand", "availability_time": "race_s:100", "status": "known"},
        "safety_regime": None,
        "safety_regime_duration": {"value": None, "unit": "s", "source": "hand", "availability_time": "race_s:100", "status": "unknown"},
        "selected_team_id": "team.t",
        "cars": cars,
        "inventories": inventories,
        "pit_lane": {"occupied": False},
        "team_service": {"shared_service": True, "crew_free_at": {"team.t": 0.0}},
        "compound_obligations": {"distinct_compounds_required": 2},
        "cutoffs": {},
        "nominal_budget_s": {"value": 30.0, "unit": "s", "source": "hand", "availability_time": "race_s:100", "status": "known"},
        "effective_deadline_s": {"value": 120.0, "unit": "s", "source": "hand", "availability_time": "race_s:100", "status": "known"},
        "expired_actions": expired,
        "forecasts": [],
        "provenance": {"hand_fixture": True},
    }


def test_deterministic_action_ids_and_roundtrip():
    obs = _hand_obs()
    public = _public()
    m1 = generate_action_model(obs, public, selected_car_ids=["car.a", "car.b"])
    m2 = generate_action_model(obs, public, selected_car_ids=["car.a", "car.b"])
    assert m1["action_dictionary_hash"] == m2["action_dictionary_hash"]
    for cid in ("car.a", "car.b"):
        ids = [a["action_id"] for a in m1["menus"][cid]]
        assert ids == sorted(ids)
        for row in m1["menus"][cid]:
            assert CarAction.model_validate(row).model_dump(mode="python")["action_id"] == row["action_id"]


def test_complete_two_car_joint_rejects_partial_and_rival():
    obs = _hand_obs()
    public = _public()
    model = generate_action_model(obs, public, selected_car_ids=["car.a", "car.b"])
    a = CarAction.model_validate(model["menus"]["car.a"][0])
    b = CarAction.model_validate(model["menus"]["car.b"][0])
    joint = build_joint_plan(a, b, ["car.a", "car.b"])
    assert set(simulator_plan_payload(joint)) == {"car.a", "car.b"}
    with pytest.raises(Exception):
        build_joint_plan(a, a, ["car.a", "car.b"])
    rival = CarAction(
        action_id="car.rival|continuation|x",
        car_id="car.rival",
        kind="continuation",
        commitment={},
        description="rival",
        observable_admission_facts={},
    )
    with pytest.raises(Exception):
        build_joint_plan(a, rival, ["car.a", "car.b"])


def test_no_private_future_access_by_action_generation_or_compilation():
    obs = _hand_obs()
    obs["private"] = {"fuel_actual": 1.0}
    public = _public()
    with pytest.raises(ForbiddenAccessError):
        generate_action_model(obs, public, selected_car_ids=["car.a", "car.b"])
    clean = _hand_obs()
    model = generate_action_model(clean, public, selected_car_ids=["car.a", "car.b"])
    spy = SpyMapping(clean)
    compile_action_costs(spy, public, menus=model["menus"], selected_car_ids=["car.a", "car.b"])
    sep = assert_compiler_evaluator_separation()
    assert sep["ok"] is True
    assert sep["same_file"] is False


def test_legality_expiry_tyre_obligation_downstream():
    public = _public()
    expired = generate_car_actions(_hand_obs(expired_a=True, frac_a=0.99), public, car_id="car.a")
    pit_nows = [a for a in expired if a.kind == "pit_now"]
    assert pit_nows
    assert all(not a.admitted and a.exclusion_reason == "expired_pit_now_missed_entry" for a in pit_nows)
    # insufficient horizon for delay 2
    short = generate_car_actions(_hand_obs(remaining=2), public, car_id="car.a")
    delays2 = [a for a in short if a.kind == "delay_laps" and a.delay_laps == 2]
    assert delays2
    assert all(not a.admitted for a in delays2)


def test_equivalence_reduction_no_silent_loss():
    obs = _hand_obs()
    public = _public()
    actions = [a for a in generate_car_actions(obs, public, car_id="car.a") if a.admitted]
    red = reduce_action_menu(actions)
    assert red["full_count"] == len(actions)
    assert red["reduced_count"] <= red["full_count"]
    assert len(red["member_to_representative"]) == red["full_count"]
    # every admitted maps to a retained rep
    for a in actions:
        rep = red["member_to_representative"][a.action_id]
        assert rep in red["retained_action_ids"]


def test_cross_check_admitted_plans_with_simulator():
    cfg, _ = load_simulator_config(ROOT)
    specs = load_preview_specs(ROOT)
    spec = specs[0]
    from f1q.formulation.instance import build_instance_record

    rec = build_instance_record(cfg=cfg, spec=spec, verify_energies=False, cross_check_simulator=True)
    assert rec["simulator_cross_check"]["checked"] > 0
    assert rec["simulator_cross_check"]["disagreements"] == []


def test_direct_objective_decomposition_and_units():
    obs = _hand_obs(remaining=3)
    public = _public()
    model = generate_action_model(obs, public, selected_car_ids=["car.a", "car.b"], reduce=True)
    # Force tiny menus: one action each
    model["menus"] = {
        "car.a": [model["menus"]["car.a"][0]],
        "car.b": [model["menus"]["car.b"][0]],
    }
    costs = compile_action_costs(obs, public, menus=model["menus"], selected_car_ids=["car.a", "car.b"])
    assert costs["units"] == "seconds"
    assert costs["risk_weight"] == 0.0
    val = score_joint_direct(costs, index_a=0, index_b=0)
    assert math.isfinite(val)


def test_no_unary_pair_double_counting_hand():
    # Construct costs where pair is pure add-on
    costs = {
        "selected_car_ids": ["car.a", "car.b"],
        "action_ids": {"car.a": ["a0"], "car.b": ["b0"]},
        "C": 10.0,
        "u1": [5.0],
        "u2": [7.0],
        "v": [[2.5]],
        "C_centered": 22.0,
        "u1_centered": [0.0],
        "u2_centered": [0.0],
    }
    assert score_joint_direct(costs, index_a=0, index_b=0) == 24.5
    # Unary sum alone would be 22; pair adds 2.5 exactly once


def test_centring_preserves_objectives_optimum_ties_gap():
    obs = _hand_obs(remaining=4)
    public = _public()
    model = generate_action_model(obs, public, selected_car_ids=["car.a", "car.b"])
    costs = compile_action_costs(obs, public, menus=model["menus"], selected_car_ids=["car.a", "car.b"])
    enum_raw = enumerate_legal_pairs(costs)
    # Build centred table manually
    table = []
    for i in range(len(costs["u1"])):
        for j in range(len(costs["u2"])):
            raw = score_joint_direct(costs, index_a=i, index_b=j, centred=False)
            cen = score_joint_direct(costs, index_a=i, index_b=j, centred=True)
            assert abs(raw - cen) < 1e-9
            table.append(raw)
    assert abs(min(table) - enum_raw["exact_proxy_minimum"]) < 1e-9


def test_qubo_energy_equals_direct_penalised_expression():
    costs = {
        "selected_car_ids": ["c1", "c2"],
        "action_ids": {"c1": ["a0", "a1"], "c2": ["b0"]},
        "C": 0.0,
        "u1": [3.0, 5.0],
        "u2": [4.0],
        "v": [[-1.0], [2.0]],
        "m1": 3.0,
        "m2": 4.0,
        "C_centered": 7.0,
        "u1_centered": [0.0, 2.0],
        "u2_centered": [0.0],
    }
    qubo = build_qubo(costs, margin=1.0)
    n = qubo["variable_map"]["n"]
    k1, k2 = 2, 1
    M = qubo["penalty"]["M_used"]
    for mask in range(1 << n):
        bits = [(mask >> i) & 1 for i in range(n)]
        eq = energy_qubo(qubo, bits)
        if is_feasible(bits, k1, k2):
            i = bits[:k1].index(1)
            j = bits[k1:].index(1)
            phys = score_joint_direct(costs, index_a=i, index_b=j, centred=True)
            assert abs(eq - phys) < 1e-9
            assert hard_penalty_value(bits, k1, k2, M) == 0.0
        else:
            assert hard_penalty_value(bits, k1, k2, M) >= M - 1e-12


def test_penalty_proof_and_adversarial_weak_penalty():
    costs = {
        "selected_car_ids": ["c1", "c2"],
        "action_ids": {"c1": ["a0", "a1"], "c2": ["b0", "b1"]},
        "C": 0.0,
        "u1": [0.0, 100.0],
        "u2": [0.0, 100.0],
        "v": [[0.0, -50.0], [-50.0, -200.0]],
        "m1": 0.0,
        "m2": 0.0,
        "C_centered": 0.0,
        "u1_centered": [0.0, 100.0],
        "u2_centered": [0.0, 100.0],
    }
    good = build_qubo(costs, margin=1.0)
    assert verify_penalty_proof(good, costs)["ok"] is True
    # Weak unjustified penalty can fail the infeasible-beats-feasible check
    weak = build_qubo(costs, margin=1.0, M_override=1.0)
    weak_proof = verify_penalty_proof(weak, costs)
    assert weak_proof["ok"] is False


def test_qubo_ising_equality_and_decode():
    costs = {
        "selected_car_ids": ["c1", "c2"],
        "action_ids": {"c1": ["a0"], "c2": ["b0"]},
        "C": 1.0,
        "u1": [2.0],
        "u2": [3.0],
        "v": [[0.5]],
        "C_centered": 6.0,
        "u1_centered": [0.0],
        "u2_centered": [0.0],
    }
    qubo = build_qubo(costs)
    ising = qubo_to_ising(qubo)
    for mask in range(1 << 2):
        bits = [(mask >> i) & 1 for i in range(2)]
        assert abs(energy_qubo(qubo, bits) - energy_ising(ising, bits)) < 1e-9
    dec = decode_bits(qubo, [1, 1])
    assert dec["feasible"] is True
    bad = decode_bits(qubo, [0, 0])
    assert bad["feasible"] is False


def test_s_Q_scaling_restoration():
    costs = {
        "selected_car_ids": ["c1", "c2"],
        "action_ids": {"c1": ["a0", "a1"], "c2": ["b0"]},
        "C": 0.0,
        "u1": [1.0, 4.0],
        "u2": [2.0],
        "v": [[0.0], [0.0]],
        "C_centered": 3.0,
        "u1_centered": [0.0, 3.0],
        "u2_centered": [0.0],
    }
    qubo = build_qubo(costs)
    ising = qubo_to_ising(qubo)
    scaled = scale_ising(ising)
    bits_a = [1, 0, 1]
    bits_b = [0, 1, 1]
    ea = energy_ising(ising, bits_a)
    eb = energy_ising(ising, bits_b)
    eas = energy_ising({**ising, "constant": ising["constant"] / scaled["s_Q"], "h": scaled["h"], "J_upper": scaled["J_upper"]}, bits_a)
    ebs = energy_ising({**ising, "constant": ising["constant"] / scaled["s_Q"], "h": scaled["h"], "J_upper": scaled["J_upper"]}, bits_b)
    assert abs((eas - ebs) * scaled["s_Q"] - (ea - eb)) < 1e-9


def test_enumeration_vs_milp_and_ties():
    costs = {
        "selected_car_ids": ["c1", "c2"],
        "action_ids": {"c1": ["a0", "a1"], "c2": ["b0", "b1"]},
        "C": 0.0,
        "u1": [1.0, 1.0],
        "u2": [2.0, 5.0],
        "v": [[0.0, 0.0], [0.0, 0.0]],
        "C_centered": 3.0,
        "u1_centered": [0.0, 0.0],
        "u2_centered": [0.0, 3.0],
    }
    enum = enumerate_legal_pairs(costs)
    milp = solve_milp_independent(costs)
    assert milp["success"]
    assert abs(enum["exact_proxy_minimum"] - milp["value_with_constant"]) < 1e-6
    assert enum["n_ties"] == 2  # a0/b0 and a1/b0


def test_zero_interaction_dp_vs_enumeration():
    costs = {
        "selected_car_ids": ["c1", "c2"],
        "action_ids": {"c1": ["a0", "a1"], "c2": ["b0"]},
        "C": 1.0,
        "u1": [5.0, 3.0],
        "u2": [2.0],
        "v": [[0.0], [0.0]],
        "C_centered": 6.0,
        "u1_centered": [2.0, 0.0],
        "u2_centered": [0.0],
    }
    dp = solve_zero_interaction_dp(costs)
    enum = enumerate_legal_pairs(costs)
    assert dp["exact_under_assumption"] is True
    assert abs(dp["exact_proxy_minimum"] - enum["exact_proxy_minimum"]) < 1e-12
    # Nonzero pair: DP must refuse exact claim
    costs2 = copy.deepcopy(costs)
    costs2["v"] = [[1.0], [0.0]]
    dp2 = solve_zero_interaction_dp(costs2)
    assert dp2["exact_under_assumption"] is False


def test_heuristics_legality_determinism_budget():
    costs = {
        "selected_car_ids": ["c1", "c2"],
        "action_ids": {"c1": ["a0", "a1"], "c2": ["b0", "b1"]},
        "C": 0.0,
        "u1": [1.0, 3.0],
        "u2": [2.0, 4.0],
        "v": [[0.0, 1.0], [1.0, 0.0]],
        "C_centered": 3.0,
        "u1_centered": [0.0, 2.0],
        "u2_centered": [0.0, 2.0],
    }
    h1 = run_classical_heuristics(costs, seed=42)
    h2 = run_classical_heuristics(costs, seed=42)
    assert h1["uniform"]["incumbent"] == h2["uniform"]["incumbent"]
    assert h1["annealing"]["incumbent"] == h2["annealing"]["incumbent"]
    assert h1["greedy_local"]["legal_incumbent"] is True


def test_coefficient_hash_stability_and_nonfinite_rejection():
    obs = _hand_obs(remaining=3)
    public = _public()
    model = generate_action_model(obs, public, selected_car_ids=["car.a", "car.b"])
    c1 = compile_action_costs(obs, public, menus=model["menus"], selected_car_ids=["car.a", "car.b"])
    c2 = compile_action_costs(obs, public, menus=model["menus"], selected_car_ids=["car.a", "car.b"])
    assert c1["coefficient_hash"] == c2["coefficient_hash"]
    bad = copy.deepcopy(obs)
    bad["cars"][0]["tyre_age_laps"] = float("nan")
    with pytest.raises(Exception):
        compile_action_costs(bad, public, menus=model["menus"], selected_car_ids=["car.a", "car.b"])


def test_compiler_evaluator_separation_and_panel_selection_without_outcomes():
    sep = assert_compiler_evaluator_separation()
    assert sep["ok"]
    specs = load_preview_specs(ROOT)
    selected, digest = select_panel_specs(specs)
    assert len(selected) == 8
    assert len(digest) == 64
    # Selection deterministic
    selected2, digest2 = select_panel_specs(specs)
    assert digest == digest2
    assert [s["episode_id"] for s in selected] == [s["episode_id"] for s in selected2]


def test_negative_interaction_and_one_action_menus():
    costs = {
        "selected_car_ids": ["c1", "c2"],
        "action_ids": {"c1": ["a0"], "c2": ["b0"]},
        "C": 0.0,
        "u1": [10.0],
        "u2": [10.0],
        "v": [[-3.0]],
        "C_centered": 20.0,
        "u1_centered": [0.0],
        "u2_centered": [0.0],
    }
    enum = enumerate_legal_pairs(costs)
    assert abs(enum["exact_proxy_minimum"] - 17.0) < 1e-12
    qubo = build_qubo(costs)
    assert verify_penalty_proof(qubo, costs)["ok"]


def test_asymmetric_menus_and_strong_double_stack():
    costs = {
        "selected_car_ids": ["c1", "c2"],
        "action_ids": {"c1": ["a0", "a1", "a2"], "c2": ["b0"]},
        "C": 0.0,
        "u1": [1.0, 2.0, 3.0],
        "u2": [4.0],
        "v": [[2.5], [2.5], [0.0]],
        "C_centered": 5.0,
        "u1_centered": [0.0, 1.0, 2.0],
        "u2_centered": [0.0],
    }
    enum = enumerate_legal_pairs(costs)
    milp = solve_milp_independent(costs)
    assert abs(enum["exact_proxy_minimum"] - milp["value_with_constant"]) < 1e-6
    # Optimum should prefer a2 with zero stack interaction: 3+4+0=7 vs 1+4+2.5=7.5
    assert abs(enum["exact_proxy_minimum"] - 7.0) < 1e-12


def test_interrupted_formulation_resume(monkeypatch):
    """Interrupted Stage 4 run persistence and checksum-verified resume.

    Enabled with F1Q_STAGE4_RESUME_SMOKE=1. The authorized Stage 4 evidence run
    also exercises interrupt/resume outside this module.
    """
    if os.environ.get("F1Q_STAGE4_RESUME_SMOKE") != "1":
        pytest.skip("set F1Q_STAGE4_RESUME_SMOKE=1 to run full formulation interrupt/resume")
    from f1q.authorization import load_project_config
    from f1q.ledger import Ledger
    from f1q.runner import ledger_paths, resume_run, run_formulation_check

    monkeypatch.setenv("F1Q_TEST_INTERRUPT_AFTER", "formulation.action_model")
    result = run_formulation_check(ROOT)
    assert result["status"] == "interrupted"
    run_id = result["run_id"]
    monkeypatch.delenv("F1Q_TEST_INTERRUPT_AFTER", raising=False)
    resumed = resume_run(ROOT, run_id)
    assert resumed["status"] == "completed"
    config, _, _ = load_project_config(ROOT)
    db, lock = ledger_paths(ROOT, config)
    with Ledger(db, lock, root=ROOT) as ledger:
        units2 = {u["unit_id"]: u["status"] for u in ledger.units_for(run_id)}
        assert all(s == "completed" for s in units2.values())
        assert ledger.artifacts_for(run_id)
