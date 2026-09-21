"""A4-specific split-clean circuit training on all 24 anchors."""

from __future__ import annotations

import time
from typing import Any, Callable

import numpy as np

from f1q.a4.circuits import c0_objective, c1_objective, simulate_c0, simulate_c1
from f1q.a4.loop import family_spec
from f1q.a4.problem import build_a4_qubo, build_menu_and_instance, extract_causal_view, qubo_structural_features
from f1q.hashing import sha256_json
from f1q.simulator.interface import RaceSimulator

FAMILY_DEPTHS = (("C0", 1), ("C0", 2), ("C1", 1), ("C1", 2))


def fit_one_start(
    instance,
    qubo: dict[str, Any],
    family: str,
    p: int,
    *,
    seed: int,
    max_evals: int,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    n_params = 2 * p
    best_params = rng.normal(0.0, 0.5, size=n_params)
    t0 = time.perf_counter()
    evals = 0
    history = []
    success = True
    failure = None
    try:
        if family == "C0":
            best_val = c0_objective(qubo, best_params)
        else:
            best_val = c1_objective(instance, qubo, best_params)
        evals = 1
        history.append({"eval": 1, "value": float(best_val)})
        while evals < max_evals:
            cand = best_params + rng.normal(0.0, 0.35, size=n_params)
            if family == "C0":
                val = c0_objective(qubo, cand)
            else:
                val = c1_objective(instance, qubo, cand)
            evals += 1
            history.append({"eval": evals, "value": float(val)})
            if val < best_val:
                best_val = val
                best_params = cand
    except Exception as exc:  # noqa: BLE001 — retain failure
        success = False
        failure = str(exc)
        best_val = float("inf")
    gammas = best_params[:p].tolist()
    betas = best_params[p:].tolist()
    return {
        "success": success,
        "failure": failure,
        "evals": evals,
        "wall_s": time.perf_counter() - t0,
        "seed": int(seed),
        "family": family,
        "p": p,
        "best_value_scaled": float(best_val) if np.isfinite(best_val) else None,
        "best_params": best_params.tolist(),
        "gammas": gammas,
        "betas": betas,
        "n_history": len(history),
        "history_compact": history[:: max(1, len(history) // 8)] if history else [],
        "params_hash": sha256_json(best_params.tolist()),
        "n_qubits": int(qubo["n"]),
    }


def run_anchor_fits(
    anchors: list[dict[str, Any]],
    *,
    max_evals: int,
    progress: Callable[[str], None],
    t_deadline: float,
) -> list[dict[str, Any]]:
    fits: list[dict[str, Any]] = []
    for block in anchors:
        if time.perf_counter() > t_deadline:
            progress("anchor training hit campaign ceiling")
            break
        spec = family_spec(
            family_id=block["family_id"],
            block_id=block["block_id"],
            regime="SC",
            partition="anchor",
            index=int(block["index"]),
            seed=int(block["seed"]),
        )
        sim = RaceSimulator()
        sim.initialize(spec)
        sim.advance_to_checkpoint()
        view = extract_causal_view(sim.observe())
        inst = build_menu_and_instance(view)
        qubo = build_a4_qubo(inst)
        feats = qubo_structural_features(inst, qubo)
        progress(f"anchor {block['block_id']} n={qubo['n']} legal={feats['n_legal_joint']}")
        for family, p in FAMILY_DEPTHS:
            for s in range(3):
                if time.perf_counter() > t_deadline:
                    break
                seed = int(block["seed"]) + 1000 * s + 17 * p + (0 if family == "C0" else 99)
                rec = fit_one_start(inst, qubo, family, p, seed=seed, max_evals=max_evals)
                rec["block_id"] = block["block_id"]
                rec["family_id"] = block["family_id"]
                rec["features"] = feats
                rec["qubo_hash"] = qubo["hash"]
                rec["observation_hash"] = inst.observation_hash
                fits.append(rec)
    return fits


def select_donors(fits: list[dict[str, Any]], *, max_donors: int = 8) -> dict[str, Any]:
    bank: dict[str, Any] = {}
    for family, p in FAMILY_DEPTHS:
        key = f"{family}_p{p}"
        ok = [f for f in fits if f.get("success") and f.get("family") == family and int(f.get("p") or 0) == p]
        ok.sort(key=lambda f: (float(f.get("best_value_scaled") or 1e9), f.get("params_hash") or ""))
        selected = ok[:max_donors]
        bank[key] = {
            "selected": [
                {
                    "params_hash": s["params_hash"],
                    "best_params": s["best_params"],
                    "gammas": s["gammas"],
                    "betas": s["betas"],
                    "best_value_scaled": s["best_value_scaled"],
                    "block_id": s["block_id"],
                    "family_id": s["family_id"],
                    "features": s.get("features"),
                    "evals": s["evals"],
                    "seed": s["seed"],
                }
                for s in selected
            ],
            "n_successful_starts": len(ok),
            "n_selected": len(selected),
        }
    return bank
