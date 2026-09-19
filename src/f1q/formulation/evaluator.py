"""Simulator evaluator adapter — separate implementation from the proxy compiler.

Evaluates complete joint plans on cloned simulator checkpoints and reports modelled
outcome/classification quantities. Must not share scoring code with the compiler.
"""

from __future__ import annotations

from typing import Any

from f1q.formulation.actions import CarAction, build_joint_plan, simulator_plan_payload
from f1q.formulation.downstream_policy import normalize_stop_record
from f1q.formulation.versions import DOWNSTREAM_POLICY_ID, DOWNSTREAM_POLICY_VERSION
from f1q.simulator.interface import RaceSimulator
from f1q.formulation.downstream_policy import compounds_used, obligation_met

# Architectural separation marker: evaluator imports simulator; compiler must not.
EVALUATOR_IMPLEMENTATION = "simulator_clone_continue_to_finish"
COMPILER_IMPLEMENTATION = "analytical_remaining_time_proxy"


def _as_action(obj: CarAction | dict[str, Any]) -> CarAction:
    if isinstance(obj, CarAction):
        return obj
    return CarAction.model_validate(obj)


def _executed_stops_from_events(events: list[dict[str, Any]], car_id: str) -> list[dict[str, Any]]:
    stops = []
    for ev in events:
        if ev.get("car_id") != car_id:
            continue
        et = ev.get("type") or ev.get("event_type")
        if et in {"pit_entry", "service_start", "tyre_change"}:
            stops.append(
                normalize_stop_record(
                    car_id=car_id,
                    source="simulator",
                    kind=str(et),
                    compound=(ev.get("detail") or {}).get("compound") if isinstance(ev.get("detail"), dict) else ev.get("compound"),
                    set_id=(ev.get("detail") or {}).get("set_id") if isinstance(ev.get("detail"), dict) else ev.get("set_id"),
                    pit_lap_index=ev.get("lap") or (ev.get("detail") or {}).get("completed_laps"),
                    reason=None,
                )
            )
    return stops


