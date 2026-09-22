"""Donor/case labels from decoded 1,024-draw legal samples.

Expectation is a separate diagnostic. Labels use the actual resampled pool.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from f1q.a4.circuits import simulate_c0, simulate_c1
from f1q.a4.contracts import N_MECHANISM_RESAMPLE_SEEDS, POOL_DRAWS, StructuralError
from f1q.a4.distributions import IdealDistribution, resample_pool
from f1q.a4.problem import binary_to_policy, proxy_direct_cost
from f1q.hashing import sha256_json
from f1q.stage5.metrics import normalised_regret


def _x_to_int(x: Any) -> int:
    arr = np.asarray(x, dtype=int).ravel()
    v = 0
    for k, b in enumerate(arr):
        if int(b):
            v |= 1 << int(k)
    return int(v)


def legal_cost_index(legal_table: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in legal_table:
        out[_x_to_int(row["x"])] = row
    return out


def label_from_pool(
    *,
    dist: IdealDistribution,
    pool: dict[str, Any],
    legal_table: list[dict[str, Any]],
    resample_s: float,
) -> dict[str, Any]:
    idx = legal_cost_index(legal_table)
    costs = [float(r["proxy_cost"]) for r in legal_table] if legal_table else [0.0]
    exact = min(costs) if costs else 0.0
    f_max = max(costs) if costs else 1.0
    draws = int(pool.get("actual_draws") or pool.get("requested_shots") or 0)
    n_feasible = 0
    n_optimal = 0
    unique_legal: set[str] = set()
    best_legal = float("inf")
    hist = pool.get("histogram_sparse") or {}
    for b_s, cnt in hist.items():
        b = int(b_s)
        c = int(cnt)
        row = idx.get(b)
        if row is None:
            continue
        n_feasible += c
        unique_legal.add(str(row["plan_hash"]))
        pc = float(row["proxy_cost"])
        if pc + 1e-12 < best_legal:
            best_legal = pc
        if abs(pc - exact) <= 1e-12:
            n_optimal += c
    feasible = n_feasible > 0
    if not feasible:
        best_legal = float(dist.expectation_scaled)
    regret = normalised_regret(
        float(best_legal if feasible else dist.expectation_scaled),
        exact,
        f_max,
        feasible=feasible,
        pool_all_infeasible=not feasible,
    )
    return {
        "raw_feasibility": (n_feasible / draws) if draws else 0.0,
        "useful_legal_candidate_yield": (len(unique_legal) / draws) if draws else 0.0,
        "optimal_sample_probability": (n_optimal / draws) if draws else 0.0,
        "best_of_pool_normalised_regret": float(regret),
        "unique_legal_candidate_count": len(unique_legal),
        "inference_resampling_s": float(resample_s),
        "n_feasible_samples": n_feasible,
        "n_optimal_samples": n_optimal,
        "pool_draws": draws,
        "exact_proxy": exact,
        "best_legal_proxy": None if not feasible else best_legal,
        "expectation_scaled_diagnostic_only": float(dist.expectation_scaled),
        "label_source": "decoded_legal_1024_draw_pool",
        "not_expectation_label": True,
        "distribution_key": dist.key,
        "seed": pool.get("seed"),
        "shot_conservation_ok": bool(pool.get("shot_conservation_ok")),
    }


def resample_label_panel(
    dist: IdealDistribution,
    legal_table: list[dict[str, Any]],
    *,
    n_seeds: int = N_MECHANISM_RESAMPLE_SEEDS,
    pool_draws: int = POOL_DRAWS,
    seed0: int = 0,
) -> dict[str, Any]:
    rows = []
    t_all = time.perf_counter()
    for i in range(int(n_seeds)):
        t0 = time.perf_counter()
        pool = resample_pool(dist, pool_draws=int(pool_draws), seed=int(seed0) + i)
        rec = label_from_pool(dist=dist, pool=pool, legal_table=legal_table, resample_s=time.perf_counter() - t0)
        rec["resample_index"] = i
        rows.append(rec)
    regrets = [float(r["best_of_pool_normalised_regret"]) for r in rows]
    return {
        "seed_rows": rows,
        "n_seeds": len(rows),
        "mean_best_of_pool_regret": float(np.mean(regrets)) if regrets else None,
        "panel_s": time.perf_counter() - t_all,
        "expectation_scaled_diagnostic_only": float(dist.expectation_scaled),
        "hash": sha256_json({"rows": rows, "key": dist.key}),
    }


def per_instance_variational_reference(
    *,
    instance: Any,
    qubo: dict[str, Any],
    family: str,
    depth: int,
    seed: int,
    legal_table: list[dict[str, Any]] | None = None,
    max_evals: int = 40,
) -> dict[str, Any]:
    """Registered per-instance COBYLA fit. Not a bank lookup."""
    from scipy.optimize import minimize

    p = int(depth)
    rng = np.random.default_rng(int(seed))
    x0 = rng.uniform(-np.pi, np.pi, size=2 * p)
    n_eval = [0]
    best = {"value": float("inf"), "gammas": list(x0[:p]), "betas": list(x0[p:])}

    def obj(x: np.ndarray) -> float:
        n_eval[0] += 1
        gammas = [float(v) for v in x[:p]]
        betas = [float(v) for v in x[p:]]
        if family == "C0":
            v = float(simulate_c0(qubo, gammas, betas, scaled=True)["expectation_scaled"])
        else:
            v = float(
                simulate_c1(
                    instance, qubo, gammas, betas, scaled=True, legal_table=legal_table, allocate_dense=False
                )["expectation_scaled"]
            )
        if v < best["value"]:
            best["value"] = v
            best["gammas"] = gammas
            best["betas"] = betas
        return v

    t0 = time.perf_counter()
    minimize(obj, x0, method="COBYLA", options={"maxiter": int(max_evals), "rhobeg": 0.5})
    fit_s = time.perf_counter() - t0
    donor = {
        "donor_id": sha256_json({"g": best["gammas"], "b": best["betas"], "family": family, "p": p})[:32],
        "family": family,
        "p": p,
        "gammas": best["gammas"],
        "betas": best["betas"],
        "best_params": best["gammas"] + best["betas"],
        "best_value_scaled": best["value"],
        "source": "per_instance_variational_fit",
        "max_evals": int(max_evals),
        "evals": n_eval[0],
        "fit_s": fit_s,
        "certified_quantum_optimum": False,
        "not_bank_lookup": True,
    }
    return {"success": n_eval[0] > 0, "donor": donor, "n_evals": n_eval[0]}


def require_not_bank_best_found(rec: dict[str, Any]) -> None:
    if rec.get("policy") == "best_found" and not rec.get("not_bank_lookup"):
        raise StructuralError(
            "SCHEMA",
            "best_found must run a registered per-instance fitting budget; bank lookup is not a variational reference",
            path="best_found",
        )
