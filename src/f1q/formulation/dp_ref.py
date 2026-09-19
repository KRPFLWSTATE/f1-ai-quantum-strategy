"""Restricted DP / analytical reference exact only when pair interactions are zero."""

from __future__ import annotations

from typing import Any

from f1q.formulation.versions import CLASSICAL_REF_VERSION, TOLERANCE_S
from f1q.hashing import sha256_json


def solve_zero_interaction_dp(costs: dict[str, Any], *, tol: float = TOLERANCE_S) -> dict[str, Any]:
    v = costs["v"]
    max_abs_v = max(abs(x) for row in v for x in row) if v else 0.0
    zero = max_abs_v <= tol
    car1, car2 = costs["selected_car_ids"]
    u1 = costs["u1"]
    u2 = costs["u2"]
    C = float(costs["C"])
    if not zero:
        return {
            "classical_ref_version": CLASSICAL_REF_VERSION,
            "method": "independent_car_minima",
            "exact_under_assumption": False,
            "assumption": "pair_interaction_identically_zero",
            "max_abs_pair": max_abs_v,
            "skipped": True,
            "reason": "nonzero_pair_interaction",
        }
    i = min(range(len(u1)), key=lambda idx: u1[idx])
    j = min(range(len(u2)), key=lambda idx: u2[idx])
    value = C + u1[i] + u2[j]
    # All tied independent minima
    i_set = [idx for idx, val in enumerate(u1) if abs(val - u1[i]) <= tol]
    j_set = [idx for idx, val in enumerate(u2) if abs(val - u2[j]) <= tol]
    minimisers = [
        {
            "i": a,
            "j": b,
            "action_id_1": costs["action_ids"][car1][a],
            "action_id_2": costs["action_ids"][car2][b],
            "value": value,
        }
        for a in i_set
        for b in j_set
    ]
    return {
        "classical_ref_version": CLASSICAL_REF_VERSION,
        "method": "independent_car_minima",
        "exact_under_assumption": True,
        "assumption": "pair_interaction_identically_zero",
        "max_abs_pair": max_abs_v,
        "exact_proxy_minimum": value,
        "minimisers": minimisers,
        "skipped": False,
        "result_hash": sha256_json({"value": value, "minimisers": minimisers}),
    }
