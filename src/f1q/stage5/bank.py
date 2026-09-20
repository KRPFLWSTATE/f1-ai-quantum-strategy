"""Preregistered QAOA parameter bank fitting (local ideal sim only)."""

from __future__ import annotations

import time
from typing import Any, Callable

import numpy as np

from f1q.hashing import sha256_json
from f1q.stage5.circuits_c1 import prepare_one_hot_uniform
from f1q.stage5.model import A2Instance
from f1q.stage5.qubo import build_a2_qubo
from f1q.stage5.sim_cache import cost_diags_from_qubo, simulate_c0_cached, simulate_c1_cached

FAMILY_DEPTHS = (("C0", 1), ("C0", 2), ("C1", 1), ("C1", 2))


def fit_one_start(
    instance: A2Instance,
    qubo: dict[str, Any],
    family: str,
    p: int,
    *,
    seed: int,
    max_evals: int = 80,
    progress: Callable[[str], None] | None = None,
    diags: np.ndarray | None = None,
    init_state: np.ndarray | None = None,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    n_params = 2 * p
    n = int(qubo["n"])
    if diags is None:
        diags = cost_diags_from_qubo(qubo, scaled=True)
    if family == "C1" and init_state is None:
        init_state = prepare_one_hot_uniform(instance)

    def _expectation(params: np.ndarray) -> float:
        gammas = params[:p].tolist()
        betas = params[p:].tolist()
        if family == "C0":
            out = simulate_c0_cached(diags, n, gammas, betas)
        else:
            out = simulate_c1_cached(instance, diags, init_state, gammas, betas)
        return float(out["expectation_scaled"])

    # Real-weight angles — no imposed 2π periodicity unless proven
    best_params = rng.normal(0.0, 0.5, size=n_params)
    best_val = _expectation(best_params)
    evals = 1
    history = [{"eval": 1, "value": best_val}]
    t0 = time.perf_counter()
    try:
        while evals < max_evals:
            cand = best_params + rng.normal(0.0, 0.35, size=n_params)
            val = _expectation(cand)
            evals += 1
            history.append({"eval": evals, "value": float(val)})
            if val < best_val:
                best_val = val
                best_params = cand
            if progress and evals % 40 == 0:
                progress(f"bank fit evals={evals}/{max_evals}")
    except Exception as exc:  # noqa: BLE001 — retain failure
        return {
            "success": False,
            "failure": str(exc),
            "evals": evals,
            "cpu_s": time.perf_counter() - t0,
            "seed": seed,
            "family": family,
            "p": p,
            "history": history,
        }
    return {
        "success": True,
        "failure": None,
        "evals": evals,
        "cpu_s": time.perf_counter() - t0,
        "seed": seed,
        "family": family,
        "p": p,
        "best_value_scaled": float(best_val),
        "best_params": best_params.tolist(),
        "history_compact": history[:: max(1, len(history) // 10)] if history else [],
        "n_history": len(history),
        "params_hash": sha256_json(best_params.tolist()),
    }


def select_donors(
    fits: list[dict[str, Any]],
    *,
    max_donors: int = 8,
) -> dict[str, Any]:
    """Select ≤8 donors per family-depth from successful training fits (best value)."""
    ok = [f for f in fits if f.get("success")]
    ok.sort(key=lambda f: (f["best_value_scaled"], f["seed"]))
    selected = ok[:max_donors]
    rejected = ok[max_donors:]
    ties = []
    if len(ok) > 1:
        for i in range(len(ok) - 1):
            if abs(ok[i]["best_value_scaled"] - ok[i + 1]["best_value_scaled"]) < 1e-12:
                ties.append({"a": ok[i]["seed"], "b": ok[i + 1]["seed"]})
    return {
        "selection_rule": "ascending_best_value_scaled_then_seed",
        "max_donors": max_donors,
        "candidates": len(ok),
        "selected": [
            {
                "seed": s["seed"],
                "best_value_scaled": s["best_value_scaled"],
                "params_hash": s["params_hash"],
                "family": s["family"],
                "p": s["p"],
                "params": s["best_params"],
            }
            for s in selected
        ],
        "rejected_count": len(rejected),
        "rejected_seeds": [r["seed"] for r in rejected],
        "ties": ties,
        "inventory_hash": sha256_json([s["params_hash"] for s in selected]),
    }


def run_parameter_bank(
    anchors: list[tuple[dict[str, Any], A2Instance]],
    *,
    starts_per_anchor: int = 3,
    max_evals: int = 80,
    max_donors: int = 8,
    progress: Callable[[str], None] | None = None,
    max_total_evals: int = 23040,
) -> dict[str, Any]:
    """Fit C0/C1 × p=1,2 on each anchor with seeded starts; build donor inventory."""
    t0 = time.perf_counter()
    total_evals = 0
    fit_failures = 0
    all_fits: list[dict[str, Any]] = []
    donors_by_key: dict[str, Any] = {}
    per_anchor: list[dict[str, Any]] = []

    for block, instance in anchors:
        qubo = build_a2_qubo(instance)
        diags = cost_diags_from_qubo(qubo, scaled=True)
        init_c1 = prepare_one_hot_uniform(instance)
        anchor_fits: list[dict[str, Any]] = []
        for family, p in FAMILY_DEPTHS:
            key = f"{family}_p{p}"
            key_fits: list[dict[str, Any]] = []
            for s_i in range(starts_per_anchor):
                if total_evals >= max_total_evals:
                    break
                seed = int(block["seed"]) + 10007 * s_i + 17 * p + (0 if family == "C0" else 99)
                remaining = max_total_evals - total_evals
                budget = min(max_evals, remaining)
                if budget <= 0:
                    break
                if progress:
                    progress(
                        f"bank {block['block_id']} {key} start={s_i} evals_so_far={total_evals}"
                    )
                fit = fit_one_start(
                    instance,
                    qubo,
                    family,
                    p,
                    seed=seed,
                    max_evals=budget,
                    progress=progress,
                    diags=diags,
                    init_state=init_c1 if family == "C1" else None,
                )
                fit["block_id"] = block["block_id"]
                fit["family_id"] = block["family_id"]
                fit["s_Q"] = qubo["s_Q"]
                total_evals += int(fit["evals"])
                if not fit["success"]:
                    fit_failures += 1
                key_fits.append(fit)
                all_fits.append(fit)
            donors_by_key.setdefault(key, []).extend(key_fits)
            anchor_fits.extend(key_fits)
        per_anchor.append({"block_id": block["block_id"], "n_fits": len(anchor_fits)})

    donor_inventory = {}
    for key, fits in donors_by_key.items():
        donor_inventory[key] = select_donors(fits, max_donors=max_donors)

    return {
        "family_depth_pairs": [f"{a}_p{b}" for a, b in FAMILY_DEPTHS],
        "n_anchors": len(anchors),
        "starts_per_anchor": starts_per_anchor,
        "max_evals_per_start": max_evals,
        "total_expectation_evaluations": total_evals,
        "fit_failures": fit_failures,
        "donors_selected_total": sum(len(v["selected"]) for v in donor_inventory.values()),
        "donor_inventory": donor_inventory,
        "per_anchor": per_anchor,
        "elapsed_s": time.perf_counter() - t0,
        "fits_retained": len(all_fits),
        "n_fit_identities": len(all_fits),
        "expected_fit_identities": len(anchors) * starts_per_anchor * len(FAMILY_DEPTHS),
        "all_fits": all_fits,
        "receipt_hash": sha256_json(
            {
                "evals": total_evals,
                "failures": fit_failures,
                "donors": {k: v["inventory_hash"] for k, v in donor_inventory.items()},
                "n_fits": len(all_fits),
            }
        ),
    }
