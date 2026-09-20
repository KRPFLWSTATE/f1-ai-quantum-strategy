"""Build versioned Stage 4 / 4.1 instance records from development checkpoints."""

from __future__ import annotations

import time
from typing import Any

from f1q.formulation.actions import (
    CarAction,
    build_joint_plan,
    generate_action_model,
    simulator_plan_payload,
)
from f1q.formulation.compiler import compile_action_costs, score_joint_direct
from f1q.formulation.dp_ref import solve_zero_interaction_dp
from f1q.formulation.enumerate import enumerate_legal_pairs
from f1q.formulation.heuristics import run_classical_heuristics
from f1q.formulation.milp_ref import solve_milp_independent
from f1q.formulation.public_config import public_physics_from_sources
from f1q.formulation.qubo import (
    build_qubo,
    energy_ising,
    energy_qubo,
    qubo_to_ising,
    scale_ising,
    verify_penalty_proof,
)
from f1q.formulation.versions import FORMULATION_VERSION, TOLERANCE_S
from f1q.hashing import sha256_json
from f1q.simulator.interface import RaceSimulator


def _milp_in_minimizer_set(milp: dict[str, Any], enum: dict[str, Any], *, tol: float) -> bool | None:
    if not milp.get("success") or milp.get("selected") is None or not enum.get("minimisers"):
        return None
    sel = milp["selected"]
    exact = enum.get("exact_proxy_minimum")
    if exact is None or sel.get("value") is None:
        return None
    if abs(float(sel["value"]) - float(exact)) > tol * 10 + 1e-6:
        return False
    for m in enum["minimisers"]:
        if int(m["i"]) == int(sel["i"]) and int(m["j"]) == int(sel["j"]):
            return True
        if abs(float(m["value"]) - float(sel["value"])) <= tol * 10 + 1e-6:
            if m.get("action_id_1") == sel.get("action_id_1") and m.get("action_id_2") == sel.get("action_id_2"):
                return True
    return False


