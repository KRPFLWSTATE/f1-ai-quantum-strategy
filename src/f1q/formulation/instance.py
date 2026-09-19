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
        "validation_agreements": 0,
        "round_trip_ok": 0,
        "cap": None,
        "hidden_cap": False,
    }
    if cross_check_simulator:
        from f1q.formulation.downstream_policy import compounds_after_mount, compounds_used, obligation_met

        menus = action_model["menus"]
        a_list = [CarAction.model_validate(a) for a in menus[selected[0]]]
        b_list = [CarAction.model_validate(b) for b in menus[selected[1]]]
        pairs = [(a, b) for a in a_list for b in b_list]
        cross["expected"] = len(pairs)
        cross["analytical_semantic"] = 0
        cross["simulated_semantic"] = 0
        required = int(public.distinct_compounds_required)
        obs_cars = {row["car_id"]: row for row in obs_data["cars"]}
        checkpoint = sim.clone()

        def analytical_obligation_ok(action: CarAction) -> tuple[bool, str]:
            car = obs_cars[action.car_id]
            inv = list((obs_data.get("inventories") or {}).get(action.car_id) or [])
            used = compounds_after_mount(car, inv, None)
            if action.kind in {"pit_now", "delay_laps"}:
                if action.compound is None:
                    return False, "missing_compound"
                after = set(used)
                after.add(str(action.compound))
                if len(after) < required:
                    return False, "instruction_leaves_obligation_unmet"
                return True, "instructed_stop_meets_obligation"
            # continuation
            if len(used) >= required:
                return True, "continuation_obligation_already_met"
            if car.get("in_pit_lane"):
                # In-pit continuation preserves committed service; infer target if public.
                pending_c = car.get("pending_compound")
                if pending_c:
                    after = set(used)
                    after.add(str(pending_c))
                    return (len(after) >= required), "in_pit_committed_service"
                # Observable-only: if already in pit, service compounds from pending may be unset
                # on the public observation; require simulation.
                return False, "in_pit_needs_simulation"
            # Downstream policy will pit onto an alternate unused set when unmet.
            after = set(used)
            alt = None
            for item in inv:
                if item.get("used") or item.get("set_id") == car.get("mounted_set_id"):
                    continue
                if item["compound"] not in used:
                    alt = item["compound"]
                    break
            if alt is None:
                return False, "no_alternate_set_for_downstream"
            after.add(alt)
            return (len(after) >= required), "downstream_policy_alternate_stop"

        for a, b in pairs:
            joint = build_joint_plan(a, b, selected)
            plan = simulator_plan_payload(joint)
            try:
                checkpoint.validate_plan(plan)
                cross["validation_agreements"] += 1
                rt = simulator_plan_payload(build_joint_plan(a, b, selected))
                if rt != plan:
                    cross["disagreements"].append(
                        {
                            "action_ids": {a.car_id: a.action_id, b.car_id: b.action_id},
                            "error": "round_trip_mismatch",
                            "failure_code": "ROUND_TRIP",
                        }
                    )
                    cross["failed"] += 1
                    continue
                cross["round_trip_ok"] += 1
                ok_a, why_a = analytical_obligation_ok(a)
                ok_b, why_b = analytical_obligation_ok(b)
                if ok_a and ok_b:
                    cross["checked"] += 1
                    cross["analytical_semantic"] += 1
                    continue
                # Fall back to full terminal simulation when analytical proof is insufficient.
                clone = checkpoint.clone()
                clone.apply_plan(plan)
                clone.continue_to_finish()
                reason_codes: list[str] = []
                for action in (a, b):
                    car = clone.engine.state["cars"][action.car_id]
                    if not obligation_met(car, required):
                        reason_codes.append(f"terminal_obligation_unmet:{action.car_id}")
                    if action.kind in {"pit_now", "delay_laps"} and action.compound:
                        if action.compound not in compounds_used(car):
                            reason_codes.append(f"instructed_compound_not_used:{action.car_id}")
                cross["simulated_semantic"] += 1
                if reason_codes:
                    cross["semantic_failures"].append(
                        {
                            "action_ids": {a.car_id: a.action_id, b.car_id: b.action_id},
                            "reason_codes": reason_codes,
                            "analytical": {"a": why_a, "b": why_b},
                            "failure_code": "SEMANTIC_ILLEGAL",
                        }
                    )
                    cross["failed"] += 1
                else:
                    cross["checked"] += 1
            except Exception as exc:
                cross["disagreements"].append(
                    {
                        "action_ids": {a.car_id: a.action_id, b.car_id: b.action_id},
                        "error": str(exc),
                        "failure_code": "VALIDATE",
                    }
                )
                cross["failed"] += 1

    # Full-to-reduced equivalence: members must share the versioned signature with their representative.
    reduction_proof: dict[str, Any] = {"cars": {}, "ok": True}
    from f1q.formulation.actions import equivalence_signature

    for cid in selected:
        red = action_model["reduction"][cid]
        member_map = red["member_to_representative"]
        full_model = generate_action_model(obs, public, selected_car_ids=selected, reduce=False)
        full_actions = {a["action_id"]: CarAction.model_validate(a) for a in full_model["menus"][cid]}
        car_proof = []
        for member_id, rep_id in member_map.items():
            if member_id == rep_id:
                continue
            m_act = full_actions.get(member_id)
            r_act = full_actions.get(rep_id)
            if m_act is None or r_act is None:
                reduction_proof["ok"] = False
                car_proof.append({"member": member_id, "rep": rep_id, "ok": False, "reason": "missing"})
                continue
            ok = equivalence_signature(m_act) == equivalence_signature(r_act)
            if not ok:
                reduction_proof["ok"] = False
            car_proof.append(
                {
                    "member": member_id,
                    "rep": rep_id,
                    "ok": ok,
                    "member_sig": list(equivalence_signature(m_act)),
                    "rep_sig": list(equivalence_signature(r_act)),
                }
            )
        reduction_proof["cars"][cid] = car_proof

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
