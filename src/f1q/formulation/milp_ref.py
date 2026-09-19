"""Independent MILP reference via scipy.optimize.milp (HiGHS). Built separately from QUBO."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import LinearConstraint, Bounds, milp

from f1q.formulation.versions import CLASSICAL_REF_VERSION, TOLERANCE_S
from f1q.hashing import sha256_json


def solve_milp_independent(costs: dict[str, Any], *, tol: float = TOLERANCE_S) -> dict[str, Any]:
    """Minimise uncentred physical objective with binary x,y and product z.

    Independent of the QUBO builder: constructs its own matrices from the cost tables.
    """
    u1 = np.asarray(costs["u1"], dtype=float)
    u2 = np.asarray(costs["u2"], dtype=float)
    v = np.asarray(costs["v"], dtype=float)
    C = float(costs["C"])
    k1 = int(u1.size)
    k2 = int(u2.size)
    if k1 == 0 or k2 == 0:
        return {
            "classical_ref_version": CLASSICAL_REF_VERSION,
            "method": "scipy.optimize.milp",
            "solver": "HiGHS (via SciPy)",
            "licence_note": "SciPy/HiGHS are free/open-source; no paid solver used",
            "status": "EMPTY_MENU",
            "success": False,
            "objective_fun": None,
            "value_with_constant": None,
            "selected": None,
            "solve_s": 0.0,
            "tolerances": {"primal": None, "comparison_tol_s": tol},
            "coefficient_scaling": {"applied": False, "max_error": 0.0},
            "n_vars": 0,
            "failure_code": "EMPTY_MENU",
            "result_hash": sha256_json({"empty": True}),
        }
    # Variables: x[0:k1], y[0:k2], z[0:k1*k2]
    n_z = k1 * k2
    n = k1 + k2 + n_z
    c = np.zeros(n)
    c[:k1] = u1
    c[k1 : k1 + k2] = u2
    for i in range(k1):
        for j in range(k2):
            c[k1 + k2 + i * k2 + j] = v[i, j]

    # Constraints
    A_rows = []
    b_lb = []
    b_ub = []
    # sum x = 1
    row = np.zeros(n)
    row[:k1] = 1.0
    A_rows.append(row)
    b_lb.append(1.0)
    b_ub.append(1.0)
    # sum y = 1
    row = np.zeros(n)
    row[k1 : k1 + k2] = 1.0
    A_rows.append(row)
    b_lb.append(1.0)
    b_ub.append(1.0)
    # z_ij <= x_i ; z_ij <= y_j ; z_ij >= x_i + y_j - 1
    for i in range(k1):
        for j in range(k2):
            z = k1 + k2 + i * k2 + j
            r1 = np.zeros(n)
            r1[z] = 1.0
            r1[i] = -1.0
            A_rows.append(r1)
            b_lb.append(-np.inf)
            b_ub.append(0.0)
            r2 = np.zeros(n)
            r2[z] = 1.0
            r2[k1 + j] = -1.0
            A_rows.append(r2)
            b_lb.append(-np.inf)
            b_ub.append(0.0)
            r3 = np.zeros(n)
            r3[z] = 1.0
            r3[i] = -1.0
            r3[k1 + j] = -1.0
            A_rows.append(r3)
            b_lb.append(-1.0)
            b_ub.append(np.inf)

    A = np.vstack(A_rows)
    constraints = LinearConstraint(A, np.asarray(b_lb), np.asarray(b_ub))
    integrality = np.ones(n)
    bounds = Bounds(0, 1)

    t0 = time.perf_counter()
    res = milp(c=c, constraints=constraints, integrality=integrality, bounds=bounds)
    solve_s = time.perf_counter() - t0

    car1, car2 = costs["selected_car_ids"]
    ids1 = costs["action_ids"][car1]
    ids2 = costs["action_ids"][car2]
    status = str(res.message)
    success = bool(res.success)
    value = None
    selected = None
    if success and res.x is not None:
        x = res.x
        i = int(np.argmax(x[:k1]))
        j = int(np.argmax(x[k1 : k1 + k2]))
        value = float(C + float(res.fun))
        selected = {
            "i": i,
            "j": j,
            "action_id_1": ids1[i],
            "action_id_2": ids2[j],
            "value": value,
        }

    mip_gap = None
    primal_bound = None
    dual_bound = None
    if hasattr(res, "mip_gap") and res.mip_gap is not None:
        try:
            mip_gap = float(res.mip_gap)
        except (TypeError, ValueError):
            mip_gap = None
    if success and res.fun is not None:
        primal_bound = float(res.fun)
    # SciPy milp/HiGHS may expose dual via unused fields; record honestly when absent.
    return {
        "classical_ref_version": CLASSICAL_REF_VERSION,
        "method": "scipy.optimize.milp",
        "solver": "HiGHS (via SciPy)",
        "licence_note": "SciPy/HiGHS are free/open-source; no paid solver used",
        "status": status,
        "success": success,
        "objective_fun": float(res.fun) if res.fun is not None else None,
        "value_with_constant": value,
        "selected": selected,
        "solve_s": solve_s,
        "timing_note": "solve_s is online MILP wall time only; excludes compilation/table construction",
        "tolerances": {"primal": None, "comparison_tol_s": tol, "solver_default": True},
        "mip_gap": mip_gap,
        "primal_bound": primal_bound,
        "dual_bound": dual_bound,
        "threads": None,
        "preprocessing": None,
        "warm_start": False,
        "cache_policy": "none",
        "coefficient_scaling": {"applied": False, "max_error": 0.0},
        "n_vars": n,
        "result_hash": sha256_json({"success": success, "selected": selected, "value": value}),
    }
