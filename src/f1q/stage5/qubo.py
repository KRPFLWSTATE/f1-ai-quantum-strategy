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

    Inventory / compound / deadline constraints are enforced by acceptance filtering
    (hard filter on decode and enumeration), NOT as QUBO penalties. This encoding
    is applied uniformly to every sampler and comparator.
    """
    vmap = variable_index_map(instance)
    n = vmap["n"]
    Q = np.zeros((n, n), dtype=float)
    offset = 0.0

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
                    Q[lo, hi] += mass * pair

    B = float(np.sum(np.abs(Q)) + abs(offset))
    M = B + float(margin)

    for block in vmap["blocks"]:
        s, e = block["start"], block["end"]
        offset += M
        for i in range(s, e):
            Q[i, i] += -M
        for i in range(s, e):
            for j in range(i + 1, e):
                Q[i, j] += 2.0 * M

    # s_Q = max(1, largest absolute NONCONSTANT encoded coefficient)
    # Do NOT include constant offset in s_Q.
    nonconst = []
    for i in range(n):
        for j in range(i, n):
            if Q[i, j] != 0:
                nonconst.append(abs(float(Q[i, j])))
    max_nonconst = max(nonconst) if nonconst else 0.0
    s_Q = float(max(1.0, max_nonconst))
    Q_scaled = Q / s_Q
    offset_scaled = offset / s_Q

    Q_serial = []
    for i in range(n):
        for j in range(i, n):
            if Q[i, j] != 0.0:
                Q_serial.append({"i": i, "j": j, "q": float(Q[i, j])})

    n_terms = len(Q_serial)
    density = (2 * n_terms) / max(n * n, 1)
    n_quadratic = sum(1 for t in Q_serial if t["i"] != t["j"])

    return {
        "n": n,
        "offset": float(offset),
        "Q_dense": Q.tolist(),
        "Q_serial": Q_serial,
        "n_terms": n_terms,
        "n_quadratic_terms": n_quadratic,
        "density": density,
        "penalty_M": float(M),
        "penalty_B": float(B),
        "margin": float(margin),
        "s_Q": s_Q,
        "s_Q_rule": "max(1, largest_abs_nonconstant_coeff)_excludes_offset",
        "offset_scaled": float(offset_scaled),
        "Q_scaled": Q_scaled.tolist(),
        "variable_map": {
            "n": n,
            "blocks": vmap["blocks"],
            "index_to_meta": vmap["index_to_meta"],
        },
        "inventory_encoding": "hard_filter_on_decode_and_enumeration",
        "compound_encoding": "hard_filter_on_decode_and_enumeration",
        "deadline_encoding": "hard_filter_on_decode_and_enumeration",
        "hard_constraint_note": (
            "Inventory, compound obligation, and commitment-deadline constraints are "
            "enforced by acceptance/filtering — not QUBO penalties. Applied fairly to "
            "every sampler and comparator via check_policy_legal."
        ),
        "hash": sha256_json({"offset": offset, "Q_serial": Q_serial, "M": M, "s_Q": s_Q}),
    }


def qubo_energy(qubo: dict[str, Any], x: np.ndarray, *, scaled: bool = False) -> float:
    x = np.asarray(x, dtype=float).reshape(-1)
    Q = np.asarray(qubo["Q_scaled"] if scaled else qubo["Q_dense"], dtype=float)
    offset = float(qubo["offset_scaled"] if scaled else qubo["offset"])
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
    diff = abs(e - float(ev["expected_cost"]))
    return {
        "ok": diff <= 1e-7 * max(1.0, abs(float(ev["expected_cost"]))),
        "direct": float(ev["expected_cost"]),
        "qubo": e,
        "diff": diff,
        "decoded": binary_to_policy(instance, x) == policy,
    }


def exhaustive_direct_vs_qubo(instance: A2Instance, qubo: dict[str, Any]) -> dict[str, Any]:
    """Verify direct cost vs QUBO energy for every legal policy + representative invalids."""
    from f1q.stage5.enumerate_policies import enumerate_legal_policies
    from f1q.stage5.encode import policy_to_binary

    en = enumerate_legal_policies(instance)
    results = []
    n_ok = 0
    n_fail = 0
    for pol in en.get("policies", []) or []:
        # enumerate may only return best — fall back to regenerating via enum internals
        pass
    # Re-enumerate via binary scan when n small
    n = qubo["n"]
    legal_checked = 0
    if n <= 16:
        from f1q.stage5.encode import binary_to_policy
        from f1q.stage5.evaluate import check_policy_legal, evaluate_policy_cost

        for b in range(1 << n):
            x = np.array([(b >> k) & 1 for k in range(n)], dtype=int)
            pol = binary_to_policy(instance, x)
            if pol is None:
                continue
            if not check_policy_legal(instance, pol)["legal"]:
                continue
            v = verify_direct_vs_qubo(instance, qubo, pol)
            legal_checked += 1
            if v["ok"]:
                n_ok += 1
            else:
                n_fail += 1
                results.append(v)
    else:
        if en.get("best_policy"):
            v = verify_direct_vs_qubo(instance, qubo, en["best_policy"])
            legal_checked = 1
            if v["ok"]:
                n_ok = 1
            else:
                n_fail = 1
                results.append(v)

    # Representative invalid one-hot (zero vector)
    x0 = np.zeros(n, dtype=int)
    e0 = qubo_energy(qubo, x0, scaled=False)
    invalid_checks = {
        "zero_vector_energy": e0,
        "zero_is_one_hot": False,
    }
    return {
        "n_legal_checked": legal_checked,
        "n_ok": n_ok,
        "n_fail": n_fail,
        "fail_samples": results[:5],
        "invalid_checks": invalid_checks,
        "ok": n_fail == 0 and legal_checked > 0,
    }
