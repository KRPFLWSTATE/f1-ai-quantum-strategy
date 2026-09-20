"""Stage 5 unit tests — no Stage 4 campaigns, no hardware."""

from __future__ import annotations

import numpy as np
import pytest

from f1q.authorization import authorize_plan, load_project_config, reject_unsupported_mode
from f1q.errors import UnsupportedModeError, AuthorizationError
from f1q.paths import resolve_project_root
from f1q.stage5.bank import fit_one_start, select_donors
from f1q.stage5.c2_admission import decide_c2_admission
from f1q.stage5.circuits_c0 import simulate_c0
from f1q.stage5.circuits_c1 import feasible_graph_edges, one_hot_feasible_mask, simulate_c1
from f1q.stage5.encode import binary_to_policy, policy_to_binary
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.evaluate import causal_visibility_ok, check_policy_legal
from f1q.stage5.headroom import run_formulation_checks
from f1q.stage5.ideal_sim import qiskit_statevector_crosscheck_c0
from f1q.stage5.milp import solve_a2_milp
from f1q.stage5.model import build_a2_instance
from f1q.stage5.qubo import build_a2_qubo, verify_direct_vs_qubo
from f1q.stage5.selector import RidgeDonorSelector, compute_features
from f1q.stage5.splits import assert_features_clean, build_phase5_splits


def _cu(seed=7):
    return build_a2_instance(
        instance_id="test_cu",
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        rung="circuit_unit",
        n_scenarios=2,
        n_epochs=2,
        n_actions=2,
        seed=seed,
    )


def test_scenario_tree_causality_and_nonanticipativity():
    inst = _cu()
    assert causal_visibility_ok(inst)
    assert inst.validate() == []
    # Non-anticipativity: one decision vector per info set, not per scenario copy
    assert len(inst.info_sets) < len(inst.scenarios) * inst.n_epochs or len(inst.scenarios) == 1
    n_vars = inst.n_logical_vars()
    assert n_vars == sum(b["size"] for b in inst.variable_blocks())
    assert n_vars <= 12


def test_inventory_and_legality():
    inst = _cu(11)
    en = enumerate_legal_policies(inst)
    assert en["status"] == "OK"
    assert en["n_legal"] >= 1
    assert check_policy_legal(inst, en["best_policy"])["legal"]


def test_direct_qubo_enum_milp_encode():
    inst = _cu(3)
    qubo = build_a2_qubo(inst)
    en = enumerate_legal_policies(inst)
    assert verify_direct_vs_qubo(inst, qubo, en["best_policy"])["ok"]
    milp = solve_a2_milp(inst)
    assert milp["success"]
    assert abs(milp["objective"] - en["best_cost"]) < 1e-6
    x = policy_to_binary(inst, en["best_policy"])
    assert binary_to_policy(inst, x) == en["best_policy"]


def test_formulation_checks_bundle():
    checks = run_formulation_checks([_cu(1), _cu(2)])
    assert checks["exact_qubo_checks"]["fail"] == 0
    assert checks["enumeration_milp_checks"]["fail"] == 0
    assert checks["nonanticipativity_checks"]["fail"] == 0


def test_c0_ideal_and_qiskit_crosscheck():
    inst = _cu(5)
    qubo = build_a2_qubo(inst)
    sim = simulate_c0(qubo, [0.4], [0.25], scaled=True)
    assert abs(sim["norm"] - 1.0) < 1e-9
    cross = qiskit_statevector_crosscheck_c0(qubo, [0.4], [0.25])
    assert cross["ok"]


def test_c1_one_hot_and_feasible_graph():
    inst = _cu(9)
    qubo = build_a2_qubo(inst)
    sim = simulate_c1(inst, qubo, [0.2], [0.1], scaled=True)
    assert abs(sim["norm"] - 1.0) < 1e-9
    assert sim["amp_outside_one_hot"] <= 1e-8
    mask = one_hot_feasible_mask(inst)
    assert mask.any()
    edges = feasible_graph_edges(inst)
    assert len(edges) >= 1


def test_split_isolation_and_no_leakage_features():
    splits = build_phase5_splits(source_hash="abc")
    assert splits["audit"]["total_blocks"] == 224
    assert splits["audit"]["overlap_failures"] == []
    assert splits["audit"]["calib_eval_test_materialized"] is False
    ids = [b["block_id"] for b in splits["anchors"] + splits["training_extra"] + splits["tuning"]]
    assert len(ids) == len(set(ids))
    with pytest.raises(ValueError):
        assert_features_clean({"exact_optimum": 1.0, "n_logical_vars": 8})


def test_bank_deterministic_and_selector_reproducible():
    inst = _cu(13)
    qubo = build_a2_qubo(inst)
    a = fit_one_start(inst, qubo, "C0", 1, seed=42, max_evals=10)
    b = fit_one_start(inst, qubo, "C0", 1, seed=42, max_evals=10)
    assert a["success"] and b["success"]
    assert a["params_hash"] == b["params_hash"]
    fits = [fit_one_start(inst, qubo, "C1", 1, seed=100 + i, max_evals=8) for i in range(3)]
    donors = select_donors(fits, max_donors=2)
    assert len(donors["selected"]) <= 2
    feats = compute_features(inst, qubo, "C1", 1)
    X = np.array([[feats[k] for k in [
        "n_logical_vars","n_info_sets","n_scenarios","n_epochs","n_blocks","mean_block_size",
        "qubo_n_terms","qubo_density","coeff_abs_mean","coeff_abs_max","penalty_M",
        "crew_overlap_cost","family_is_c1","depth_p","nnz_Q"
    ]]])
    y = np.array([[0.1, 0.2]])
    sel = RidgeDonorSelector(1.0)
    r1 = sel.fit(X, y, ["d0", "d1"])
    r2 = RidgeDonorSelector(1.0).fit(X, y, ["d0", "d1"])
    assert r1["weights_hash"] == r2["weights_hash"]


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
    # QPU jobs always zero in stage5 package constant
    from f1q.stage5 import QPU_EXECUTION_AUTHORISED
    assert QPU_EXECUTION_AUTHORISED is False
