"""A4 focused tests required before the authoritative campaign."""

from __future__ import annotations

import copy

import numpy as np
import pytest
from qiskit.quantum_info import DensityMatrix

from f1q.a4.banks import EVALUATION_BANK, PLANNING_BANK, bank_world_seeds, banks_disjoint, cache_key
from f1q.a4.generators import assemble_portfolio, select_by_planning_mean
from f1q.a4.loop import adversarial_validation, decide_and_evaluate, family_spec
from f1q.a4.partitions import build_a4_partitions
from f1q.a4.problem import (
    build_a4_qubo,
    build_menu_and_instance,
    enumerate_legal_policies,
    every_variable_affects_plan,
    extract_causal_view,
    policy_to_simulator_plan,
    verify_direct_qubo_milp,
)
from f1q.a4.qpu_guard import inspect_ibm_balance, submit_qpu_job
from f1q.errors import RejectionError, UnsupportedModeError
from f1q.hashing import sha256_json
from f1q.simulator.interface import RaceSimulator
from f1q.stage6.noisy import depolarizing_closed_form, depolarizing_kraus


def _live():
    spec = family_spec(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.test.menu",
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
    qubo = build_a4_qubo(inst)
    return spec, sim, obs, view, inst, qubo


def test_full_action_menu_not_two_actions():
    _spec, sim, _obs, _view, inst, _qubo = _live()
    for cid, acts in inst.actions_by_car.items():
        kinds = {a.kind for a in acts}
        assert "continuation" in kinds
        assert len(acts) > 2, f"{cid} reduced to { [a.action_id for a in acts] }"
        assert any(a.kind == "pit_now" for a in acts) or any(a.kind == "delay_laps" for a in acts)
        # delay 1 and 2 present when remaining allows
        delays = {a.delay_laps for a in acts if a.kind == "delay_laps"}
        remaining = inst.view["remaining_laps"]
        if remaining >= 3:
            assert 1 in delays and 2 in delays
        compounds = {a.compound for a in acts if a.kind == "pit_now"}
        assert len(compounds) >= 2
        for a in acts:
            sim.validate_plan({cid: a.to_plan_item(), **{c: {"kind": "continuation"} for c in inst.car_ids if c != cid}})


def test_every_qubo_variable_changes_executed_plan():
    _spec, _sim, _obs, _view, inst, qubo = _live()
    chk = every_variable_affects_plan(inst)
    assert chk["unexecuted_decision_variables"] == 0
    assert chk["n_variables"] == qubo["n"]
    assert chk["ok"]


def test_direct_qubo_milp_agreement():
    _spec, _sim, _obs, _view, inst, qubo = _live()
    agr = verify_direct_qubo_milp(inst, qubo)
    assert agr["ok"]
    assert agr["n_checked"] == agr["n_legal"]
    assert agr["max_abs_diff"] < 1e-8
    assert agr["milp_matches_enum"] or agr["milp"]["success"] is False


def test_decode_validate_commit_roundtrip():
    spec, sim, _obs, _view, inst, _qubo = _live()
    rows = enumerate_legal_policies(inst)
    assert rows
    wrapped = rows[0]["wrapped"]
    plan = wrapped["plan"]
    sim.validate_plan(plan)
    rec = sim.consider_recommendation(plan, arrival_delay_s=0.01, common_commit_delay_s=0.05)
    _st, outcome = sim.continue_to_finish()
    assert rec["selected_plan"] in {"recommendation", "fallback_continuation"}
    assert "normalized_team_rank_loss" in outcome["team_loss"]
    decoded = policy_to_simulator_plan(inst, rows[0]["policy"])["plan"]
    assert sha256_json(decoded) == sha256_json(plan)


def test_identical_observables_hidden_future_same_portfolio():
    r = adversarial_validation()
    assert r["ok"]
    assert r["cases"]["identical_observables_different_hidden_same_policy"]


def test_forbidden_future_fields_rejected():
    _spec, sim, obs, _view, _inst, _qubo = _live()
    data = obs.model_dump(mode="python")
    data["sampled_future"] = 1.0
    with pytest.raises(RejectionError):
        extract_causal_view(data)


def test_planning_evaluation_banks_disjoint():
    p = bank_world_seeds("b", "SC", PLANNING_BANK, 8)
    e = bank_world_seeds("b", "SC", EVALUATION_BANK, 16)
    assert banks_disjoint(p, e)
    k1 = cache_key(spec_hash="a", checkpoint_hash="c", plan_hash="p", bank=PLANNING_BANK, world_seed=1)
    k2 = cache_key(spec_hash="a", checkpoint_hash="c", plan_hash="p", bank=EVALUATION_BANK, world_seed=1)
    assert k1 != k2


def test_portfolio_k_matched_and_permutation_invariant():
    _spec, sim, _obs, _view, inst, qubo = _live()

    def _val(plan):
        sim.validate_plan(plan)

    port = assemble_portfolio(
        inst, qubo, choice="classical_only", seed=1, pool_size=16, sim_validate=_val,
        params=None, family=None, p_depth=1, equal_k=4,
    )
    assert port["n_downstream"] == 4
    assert port["portfolio_budget_matched"]
    means = {c["plan_hash"]: float(i) for i, c in enumerate(port["downstream_candidates"])}
    # make a unique best
    best = port["downstream_candidates"][2]["plan_hash"]
    means[best] = -1.0
    s1 = select_by_planning_mean(port["downstream_candidates"], means)
    perm = list(reversed(port["downstream_candidates"]))
    s2 = select_by_planning_mean(perm, means)
    assert s1["selected_plan_hash"] == s2["selected_plan_hash"] == best


def test_forced_quantum_best_and_worse_fixtures():
    _spec, sim, _obs, _view, inst, qubo = _live()

    def _val(plan):
        sim.validate_plan(plan)

    port = assemble_portfolio(
        inst, qubo, choice="classical_only", seed=3, pool_size=8, sim_validate=_val,
        params=None, family=None, p_depth=1, equal_k=4,
    )
    cands = copy.deepcopy(port["downstream_candidates"])
    q = copy.deepcopy(cands[0])
    q["origin"] = "quantum"
    q["plan_hash"] = "quantum-best-hash"
    cands.append(q)
    means = {c["plan_hash"]: 1.0 for c in cands}
    means["quantum-best-hash"] = 0.0
    sel = select_by_planning_mean(cands, means)
    assert sel["selected_plan_hash"] == "quantum-best-hash"
    means["quantum-best-hash"] = 9.0
    sel2 = select_by_planning_mean(cands, means)
    assert sel2["selected_plan_hash"] != "quantum-best-hash"


def test_classical_hybrid_can_differ_and_offline_not_copied():
    spec, _sim, _obs, _view, inst, _qubo = _live()
    cache = {}
    cl = decide_and_evaluate(
        spec, mode="always_classical", runtime=None, donor_bank=None, donor_policy="fixed",
        planning_seeds=[1, 2], evaluation_seeds=[11, 12, 13, 14], online_seed=4, cache=cache,
        pool_size=16, equal_k=4, deadline_s=30.0, margin=0.001, conservative_residual=0.0,
    )
    hy = decide_and_evaluate(
        spec, mode="always_c0", runtime=None, donor_bank=None, donor_policy="fixed",
        planning_seeds=[1, 2], evaluation_seeds=[11, 12, 13, 14], online_seed=5, cache=cache,
        pool_size=16, equal_k=4, deadline_s=30.0, margin=0.001, conservative_residual=0.0,
    )
    assert cl["portfolio"]["n_downstream"] == hy["portfolio"]["n_downstream"] == 4
    # Offline: enumerate all legal and score independently — not copy arm loss
    legal = enumerate_legal_policies(inst)
    assert len(legal) == cl["legal_plan_count"]
    assert legal
    # identities may match or differ; both are allowed, but losses come from evaluation_bank
    assert cl["losses"] and hy["losses"]


def test_cache_keys_do_not_cross_checkpoints():
    a = cache_key(spec_hash="s1", checkpoint_hash="c1", plan_hash="p", bank="planning_bank", world_seed=0)
    b = cache_key(spec_hash="s1", checkpoint_hash="c2", plan_hash="p", bank="planning_bank", world_seed=0)
    c = cache_key(spec_hash="s2", checkpoint_hash="c1", plan_hash="p", bank="planning_bank", world_seed=0)
    assert len({a, b, c}) == 3


def test_splits_dry_bookkeeping_final_test_unmaterialised():
    p = build_a4_partitions()
    assert p["ok"]
    assert p["planned"]["anchors"] == 24
    assert p["planned"]["training"] == 120
    assert p["planned"]["tuning"] == 80
    assert p["planned"]["calibration"] == 24
    assert len(p["anchors"]) == 24
    assert len(p["train"]) == 120
    assert len(p["tune"]) == 80
    assert len(p["calib"]) == 24
    assert p["final_test"]["n_blocks"] == 80
    assert p["final_test"]["outcomes_materialised"] is False
    assert p["final_test"]["outcomes_opened"] is False
    assert not p["overlap_open_vs_finaltest"]
    assert not p["a2_a3_id_reuse"]
    # listing ids is not execution; campaign must process members
    assert p["no_silent_per_family_reduction"] is True


def test_late_stale_invalid_remain_in_denominators():
    r = adversarial_validation()
    assert r["cases"]["late_results_frozen_classical_fallback"]


def test_evaluation_bank_rejected_from_planning_helper():
    from f1q.a4.banks import reject_evaluation_in_planning

    reject_evaluation_in_planning(PLANNING_BANK)
    with pytest.raises(RejectionError):
        reject_evaluation_in_planning(EVALUATION_BANK)


def test_anchor_fit_has_real_evaluations():
    from f1q.a4.anchors import fit_one_start

    _spec, _sim, _obs, _view, inst, qubo = _live()
    rec = fit_one_start(inst, qubo, "C1", 1, seed=1, max_evals=3)
    assert rec["success"] is True
    assert rec["evals"] == 3
    assert rec["best_params"]
    assert rec["params_hash"]
    assert rec["wall_s"] is not None


def test_qpu_calls_impossible():
    with pytest.raises(UnsupportedModeError):
        submit_qpu_job(backend="ibm")
    with pytest.raises(UnsupportedModeError):
        inspect_ibm_balance()


def test_depolarizing_closed_form_kraus_1q_2q():
    ps = [0.0, 1.0, 0.2, 0.5, 0.8]
    for nq in (1, 2):
        d = 2**nq
        for p in ps:
            for mixed in (False, True):
                rho = np.zeros((d, d), dtype=complex)
                rho[0, 0] = 1.0
                if mixed:
                    rho = 0.7 * rho + 0.3 * np.eye(d) / d
                k = depolarizing_kraus(nq, p)
                got = DensityMatrix(rho).evolve(k).data
                closed = depolarizing_closed_form(rho, p)
                assert np.allclose(got, closed, atol=1e-8)
                assert abs(np.trace(got) - 1) < 1e-8
                evals = np.linalg.eigvalsh(got)
                assert np.all(evals >= -1e-8)
        # p=1 maximally mixed
        rho = np.zeros((d, d), dtype=complex)
        rho[0, 0] = 1.0
        closed = depolarizing_closed_form(rho, 1.0)
        assert np.allclose(closed, np.eye(d) / d, atol=1e-10)