def evaluate_joint_plan_on_checkpoint(
    *,
    cfg: dict[str, Any],
    spec: dict[str, Any],
    action_a: CarAction | dict[str, Any],
    action_b: CarAction | dict[str, Any],
) -> dict[str, Any]:
    """Modelled development diagnostic — not race truth.

    Reports checkpoint instruction validity, execution success, instructed vs
    executed stops, terminal compound-obligation satisfaction, and overall
    semantic legality with reason codes. Does not label a terminally illegal
    plan as legal.
    """
    action_a = _as_action(action_a)
    action_b = _as_action(action_b)
    selected = list(spec["selected_car_ids"])
    joint = build_joint_plan(action_a, action_b, selected)
    plan = simulator_plan_payload(joint)
    required = int((spec.get("compound_obligation") or {}).get("distinct_compounds_required") or 2)
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    checkpoint_instruction_valid = False
    legality: dict[str, Any] = {"ok": False}
    reason_codes: list[str] = []
    try:
        legality = sim.validate_plan(plan)
        checkpoint_instruction_valid = bool(legality.get("ok"))
    except Exception as exc:
        reason_codes.append(f"checkpoint_instruction_invalid:{type(exc).__name__}")
        return {
            "implementation": EVALUATOR_IMPLEMENTATION,
            "not_race_truth": True,
            "modelled_development_diagnostic": True,
            "checkpoint_instruction_valid": False,
            "execution_success": False,
            "terminal_obligation_satisfied": False,
            "semantic_legal": False,
            "legal": False,
            "reason_codes": reason_codes + [f"{type(exc).__name__}: {exc}"],
            "legality": {"ok": False, "error": str(exc)},
            "action_ids": joint["_meta"]["action_ids"],
            "downstream_policy_id": DOWNSTREAM_POLICY_ID,
            "downstream_policy_version": DOWNSTREAM_POLICY_VERSION,
        }

    try:
        clone = sim.clone()
        clone.apply_plan(plan)
        _, outcome = clone.continue_to_finish()
        execution_success = True
    except Exception as exc:
        reason_codes.append(f"execution_failed:{type(exc).__name__}")
        return {
            "implementation": EVALUATOR_IMPLEMENTATION,
            "not_race_truth": True,
            "modelled_development_diagnostic": True,
            "checkpoint_instruction_valid": checkpoint_instruction_valid,
            "execution_success": False,
            "terminal_obligation_satisfied": False,
            "semantic_legal": False,
            "legal": False,
            "reason_codes": reason_codes + [f"{type(exc).__name__}: {exc}"],
            "legality": legality,
            "action_ids": joint["_meta"]["action_ids"],
            "downstream_policy_id": DOWNSTREAM_POLICY_ID,
            "downstream_policy_version": DOWNSTREAM_POLICY_VERSION,
        }

    ranks = {cid: outcome["ranking"]["ranks"][cid] for cid in selected}
    field_size = int(outcome["ranking"]["field_size"])
    r1 = ranks[selected[0]]
    r2 = ranks[selected[1]]
    L = (r1 + r2 - 2) / (2 * (field_size - 1))

    terminal: dict[str, Any] = {}
    obligation_ok = True
    instructed_vs_executed: dict[str, Any] = {}
    events = list(clone.engine.state.get("events") or [])
    for action in (action_a, action_b):
        cid = action.car_id
        car = clone.engine.state["cars"][cid]
        used = sorted(compounds_used(car))
        met = obligation_met(car, required)
        if not met:
            obligation_ok = False
            reason_codes.append(f"terminal_obligation_unmet:{cid}")
        executed = _executed_stops_from_events(events, cid)
        instructed = []
        if action.kind in {"pit_now", "delay_laps"}:
            instructed.append(
                normalize_stop_record(
                    car_id=cid,
                    source="instruction",
                    kind=action.kind,
                    compound=action.compound,
                    set_id=action.set_id,
                    pit_lap_index=0 if action.kind == "pit_now" else int(action.delay_laps or 0),
                )
            )
        # Check instructed set/compound appears in terminal state when a stop was instructed.
        set_ok = True
        if action.kind in {"pit_now", "delay_laps"} and action.set_id:
            if car.get("mounted_set_id") != action.set_id and action.compound not in used:
                set_ok = False
                reason_codes.append(f"instructed_set_not_reflected:{cid}")
            elif action.compound and action.compound not in used:
                set_ok = False
                reason_codes.append(f"instructed_compound_not_used:{cid}")
        instructed_vs_executed[cid] = {
            "instructed": instructed,
            "executed_stops": executed,
            "instructed_set_compound_ok": set_ok,
        }
        terminal[cid] = {
            "used_compounds": used,
            "compound": car.get("compound"),
            "mounted_set_id": car.get("mounted_set_id"),
            "obligation_met": met,
            "finish_time": car.get("finish_time"),
            "classified_position": car.get("classified_position_init"),
        }

    semantic_legal = checkpoint_instruction_valid and execution_success and obligation_ok and not any(
        code.startswith("instructed_") for code in reason_codes
    )
    if semantic_legal:
        reason_codes.append("ok")

    return {
        "implementation": EVALUATOR_IMPLEMENTATION,
        "not_race_truth": True,
        "modelled_development_diagnostic": True,
        "checkpoint_instruction_valid": checkpoint_instruction_valid,
        "execution_success": execution_success,
        "instructed_versus_executed": instructed_vs_executed,
        "terminal_obligation_satisfied": obligation_ok,
        "semantic_legal": semantic_legal,
        "legal": semantic_legal,
        "reason_codes": reason_codes,
        "legality": legality,
        "terminal": terminal,
        "final_used_compounds": {cid: terminal[cid]["used_compounds"] for cid in selected},
        "leader_finish_classification": outcome["ranking"],
        "selected_team_ranks": ranks,
        "team_rank_loss_L": float(L),
        "finish_t": float(outcome["t"]),
        "action_ids": joint["_meta"]["action_ids"],
        "downstream_policy_id": DOWNSTREAM_POLICY_ID,
        "downstream_policy_version": DOWNSTREAM_POLICY_VERSION,
    }


def assert_compiler_evaluator_separation() -> dict[str, Any]:
    import ast
    import f1q.formulation.compiler as compiler_mod
    import f1q.formulation.evaluator as evaluator_mod

    compiler_file = getattr(compiler_mod, "__file__", "")
    evaluator_file = getattr(evaluator_mod, "__file__", "")
    with open(compiler_file, encoding="utf-8") as handle:
        compiler_src = handle.read()
    with open(evaluator_file, encoding="utf-8") as handle:
        evaluator_src = handle.read()
    tree = ast.parse(compiler_src)
    banned_names = {"continue_to_finish", "RaceSimulator"}
    banned_modules = {"f1q.formulation.evaluator", "f1q.simulator.engine", "f1q.simulator.interface"}
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in banned_modules or alias.name.startswith("f1q.simulator"):
                    hits.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod in banned_modules or mod.startswith("f1q.simulator"):
                hits.append(f"from {mod}")
        elif isinstance(node, ast.Name) and node.id in banned_names:
            hits.append(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in banned_names:
            hits.append(node.attr)
    return {
        "ok": len(hits) == 0 and compiler_file != evaluator_file,
        "compiler_banned_hits": hits,
        "compiler_implementation": COMPILER_IMPLEMENTATION,
        "evaluator_implementation": EVALUATOR_IMPLEMENTATION,
        "same_file": compiler_file == evaluator_file,
        "evaluator_uses_simulator": "RaceSimulator" in evaluator_src,
    }
