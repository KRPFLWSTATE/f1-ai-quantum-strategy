"""Direct policy-cost evaluator and legality (inventory, deadlines, causal visibility)."""

from __future__ import annotations

from typing import Any

from f1q.stage5.model import (
    A2Instance,
    Action,
    info_set_for_scenario,
    policy_selects,
)


def _action_lookup(instance: A2Instance, car_id: str, action_id: str) -> Action:
    for a in instance.actions_by_car[car_id]:
        if a.action_id == action_id:
            return a
    raise KeyError(action_id)


def check_policy_legal(instance: A2Instance, policy: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Validate one-hot completeness, inventory along every scenario path, obligations."""
    # Completeness / causal: every info set must have a choice for both cars
    for info in instance.info_sets:
        if info.info_set_id not in policy:
            return {"legal": False, "reason": f"missing info set {info.info_set_id}"}
        for car in instance.car_ids:
            aid = policy[info.info_set_id].get(car)
            if not aid:
                return {"legal": False, "reason": f"missing action {car}@{info.info_set_id}"}
            ids = {a.action_id for a in instance.actions_by_car[car]}
            if aid not in ids:
                return {"legal": False, "reason": f"illegal action {aid}"}

    # Inventory along each scenario (causal path through reachable info sets)
    for sc in instance.scenarios:
        inv = {c: instance.initial_inventory[c].copy() for c in instance.car_ids}
        for epoch in range(instance.n_epochs):
            info = info_set_for_scenario(instance, epoch, sc.scenario_id)
            for car in instance.car_ids:
                aid = policy_selects(policy, info.info_set_id, car)
                action = _action_lookup(instance, car, aid)
                nxt = inv[car].apply(action)
                if nxt is None:
                    return {
                        "legal": False,
                        "reason": f"inventory fail {car} {aid} scenario={sc.scenario_id} epoch={epoch}",
                    }
                inv[car] = nxt
        for car in instance.car_ids:
            if not inv[car].obligation_ok(terminal=True):
                return {
                    "legal": False,
                    "reason": f"compound obligation unmet for {car} scenario={sc.scenario_id}",
                }
    return {"legal": True, "reason": None}


def evaluate_policy_cost(instance: A2Instance, policy: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Expected team loss under scenario probabilities (direct analytical evaluator)."""
    legal = check_policy_legal(instance, policy)
    if not legal["legal"]:
        return {
            "feasible": False,
            "reason": legal["reason"],
            "expected_cost": None,
            "scenario_costs": {},
        }
    scenario_costs: dict[str, float] = {}
    expected = 0.0
    for sc in instance.scenarios:
        cost = float(instance.scenario_leaf_costs[sc.scenario_id])
        for epoch in range(instance.n_epochs):
            info = info_set_for_scenario(instance, epoch, sc.scenario_id)
            a1 = policy_selects(policy, info.info_set_id, instance.car_ids[0])
            a2 = policy_selects(policy, info.info_set_id, instance.car_ids[1])
            cost += instance.action_costs[(info.info_set_id, instance.car_ids[0], a1)]
            cost += instance.action_costs[(info.info_set_id, instance.car_ids[1], a2)]
            cost += instance.pair_costs.get((info.info_set_id, a1, a2), 0.0)
        scenario_costs[sc.scenario_id] = cost
        expected += sc.probability * cost
    return {
        "feasible": True,
        "reason": None,
        "expected_cost": float(expected),
        "scenario_costs": scenario_costs,
    }


def causal_visibility_ok(instance: A2Instance) -> bool:
    """Info-set reachable scenarios must be consistent with observable signatures."""
    for info in instance.info_sets:
        for sid in info.reachable_scenarios:
            sc = next(s for s in instance.scenarios if s.scenario_id == sid)
            if info.epoch == 0:
                continue
            if info.epoch == 1 and not info.observable_signature.startswith(f"dur:{sc.sc_duration_laps}"):
                return False
            if info.epoch >= 2:
                expected = f"dur:{sc.sc_duration_laps}|rst:{sc.restart_mode}"
                if info.observable_signature != expected:
                    return False
    return True
