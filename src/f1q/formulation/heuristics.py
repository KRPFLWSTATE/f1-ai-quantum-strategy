"""Classical heuristic candidates over legal joint plans using the direct proxy scorer."""

from __future__ import annotations

import math
import random
from typing import Any

from f1q.formulation.compiler import score_joint_direct
from f1q.formulation.versions import CLASSICAL_REF_VERSION


def _score(costs: dict[str, Any], i: int, j: int) -> float:
    return score_joint_direct(costs, index_a=i, index_b=j, centred=False)


def greedy_plus_local(costs: dict[str, Any], *, eval_budget: int = 10_000) -> dict[str, Any]:
    k1 = len(costs["u1"])
    k2 = len(costs["u2"])
    if k1 == 0 or k2 == 0:
        return {
            "method": "greedy_plus_one_car_local",
            "classical_ref_version": CLASSICAL_REF_VERSION,
            "incumbent": None,
            "evaluations": 0,
            "direct_scorer_calls": 0,
            "eval_budget": eval_budget,
            "legal_incumbent": False,
            "failure_code": "EMPTY_MENU",
        }
    evaluations = 0
    # Preselection: score all unary-min car1 against each car2 action.
    i0 = min(range(k1), key=lambda i: costs["u1"][i])
    # The min over u1 does not call the joint scorer; joint calls follow.
    j0 = min(range(k2), key=lambda j: _score(costs, i0, j))
    evaluations += k2
    best_i, best_j = i0, j0
    best = _score(costs, best_i, best_j)
    evaluations += 1
    improved = True
    while improved and evaluations < eval_budget:
        improved = False
        for i in range(k1):
            if evaluations >= eval_budget:
                break
            val = _score(costs, i, best_j)
            evaluations += 1
            if val < best - 1e-15:
                best, best_i = val, i
                improved = True
        for j in range(k2):
            if evaluations >= eval_budget:
                break
            val = _score(costs, best_i, j)
            evaluations += 1
            if val < best - 1e-15:
                best, best_j = val, j
                improved = True
    car1, car2 = costs["selected_car_ids"]
    return {
        "method": "greedy_plus_one_car_local",
        "classical_ref_version": CLASSICAL_REF_VERSION,
        "incumbent": {
            "i": best_i,
            "j": best_j,
            "action_id_1": costs["action_ids"][car1][best_i],
            "action_id_2": costs["action_ids"][car2][best_j],
            "value": best,
        },
        "evaluations": evaluations,
        "direct_scorer_calls": evaluations,
        "eval_budget": eval_budget,
        "legal_incumbent": True,
        "note": "evaluations counts every score_joint_direct call including repeated calls",
    }


def uniform_legal_sample(
    costs: dict[str, Any],
    *,
    n_samples: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    k1 = len(costs["u1"])
    k2 = len(costs["u2"])
    if k1 == 0 or k2 == 0:
        return {
            "method": "uniform_legal_sample",
            "seed": seed,
            "n_samples": n_samples,
            "incumbent": None,
            "legal_incumbent": False,
            "evaluations": 0,
            "direct_scorer_calls": 0,
            "failure_code": "EMPTY_MENU",
        }
    car1, car2 = costs["selected_car_ids"]
    best_i = rng.randrange(k1)
    best_j = rng.randrange(k2)
    best = _score(costs, best_i, best_j)
    evaluations = 1  # initial state
    for _ in range(n_samples):
        i = rng.randrange(k1)
        j = rng.randrange(k2)
        val = _score(costs, i, j)
        evaluations += 1
        if val < best:
            best, best_i, best_j = val, i, j
    return {
        "method": "uniform_legal_sample",
        "seed": seed,
        "n_samples": n_samples,
        "incumbent": {
            "i": best_i,
            "j": best_j,
            "action_id_1": costs["action_ids"][car1][best_i],
            "action_id_2": costs["action_ids"][car2][best_j],
            "value": best,
        },
        "legal_incumbent": True,
        "evaluations": evaluations,
        "direct_scorer_calls": evaluations,
        "accounting": "1 initial + n_samples loop evaluations",
    }


def simulated_annealing_legal(
    costs: dict[str, Any],
    *,
    seed: int,
    steps: int = 200,
    t0: float = 5.0,
) -> dict[str, Any]:
    rng = random.Random(seed)
    k1 = len(costs["u1"])
    k2 = len(costs["u2"])
    if k1 == 0 or k2 == 0:
        return {
            "method": "simulated_annealing_legal",
            "seed": seed,
            "steps": steps,
            "incumbent": None,
            "legal_incumbent": False,
            "evaluations": 0,
            "direct_scorer_calls": 0,
            "failure_code": "EMPTY_MENU",
        }
    car1, car2 = costs["selected_car_ids"]
    i, j = rng.randrange(k1), rng.randrange(k2)
    cur = _score(costs, i, j)
    evaluations = 1  # initial state
    best_i, best_j, best = i, j, cur
    for step in range(steps):
        temp = t0 * (1.0 - step / max(1, steps))
        if rng.random() < 0.5:
            ni = rng.randrange(k1)
            nj = j
        else:
            ni = i
            nj = rng.randrange(k2)
        nxt = _score(costs, ni, nj)
        evaluations += 1
        delta = nxt - cur
        if delta <= 0 or rng.random() < math.exp(-delta / max(temp, 1e-9)):
            i, j, cur = ni, nj, nxt
            if cur < best:
                best_i, best_j, best = i, j, cur
    return {
        "method": "simulated_annealing_legal",
        "seed": seed,
        "steps": steps,
        "incumbent": {
            "i": best_i,
            "j": best_j,
            "action_id_1": costs["action_ids"][car1][best_i],
            "action_id_2": costs["action_ids"][car2][best_j],
            "value": best,
        },
        "legal_incumbent": True,
        "evaluations": evaluations,
        "direct_scorer_calls": evaluations,
        "accounting": "1 initial + steps proposal evaluations",
    }


def run_classical_heuristics(costs: dict[str, Any], *, seed: int = 20260919) -> dict[str, Any]:
    g = greedy_plus_local(costs)
    u = uniform_legal_sample(costs, n_samples=64, seed=seed)
    s = simulated_annealing_legal(costs, seed=seed + 1, steps=128)
    return {"greedy_local": g, "uniform": u, "annealing": s, "seed": seed}
