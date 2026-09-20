"""Size-ladder measurements and resource estimates for A2 rungs."""

from __future__ import annotations

import time
from typing import Any

from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.ideal_sim import estimate_statevector_memory_bytes, statevector_feasible
from f1q.stage5.milp import solve_a2_milp
from f1q.stage5.model import A2Instance, build_a2_instance
from f1q.stage5.qubo import build_a2_qubo


RUNG_SPECS = {
    "circuit_unit": {"n_scenarios": 2, "n_epochs": 2, "n_actions": 2},
    "tiny": {"n_scenarios": 3, "n_epochs": 2, "n_actions": 3},
    "small": {"n_scenarios": 4, "n_epochs": 3, "n_actions": 3},
    "larger": {"n_scenarios": 8, "n_epochs": 4, "n_actions": 4},
}


def measure_rung(rung: str, *, family_id: str, seed: int, execute_exact: bool) -> dict[str, Any]:
    spec = RUNG_SPECS[rung]
    t0 = time.perf_counter()
    inst = build_a2_instance(
        instance_id=f"{rung}:{family_id}:{seed}",
        family_id=family_id,
        rung=rung,
        seed=seed,
        **spec,
    )
    construct_s = time.perf_counter() - t0
    t1 = time.perf_counter()
    qubo = build_a2_qubo(inst)
    qubo_s = time.perf_counter() - t1
    n = inst.n_logical_vars()
    mem = estimate_statevector_memory_bytes(n)
    row: dict[str, Any] = {
        "rung": rung,
        "n_info_sets": len(inst.info_sets),
        "n_scenarios": len(inst.scenarios),
        "n_epochs": inst.n_epochs,
        "n_actions_per_car": spec["n_actions"],
        "logical_vars": n,
        "qubo_terms": qubo["n_terms"],
        "qubo_density": qubo["density"],
        "statevector_memory_bytes_complex128": mem,
        "ideal_statevector_feasible": statevector_feasible(n),
        "construction_s": construct_s + qubo_s,
        "executed_exact": False,
        "feasible_policy_count": None,
        "exact_enum_s": None,
        "milp_s": None,
        "note": None,
    }
    if execute_exact and n <= 16:
        en = enumerate_legal_policies(inst)
        row["feasible_policy_count"] = en.get("n_legal")
        row["exact_enum_s"] = en.get("elapsed_s")
        row["executed_exact"] = en.get("status") == "OK"
        milp = solve_a2_milp(inst, time_limit_s=20.0)
        row["milp_s"] = milp.get("solve_s")
        row["milp_success"] = milp.get("success")
    elif not execute_exact:
        # Derived estimate of one-hot space
        space = 1
        for b in inst.variable_blocks():
            space *= b["size"]
        row["feasible_policy_count"] = None
        row["one_hot_space_estimate"] = space
        row["note"] = "resource_estimation_only_not_circuit_execution"
    if n >= 30:
        row["note"] = (
            (row.get("note") or "")
            + "; dense statevector NOT claimed locally practical without measured evidence"
        ).strip("; ")
    return row


def build_size_ladder(family_id: str = "fam.green_pit_low.tyre_near_linear.traffic_sparse") -> list[dict[str, Any]]:
    rows = []
    rows.append(measure_rung("circuit_unit", family_id=family_id, seed=101, execute_exact=True))
    rows.append(measure_rung("tiny", family_id=family_id, seed=202, execute_exact=True))
    rows.append(measure_rung("small", family_id=family_id, seed=303, execute_exact=False))
    rows.append(measure_rung("larger", family_id=family_id, seed=404, execute_exact=False))
    return rows
