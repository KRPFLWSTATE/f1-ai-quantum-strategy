"""Classical and quantum candidate generators with matched downstream budget K."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from f1q.a4.problem import (
    A4Instance,
    binary_to_policy,
    enumerate_legal_policies,
    plan_fingerprint,
    repair_to_legal_plan,
)
from f1q.hashing import sha256_json


def _legal_rows(instance: A4Instance, legal_table: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if legal_table is not None:
        return legal_table
    return enumerate_legal_policies(instance)


def greedy_plan(instance: A4Instance, legal_table: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = _legal_rows(instance, legal_table)
    if not rows:
        return {"plan": {c: {"kind": "continuation"} for c in instance.car_ids}, "method": "empty_fallback", "proxy_cost": 0.0}
    return {**rows[0], "method": "exact_proxy_ranking"}


def local_improve(instance: A4Instance, seed: int = 0, legal_table: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = _legal_rows(instance, legal_table)
    if not rows:
        return greedy_plan(instance, legal_table)
    rng = np.random.default_rng(seed)
    cur = dict(rows[0])
    for _ in range(min(12, len(rows))):
        cand = rows[int(rng.integers(0, len(rows)))]
        if cand["proxy_cost"] < cur["proxy_cost"]:
            cur = dict(cand)
    cur["method"] = "greedy_plus_local"
    return cur


def simulated_annealing(instance: A4Instance, seed: int, steps: int = 40, legal_table: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = _legal_rows(instance, legal_table)
    if not rows:
        return greedy_plan(instance, legal_table)
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


def uniform_legal(instance: A4Instance, k: int, seed: int, legal_table: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = _legal_rows(instance, legal_table)
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


def diversity_topk(instance: A4Instance, k: int, legal_table: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = _legal_rows(instance, legal_table)
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
            d = min(
                float(np.sum(np.abs(np.asarray(r["x"], dtype=float) - np.asarray(s["x"], dtype=float))))
                for s in selected
                if s.get("x") is not None
            )
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


def classical_ranked(
    instance: A4Instance,
    *,
    seed: int = 0,
    n_stochastic_seeds: int = 1,
    legal_table: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    _unique_add(out, seen, greedy_plan(instance, legal_table))
    _unique_add(out, seen, local_improve(instance, seed=seed, legal_table=legal_table))
    for s in range(max(1, n_stochastic_seeds)):
        _unique_add(out, seen, simulated_annealing(instance, seed=seed + 17 + 101 * s, legal_table=legal_table))
        for r in uniform_legal(instance, k=4, seed=seed + 3 + 53 * s, legal_table=legal_table):
            _unique_add(out, seen, r)
    for r in diversity_topk(instance, k=8, legal_table=legal_table):
        _unique_add(out, seen, r)
    for r in out:
        r["origin"] = "classical"
        r["found_by"] = sorted(set(list(r.get("found_by") or []) + ["classical"]))
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
    prepared_case_hash: str | None = None,
    dist_cache: Any | None = None,
    legal_table: list[dict[str, Any]] | None = None,
    distribution: Any | None = None,
) -> dict[str, Any]:
    from f1q.a4.distributions import build_ideal_distribution, resample_pool

    gammas, betas = params
    n = int(qubo["n"])
    pch = prepared_case_hash or sha256_json({"instance": instance.instance_id, "qubo": qubo.get("hash")})
    dist = distribution or build_ideal_distribution(
        instance=instance,
        qubo=qubo,
        family=family,
        depth=p,
        gammas=gammas,
        betas=betas,
        prepared_case_hash=pch,
        cache=dist_cache,
        legal_table=legal_table,
    )
    pool_rec = resample_pool(dist, pool_draws=int(pool_size), seed=int(seed))
    n_legal = n_decode_invalid = n_repaired = 0
    decoded = []
    seen_plans: set[str] = set()
    hist = pool_rec["histogram_sparse"]
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
            "found_by": ["quantum"],
            "family": family,
            "p": p,
            "x": x,
        }
        decoded.append(row)
        seen_plans.add(ph)
    pool = {
        **pool_rec,
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
        "rng_id": "numpy.random.Generator",
        "numpy_version": str(np.__version__),
        "distribution_hash": dist.distribution_hash,
    }
    return {
        "family": family,
        "p": p,
        "n": n,
        "norm": 1.0,
        "expectation_scaled": float(dist.expectation_scaled),
        "amp_outside_one_hot": 0.0,
        "pool": pool,
        "decoded": decoded,
        "distribution_key": dist.key,
        "dense_2n_allocated": dist.dense_2n_allocated,
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
    legal_table: list[dict[str, Any]] | None = None,
    donor_id: str | None = None,
    prepared_case_hash: str | None = None,
    dist_cache: Any | None = None,
) -> dict[str, Any]:
    """Matched K unique downstream slots.

    Hybrid never removes the fallback or the strongest classical incumbent.
    Quantum competes only for remaining slots. Duplicate hashes merge found_by.
    """
    classical = classical_ranked(instance, seed=seed, n_stochastic_seeds=n_stochastic_seeds, legal_table=legal_table)
    fallback = mandatory_fallback(instance)
    fallback["found_by"] = ["classical"]
    qrec = None
    quantum_unique: list[dict[str, Any]] = []
    quantumish = {
        "hybrid_c0",
        "hybrid_c1",
        "always_c0",
        "always_c1",
        "C0_p1",
        "C0_p2",
        "C1_p1",
        "C1_p2",
    }
    if choice in quantumish and params is not None and family is not None:
        seed_receipts: list[dict[str, Any]] = []
        seen_q: set[str] = set()
        qrec = None
        n_seeds = max(1, int(n_stochastic_seeds))
        for s_i in range(n_seeds):
            qrec_s = quantum_candidates(
                instance,
                qubo,
                family=family,
                p=p_depth,
                params=params,
                pool_size=pool_size,
                seed=seed + 10007 * s_i,
                sim_validate=sim_validate,
                prepared_case_hash=prepared_case_hash,
                dist_cache=dist_cache,
                legal_table=legal_table,
            )
            seed_receipts.append(
                {
                    **qrec_s["pool"],
                    "policy_seed": seed + 10007 * s_i,
                    "seed_index": s_i,
                }
            )
            qrec = qrec_s
            for row in qrec_s["decoded"]:
                if row["plan_hash"] in seen_q:
                    continue
                seen_q.add(row["plan_hash"])
                row = dict(row)
                row["donor_id"] = donor_id
                quantum_unique.append(row)
        if qrec is not None:
            qrec = dict(qrec)
            qrec["seed_receipts"] = seed_receipts
            qrec["n_stochastic_seeds"] = n_seeds
            qrec["pool"] = seed_receipts[0]

    def _merge(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        fb = sorted(set(list(existing.get("found_by") or []) + list(incoming.get("found_by") or [])))
        existing["found_by"] = fb
        if "quantum" in fb and "classical" in fb:
            existing["origin"] = "merged"
        return existing

    by_hash: dict[str, dict[str, Any]] = {}

    def _put(row: dict[str, Any]) -> None:
        ph = row.get("plan_hash") or plan_fingerprint(row["plan"])
        row = dict(row)
        row["plan_hash"] = ph
        row["found_by"] = sorted(set(list(row.get("found_by") or [row.get("origin") or "classical"])))
        if ph in by_hash:
            _merge(by_hash[ph], row)
        else:
            by_hash[ph] = row

    _put(fallback)
    incumbent = None
    for row in classical:
        if row["plan_hash"] != fallback["plan_hash"]:
            incumbent = row
            break
    if incumbent is not None:
        _put(incumbent)

    classical_k_hashes: list[str] = [fallback["plan_hash"]]
    if incumbent is not None:
        classical_k_hashes.append(incumbent["plan_hash"])
    for row in classical:
        if len(classical_k_hashes) >= equal_k:
            break
        if row["plan_hash"] not in classical_k_hashes:
            classical_k_hashes.append(row["plan_hash"])
            if choice in {"classical_only", "always_classical", "stop_fallback"}:
                _put(row)

    if choice not in {"classical_only", "always_classical", "stop_fallback"}:
        for row in quantum_unique:
            _put(row)
        # Fill remaining slots: quantum incremental first, then classical, never dropping fallback/incumbent.
        protected = {fallback["plan_hash"]}
        if incumbent is not None:
            protected.add(incumbent["plan_hash"])
        slots_order = [fallback["plan_hash"]]
        if incumbent is not None:
            slots_order.append(incumbent["plan_hash"])
        for row in quantum_unique:
            if len(slots_order) >= equal_k:
                break
            if row["plan_hash"] not in slots_order:
                _put(row)
                slots_order.append(row["plan_hash"])
        for row in classical:
            if len(slots_order) >= equal_k:
                break
            if row["plan_hash"] not in slots_order:
                _put(row)
                slots_order.append(row["plan_hash"])
        slots = [by_hash[h] for h in slots_order if h in by_hash]
    else:
        slots_order = list(classical_k_hashes)
        slots = [by_hash[h] for h in slots_order if h in by_hash]

    if len(slots) > equal_k:
        slots = slots[:equal_k]
    legal_n = len(_legal_rows(instance, legal_table))
    matched = (len(slots) == equal_k) or (legal_n < equal_k and len(slots) == legal_n)

    classical_set = set(classical_k_hashes[:equal_k])
    hybrid_set = {s["plan_hash"] for s in slots}
    for s in slots:
        fb = set(s.get("found_by") or [])
        s["quantum_generated"] = "quantum" in fb
        s["classical_generated"] = "classical" in fb
        s["quantum_incremental_at_k"] = s["plan_hash"] in hybrid_set and s["plan_hash"] not in classical_set

    n_quantum_origin = sum(1 for s in slots if s.get("quantum_generated"))
    n_incremental = sum(1 for s in slots if s.get("quantum_incremental_at_k"))
    return {
        "choice": choice,
        "classical_ranked": classical,
        "quantum": qrec,
        "downstream_candidates": slots,
        "n_downstream": len(slots),
        "fairness_equal_k": equal_k,
        "portfolio_budget_matched": bool(matched) and len(slots) <= equal_k,
        "n_quantum_origin_in_k": n_quantum_origin,
        "n_quantum_incremental_at_k": n_incremental,
        "quantum_origin_fraction": n_quantum_origin / max(len(slots), 1),
        "mandatory_classical_fallback": True,
        "strongest_classical_incumbent_retained": incumbent is None or (incumbent["plan_hash"] in {s["plan_hash"] for s in slots}),
        "replaced_not_appended": True,
        "n_classical_ranked": len(classical),
        "n_quantum_unique": len(quantum_unique),
        "classical_k_hashes": list(classical_set),
        "legal_plan_count": legal_n,
        "n_unique_hashes": len({s["plan_hash"] for s in slots}),
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
