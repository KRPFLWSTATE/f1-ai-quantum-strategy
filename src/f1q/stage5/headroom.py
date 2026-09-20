"""Classical correctness checks and development headroom measurement."""

from __future__ import annotations

from typing import Any

from f1q.stage5.encode import binary_to_policy, policy_to_binary
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.evaluate import causal_visibility_ok, evaluate_policy_cost
from f1q.stage5.heuristic import greedy_safe_fallback
from f1q.stage5.milp import solve_a2_milp
from f1q.stage5.model import A2Instance
from f1q.stage5.qubo import build_a2_qubo, verify_direct_vs_qubo


def run_formulation_checks(instances: list[A2Instance]) -> dict[str, Any]:
    exact_qubo = {"pass": 0, "fail": 0, "cases": []}
    enum_milp = {"pass": 0, "fail": 0, "cases": []}
    encode_decode = {"pass": 0, "fail": 0}
    nonanticipativity = {"pass": 0, "fail": 0}
    causal = {"pass": 0, "fail": 0}
    fallback = {"pass": 0, "fail": 0}
    inventory_legality = {"pass": 0, "fail": 0}

    for inst in instances:
        if causal_visibility_ok(inst):
            causal["pass"] += 1
        else:
            causal["fail"] += 1

        # Non-anticipativity by construction: variables only on info sets
        if inst.n_logical_vars() == sum(b["size"] for b in inst.variable_blocks()):
            nonanticipativity["pass"] += 1
        else:
            nonanticipativity["fail"] += 1

        qubo = build_a2_qubo(inst)
        en = enumerate_legal_policies(inst)
        if en["status"] != "OK" or en["best_policy"] is None:
            exact_qubo["fail"] += 1
            enum_milp["fail"] += 1
            continue
        inventory_legality["pass"] += 1
        v = verify_direct_vs_qubo(inst, qubo, en["best_policy"])
        if v["ok"]:
            exact_qubo["pass"] += 1
        else:
            exact_qubo["fail"] += 1
        exact_qubo["cases"].append({"id": inst.instance_id, **v})

        x = policy_to_binary(inst, en["best_policy"])
        dec = binary_to_policy(inst, x)
        if dec == en["best_policy"]:
            encode_decode["pass"] += 1
        else:
            encode_decode["fail"] += 1

        milp = solve_a2_milp(inst)
        if milp["success"] and abs(milp["objective"] - en["best_cost"]) <= 1e-5 * max(1.0, abs(en["best_cost"])):
            enum_milp["pass"] += 1
        else:
            # Try comparing when milp finds legal equal cost
            ok = False
            if milp["success"] and milp["policy"] is not None:
                ev = evaluate_policy_cost(inst, milp["policy"])
                if ev["feasible"] and abs(float(ev["expected_cost"]) - en["best_cost"]) <= 1e-5:
                    ok = True
            if ok:
                enum_milp["pass"] += 1
            else:
                enum_milp["fail"] += 1
        enum_milp["cases"].append(
            {
                "id": inst.instance_id,
                "enum": en["best_cost"],
                "milp": milp.get("objective"),
                "milp_success": milp.get("success"),
            }
        )

        fb = greedy_safe_fallback(inst)
        if fb["feasible"]:
            fallback["pass"] += 1
        else:
            fallback["fail"] += 1

    return {
        "exact_qubo_checks": exact_qubo,
        "enumeration_milp_checks": enum_milp,
        "encode_decode": encode_decode,
        "nonanticipativity_checks": nonanticipativity,
        "causal_visibility": causal,
        "fallback_feasibility": fallback,
        "inventory_legality": inventory_legality,
        "n_instances": len(instances),
    }


def measure_headroom(instances: list[A2Instance]) -> dict[str, Any]:
    """Development headroom = fallback/incumbent − exact (strongest deadline-feasible)."""
    rows = []
    nonzero = 0
    zero = 0
    unresolved = 0
    exact_in_deadline = 0
    for inst in instances:
        en = enumerate_legal_policies(inst)
        fb = greedy_safe_fallback(inst)
        milp = solve_a2_milp(inst, time_limit_s=min(30.0, inst.deadline_s * 10))
        if en["status"] != "OK" or en["best_cost"] is None:
            unresolved += 1
            rows.append({"id": inst.instance_id, "status": "UNRESOLVED"})
            continue
        exact = float(en["best_cost"])
        enum_s = float(en["elapsed_s"])
        if enum_s <= inst.deadline_s:
            exact_in_deadline += 1
            # Exact is operational competitor when inside deadline
            incumbent = exact  # strongest deadline-feasible includes exact
            # Headroom vs weak fallback only for diagnostic; operational headroom vs exact = 0
            headroom_vs_fallback = (float(fb["cost"]) - exact) if fb["feasible"] else None
            obj_headroom = 0.0  # exact finishes inside deadline
        else:
            incumbent = float(fb["cost"]) if fb["feasible"] else None
            headroom_vs_fallback = None
            obj_headroom = None if incumbent is None else float(incumbent) - exact

        if obj_headroom is None:
            unresolved += 1
            status = "UNRESOLVED"
        elif abs(obj_headroom) <= 1e-12:
            zero += 1
            status = "ZERO"
        else:
            nonzero += 1
            status = "NONZERO"

        rows.append(
            {
                "id": inst.instance_id,
                "rung": inst.rung,
                "exact_cost": exact,
                "fallback_cost": fb.get("cost"),
                "milp_cost": milp.get("objective"),
                "enum_s": enum_s,
                "deadline_s": inst.deadline_s,
                "exact_inside_deadline": enum_s <= inst.deadline_s,
                "objective_headroom": obj_headroom,
                "headroom_vs_weak_fallback": headroom_vs_fallback,
                "status": status,
            }
        )

    if nonzero and zero:
        label = "MIXED"
    elif nonzero:
        label = "NONZERO"
    elif zero and not unresolved:
        label = "ZERO"
    elif unresolved and not nonzero and not zero:
        label = "INCONCLUSIVE"
    else:
        label = "MIXED" if unresolved else "ZERO"

    return {
        "DEVELOPMENT_HEADROOM": label,
        "SUPERIORITY_PATH_AVAILABLE": label == "NONZERO",
        "n_nonzero": nonzero,
        "n_zero": zero,
        "n_unresolved": unresolved,
        "n_exact_inside_deadline": exact_in_deadline,
        "rows": rows,
        "note": (
            "When exact enumeration finishes inside the operational deadline it is an "
            "operational classical competitor; objective headroom vs that incumbent is zero. "
            "Weak fallback gaps are reported separately and do not manufacture superiority headroom."
        ),
    }
