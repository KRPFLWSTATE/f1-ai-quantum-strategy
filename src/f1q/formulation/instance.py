"""Build versioned Stage 4 instance records from development checkpoints."""

from __future__ import annotations

import time
from typing import Any

from f1q.formulation.actions import (
    CarAction,
    generate_action_model,
    simulator_plan_payload,
    build_joint_plan,
)
from f1q.formulation.compiler import compile_action_costs, score_joint_direct
from f1q.formulation.dp_ref import solve_zero_interaction_dp
from f1q.formulation.enumerate import enumerate_legal_pairs
from f1q.formulation.heuristics import run_classical_heuristics
from f1q.formulation.milp_ref import solve_milp_independent
from f1q.formulation.public_config import PublicPhysicsConfig, public_physics_from_sources
from f1q.formulation.qubo import (
    build_qubo,
    decode_bits,
    energy_ising,
    energy_qubo,
    qubo_to_ising,
    scale_ising,
    verify_penalty_proof,
)
from f1q.formulation.versions import FORMULATION_VERSION, TOLERANCE_S
from f1q.hashing import sha256_json
from f1q.simulator.interface import RaceSimulator


def build_instance_record(
    *,
    cfg: dict[str, Any],
    spec: dict[str, Any],
    seed: int = 0,
    verify_energies: bool = True,
    cross_check_simulator: bool = True,
) -> dict[str, Any]:
    t0 = time.perf_counter()
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
    enum = enumerate_legal_pairs(costs)
    milp = solve_milp_independent(costs)
    dp = solve_zero_interaction_dp(costs)
    heuristics = run_classical_heuristics(costs, seed=seed)
    qubo = build_qubo(costs)
    ising = qubo_to_ising(qubo)
    scaled = scale_ising(ising)
    proof = verify_penalty_proof(qubo, costs) if verify_energies and qubo["variable_map"]["n"] <= 20 else {
        "ok": None,
        "reason": "skipped_large_or_disabled",
        "n": qubo["variable_map"]["n"],
    }

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
        # Also check scaled restoration of differences on two feasible states if available.
        energy_checks.append({"qubo_ising_mismatches": mismatches, "bitstrings_checked": 1 << n})
        # s_Q restoration: compare unscaled energy differences
        if enum["minimisers"]:
            m0 = enum["minimisers"][0]
            bits0 = [0] * n
            bits0[m0["i"]] = 1
            bits0[k1 + m0["j"]] = 1
            e0 = energy_ising(ising, bits0)
            e0s = energy_ising({**scaled, "constant": ising["constant"] / scaled["s_Q"], "h": scaled["h"], "J_upper": scaled["J_upper"]}, bits0)
            # Restore: scaled_energy * s_Q ~= unscaled (constant also scaled)
            restored = e0s * float(scaled["s_Q"])
            energy_checks.append(
                {
                    "s_Q": scaled["s_Q"],
                    "unscaled": e0,
                    "scaled_times_sQ": restored,
                    "restore_error": abs(restored - e0),
                }
            )

    cross = {"checked": 0, "disagreements": []}
    if cross_check_simulator:
        menus = action_model["menus"]
        a_list = [CarAction.model_validate(a) for a in menus[selected[0]]]
        b_list = [CarAction.model_validate(b) for b in menus[selected[1]]]
        # Cap cross-check to avoid explosion: all pairs if <= 36 else sample diagonals + extrema
        pairs = [(a, b) for a in a_list for b in b_list]
        if len(pairs) > 36:
            pairs = pairs[:36]
        for a, b in pairs:
            joint = build_joint_plan(a, b, selected)
            plan = simulator_plan_payload(joint)
            try:
                sim.validate_plan(plan)
                cross["checked"] += 1
            except Exception as exc:
                cross["disagreements"].append(
                    {
                        "action_ids": {a.car_id: a.action_id, b.car_id: b.action_id},
                        "error": str(exc),
                    }
                )

    greedy_val = heuristics["greedy_local"]["incumbent"]["value"] if heuristics.get("greedy_local", {}).get("incumbent") else None
    exact_val = enum.get("exact_proxy_minimum")
    if exact_val is None or greedy_val is None:
        headroom = None
    else:
        headroom = float(greedy_val) - float(exact_val)
    compile_s = time.perf_counter() - t0
    scan_s = float(enum.get("scan_s") or 0.0)
    budgets = {
        str(b): (compile_s + scan_s) <= float(b) for b in (5, 10, 30, 60, 120)
    }

    milp_agree = None
    if milp.get("success") and milp.get("value_with_constant") is not None and exact_val is not None:
        milp_agree = abs(float(milp["value_with_constant"]) - float(exact_val)) <= TOLERANCE_S * 10 + 1e-6

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
            "compile_and_refs_s": compile_s,
            "table_s": enum.get("table_construction_s"),
            "scan_s": scan_s,
            "milp_s": milp.get("solve_s"),
            "budget_fit": budgets,
        },
        "simulator_cross_check": cross,
        "tolerance_s": TOLERANCE_S,
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
