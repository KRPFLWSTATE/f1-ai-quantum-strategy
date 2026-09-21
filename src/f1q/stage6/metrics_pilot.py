"""Pilot metrics: exact ideal distribution once; reusable seeded pool sampling."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from f1q.stage5.encode import binary_to_policy
from f1q.stage5.evaluate import check_policy_legal, evaluate_policy_cost
from f1q.stage5.metrics import (
    COST_ABS_TOL,
    PROB_ABS_TOL,
    REGRET_EQ_TOL,
    costs_equal,
    normalised_regret,
)
from f1q.stage5.model import A2Instance


def exact_distribution_metrics(
    instance: A2Instance,
    probs: np.ndarray,
    *,
    exact_cost: float | None,
    f_max: float | None,
    weak_incumbent_cost: float | None,
    improvement_tol: float,
) -> dict[str, Any]:
    """Exact ideal probabilities (one-hot vs full semantic legality separately)."""
    n = int(round(np.log2(probs.size)))
    assert 1 << n == probs.size
    one_hot_prob = 0.0
    complete_legal_prob = 0.0
    optimal_mass = 0.0
    tie_optimum_mass = 0.0
    strictly_improving_vs_exact = 0.0
    strictly_improving_vs_weak = 0.0
    expected_cost_legal = 0.0
    legal_mass_for_expect = 0.0

    t0 = time.perf_counter()
    for b in range(1 << n):
        pr = float(probs[b])
        if pr <= PROB_ABS_TOL:
            continue
        x = np.array([(b >> k) & 1 for k in range(n)], dtype=int)
        pol = binary_to_policy(instance, x)
        if pol is None:
            continue
        one_hot_prob += pr
        legal = check_policy_legal(instance, pol)
        if not legal["legal"]:
            continue
        complete_legal_prob += pr
        ev = evaluate_policy_cost(instance, pol)
        c = float(ev["expected_cost"])
        expected_cost_legal += pr * c
        legal_mass_for_expect += pr
        if exact_cost is not None and costs_equal(c, exact_cost):
            optimal_mass += pr
            tie_optimum_mass += pr
        if exact_cost is not None and c < float(exact_cost) - improvement_tol:
            strictly_improving_vs_exact += pr
        if weak_incumbent_cost is not None and c < float(weak_incumbent_cost) - improvement_tol:
            strictly_improving_vs_weak += pr

    return {
        "one_hot_probability": float(one_hot_prob),
        "complete_legal_policy_probability": float(complete_legal_prob),
        "legal_sample_yield": float(complete_legal_prob),
        "optimal_sample_probability": float(optimal_mass),
        "tie_optimum_mass": float(tie_optimum_mass),
        "strictly_improving_vs_exact_probability": float(strictly_improving_vs_exact),
        "strictly_improving_vs_weak_probability": float(strictly_improving_vs_weak),
        "expected_cost_on_legal_support": (
            None if legal_mass_for_expect <= PROB_ABS_TOL else float(expected_cost_legal / legal_mass_for_expect)
        ),
        "exact_scan_s": time.perf_counter() - t0,
        "f_star": exact_cost,
        "f_max": f_max,
        "note_exact_incumbent": (
            "When incumbent is exact, strictly positive proxy improvement probability is zero "
            "within declared tolerance; ties are not improvements."
        ),
    }


def pool_sample_metrics(
    instance: A2Instance,
    probs: np.ndarray,
    *,
    exact_cost: float | None,
    f_max: float | None,
    pool_size: int,
    seed: int,
) -> dict[str, Any]:
    """One seeded best-of-pool measurement (does not recompute exact ideal probs)."""
    n = int(round(np.log2(probs.size)))
    p_norm = probs / max(float(probs.sum()), 1e-30)
    rng = np.random.default_rng(seed)
    idx = rng.choice(1 << n, size=min(pool_size, 1 << n), replace=True, p=p_norm)
    best_cost: float | None = None
    n_feasible = 0
    t0 = time.perf_counter()
    for b in idx:
        x = np.array([(int(b) >> k) & 1 for k in range(n)], dtype=int)
        pol = binary_to_policy(instance, x)
        if pol is None:
            continue
        if not check_policy_legal(instance, pol)["legal"]:
            continue
        c = float(evaluate_policy_cost(instance, pol)["expected_cost"])
        n_feasible += 1
        if best_cost is None or c < best_cost:
            best_cost = c
    pool_all_infeasible = n_feasible == 0
    norm_regret = normalised_regret(
        best_cost,
        exact_cost,
        f_max,
        feasible=not pool_all_infeasible,
        pool_all_infeasible=pool_all_infeasible,
    )
    unnorm = None if best_cost is None or exact_cost is None else float(best_cost) - float(exact_cost)
    return {
        "seed": int(seed),
        "pool_size": int(pool_size),
        "n_feasible_in_pool": int(n_feasible),
        "best_of_pool_cost": best_cost,
        "best_of_pool_unnormalised_gap": unnorm,
        "best_of_pool_normalised_regret": float(norm_regret),
        "all_infeasible_pool": pool_all_infeasible,
        "pool_s": time.perf_counter() - t0,
    }


def aggregate_pools(pool_rows: list[dict[str, Any]]) -> dict[str, Any]:
    regs = [float(r["best_of_pool_normalised_regret"]) for r in pool_rows]
    feas = [int(r["n_feasible_in_pool"]) for r in pool_rows]
    return {
        "n_pool_seeds": len(pool_rows),
        "mean_normalised_regret": float(np.mean(regs)) if regs else None,
        "std_normalised_regret": float(np.std(regs, ddof=1)) if len(regs) > 1 else 0.0,
        "mean_feasible_in_pool": float(np.mean(feas)) if feas else 0.0,
        "all_infeasible_pool_rate": float(np.mean([1.0 if r["all_infeasible_pool"] else 0.0 for r in pool_rows])),
    }
