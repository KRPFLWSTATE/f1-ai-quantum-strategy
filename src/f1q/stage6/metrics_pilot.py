"""Pilot metrics: exact ideal distribution once; reusable seeded pool sampling."""

from __future__ import annotations

import time
from collections import Counter
from typing import Any

import numpy as np

from f1q.hashing import sha256_bytes
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


def distribution_hash(probs: np.ndarray) -> str:
    """SHA-256 of little-endian float64 normalised probability vector."""
    p = np.asarray(probs, dtype=np.float64).reshape(-1)
    s = float(p.sum())
    p_norm = p / max(s, 1e-30)
    return sha256_bytes(np.ascontiguousarray(p_norm).tobytes())


def pool_sample_metrics(
    instance: A2Instance,
    probs: np.ndarray,
    *,
    exact_cost: float | None,
    f_max: float | None,
    pool_size: int,
    seed: int,
    distribution_id: str | None = None,
    circuit_id: str | None = None,
    parameter_id: str | None = None,
    instance_id: str | None = None,
    policy_id: str | None = None,
    persist_histogram: bool = True,
) -> dict[str, Any]:
    """One seeded best-of-pool measurement with replacement (no Hilbert-space draw cap).

    Draws exactly ``pool_size`` outcomes with replacement from the normalised
    distribution. Duplicate bitstrings are allowed. Counts always sum to
    ``actual_draws``. Sparse bitstring→count histograms are persisted so the
    sample is independently recoverable without the dense probability vector.
    """
    if pool_size < 0:
        raise ValueError("pool_size must be non-negative")
    n = int(round(np.log2(probs.size)))
    assert 1 << n == probs.size
    p_sum = float(np.asarray(probs, dtype=float).sum())
    p_norm = np.asarray(probs, dtype=np.float64) / max(p_sum, 1e-30)
    dist_hash = distribution_hash(p_norm)
    rng = np.random.default_rng(seed)
    bitgen = type(rng.bit_generator).__name__
    # CRITICAL: never cap draws at 2**n — sampling with replacement may exceed Hilbert dim.
    idx = rng.choice(1 << n, size=int(pool_size), replace=True, p=p_norm)
    actual_draws = int(idx.size)
    counts = Counter(int(b) for b in idx)
    count_sum = int(sum(counts.values()))

    best_cost: float | None = None
    best_bitstring: int | None = None
    n_one_hot = 0
    n_legal = 0
    n_invalid = 0
    n_infeasible_decode = 0
    n_semantic_invalid = 0
    tied_best: list[int] = []
    t0 = time.perf_counter()
    for b_int, cnt in counts.items():
        x = np.array([(b_int >> k) & 1 for k in range(n)], dtype=int)
        pol = binary_to_policy(instance, x)
        if pol is None:
            n_infeasible_decode += cnt
            n_invalid += cnt
            continue
        n_one_hot += cnt
        if not check_policy_legal(instance, pol)["legal"]:
            n_invalid += cnt
            n_semantic_invalid += cnt
            continue
        n_legal += cnt
        c = float(evaluate_policy_cost(instance, pol)["expected_cost"])
        if best_cost is None or c < best_cost - COST_ABS_TOL:
            best_cost = c
            best_bitstring = b_int
            tied_best = [b_int]
        elif best_cost is not None and abs(c - best_cost) <= COST_ABS_TOL:
            tied_best.append(b_int)

    pool_all_infeasible = n_legal == 0
    # Candidate selection: lex-first among tied best bitstrings (stable, inspectable).
    if tied_best:
        best_bitstring = min(tied_best)
    norm_regret = normalised_regret(
        best_cost,
        exact_cost,
        f_max,
        feasible=not pool_all_infeasible,
        pool_all_infeasible=pool_all_infeasible,
    )
    unnorm = None if best_cost is None or exact_cost is None else float(best_cost) - float(exact_cost)
    histogram_sparse = {str(b): int(c) for b, c in sorted(counts.items())} if persist_histogram else None
    return {
        "seed": int(seed),
        "requested_shots": int(pool_size),
        "actual_draws": actual_draws,
        "counts_sum": count_sum,
        "histogram_sum": count_sum,
        "shot_conservation_ok": actual_draws == int(pool_size) and count_sum == actual_draws,
        "n_unique_outcomes": len(counts),
        "n_one_hot_in_pool": int(n_one_hot),
        "n_feasible_in_pool": int(n_legal),
        "n_legal_in_pool": int(n_legal),
        "n_invalid_in_pool": int(n_invalid),
        "n_infeasible_decode": int(n_infeasible_decode),
        "n_decoding_invalid": int(n_infeasible_decode),
        "n_semantic_invalid": int(n_semantic_invalid),
        "best_of_pool_cost": best_cost,
        "best_of_pool_bitstring": best_bitstring,
        "selected_candidate_bitstring": best_bitstring,
        "n_tied_best": len(tied_best),
        "candidate_selection_rule": "lex_first_among_tied_best_bitstrings",
        "tie_rule": "lex_first_among_tied_best_bitstrings",
        "best_of_pool_unnormalised_gap": unnorm,
        "best_of_pool_normalised_regret": float(norm_regret),
        "all_infeasible_pool": pool_all_infeasible,
        "distribution_id": distribution_id,
        "distribution_hash": dist_hash,
        "circuit_id": circuit_id,
        "parameter_id": parameter_id,
        "instance_id": instance_id or getattr(instance, "instance_id", None),
        "policy_id": policy_id,
        "n_qubits": n,
        "rng_id": "numpy.random.Generator",
        "rng_bit_generator": bitgen,
        "numpy_version": str(np.__version__),
        "sampling_with_replacement": True,
        "hilbert_cap_applied": False,
        "pool_size": int(pool_size),  # retained for backward-compatible readers
        "pool_s": time.perf_counter() - t0,
        "counts_digest_n_nonzero": len(counts),
        "histogram_sparse": histogram_sparse,
    }


def aggregate_pools(pool_rows: list[dict[str, Any]]) -> dict[str, Any]:
    regs = [float(r["best_of_pool_normalised_regret"]) for r in pool_rows]
    feas = [int(r.get("n_feasible_in_pool", r.get("n_legal_in_pool", 0))) for r in pool_rows]
    draws = [int(r.get("actual_draws", r.get("pool_size", 0))) for r in pool_rows]
    return {
        "n_pool_seeds": len(pool_rows),
        "mean_normalised_regret": float(np.mean(regs)) if regs else None,
        "std_normalised_regret": float(np.std(regs, ddof=1)) if len(regs) > 1 else 0.0,
        "mean_feasible_in_pool": float(np.mean(feas)) if feas else 0.0,
        "mean_actual_draws": float(np.mean(draws)) if draws else 0.0,
        "all_shot_conservation_ok": all(bool(r.get("shot_conservation_ok", False)) for r in pool_rows),
        "all_infeasible_pool_rate": float(np.mean([1.0 if r["all_infeasible_pool"] else 0.0 for r in pool_rows])),
    }
