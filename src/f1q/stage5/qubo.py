"""QUBO / Ising compilation for A2 policy selection with explicit scaling."""

from __future__ import annotations

from typing import Any

import numpy as np

from f1q.hashing import sha256_json
from f1q.stage5.encode import binary_to_policy, variable_index_map
from f1q.stage5.evaluate import evaluate_policy_cost
from f1q.stage5.model import A2Instance, info_set_for_scenario


def build_a2_qubo(instance: A2Instance, *, margin: float = 1.0) -> dict[str, Any]:
    """E(x) = offset + x^T Q x with one-hot penalties and expected policy cost.

    Inventory soft-encoded with large penalties on consumption excess (per scenario path).
    Obligation soft-encoded similarly.
    """
    vmap = variable_index_map(instance)
    n = vmap["n"]
    Q = np.zeros((n, n), dtype=float)
    offset = 0.0

    # Expected unary + leaf
    leaf = sum(sc.probability * instance.scenario_leaf_costs[sc.scenario_id] for sc in instance.scenarios)
    offset += leaf
    for meta in vmap["index_to_meta"]:
        key = (meta["info_set_id"], meta["car_id"], meta["action_id"])
        total = 0.0
        for sc in instance.scenarios:
            info = info_set_for_scenario(instance, meta["epoch"], sc.scenario_id)
            if info.info_set_id != meta["info_set_id"]:
                continue
            total += sc.probability * instance.action_costs[key]
        Q[meta["index"], meta["index"]] += total

    # Pair costs as quadratic
    c0, c1 = instance.car_ids
    for info in instance.info_sets:
        mass = sum(
            sc.probability
            for sc in instance.scenarios
            if sc.scenario_id in info.reachable_scenarios
        )
        for a1 in instance.actions_by_car[c0]:
            for a2 in instance.actions_by_car[c1]:
                pair = instance.pair_costs.get((info.info_set_id, a1.action_id, a2.action_id), 0.0)
                if pair == 0.0:
                    continue
                i = vmap["key_to_index"][(info.info_set_id, c0, a1.action_id)]
                j = vmap["key_to_index"][(info.info_set_id, c1, a2.action_id)]
                lo, hi = (i, j) if i <= j else (j, i)
                if lo == hi:
                    Q[lo, lo] += mass * pair
                else:
                    Q[lo, hi] += mass * pair  # x_i x_j coefficient in upper

    # Penalty bound from unpenalised coeffs
    B = float(np.sum(np.abs(Q)) + abs(offset))
    M = B + float(margin)

    # One-hot: M*(sum x - 1)^2 = M*(sum_i x_i + 2 sum_{i<j} x_i x_j - 2 sum x_i + 1)
    # = const M + diag(-M) + upper 2M
    for block in vmap["blocks"]:
        s, e = block["start"], block["end"]
        offset += M
        for i in range(s, e):
            Q[i, i] += -M
        for i in range(s, e):
            for j in range(i + 1, e):
                Q[i, j] += 2.0 * M

    # Inventory / compound obligations are enforced by legal-policy enumeration and
    # decode filters (hard). Soft inventory penalties are omitted so feasible one-hot
    # rankings are not distorted by M*(use-stock)^2 on under-capacity feasible points.

    # Scaling s_Q so max |coeff| ~ 1 for variational work
    coeffs = [abs(offset)]
    for i in range(n):
        for j in range(i, n):
            if Q[i, j] != 0:
                coeffs.append(abs(Q[i, j]))
    max_c = max(coeffs) if coeffs else 1.0
    s_Q = float(max_c) if max_c > 0 else 1.0
    Q_scaled = Q / s_Q
    offset_scaled = offset / s_Q

    # Upper-triangular serial
    Q_serial = []
    for i in range(n):
        for j in range(i, n):
            if Q[i, j] != 0.0:
                Q_serial.append({"i": i, "j": j, "q": float(Q[i, j])})

    n_terms = len(Q_serial)
    density = (2 * n_terms) / max(n * n, 1)

    return {
        "n": n,
        "offset": float(offset),
        "Q_dense": Q.tolist(),
        "Q_serial": Q_serial,
        "n_terms": n_terms,
        "density": density,
        "penalty_M": float(M),
        "penalty_B": float(B),
        "margin": float(margin),
        "s_Q": s_Q,
        "offset_scaled": float(offset_scaled),
        "Q_scaled": Q_scaled.tolist(),
        "variable_map": {
            "n": n,
            "blocks": vmap["blocks"],
            "index_to_meta": vmap["index_to_meta"],
        },
        "inventory_encoding": "hard_filter_on_decode_and_enumeration",
        "hash": sha256_json({"offset": offset, "Q_serial": Q_serial, "M": M}),
    }


def qubo_energy(qubo: dict[str, Any], x: np.ndarray, *, scaled: bool = False) -> float:
    x = np.asarray(x, dtype=float).reshape(-1)
    Q = np.asarray(qubo["Q_scaled"] if scaled else qubo["Q_dense"], dtype=float)
    offset = float(qubo["offset_scaled"] if scaled else qubo["offset"])
    # E = offset + sum_{i<=j} Q_ij x_i x_j with Q stored full upper+diag
    n = x.size
    e = offset
    for i in range(n):
        if x[i] == 0:
            continue
        e += Q[i, i] * x[i] * x[i]
        for j in range(i + 1, n):
            e += Q[i, j] * x[i] * x[j]
    return float(e)


def verify_direct_vs_qubo(instance: A2Instance, qubo: dict[str, Any], policy: dict) -> dict[str, Any]:
    from f1q.stage5.encode import policy_to_binary

    ev = evaluate_policy_cost(instance, policy)
    if not ev["feasible"]:
        return {"ok": False, "reason": ev["reason"]}
    x = policy_to_binary(instance, policy)
    e = qubo_energy(qubo, x, scaled=False)
    # One-hot feasible => penalty terms cancel to 0 net vs unpenalised expected cost
    # Unpenalised = expected cost; with one-hot exact, P=0 contribution net:
    # M*(0)^2 expansion: offset+=M, diag -M, so for exactly one: M - M = 0. Good.
    diff = abs(e - float(ev["expected_cost"]))
    return {
        "ok": diff <= 1e-7 * max(1.0, abs(float(ev["expected_cost"]))),
        "direct": float(ev["expected_cost"]),
        "qubo": e,
        "diff": diff,
        "decoded": binary_to_policy(instance, x) == policy,
    }
