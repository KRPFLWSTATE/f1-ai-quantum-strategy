"""Classical and quantum candidate generators with matched downstream budget K."""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable

import numpy as np

from f1q.a4.circuits import simulate_c0, simulate_c1
from f1q.a4.problem import (
    A4Instance,
    binary_to_policy,
    enumerate_legal_policies,
    plan_fingerprint,
    repair_to_legal_plan,
)
from f1q.hashing import sha256_json
from f1q.stage6.metrics_pilot import distribution_hash


def greedy_plan(instance: A4Instance) -> dict[str, Any]:
    rows = enumerate_legal_policies(instance)
    if not rows:
        return {"plan": {c: {"kind": "continuation"} for c in instance.car_ids}, "method": "empty_fallback", "proxy_cost": 0.0}
    return {**rows[0], "method": "exact_proxy_ranking"}


def local_improve(instance: A4Instance, seed: int = 0) -> dict[str, Any]:
    rows = enumerate_legal_policies(instance)
    if not rows:
        return greedy_plan(instance)
    rng = np.random.default_rng(seed)
    cur = dict(rows[0])
    for _ in range(min(12, len(rows))):
        cand = rows[int(rng.integers(0, len(rows)))]
        if cand["proxy_cost"] < cur["proxy_cost"]:
            cur = dict(cand)
    cur["method"] = "greedy_plus_local"
    return cur


def simulated_annealing(instance: A4Instance, seed: int, steps: int = 40) -> dict[str, Any]:
    rows = enumerate_legal_policies(instance)
    if not rows:
        return greedy_plan(instance)
    rng = np.random.default_rng(seed)
    idx = int(rng.integers(0, len(rows)))
    cur = dict(rows[idx])
    best = dict(cur)
    for t in range(steps):
        nxt = dict(rows[int(rng.integers(0, len(rows)))])
        d = nxt["proxy_cost"] - cur["proxy_cost"]
        T = max(0.01, 0.4 * (1.0 - t / steps))
        if d <= 0 or rng.random() < np.exp(-d / max(T, 1e-9)):
            cur = nxt
            if cur["proxy_cost"] < best["proxy_cost"]:
                best = dict(cur)
    best["method"] = "sa"
    return best


def uniform_legal(instance: A4Instance, k: int, seed: int) -> list[dict[str, Any]]:
    rows = enumerate_legal_policies(instance)
    if not rows:
        return []
    rng = np.random.default_rng(seed)
    take = min(k, len(rows))
    idxs = rng.choice(len(rows), size=take, replace=False)
    out = []
    for i in idxs:
        r = dict(rows[int(i)])
        r["method"] = "uniform_legal"
        out.append(r)
    return out


def diversity_topk(instance: A4Instance, k: int) -> list[dict[str, Any]]:
    rows = enumerate_legal_policies(instance)
    if not rows:
        return []
    selected = [dict(rows[0])]
    selected[0]["method"] = "diversity_topk"
    for _ in range(min(k, len(rows)) - 1):
        best = None
        best_d = -1.0
        for r in rows:
            if any(r["plan_hash"] == s["plan_hash"] for s in selected):
                continue
            d = min(float(np.sum(np.abs(r["x"] - s["x"]))) for s in selected)
            if d > best_d:
                best_d = d
                best = dict(r)
        if best is None:
            break
        best["method"] = "diversity_topk"
        selected.append(best)
    return selected


def mandatory_fallback(instance: A4Instance) -> dict[str, Any]:
    plan = {c: {"kind": "continuation"} for c in instance.car_ids}
    return {
        "plan": plan,
        "method": "mandatory_fallback",
        "proxy_cost": None,
        "x": None,
        "plan_hash": plan_fingerprint(plan),
        "origin": "classical_fallback",
    }


