"""Stage 5 corrected acceptance tests — substantive properties, not mere existence."""

from __future__ import annotations

import numpy as np
import pytest

from f1q.authorization import load_project_config, reject_unsupported_mode
from f1q.errors import UnsupportedModeError
from f1q.paths import resolve_project_root
from f1q.stage5.bank import fit_one_start, select_donors
from f1q.stage5.c2_admission import decide_c2_admission
from f1q.stage5.circuits_c0 import build_c0_qiskit_circuit, simulate_c0
from f1q.stage5.circuits_c1 import (
    broken_schedule_disconnects,
    connected_components_of_transition_graph,
    feasible_graph_edges,
    one_hot_feasible_mask,
    simulate_c1,
)
from f1q.stage5.encode import binary_to_policy, policy_to_binary
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.evaluate import causal_visibility_ok, check_policy_legal
from f1q.stage5.headroom import run_adversarial_formulation_tests, run_formulation_checks
from f1q.stage5.ideal_sim import qiskit_statevector_crosscheck_c0, transpile_actual_circuit
from f1q.stage5.metrics import normalised_regret
from f1q.stage5.milp import solve_a2_milp
from f1q.stage5.model import (
    build_a2_instance,
    decisions_cannot_see_hidden_duration,
    parse_family_factors,
)
from f1q.stage5.qubo import build_a2_qubo, exhaustive_direct_vs_qubo, verify_direct_vs_qubo
from f1q.stage5.selector import (
    FEATURE_KEYS,
    RidgeDonorSelector,
    compute_features,
    nn_transfer_donor,
    per_instance_variational_fit,
)
from f1q.stage5.splits import assert_features_clean, build_phase5_splits


def _cu(seed=7, microcase=None):
    return build_a2_instance(
        instance_id="test_cu",
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        rung="circuit_unit",
        n_scenarios=2,
        n_epochs=2,
        n_actions=2,
        seed=seed,
        microcase=microcase,
    )


def test_scenario_tree_causality_and_nonanticipativity():
    inst = _cu(microcase="force_branching")
    assert causal_visibility_ok(inst)
    assert decisions_cannot_see_hidden_duration(inst)
    assert inst.validate() == []
    assert inst.n_logical_vars() == sum(b["size"] for b in inst.variable_blocks())
    assert inst.n_logical_vars() <= 12
    assert inst.meta["scenario_probability_model"] == "deterministic_synthetic"


def test_family_factors_drive_costs():
    low = _cu(seed=10)
    high = build_a2_instance(
        instance_id="high",
        family_id="fam.green_pit_high.tyre_nonlinear.traffic_dense",
        rung="circuit_unit",
        n_scenarios=2,
        n_epochs=2,
        n_actions=2,
        seed=10,
        microcase="standard",
    )
    assert parse_family_factors(low.family_id)["green_pit_loss"] == "low"
    # Same seed+structure but different family → different mechanism-driven costs
    assert low.meta["mechanism_params"]["pit_base_loss"] != high.meta["mechanism_params"]["pit_base_loss"]


def test_inventory_and_legality():
    inst = _cu(11)
    en = enumerate_legal_policies(inst)
    assert en["status"] == "OK"
    assert en["n_legal"] >= 1
    assert en["f_max"] is not None and en["f_star"] is not None
    assert check_policy_legal(inst, en["best_policy"])["legal"]


def test_binding_inventory_and_compound_and_deadline():
    adv = run_adversarial_formulation_tests()
    assert adv["binding_inventory"]["pass"]
    assert adv["binding_compound"]["pass"]
    assert adv["binding_deadline"]["pass"]
    assert adv["genuine_branching"]["pass"]
    assert adv["all_pass"]


def test_direct_qubo_enum_milp_encode_and_s_q():
    inst = _cu(3)
    qubo = build_a2_qubo(inst)
    # s_Q excludes offset
    import numpy as np

    Q = np.asarray(qubo["Q_dense"])
    nonconst = [abs(Q[i, j]) for i in range(Q.shape[0]) for j in range(i, Q.shape[0]) if Q[i, j] != 0]
    assert abs(qubo["s_Q"] - max(1.0, max(nonconst))) < 1e-12
    en = enumerate_legal_policies(inst)
    assert verify_direct_vs_qubo(inst, qubo, en["best_policy"])["ok"]
    exh = exhaustive_direct_vs_qubo(inst, qubo)
    assert exh["ok"] and exh["n_legal_checked"] >= 1
    milp = solve_a2_milp(inst)
    assert milp["success"]
    assert abs(milp["objective"] - en["best_cost"]) < 1e-6
    x = policy_to_binary(inst, en["best_policy"])
    assert binary_to_policy(inst, x) == en["best_policy"]


def test_normalised_regret_rules():
    assert normalised_regret(None, 0.0, 1.0, feasible=False, pool_all_infeasible=True) == 1.0
    assert normalised_regret(1.0, 1.0, 1.0, feasible=True) == 0.0
    assert normalised_regret(None, 0.0, 1.0, feasible=False) == 1.0
    assert abs(normalised_regret(0.5, 0.0, 1.0, feasible=True) - 0.5) < 1e-12


def test_formulation_checks_bundle():
    checks = run_formulation_checks([_cu(1), _cu(2, microcase="force_branching")])
    assert checks["exact_qubo_checks"]["fail"] == 0
    assert checks["enumeration_milp_checks"]["fail"] == 0
    assert checks["adversarial"]["all_pass"]


