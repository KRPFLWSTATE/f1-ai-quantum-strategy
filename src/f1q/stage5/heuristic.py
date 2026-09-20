"""Deterministic classical heuristic / safe fallback for A2."""

from __future__ import annotations

from typing import Any

from f1q.stage5.evaluate import check_policy_legal, evaluate_policy_cost
from f1q.stage5.model import A2Instance


def greedy_safe_fallback(instance: A2Instance) -> dict[str, Any]:
    """Deterministic feasible incumbent: prefer continue, else cheapest legal pit.

    Weak fallback must not manufacture headroom — reported separately from exact.
    """
    policy: dict[str, dict[str, str]] = {}
    for info in instance.info_sets:
        policy[info.info_set_id] = {}
        for car in instance.car_ids:
            # Prefer continue if present
            ids = [a.action_id for a in instance.actions_by_car[car]]
            chosen = "continue" if "continue" in ids else ids[0]
            policy[info.info_set_id][car] = chosen

    if check_policy_legal(instance, policy)["legal"]:
        ev = evaluate_policy_cost(instance, policy)
        return {
            "policy": policy,
            "feasible": True,
            "cost": float(ev["expected_cost"]),
            "method": "greedy_prefer_continue",
        }

    # Repair: try all one-hot combinations greedily per info set in order
    for info in instance.info_sets:
        best_local = None
        best_score = float("inf")
        acts0 = instance.actions_by_car[instance.car_ids[0]]
        acts1 = instance.actions_by_car[instance.car_ids[1]]
        for a0 in acts0:
            for a1 in acts1:
                trial = {k: dict(v) for k, v in policy.items()}
                trial[info.info_set_id] = {
                    instance.car_ids[0]: a0.action_id,
                    instance.car_ids[1]: a1.action_id,
                }
                # Partial legality check via full if complete
                if all(trial[i.info_set_id][c] for i in instance.info_sets for c in instance.car_ids):
                    if not check_policy_legal(instance, trial)["legal"]:
                        continue
                    cost = float(evaluate_policy_cost(instance, trial)["expected_cost"])
                else:
                    cost = (
                        instance.action_costs[(info.info_set_id, instance.car_ids[0], a0.action_id)]
                        + instance.action_costs[(info.info_set_id, instance.car_ids[1], a1.action_id)]
                    )
                if cost < best_score:
                    best_score = cost
                    best_local = (a0.action_id, a1.action_id)
        if best_local is None:
            return {"policy": None, "feasible": False, "cost": None, "method": "greedy_prefer_continue"}
        policy[info.info_set_id] = {
            instance.car_ids[0]: best_local[0],
            instance.car_ids[1]: best_local[1],
        }

    legal = check_policy_legal(instance, policy)
    if not legal["legal"]:
        return {"policy": policy, "feasible": False, "cost": None, "reason": legal["reason"], "method": "greedy_prefer_continue"}
    ev = evaluate_policy_cost(instance, policy)
    return {
        "policy": policy,
        "feasible": True,
        "cost": float(ev["expected_cost"]),
        "method": "greedy_prefer_continue",
    }