def _unique_add(out: list[dict[str, Any]], seen: set[str], row: dict[str, Any]) -> bool:
    key = row.get("plan_hash") or plan_fingerprint(row["plan"])
    row["plan_hash"] = key
    if key in seen:
        return False
    seen.add(key)
    out.append(row)
    return True


def classical_ranked(instance: A4Instance, *, seed: int = 0, n_stochastic_seeds: int = 1) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    _unique_add(out, seen, greedy_plan(instance))
    _unique_add(out, seen, local_improve(instance, seed=seed))
    for s in range(max(1, n_stochastic_seeds)):
        _unique_add(out, seen, simulated_annealing(instance, seed=seed + 17 + 101 * s))
        for r in uniform_legal(instance, k=4, seed=seed + 3 + 53 * s):
            _unique_add(out, seen, r)
    for r in diversity_topk(instance, k=8):
        _unique_add(out, seen, r)
    for r in out:
        r["origin"] = "classical"
    return out


def quantum_candidates(
    instance: A4Instance,
    qubo: dict[str, Any],
    *,
    family: str,
    p: int,
    params: tuple[list[float], list[float]],
    pool_size: int,
    seed: int,
    sim_validate: Callable,
) -> dict[str, Any]:
    gammas, betas = params
    if family == "C0":
        sim = simulate_c0(qubo, gammas, betas, scaled=True)
    else:
        sim = simulate_c1(instance, qubo, gammas, betas, scaled=True)
    n = int(qubo["n"])
    p_norm = np.asarray(sim["probs"], dtype=np.float64)
    p_norm = p_norm / max(float(p_norm.sum()), 1e-30)
    rng = np.random.default_rng(seed)
    idx = rng.choice(p_norm.size, size=int(pool_size), replace=True, p=p_norm)
    counts = Counter(int(b) for b in idx)
    hist = {str(b): int(c) for b, c in sorted(counts.items())}
    n_legal = n_decode_invalid = n_repaired = 0
    decoded = []
    seen_plans: set[str] = set()
    for b_s, cnt in sorted(hist.items(), key=lambda kv: -int(kv[1])):
        b = int(b_s)
        x = np.array([(b >> k) & 1 for k in range(n)], dtype=int)
        repaired = repair_to_legal_plan(instance, sim_validate, x)
        if binary_to_policy(instance, x) is None:
            n_decode_invalid += int(cnt)
        elif repaired["repaired"]:
            n_repaired += int(cnt)
        else:
            n_legal += int(cnt)
        ph = plan_fingerprint(repaired["plan"])
        row = {
            "bitstring": b,
            "count": int(cnt),
            "plan": repaired["plan"],
            "plan_hash": ph,
            "repaired": repaired["repaired"],
            "reason": repaired["reason"],
            "method": f"quantum_{family}_p{p}",
            "origin": "quantum",
            "family": family,
            "p": p,
            "x": x,
        }
        decoded.append(row)
        seen_plans.add(ph)
    pool = {
        "seed": int(seed),
        "requested_shots": int(pool_size),
        "actual_draws": int(idx.size),
        "histogram_sum": int(sum(counts.values())),
        "shot_conservation_ok": int(idx.size) == int(pool_size) and int(sum(counts.values())) == int(idx.size),
        "histogram_sparse": hist,
        "distribution_hash": distribution_hash(p_norm),
        "rng_id": "numpy.random.Generator",
        "rng_bit_generator": type(rng.bit_generator).__name__,
        "numpy_version": str(np.__version__),
        "n_legal_in_pool": n_legal,
        "n_decoding_invalid": n_decode_invalid,
        "n_repaired": n_repaired,
        "circuit_id": family,
        "instance_id": instance.instance_id,
        "policy_id": f"{family}_p{p}",
        "n_unique_decoded_plans": len(seen_plans),
        "duplicates_in_denominator": True,
        "repaired_in_denominator": True,
        "invalid_in_denominator": True,
    }
    return {
        "family": family,
        "p": p,
        "n": n,
        "norm": float(sim["norm"]),
        "expectation_scaled": float(sim["expectation_scaled"]),
        "amp_outside_one_hot": float(sim.get("amp_outside_one_hot", 0.0)),
        "pool": pool,
        "decoded": decoded,
        "resource_counts": {"n_qubits": n, "p": p, "param_count": 2 * p, "family": family},
        "not_claimed_novel_mixer": True,
    }


