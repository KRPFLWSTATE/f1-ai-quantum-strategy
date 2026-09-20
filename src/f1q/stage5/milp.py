"""Independent SciPy MILP reference for A2 policy selection."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from f1q.stage5.encode import binary_to_policy, variable_index_map
from f1q.stage5.evaluate import evaluate_policy_cost
from f1q.stage5.model import A2Instance, info_set_for_scenario


def solve_a2_milp(instance: A2Instance, *, time_limit_s: float = 30.0) -> dict[str, Any]:
    """Minimise expected cost with binary one-hot variables per info-set/car block.

    Inventory/obligation enforced via path linearisation for small instances.
    Independent of QUBO builder.
    """
    vmap = variable_index_map(instance)
    n = vmap["n"]
    if n == 0:
        return {"success": False, "status": "EMPTY", "objective": None, "policy": None, "solve_s": 0.0}

    # Objective: for each scenario, sum costs along path × probability
    c = np.zeros(n)
    # Unary contributions
    for meta in vmap["index_to_meta"]:
        key = (meta["info_set_id"], meta["car_id"], meta["action_id"])
        # Expected unary: sum_s p_s * cost if info set reachable in s
        total = 0.0
        for sc in instance.scenarios:
            info = info_set_for_scenario(instance, meta["epoch"], sc.scenario_id)
            if info.info_set_id != meta["info_set_id"]:
                continue
            total += sc.probability * instance.action_costs[key]
        c[meta["index"]] = total

    # Pair / crew costs need products — introduce z for each info-set joint pair when needed
    # Variables: x[0:n], then z for each info set × a1 × a2
    z_meta: list[tuple[str, str, str, int, int]] = []  # info, a1, a2, i_idx, j_idx
    z_start = n
    for block_pair in _joint_blocks(instance, vmap):
        info_id, i_idx, j_idx, a1, a2 = block_pair
        z_meta.append((info_id, a1, a2, i_idx, j_idx))
    n_z = len(z_meta)
    n_tot = n + n_z
    c_full = np.zeros(n_tot)
    c_full[:n] = c
    for zi, (info_id, a1, a2, _i, _j) in enumerate(z_meta):
        pair = instance.pair_costs.get((info_id, a1, a2), 0.0)
        # Expected pair: probability mass of scenarios through this info set
        mass = 0.0
        info = next(x for x in instance.info_sets if x.info_set_id == info_id)
        for sc in instance.scenarios:
            if sc.scenario_id in info.reachable_scenarios:
                mass += sc.probability
        c_full[z_start + zi] = mass * pair

    # Constant leaf expected
    leaf = sum(sc.probability * instance.scenario_leaf_costs[sc.scenario_id] for sc in instance.scenarios)

    A_rows = []
    b_lb = []
    b_ub = []
    # One-hot per block
    for block in vmap["blocks"]:
        row = np.zeros(n_tot)
        row[block["start"] : block["end"]] = 1.0
        A_rows.append(row)
        b_lb.append(1.0)
        b_ub.append(1.0)

    # z <= x_i, z <= x_j, z >= x_i + x_j - 1
    for zi, (_info_id, _a1, _a2, i_idx, j_idx) in enumerate(z_meta):
        z = z_start + zi
        r1 = np.zeros(n_tot)
        r1[z] = 1.0
        r1[i_idx] = -1.0
        A_rows.append(r1)
        b_lb.append(-np.inf)
        b_ub.append(0.0)
        r2 = np.zeros(n_tot)
        r2[z] = 1.0
        r2[j_idx] = -1.0
        A_rows.append(r2)
        b_lb.append(-np.inf)
        b_ub.append(0.0)
        r3 = np.zeros(n_tot)
        r3[z] = 1.0
        r3[i_idx] = -1.0
        r3[j_idx] = -1.0
        A_rows.append(r3)
        b_lb.append(-1.0)
        b_ub.append(np.inf)

    # Commitment deadline: expired actions forbidden at info sets beyond expiry
    for meta in vmap["index_to_meta"]:
        action = next(
            a
            for a in instance.actions_by_car[meta["car_id"]]
            if a.action_id == meta["action_id"]
        )
        if action.commitment_expires_epoch is not None and meta["epoch"] > action.commitment_expires_epoch:
            row = np.zeros(n_tot)
            row[meta["index"]] = 1.0
            A_rows.append(row)
            b_lb.append(0.0)
            b_ub.append(0.0)

    # Inventory stock: path-wise per scenario
    for sc in instance.scenarios:
        for car in instance.car_ids:
            for compound in ("soft", "medium", "hard"):
                row = np.zeros(n_tot)
                stock = getattr(instance.initial_inventory[car], compound)
                for epoch in range(instance.n_epochs):
                    info = info_set_for_scenario(instance, epoch, sc.scenario_id)
                    for a in instance.actions_by_car[car]:
                        if a.kind == "pit_now" and a.compound == compound:
                            idx = vmap["key_to_index"][(info.info_set_id, car, a.action_id)]
                            row[idx] = 1.0
                A_rows.append(row)
                b_lb.append(-np.inf)
                b_ub.append(float(stock))

    # Compound obligation: on every scenario path, distinct compounds used ≥ required
    # Introduce binary u[sc, car, compound] indicators (appended after z)
    u_meta: list[tuple[str, str, str]] = []
    u_start = n_tot
    for sc in instance.scenarios:
        for car in instance.car_ids:
            for compound in ("soft", "medium", "hard"):
                u_meta.append((sc.scenario_id, car, compound))
    n_u = len(u_meta)
    if n_u:
        # Expand c_full / A for u variables
        c_full = np.concatenate([c_full, np.zeros(n_u)])
        if A_rows:
            A_rows = [np.concatenate([r, np.zeros(n_u)]) for r in A_rows]
        n_tot = n_tot + n_u
        for ui, (sid, car, compound) in enumerate(u_meta):
            u_idx = u_start + ui
            # u >= each pit action of this compound along the scenario path
            sc = next(s for s in instance.scenarios if s.scenario_id == sid)
            pit_idxs = []
            for epoch in range(instance.n_epochs):
                info = info_set_for_scenario(instance, epoch, sc.scenario_id)
                for a in instance.actions_by_car[car]:
                    if a.kind == "pit_now" and a.compound == compound:
                        pit_idxs.append(vmap["key_to_index"][(info.info_set_id, car, a.action_id)])
            # Also count initially used compounds
            initially = compound in instance.initial_inventory[car].compounds_used
            if initially:
                # Force u = 1
                row = np.zeros(n_tot)
                row[u_idx] = 1.0
                A_rows.append(row)
                b_lb.append(1.0)
                b_ub.append(1.0)
            else:
                # u >= x_i for each pit; u <= sum x_i
                for idx in pit_idxs:
                    row = np.zeros(n_tot)
                    row[u_idx] = 1.0
                    row[idx] = -1.0
                    A_rows.append(row)
                    b_lb.append(0.0)
                    b_ub.append(np.inf)
                if pit_idxs:
                    row = np.zeros(n_tot)
                    row[u_idx] = 1.0
                    for idx in pit_idxs:
                        row[idx] -= 1.0
                    A_rows.append(row)
                    b_lb.append(-np.inf)
                    b_ub.append(0.0)
                else:
                    row = np.zeros(n_tot)
                    row[u_idx] = 1.0
                    A_rows.append(row)
                    b_lb.append(0.0)
                    b_ub.append(0.0)
        # sum_u >= required per (scenario, car)
        for sc in instance.scenarios:
            for car in instance.car_ids:
                req = instance.initial_inventory[car].required_compounds
                row = np.zeros(n_tot)
                for ui, (sid, c, compound) in enumerate(u_meta):
                    if sid == sc.scenario_id and c == car:
                        row[u_start + ui] = 1.0
                A_rows.append(row)
                b_lb.append(float(req))
                b_ub.append(np.inf)

    A = np.vstack(A_rows) if A_rows else np.zeros((0, n_tot))
    constraints = LinearConstraint(A, np.asarray(b_lb), np.asarray(b_ub))
    integrality = np.ones(n_tot)
    bounds = Bounds(0, 1)

    t0 = time.perf_counter()
    # SciPy milp options
    options = {"time_limit": time_limit_s, "disp": False}
    try:
        res = milp(c=c_full, constraints=constraints, integrality=integrality, bounds=bounds, options=options)
    except TypeError:
        res = milp(c=c_full, constraints=constraints, integrality=integrality, bounds=bounds)
    solve_s = time.perf_counter() - t0

    if not res.success or res.x is None:
        return {
            "success": False,
            "status": str(res.message),
            "objective": None,
            "policy": None,
            "solve_s": solve_s,
            "leaf_constant": leaf,
            "method": "scipy.optimize.milp",
        }

    x = np.rint(res.x[:n]).astype(int)
    policy = binary_to_policy(instance, x)
    if policy is None:
        return {
            "success": False,
            "status": "DECODE_FAILED",
            "objective": None,
            "policy": None,
            "solve_s": solve_s,
            "leaf_constant": leaf,
            "method": "scipy.optimize.milp",
        }
    # Re-evaluate with direct evaluator (handles obligation exactly)
    ev = evaluate_policy_cost(instance, policy)
    if not ev["feasible"]:
        # MILP inventory may miss obligation — fall back: mark failure for obligation
        return {
            "success": False,
            "status": f"POST_ILLEGAL:{ev['reason']}",
            "objective": None,
            "policy": policy,
            "solve_s": solve_s,
            "leaf_constant": leaf,
            "method": "scipy.optimize.milp",
            "milp_raw_obj": float(res.fun) + leaf,
        }
    return {
        "success": True,
        "status": "OK",
        "objective": float(ev["expected_cost"]),
        "milp_raw_obj": float(res.fun) + leaf,
        "policy": policy,
        "solve_s": solve_s,
        "leaf_constant": leaf,
        "method": "scipy.optimize.milp",
        "solver": "HiGHS (via SciPy)",
        "licence_note": "SciPy/HiGHS free/open-source; no paid solver",
    }


def _joint_blocks(instance: A2Instance, vmap: dict[str, Any]):
    out = []
    c0, c1 = instance.car_ids
    for info in instance.info_sets:
        for a1 in instance.actions_by_car[c0]:
            for a2 in instance.actions_by_car[c1]:
                i_idx = vmap["key_to_index"][(info.info_set_id, c0, a1.action_id)]
                j_idx = vmap["key_to_index"][(info.info_set_id, c1, a2.action_id)]
                out.append((info.info_set_id, i_idx, j_idx, a1.action_id, a2.action_id))
    return out
