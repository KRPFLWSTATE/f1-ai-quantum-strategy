"""Legal-policy enumeration for micro/tiny A2 instances."""

from __future__ import annotations

import itertools
import time
from typing import Any

from f1q.stage5.evaluate import check_policy_legal, evaluate_policy_cost
from f1q.stage5.model import A2Instance


def enumerate_legal_policies(instance: A2Instance, *, max_policies: int = 5_000_000) -> dict[str, Any]:
    """Enumerate all one-hot policies; filter by inventory/obligation legality."""
    t0 = time.perf_counter()
    blocks = []
    for info in instance.info_sets:
        for car in instance.car_ids:
            aids = [a.action_id for a in instance.actions_by_car[car]]
            blocks.append((info.info_set_id, car, aids))
    sizes = [len(b[2]) for b in blocks]
    total_one_hot = 1
    for s in sizes:
        total_one_hot *= s
        if total_one_hot > max_policies:
            return {
                "status": "TOO_LARGE",
                "total_one_hot_space": None,
                "n_legal": None,
                "best_cost": None,
                "worst_cost": None,
                "f_star": None,
                "f_max": None,
                "best_policy": None,
                "elapsed_s": time.perf_counter() - t0,
                "truncated": True,
            }

    best_cost = float("inf")
    worst_cost = float("-inf")
    best_policy = None
    n_legal = 0
    legal_costs: list[float] = []
    choice_iters = [b[2] for b in blocks]
    for choices in itertools.product(*choice_iters):
        policy: dict[str, dict[str, str]] = {}
        for (info_id, car, _), aid in zip(blocks, choices):
            policy.setdefault(info_id, {})[car] = aid
        if not check_policy_legal(instance, policy)["legal"]:
            continue
        n_legal += 1
        ev = evaluate_policy_cost(instance, policy)
        cost = float(ev["expected_cost"])
        legal_costs.append(cost)
        if cost < best_cost:
            best_cost = cost
            best_policy = policy
        if cost > worst_cost:
            worst_cost = cost
    return {
        "status": "OK",
        "total_one_hot_space": total_one_hot,
        "n_legal": n_legal,
        "best_cost": None if best_policy is None else float(best_cost),
        "worst_cost": None if best_policy is None else float(worst_cost),
        "f_star": None if best_policy is None else float(best_cost),
        "f_max": None if best_policy is None else float(worst_cost),
        "best_policy": best_policy,
        "legal_costs_sample": legal_costs[:32],
        "elapsed_s": time.perf_counter() - t0,
        "truncated": False,
    }