def assemble_portfolio(
    instance: A4Instance,
    qubo: dict[str, Any],
    *,
    choice: str,
    seed: int,
    pool_size: int,
    sim_validate: Callable,
    params: tuple[list[float], list[float]] | None,
    family: str | None,
    p_depth: int,
    equal_k: int,
    n_stochastic_seeds: int = 1,
) -> dict[str, Any]:
    """Matched K unique downstream slots including mandatory fallback.

    Hybrid *replaces* classical slots with quantum-origin candidates; it does not
    append an extra quantum budget.
    """
    classical = classical_ranked(instance, seed=seed, n_stochastic_seeds=n_stochastic_seeds)
    fallback = mandatory_fallback(instance)
    qrec = None
    quantum_unique: list[dict[str, Any]] = []
    if choice in {"hybrid_c0", "hybrid_c1", "always_c0", "always_c1"} and params is not None and family is not None:
        qrec = quantum_candidates(
            instance,
            qubo,
            family=family,
            p=p_depth,
            params=params,
            pool_size=pool_size,
            seed=seed,
            sim_validate=sim_validate,
        )
        seen_q: set[str] = set()
        for row in qrec["decoded"]:
            if row["plan_hash"] in seen_q:
                continue
            seen_q.add(row["plan_hash"])
            quantum_unique.append(row)

    slots: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Mandatory fallback occupies one slot.
    _unique_add(slots, seen, fallback)

    if choice in {"classical_only", "always_classical"}:
        for row in classical:
            if len(slots) >= equal_k:
                break
            _unique_add(slots, seen, row)
    else:
        for row in quantum_unique:
            if len(slots) >= equal_k:
                break
            _unique_add(slots, seen, row)
        n_q_origin = sum(1 for s in slots if s.get("origin") == "quantum")
        for row in classical:
            if len(slots) >= equal_k:
                break
            _unique_add(slots, seen, row)
        _ = n_q_origin

    # If still short, cycle remaining classical then fallback already present.
    if len(slots) < equal_k:
        for row in classical:
            if len(slots) >= equal_k:
                break
            _unique_add(slots, seen, row)

    n_quantum_origin = sum(1 for s in slots if s.get("origin") == "quantum")
    return {
        "choice": choice,
        "classical_ranked": classical,
        "quantum": qrec,
        "downstream_candidates": slots,
        "n_downstream": len(slots),
        "fairness_equal_k": equal_k,
        "portfolio_budget_matched": len(slots) == equal_k,
        "n_quantum_origin_in_k": n_quantum_origin,
        "quantum_origin_fraction": n_quantum_origin / max(len(slots), 1),
        "mandatory_classical_fallback": True,
        "replaced_not_appended": True,
        "n_classical_ranked": len(classical),
        "n_quantum_unique": len(quantum_unique),
    }


def select_by_planning_mean(
    candidates: list[dict[str, Any]],
    planning_means: dict[str, float],
) -> dict[str, Any]:
    """Lowest planning-bank mean loss; lex plan_hash tie. Order of array cannot win."""
    ranked = sorted(
        candidates,
        key=lambda r: (float(planning_means[r["plan_hash"]]), r["plan_hash"]),
    )
    winner = ranked[0]
    return {
        "selected": winner,
        "selected_plan_hash": winner["plan_hash"],
        "selected_origin": winner.get("origin"),
        "n_considered": len(candidates),
        "tie_rule": "min_planning_mean_then_lex_plan_hash",
    }
