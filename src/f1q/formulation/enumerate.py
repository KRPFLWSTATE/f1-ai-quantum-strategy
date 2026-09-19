"""Vectorised legal enumeration over K1×K2 pairs (not 2^(K1+K2))."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from f1q.formulation.versions import CLASSICAL_REF_VERSION, TOLERANCE_S
from f1q.hashing import sha256_json


def enumerate_legal_pairs(costs: dict[str, Any], *, tol: float = TOLERANCE_S) -> dict[str, Any]:
    t_table0 = time.perf_counter()
    u1 = np.asarray(costs["u1"], dtype=float)
    u2 = np.asarray(costs["u2"], dtype=float)
    v = np.asarray(costs["v"], dtype=float)
    C = float(costs["C"])
    if u1.size == 0 or u2.size == 0:
        return {
            "classical_ref_version": CLASSICAL_REF_VERSION,
            "method": "numpy_vectorised_legal_enumeration",
            "k1": int(u1.size),
            "k2": int(u2.size),
            "legal_action_count": 0,
            "exact_proxy_minimum": None,
            "minimisers": [],
            "n_ties": 0,
            "gap_to_next_value": None,
            "table_construction_s": time.perf_counter() - t_table0,
            "scan_s": 0.0,
            "memory_estimate_bytes": 0,
            "tolerance_s": tol,
            "operational_competitor": True,
            "failure_code": "EMPTY_MENU",
            "result_hash": sha256_json({"empty": True, "k1": int(u1.size), "k2": int(u2.size)}),
        }
    # Broadcasting: table[i,j] = C + u1[i] + u2[j] + v[i,j]
    table = C + u1[:, None] + u2[None, :] + v
    t_table = time.perf_counter() - t_table0

    t_scan0 = time.perf_counter()
    flat = table.ravel()
    best = float(np.min(flat))
    # All ties within tolerance of best
    mask = np.abs(table - best) <= tol
    idxs = np.argwhere(mask)
    t_scan = time.perf_counter() - t_scan0

    car1, car2 = costs["selected_car_ids"]
    ids1 = costs["action_ids"][car1]
    ids2 = costs["action_ids"][car2]
    minimisers = [
        {
            "i": int(i),
            "j": int(j),
            "action_id_1": ids1[int(i)],
            "action_id_2": ids2[int(j)],
            "value": float(table[int(i), int(j)]),
        }
        for i, j in idxs
    ]
    minimisers.sort(key=lambda m: (m["action_id_1"], m["action_id_2"]))

    # Gap to second-best distinct value (if any)
    unique_vals = np.unique(np.round(flat, 12))
    unique_vals.sort()
    gap = None
    if len(unique_vals) >= 2:
        gap = float(unique_vals[1] - unique_vals[0])

    mem_bytes = int(table.nbytes + u1.nbytes + u2.nbytes + v.nbytes)
    result = {
        "classical_ref_version": CLASSICAL_REF_VERSION,
        "method": "numpy_vectorised_legal_enumeration",
        "k1": int(u1.size),
        "k2": int(u2.size),
        "legal_action_count": int(u1.size * u2.size),
        "exact_proxy_minimum": best,
        "minimisers": minimisers,
        "n_ties": len(minimisers),
        "gap_to_next_value": gap,
        "table_construction_s": t_table,
        "scan_s": t_scan,
        "memory_estimate_bytes": mem_bytes,
        "tolerance_s": tol,
        "operational_competitor": True,
        "result_hash": sha256_json(
            {
                "best": best,
                "minimisers": [(m["action_id_1"], m["action_id_2"]) for m in minimisers],
                "k1": int(u1.size),
                "k2": int(u2.size),
            }
        ),
    }
    return result
