"""Regression tests for corrected shot accounting and related Stage 6 fixes."""

from __future__ import annotations

import numpy as np

from f1q.stage5.model import build_a2_instance
from f1q.stage5.qubo import build_a2_qubo
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage6.metrics_pilot import pool_sample_metrics
from f1q.stage6.noisy import verify_analytical_channel_behaviour, simulate_circuit_with_depolarizing
from f1q.stage6.novelty import build_novelty_comparison
from f1q.stage6.sizing import stratified_block_bootstrap, recommend_independent_blocks_for_precision
from qiskit import QuantumCircuit


def _tiny_instance():
    return build_a2_instance(
        instance_id="test.shots",
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        rung="circuit_unit",
        seed=1,
        n_scenarios=2,
        n_epochs=2,
        n_actions=2,
        microcase="standard",
    )


def test_pool_1024_draws_from_8qubit_distribution():
    inst = _tiny_instance()
    qubo = build_a2_qubo(inst)
    n = qubo["n"]
    assert n == 8
    dim = 1 << n
    probs = np.ones(dim) / dim
    en = enumerate_legal_policies(inst)
    row = pool_sample_metrics(
        inst,
        probs,
        exact_cost=en.get("f_star"),
        f_max=en.get("f_max"),
        pool_size=1024,
        seed=123,
    )
    assert row["requested_shots"] == 1024
    assert row["actual_draws"] == 1024
    assert row["counts_sum"] == 1024
    assert row["shot_conservation_ok"] is True
    assert row["hilbert_cap_applied"] is False
    # With replacement, unique outcomes can be < 256 while draws = 1024
    assert row["n_unique_outcomes"] <= dim
    assert row["n_unique_outcomes"] >= 1


def test_duplicate_outcomes_allowed_and_counts_sum():
    inst = _tiny_instance()
    dim = 1 << 8
    # Degenerate two-outcome distribution
    probs = np.zeros(dim)
    probs[0] = 0.5
    probs[1] = 0.5
    en = enumerate_legal_policies(inst)
    row = pool_sample_metrics(
        inst, probs, exact_cost=en.get("f_star"), f_max=en.get("f_max"), pool_size=100, seed=7
    )
    assert row["actual_draws"] == 100
    assert row["counts_sum"] == 100
    assert row["n_unique_outcomes"] <= 2


def test_all_invalid_pool_handled():
    inst = _tiny_instance()
    dim = 1 << 8
    # Put all mass on a non-one-hot bitstring if possible: all-zero often invalid for one-hot blocks
    probs = np.zeros(dim)
    probs[0] = 1.0
    en = enumerate_legal_policies(inst)
    row = pool_sample_metrics(
        inst, probs, exact_cost=en.get("f_star"), f_max=en.get("f_max"), pool_size=64, seed=3
    )
    assert row["actual_draws"] == 64
    # May be all infeasible depending on encoding; must not crash and must flag conservation
    assert row["shot_conservation_ok"] is True
    assert isinstance(row["all_infeasible_pool"], bool)


def test_analytical_channel_self_check():
    r = verify_analytical_channel_behaviour()
    assert r["ok"] is True


def test_zero_noise_density_matrix_matches_h():
    qc = QuantumCircuit(1)
    qc.h(0)
    zn = simulate_circuit_with_depolarizing(qc, p1=0.0, p2=0.0)
    assert abs(zn["probs"][0] - 0.5) < 1e-10
    assert abs(zn["probs"][1] - 0.5) < 1e-10


def test_gate_e_fail_for_intended_contribution():
    n = build_novelty_comparison(pilot_headroom="ZERO", causal_operational_ready=False)
    assert n["GATE_E_SCIENTIFIC_VALUE"] == "FAIL_FOR_INTENDED_CONTRIBUTION"
    assert n["prior_gate_e_pass_withdrawn"] is True
    assert n["contribution_assessment"]["adequacy_for_ai_quantum_f1_objective"] == "INSUFFICIENT"


def test_stratified_bootstrap_executed():
    effects = []
    fams = [f"fam.{i}" for i in range(8)]
    for fi, fam in enumerate(fams):
        for b in range(3):
            effects.append({"block_id": f"{fam}.{b}", "family_id": fam, "effect": 0.01 * fi + 0.001 * b})
    boot = stratified_block_bootstrap(effects, n_boot=200, seed=1)
    assert boot["status"] == "EXECUTED"
    assert boot["n_families"] == 8
    assert len(boot["ci95"]) == 2


def test_zero_halfwidth_recommendation_not_superiority():
    r = recommend_independent_blocks_for_precision(
        observed_halfwidth=0.0,
        target_halfwidth=0.05,
        n_blocks_observed=24,
        floor=80,
        cap=160,
    )
    assert r["status"] == "DEGENERATE_ZERO_OBSERVED_HALFWIDTH"
    assert r["suggested_held_out_mechanism_blocks"] == 80
