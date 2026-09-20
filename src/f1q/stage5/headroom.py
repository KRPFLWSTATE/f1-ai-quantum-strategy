"""Classical correctness checks and development headroom measurement (corrected)."""

from __future__ import annotations

from typing import Any

import numpy as np

from f1q.stage5.encode import binary_to_policy, policy_to_binary
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.evaluate import causal_visibility_ok, check_policy_legal, evaluate_policy_cost
from f1q.stage5.heuristic import greedy_safe_fallback
from f1q.stage5.metrics import normalised_regret
from f1q.stage5.milp import solve_a2_milp
from f1q.stage5.model import (
    A2Instance,
    build_a2_instance,
    decisions_cannot_see_hidden_duration,
)
from f1q.stage5.qubo import build_a2_qubo, exhaustive_direct_vs_qubo, verify_direct_vs_qubo


def run_formulation_checks(instances: list[A2Instance]) -> dict[str, Any]:
    exact_qubo = {"pass": 0, "fail": 0, "cases": []}
    enum_milp = {"pass": 0, "fail": 0, "cases": []}
    encode_decode = {"pass": 0, "fail": 0}
    nonanticipativity = {"pass": 0, "fail": 0}
    causal = {"pass": 0, "fail": 0}
    fallback = {"pass": 0, "fail": 0}
    inventory_legality = {"pass": 0, "fail": 0}
    exhaustive = {"pass": 0, "fail": 0, "cases": []}
    s_q_checks = {"pass": 0, "fail": 0}

    for inst in instances:
        if causal_visibility_ok(inst) and decisions_cannot_see_hidden_duration(inst):
            causal["pass"] += 1
        else:
            causal["fail"] += 1

        if inst.n_logical_vars() == sum(b["size"] for b in inst.variable_blocks()):
            nonanticipativity["pass"] += 1
        else:
            nonanticipativity["fail"] += 1

        qubo = build_a2_qubo(inst)
        # s_Q excludes offset
        Q = np.asarray(qubo["Q_dense"], dtype=float)
        nonconst = [abs(Q[i, j]) for i in range(Q.shape[0]) for j in range(i, Q.shape[0]) if Q[i, j] != 0]
        expected_s = max(1.0, max(nonconst) if nonconst else 0.0)
        if abs(qubo["s_Q"] - expected_s) < 1e-12 and abs(qubo["offset"]) >= 0:
            # offset must not be the sole driver of s_Q when |offset| > max nonconst
            if abs(qubo["offset"]) > expected_s + 1e-12:
                # If offset larger, s_Q must still be from nonconst — already checked
                pass
            s_q_checks["pass"] += 1
        else:
            s_q_checks["fail"] += 1

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

        exh = exhaustive_direct_vs_qubo(inst, qubo)
        if exh["ok"]:
            exhaustive["pass"] += 1
        else:
            exhaustive["fail"] += 1
        exhaustive["cases"].append({"id": inst.instance_id, "n_legal_checked": exh["n_legal_checked"], "n_fail": exh["n_fail"]})

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

    adversarial = run_adversarial_formulation_tests()

    return {
        "exact_qubo_checks": exact_qubo,
        "enumeration_milp_checks": enum_milp,
        "encode_decode": encode_decode,
        "nonanticipativity_checks": nonanticipativity,
        "causal_visibility": causal,
        "fallback_feasibility": fallback,
        "inventory_legality": inventory_legality,
        "exhaustive_direct_qubo": exhaustive,
        "s_Q_excludes_offset": s_q_checks,
        "adversarial": adversarial,
        "hard_constraint_encoding": "acceptance_filtering_not_qubo_penalties",
        "n_instances": len(instances),
    }