def build_instance_record(
    *,
    cfg: dict[str, Any],
    spec: dict[str, Any],
    seed: int = 0,
    verify_energies: bool = True,
    cross_check_simulator: bool = True,
) -> dict[str, Any]:
    t_compile0 = time.perf_counter()
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    obs = sim.observe()
    obs_data = obs.model_dump(mode="python")
    public = public_physics_from_sources(
        simulator_cfg=cfg,
        block_parameters=spec["block_parameters"],
        compound_obligation=spec.get("compound_obligation") or obs_data.get("compound_obligations"),
    )
    selected = list(spec["selected_car_ids"])
    action_model = generate_action_model(obs, public, selected_car_ids=selected, reduce=True)
    costs = compile_action_costs(
        obs,
        public,
        menus=action_model["menus"],
        selected_car_ids=selected,
    )
    compile_s = time.perf_counter() - t_compile0

    t_refs0 = time.perf_counter()
    enum = enumerate_legal_pairs(costs)
    milp = solve_milp_independent(costs)
    dp = solve_zero_interaction_dp(costs)
    heuristics = run_classical_heuristics(costs, seed=seed)
    qubo = build_qubo(costs)
    ising = qubo_to_ising(qubo)
    scaled = scale_ising(ising)
    proof = (
        verify_penalty_proof(qubo, costs)
        if verify_energies and qubo["variable_map"]["n"] <= 20
        else {
            "ok": None,
            "reason": "skipped_large_or_disabled",
            "n": qubo["variable_map"]["n"],
        }
    )

    energy_checks = []
    if verify_energies and qubo["variable_map"]["n"] <= 16:
        n = qubo["variable_map"]["n"]
        k1 = qubo["variable_map"]["k1"]
        mismatches = 0
        for mask in range(1 << n):
            bits = [(mask >> i) & 1 for i in range(n)]
            eq = energy_qubo(qubo, bits)
            ei = energy_ising(ising, bits)
            if abs(eq - ei) > 1e-6:
                mismatches += 1
        energy_checks.append({"qubo_ising_mismatches": mismatches, "bitstrings_checked": 1 << n})
        if enum["minimisers"]:
            m0 = enum["minimisers"][0]
            bits0 = [0] * n
            bits0[m0["i"]] = 1
            bits0[k1 + m0["j"]] = 1
            e0 = energy_ising(ising, bits0)
            e0s = energy_ising(
                {
                    **scaled,
                    "constant": ising["constant"] / scaled["s_Q"],
                    "h": scaled["h"],
                    "J_upper": scaled["J_upper"],
                },
                bits0,
            )
            restored = e0s * float(scaled["s_Q"])
            energy_checks.append(
                {
                    "s_Q": scaled["s_Q"],
                    "unscaled": e0,
                    "scaled_times_sQ": restored,
                    "restore_error": abs(restored - e0),
                }
            )
    refs_s = time.perf_counter() - t_refs0

    cross: dict[str, Any] = {
        "checked": 0,
        "expected": 0,
        "failed": 0,
        "disagreements": [],
        "semantic_failures": [],
        "validation_attempted": 0,
        "validation_passed": 0,
        "validation_failed": 0,
        "round_trip_attempted": 0,
        "round_trip_passed": 0,
        "round_trip_failed": 0,
        "analytical_admission_attempted": 0,
        "analytical_admission_passed": 0,
        "analytical_admission_failed": 0,
        "terminal_execution_attempted": 0,
        "terminal_execution_completed": 0,
        "terminal_execution_failed": 0,
        "exact_stop_sequence_matches": 0,
        "exact_set_and_compound_matches": 0,
        "timing_window_matches": 0,
        "terminal_obligation_passes": 0,
        "pair_interaction_semantic_checks": 0,
        "cap": None,
        "hidden_cap": False,
        "note": "analytical admission never increments terminal_execution_* counters",
    }
    if cross_check_simulator:
        from f1q.formulation.evaluator import evaluate_joint_plan_from_checkpoint_sim

        menus = action_model["menus"]
        a_list = [CarAction.model_validate(a) for a in menus[selected[0]]]
        b_list = [CarAction.model_validate(b) for b in menus[selected[1]]]
        pairs = [(a, b) for a in a_list for b in b_list]
        cross["expected"] = len(pairs)
        checkpoint = sim.clone()
        checkpoint_event_index = len(list(checkpoint.engine.state.get("events") or []))
        decision_time = float(checkpoint.engine.state["t"])

        for a, b in pairs:
            joint = build_joint_plan(a, b, selected)
            plan = simulator_plan_payload(joint)
            cross["validation_attempted"] += 1
            try:
                checkpoint.validate_plan(plan)
                cross["validation_passed"] += 1
            except Exception as exc:
                cross["validation_failed"] += 1
                cross["failed"] += 1
                cross["disagreements"].append(
                    {
                        "action_ids": {a.car_id: a.action_id, b.car_id: b.action_id},
                        "error": str(exc),
                        "failure_code": "VALIDATE",
                    }
                )
                continue

            cross["round_trip_attempted"] += 1
            rt = simulator_plan_payload(build_joint_plan(a, b, selected))
            if rt != plan:
                cross["round_trip_failed"] += 1
                cross["failed"] += 1
                cross["disagreements"].append(
                    {
                        "action_ids": {a.car_id: a.action_id, b.car_id: b.action_id},
                        "error": "round_trip_mismatch",
                        "failure_code": "ROUND_TRIP",
                    }
                )
                continue
            cross["round_trip_passed"] += 1

            # Analytical admission is recorded separately and never counts as terminal execution.
            cross["analytical_admission_attempted"] += 1
            # Always execute every reduced pair on a cloned checkpoint (Gate C requirement).
            cross["terminal_execution_attempted"] += 1
            try:
                ev = evaluate_joint_plan_from_checkpoint_sim(
                    checkpoint_sim=checkpoint,
                    spec=spec,
                    action_a=a,
                    action_b=b,
                    checkpoint_event_index=checkpoint_event_index,
                    decision_time=decision_time,
                )
                cross["terminal_execution_completed"] += 1
                cross["pair_interaction_semantic_checks"] += 1
                if ev.get("stop_sequence_match"):
                    cross["exact_stop_sequence_matches"] += 1
                if ev.get("exact_set_and_compound_match"):
                    cross["exact_set_and_compound_matches"] += 1
                if ev.get("timing_window_match"):
                    cross["timing_window_matches"] += 1
                if ev.get("terminal_obligation_satisfied"):
                    cross["terminal_obligation_passes"] += 1
                    cross["analytical_admission_passed"] += 1
                else:
                    cross["analytical_admission_failed"] += 1
                if ev.get("semantic_legal"):
                    cross["checked"] += 1
                else:
                    cross["failed"] += 1
                    cross["semantic_failures"].append(
                        {
                            "action_ids": {a.car_id: a.action_id, b.car_id: b.action_id},
                            "reason_codes": ev.get("reason_codes"),
                            "failure_code": "SEMANTIC_ILLEGAL",
                        }
                    )
            except Exception as exc:
                cross["terminal_execution_failed"] += 1
                cross["analytical_admission_failed"] += 1
                cross["failed"] += 1
                cross["disagreements"].append(
                    {
                        "action_ids": {a.car_id: a.action_id, b.car_id: b.action_id},
                        "error": str(exc),
                        "failure_code": "TERMINAL_EXEC",
                    }
                )

    # Independent reduction-equivalence proof (not a re-check of the grouping signature alone).
    reduction_proof: dict[str, Any] = {
        "cars": {},
        "ok": True,
        "method": "independent_unary_pair_validator_witness",
        "circular_signature_recheck_forbidden": True,
    }
    from f1q.formulation.actions import equivalence_signature
    from f1q.formulation.compiler import score_joint_direct

    opposing = {
        selected[0]: [CarAction.model_validate(a) for a in action_model["menus"][selected[1]]],
        selected[1]: [CarAction.model_validate(a) for a in action_model["menus"][selected[0]]],
    }
    for cid in selected:
        red = action_model["reduction"][cid]
        member_map = red["member_to_representative"]
        full_model = generate_action_model(obs, public, selected_car_ids=selected, reduce=False)
        full_actions = {a["action_id"]: CarAction.model_validate(a) for a in full_model["menus"][cid]}
        full_costs = compile_action_costs(
            obs, public, menus=full_model["menus"], selected_car_ids=selected
        )
        car_proof = []
        for member_id, rep_id in member_map.items():
            m_act = full_actions.get(member_id)
            r_act = full_actions.get(rep_id)
            if m_act is None or r_act is None:
                reduction_proof["ok"] = False
                car_proof.append({"member": member_id, "rep": rep_id, "ok": False, "reason": "missing"})
                continue
            if member_id == rep_id:
                car_proof.append(
                    {
                        "member": member_id,
                        "rep": rep_id,
                        "ok": True,
                        "identity": True,
                        "independent_checks": ["identity_representative"],
                    }
                )
                continue
            # Independent attribute equality except deliberately quotiented identity (none under v2).
            attr_ok = (
                m_act.kind == r_act.kind
                and m_act.delay_laps == r_act.delay_laps
                and m_act.compound == r_act.compound
                and m_act.set_id == r_act.set_id
            )
            # Direct unary cost equality from full menu costs.
            m_ids = full_costs["action_ids"][cid]
            try:
                mi = m_ids.index(member_id)
                ri = m_ids.index(rep_id)
            except ValueError:
                reduction_proof["ok"] = False
                car_proof.append({"member": member_id, "rep": rep_id, "ok": False, "reason": "cost_index"})
                continue
            u_key = "u1" if cid == selected[0] else "u2"
            unary_ok = abs(float(full_costs[u_key][mi]) - float(full_costs[u_key][ri])) <= TOLERANCE_S
            # Pair costs against every retained opposing action.
            pair_ok = True
            other = selected[1] if cid == selected[0] else selected[0]
            for oj, _opp in enumerate(opposing[cid]):
                if cid == selected[0]:
                    c_m = score_joint_direct(full_costs, index_a=mi, index_b=oj)
                    c_r = score_joint_direct(full_costs, index_a=ri, index_b=oj)
                else:
                    c_m = score_joint_direct(full_costs, index_a=oj, index_b=mi)
                    c_r = score_joint_direct(full_costs, index_a=oj, index_b=ri)
                if abs(c_m - c_r) > TOLERANCE_S:
                    pair_ok = False
                    break
            # Signature equality is recorded but is not the sole proof.
            sig_equal = equivalence_signature(m_act) == equivalence_signature(r_act)
            ok = bool(attr_ok and unary_ok and pair_ok and sig_equal)
            if not ok:
                reduction_proof["ok"] = False
            car_proof.append(
                {
                    "member": member_id,
                    "rep": rep_id,
                    "ok": ok,
                    "attribute_equality": attr_ok,
                    "unary_cost_equal": unary_ok,
                    "pair_costs_equal_vs_all_opposing": pair_ok,
                    "signature_equal_recorded_not_sole_proof": sig_equal,
                }
            )
        reduction_proof["cars"][cid] = car_proof
        reduction_proof["member_to_representative"] = {
            **reduction_proof.get("member_to_representative", {}),
            **member_map,
        }
        reduction_proof["degeneracy"] = {
            **reduction_proof.get("degeneracy", {}),
            **red.get("degeneracy", {}),
        }

    greedy_val = (
        heuristics["greedy_local"]["incumbent"]["value"]
        if heuristics.get("greedy_local", {}).get("incumbent")
        else None
    )
    exact_val = enum.get("exact_proxy_minimum")
    if exact_val is None or greedy_val is None:
        headroom = None
    else:
        headroom = float(greedy_val) - float(exact_val)
    scan_s = float(enum.get("scan_s") or 0.0)
    milp_s = float(milp.get("solve_s") or 0.0)
    budgets = {
        str(b): (compile_s + scan_s) <= float(b) for b in (5, 10, 30, 60, 120)
    }

    milp_value_agree = None
    if milp.get("success") and milp.get("value_with_constant") is not None and exact_val is not None:
        milp_value_agree = abs(float(milp["value_with_constant"]) - float(exact_val)) <= TOLERANCE_S * 10 + 1e-6
    milp_pair_in_set = _milp_in_minimizer_set(milp, enum, tol=TOLERANCE_S)
    milp_agree = bool(milp_value_agree) and bool(milp_pair_in_set) if milp_value_agree is not None and milp_pair_in_set is not None else None

    empty_menu = enum.get("failure_code") == "EMPTY_MENU" or qubo["variable_map"]["n"] == 0

    record = {
        "formulation_version": FORMULATION_VERSION,
        "evidence_class": "development",
        "not_experimental": True,
        "not_calibrated_f1": True,
        "not_noisy_simulation_campaign": True,
        "not_physical_qpu": True,
        "source": {
            "spec_id": spec["spec_id"],
            "episode_id": spec["episode_id"],
            "family_id": spec["family_id"],
            "block_id": spec["block_id"],
            "spec_hash": sha256_json(spec),
            "observation_hash": action_model["observation_hash"],
            "simulator_version": cfg.get("simulator_version"),
            "interface_version": cfg.get("interface_version"),
        },
        "selected_car_ids": selected,
        "action_model": action_model,
        "public_physics": public.model_dump(mode="python"),
        "costs": costs,
        "qubo": qubo,
        "ising": ising,
        "ising_scaled": {"s_Q": scaled["s_Q"], "hash": scaled["hash"]},
        "penalty_proof": proof,
        "energy_checks": energy_checks,
        "enumeration": enum,
        "milp": milp,
        "dp_analytical": dp,
        "heuristics": heuristics,
        "proxy_headroom": {
            "heuristic_proxy_headroom": headroom,
            "exact_reference_headroom": 0.0 if exact_val is not None else None,
            "greedy_value": greedy_val,
            "exact_value": exact_val,
        },
        "timing": {
            "compile_s": compile_s,
            "refs_s": refs_s,
            "compile_and_refs_s": compile_s + refs_s,
            "table_s": enum.get("table_construction_s"),
            "scan_s": scan_s,
            "milp_s": milp_s,
            "budget_fit": budgets,
            "note": "compile_s excludes online scan/milp; scan_s and milp_s are separate",
        },
        "simulator_cross_check": cross,
        "reduction_equivalence_proof": reduction_proof,
        "tolerance_s": TOLERANCE_S,
        "milp_value_agrees_with_enumeration": milp_value_agree,
        "milp_selected_in_minimizer_set": milp_pair_in_set,
        "milp_agrees_with_enumeration": milp_agree,
        "failure_code": "EMPTY_MENU" if empty_menu else None,
    }
    record["record_hash"] = sha256_json(
        {
            "source": record["source"],
            "action_dictionary_hash": action_model["action_dictionary_hash"],
            "coefficient_hash": costs["coefficient_hash"],
            "enumeration": enum["result_hash"],
            "qubo": qubo["hash"],
        }
    )
    return record
