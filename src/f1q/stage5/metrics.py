"""Dossier-aligned normalised regret and feasibility metrics (Phase 5 corrected)."""

from __future__ import annotations

from typing import Any

import numpy as np

from f1q.stage5.encode import binary_to_policy
from f1q.stage5.evaluate import check_policy_legal, evaluate_policy_cost
from f1q.stage5.model import A2Instance

# Explicit numerical tolerances (frozen for corrected Phase 5)
COST_ABS_TOL = 1e-8
COST_REL_TOL = 1e-8
PROB_ABS_TOL = 1e-12
REGRET_EQ_TOL = 1e-12

# Useful = legal AND strictly better than weak incumbent by this relative margin of range
USEFUL_IMPROVEMENT_FRAC = 0.05


def costs_equal(a: float, b: float) -> bool:
    return abs(a - b) <= COST_ABS_TOL + COST_REL_TOL * max(1.0, abs(a), abs(b))


def normalised_regret(
    f_a: float | None,
    f_star: float | None,
    f_max: float | None,
    *,
    feasible: bool,
    pool_all_infeasible: bool = False,
) -> float:
    """Dossier normalised regret: (f(a)-f*)/(f_max-f*).

    Rules:
    - all-infeasible sampled pool → regret 1
    - missing / infeasible sample → never mapped to 0 via silent coercion; caller must not
      treat None as zero. This function returns 1.0 when infeasible/missing.
    - zero legal objective range → every feasible sample has regret 0
    """
    if pool_all_infeasible:
        return 1.0
    if not feasible or f_a is None or f_star is None or f_max is None:
        return 1.0
    denom = float(f_max) - float(f_star)
    if abs(denom) <= REGRET_EQ_TOL:
        return 0.0
    return float((float(f_a) - float(f_star)) / denom)


def legal_cost_range(instance: A2Instance, legal_costs: list[float]) -> dict[str, Any]:
    if not legal_costs:
        return {
            "f_star": None,
            "f_max": None,
            "range": None,
            "n_legal": 0,
            "zero_range": False,
        }
    f_star = float(min(legal_costs))
    f_max = float(max(legal_costs))
    return {
        "f_star": f_star,
        "f_max": f_max,
        "range": f_max - f_star,
        "n_legal": len(legal_costs),
        "zero_range": abs(f_max - f_star) <= REGRET_EQ_TOL,
    }


def evaluate_distribution_metrics(
    instance: A2Instance,
    probs: np.ndarray,
    *,
    exact_cost: float | None,
    f_max: float | None,
    weak_incumbent_cost: float | None,
    pool_size: int,
    seed: int,
) -> dict[str, Any]:
    """Full metric suite over a measurement distribution."""
    n = int(np.log2(probs.size))
    assert 1 << n == probs.size
    one_hot_prob = 0.0
    complete_legal_prob = 0.0
    useful_feasible_prob = 0.0
    optimal_sample_prob = 0.0
    rng = np.random.default_rng(seed)

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
        if exact_cost is not None and costs_equal(c, exact_cost):
            optimal_sample_prob += pr
        # Useful: legal and improves on weak incumbent by declared margin of range
        if weak_incumbent_cost is not None and f_max is not None and exact_cost is not None:
            rng_span = float(f_max) - float(exact_cost)
            margin = USEFUL_IMPROVEMENT_FRAC * rng_span if abs(rng_span) > REGRET_EQ_TOL else 0.0
            if c <= weak_incumbent_cost - margin + COST_ABS_TOL:
                useful_feasible_prob += pr
        elif exact_cost is not None and costs_equal(c, exact_cost):
            useful_feasible_prob += pr

    # Best-of-pool
    p_norm = probs / max(float(probs.sum()), 1e-30)
    idx = rng.choice(1 << n, size=min(pool_size, 1 << n), replace=True, p=p_norm)
    best_cost: float | None = None
    n_feasible_pool = 0
    for b in idx:
        x = np.array([(int(b) >> k) & 1 for k in range(n)], dtype=int)
        pol = binary_to_policy(instance, x)
        if pol is None:
            continue
        if not check_policy_legal(instance, pol)["legal"]:
            continue
        c = float(evaluate_policy_cost(instance, pol)["expected_cost"])
        n_feasible_pool += 1
        if best_cost is None or c < best_cost:
            best_cost = c

    pool_all_infeasible = n_feasible_pool == 0
    unnorm_gap = None
    if best_cost is not None and exact_cost is not None:
        unnorm_gap = float(best_cost) - float(exact_cost)
    norm_regret = normalised_regret(
        best_cost,
        exact_cost,
        f_max,
        feasible=not pool_all_infeasible,
        pool_all_infeasible=pool_all_infeasible,
    )

    return {
        "one_hot_probability": float(one_hot_prob),
        "complete_legal_policy_probability": float(complete_legal_prob),
        "useful_feasible_probability": float(useful_feasible_prob),
        "useful_definition": {
            "rule": "legal_and_improves_weak_incumbent_by_frac_of_range",
            "improvement_frac": USEFUL_IMPROVEMENT_FRAC,
            "note": "Not equal to complete legal probability",
        },
        "optimal_sample_probability": float(optimal_sample_prob),
        "best_of_pool_cost": best_cost,
        "best_of_pool_unnormalised_gap": unnorm_gap,
        "best_of_pool_normalised_regret": float(norm_regret),
        "all_infeasible_pool": pool_all_infeasible,
        "all_infeasible_pool_rate": 1.0 if pool_all_infeasible else 0.0,
        "n_feasible_in_pool": n_feasible_pool,
        "pool_size": pool_size,
        "f_star": exact_cost,
        "f_max": f_max,
        "tolerances": {
            "COST_ABS_TOL": COST_ABS_TOL,
            "COST_REL_TOL": COST_REL_TOL,
            "PROB_ABS_TOL": PROB_ABS_TOL,
            "REGRET_EQ_TOL": REGRET_EQ_TOL,
        },
    }