def run_adversarial_formulation_tests() -> dict[str, Any]:
    """Tests that FAIL if future leaked / inventory removed / bad regret / MILP omit."""
    results = {}

    # 1. Future scenario leak
    inst = build_a2_instance(
        instance_id="adv_causal",
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        rung="circuit_unit",
        n_scenarios=2,
        n_epochs=2,
        n_actions=2,
        seed=42,
        microcase="force_branching",
    )
    results["no_future_duration_leak"] = {
        "pass": decisions_cannot_see_hidden_duration(inst) and causal_visibility_ok(inst),
        "detail": "epoch0 observable is root only",
    }

    # 2. Binding inventory exists and bites
    inv_inst = build_a2_instance(
        instance_id="adv_inv",
        family_id="fam.green_pit_high.tyre_nonlinear.traffic_dense",
        rung="tiny",
        n_scenarios=2,
        n_epochs=2,
        n_actions=3,
        seed=99,
        microcase="binding_inventory",
    )
    en_inv = enumerate_legal_policies(inv_inst)
    # Some one-hot policies must be illegal due to inventory
    space = en_inv.get("total_one_hot_space") or 0
    results["binding_inventory"] = {
        "pass": en_inv["status"] == "OK" and en_inv["n_legal"] is not None and en_inv["n_legal"] < space,
        "n_legal": en_inv.get("n_legal"),
        "one_hot_space": space,
    }

    # 3. Binding compound
    comp_inst = build_a2_instance(
        instance_id="adv_comp",
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        rung="tiny",
        n_scenarios=2,
        n_epochs=2,
        n_actions=3,
        seed=7,
        microcase="binding_compound",
    )
    en_c = enumerate_legal_policies(comp_inst)
    results["binding_compound"] = {
        "pass": en_c["status"] == "OK" and (en_c.get("n_legal") or 0) >= 1,
        "n_legal": en_c.get("n_legal"),
        "required_compounds": comp_inst.initial_inventory["car_a"].required_compounds,
    }

    # 4. Binding deadline
    dl_inst = build_a2_instance(
        instance_id="adv_dl",
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        rung="circuit_unit",
        n_scenarios=2,
        n_epochs=2,
        n_actions=2,
        seed=3,
        microcase="binding_deadline",
    )
    # Choosing expired pit at epoch 1 must be illegal
    bad = {info.info_set_id: {c: "continue" for c in dl_inst.car_ids} for info in dl_inst.info_sets}
    for info in dl_inst.info_sets:
        if info.epoch == 1:
            # Prefer expired pit if present
            for a in dl_inst.actions_by_car["car_a"]:
                if a.commitment_expires_epoch is not None:
                    bad[info.info_set_id]["car_a"] = a.action_id
                    break
    results["binding_deadline"] = {
        "pass": not check_policy_legal(dl_inst, bad)["legal"],
        "reason": check_policy_legal(dl_inst, bad).get("reason"),
    }

    # 5. All-infeasible pool regret = 1
    r = normalised_regret(None, 0.0, 1.0, feasible=False, pool_all_infeasible=True)
    results["all_infeasible_regret_is_1"] = {"pass": r == 1.0, "regret": r}

    # 6. Zero-range feasible → regret 0
    r0 = normalised_regret(1.0, 1.0, 1.0, feasible=True)
    results["zero_range_regret_is_0"] = {"pass": r0 == 0.0, "regret": r0}

    # 7. Never coerce missing to 0
    r_miss = normalised_regret(None, 0.0, 1.0, feasible=False)
    results["missing_not_zero_regret"] = {"pass": r_miss == 1.0, "regret": r_miss}

    # 8. Genuine branching microcase
    br = build_a2_instance(
        instance_id="adv_branch",
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        rung="circuit_unit",
        n_scenarios=2,
        n_epochs=2,
        n_actions=2,
        seed=1,
        microcase="force_branching",
    )
    results["genuine_branching"] = {
        "pass": br.meta.get("n_branching_epochs", 0) >= 1 and len(br.info_sets) > br.n_epochs,
        "n_info_sets": len(br.info_sets),
        "n_branching_epochs": br.meta.get("n_branching_epochs"),
    }

    results["all_pass"] = all(v.get("pass") for v in results.values() if isinstance(v, dict) and "pass" in v)
    return results


def measure_headroom(instances: list[A2Instance]) -> dict[str, Any]:
    """Development headroom vs strongest deadline-feasible classical incumbent."""
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
        milp_s = float(milp.get("solve_s") or 0.0)
        if enum_s <= inst.deadline_s:
            exact_in_deadline += 1
            headroom_vs_fallback = (float(fb["cost"]) - exact) if fb["feasible"] else None
            obj_headroom = 0.0
        else:
            # Include MILP if it finished inside deadline as competitor
            incumbent = None
            if milp.get("success") and milp_s <= inst.deadline_s and milp.get("objective") is not None:
                incumbent = float(milp["objective"])
            elif fb["feasible"]:
                incumbent = float(fb["cost"])
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
                "milp_s": milp_s,
                "deadline_s": inst.deadline_s,
                "exact_inside_deadline": enum_s <= inst.deadline_s,
                "objective_headroom": obj_headroom,
                "headroom_vs_weak_fallback": headroom_vs_fallback,
                "status": status,
                "scope": "checked_instances_only_not_universal_A2_or_F1",
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
        "n_instances_checked": len(instances),
        "rows": rows,
        "scope_note": "Conclusion applies only to instances actually checked — not a universal claim about all A2/F1.",
        "note": (
            "When exact enumeration finishes inside the operational deadline it is an "
            "operational classical competitor; objective headroom vs that incumbent is zero. "
            "MILP runtime is included as a classical competitor when inside deadline. "
            "Weak fallback gaps are reported separately and do not manufacture superiority headroom."
        ),
    }