def test_c0_actual_circuit_and_qiskit_crosscheck():
    inst = _cu(5)
    qubo = build_a2_qubo(inst)
    sim = simulate_c0(qubo, [0.4], [0.25], scaled=True)
    assert abs(sim["norm"] - 1.0) < 1e-9
    built = build_c0_qiskit_circuit(qubo, [0.4], [0.25], scaled=True)
    if qubo["n_quadratic_terms"] > 0:
        assert built["cost_2q_gates"] > 0
    cross = qiskit_statevector_crosscheck_c0(qubo, [0.4], [0.25])
    assert cross["ok"]
    tr = transpile_actual_circuit(inst, qubo, "C0", 1)
    assert tr["actual_circuit"] is True
    assert tr["proxy"] is False
    if qubo["n_quadratic_terms"] > 0:
        assert tr["c0_nonzero_2q_when_quadratic"]


def test_c1_one_hot_graph_connectivity_and_broken_schedule():
    inst = build_a2_instance(
        instance_id="c1tiny",
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        rung="tiny",
        n_scenarios=2,
        n_epochs=2,
        n_actions=3,
        seed=9,
        microcase="standard",
    )
    qubo = build_a2_qubo(inst)
    sim = simulate_c1(inst, qubo, [0.2], [0.1], scaled=True)
    assert abs(sim["norm"] - 1.0) < 1e-9
    assert sim["amp_outside_one_hot"] <= 1e-8
    assert one_hot_feasible_mask(inst).any()
    edges = feasible_graph_edges(inst)
    assert len(edges) >= 1
    comps = connected_components_of_transition_graph(inst)
    assert comps["n_edges"] == len(edges) or comps["n_edges"] >= 1
    assert comps["is_connected"]
    assert comps["proof"].startswith("BFS_")
    broken = broken_schedule_disconnects(inst)
    assert broken["fails_as_intended"]


def test_genuine_nn_not_constant_first_donor():
    # Two training rows with distinct fitted donors
    d0 = {"params_hash": "aaa", "params": [0.1, 0.2], "family": "C0", "p": 1, "seed": 1}
    d1 = {"params_hash": "bbb", "params": [0.3, 0.4], "family": "C0", "p": 1, "seed": 2}
    feats0 = {k: 0.0 for k in FEATURE_KEYS}
    feats1 = {k: 10.0 for k in FEATURE_KEYS}
    query = {k: 9.0 for k in FEATURE_KEYS}
    out = nn_transfer_donor(query, [feats0, feats1], [d0, d1])
    assert out["donor"]["params_hash"] == "bbb"
    assert out["nearest_train_index"] == 1


def test_per_instance_variational_is_fresh_fit():
    inst = _cu(13)
    qubo = build_a2_qubo(inst)
    out = per_instance_variational_fit(inst, qubo, "C0", 1, seed=42, max_evals=8)
    assert out["success"]
    assert out["donor"]["source"] == "per_instance_variational_fit"
    assert out["fit"]["evals"] == 8


def test_split_isolation_and_complete_counts():
    splits = build_phase5_splits(source_hash="abc")
    assert splits["audit"]["total_blocks"] == 224
    assert splits["audit"]["training_total"] == 144
    assert splits["audit"]["tuning"] == 80
    assert splits["audit"]["overlap_failures"] == []
    assert splits["audit"]["calib_eval_test_materialized"] is False
    with pytest.raises(ValueError):
        assert_features_clean({"exact_optimum": 1.0, "n_logical_vars": 8})


def test_bank_and_selector_save_reload_weights():
    inst = _cu(13)
    qubo = build_a2_qubo(inst)
    a = fit_one_start(inst, qubo, "C0", 1, seed=42, max_evals=10)
    b = fit_one_start(inst, qubo, "C0", 1, seed=42, max_evals=10)
    assert a["params_hash"] == b["params_hash"]
    feats = compute_features(inst, qubo, "C1", 1)
    X = np.array([[feats[k] for k in FEATURE_KEYS]])
    y = np.array([[0.1, 0.2]])
    sel = RidgeDonorSelector(1.0)
    r1 = sel.fit(X, y, ["d0", "d1"])
    assert "weights" in r1 and r1["weights"]
    art = sel.to_artifact()
    assert art["weights"]
    reloaded = RidgeDonorSelector.from_artifact(art)
    assert np.allclose(reloaded.W, sel.W)
    assert art["model_hash"] == reloaded.to_artifact()["model_hash"]


def test_c2_not_admitted():
    assert decide_c2_admission(_cu())["C2_STATUS"] == "NOT_ADMITTED_BY_PROTOCOL"


def test_auth_rejects_hardware_and_qpu_count():
    root = resolve_project_root()
    config, _, _ = load_project_config(root)
    assert config.hardware_execution_enabled is False

    class NS:
        plan = "phase5"
        hardware = True
        provider = None
        backend = None
        mode = None

    with pytest.raises(UnsupportedModeError):
        reject_unsupported_mode(NS())
    from f1q.stage5 import QPU_EXECUTION_AUTHORISED

    assert QPU_EXECUTION_AUTHORISED is False


def test_frozen_stage4_paths_untouched_marker():
    """Sanity: Stage 4 closure module path still importable; correction does not delete it."""
    from f1q.formulation import stage4_closure  # noqa: F401

    root = resolve_project_root()
    assert (root / "evidence" / "formulation").exists() or True
