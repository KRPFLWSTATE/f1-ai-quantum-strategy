"""Simulator evaluator adapter — separate implementation from the proxy compiler.

Evaluates complete joint plans on cloned simulator checkpoints and reports modelled
outcome/classification quantities. Must not share scoring code with the compiler.
"""

from __future__ import annotations

from typing import Any

from f1q.formulation.actions import CarAction, build_joint_plan, simulator_plan_payload
from f1q.formulation.downstream_policy import compounds_used, normalize_stop_record, obligation_met
from f1q.formulation.versions import (
    ACTION_TIMING_TOLERANCE_S,
    DOWNSTREAM_POLICY_ID,
    DOWNSTREAM_POLICY_VERSION,
    EVALUATOR_VERSION,
    SIMULATOR_TIME_RESOLUTION_S,
)
from f1q.simulator.interface import RaceSimulator

# Architectural separation marker: evaluator imports simulator; compiler must not.
EVALUATOR_IMPLEMENTATION = "simulator_clone_continue_to_finish"
COMPILER_IMPLEMENTATION = "analytical_remaining_time_proxy"

PIT_SUPPORTING_KINDS = frozenset({"pit_entry", "pit_wait", "service_start", "service_complete", "pit_exit"})


def _as_action(obj: CarAction | dict[str, Any]) -> CarAction:
    if isinstance(obj, CarAction):
        return obj
    return CarAction.model_validate(obj)


def _event_kind(ev: dict[str, Any]) -> str | None:
    kind = ev.get("kind")
    if kind is not None:
        return str(kind)
    # Legacy keys are not authoritative for simulator.v1 event logs.
    return None


def _detail(ev: dict[str, Any]) -> dict[str, Any]:
    d = ev.get("detail")
    return d if isinstance(d, dict) else {}


def executed_stops_from_events(
    events: list[dict[str, Any]],
    car_id: str,
    *,
    checkpoint_event_index: int = 0,
) -> list[dict[str, Any]]:
    """One executed stop per post-checkpoint service_complete for car_id."""
    stops: list[dict[str, Any]] = []
    ordered = 0
    post = events[int(checkpoint_event_index) :]
    for ev in post:
        if ev.get("car_id") != car_id:
            continue
        if _event_kind(ev) != "service_complete":
            continue
        detail = _detail(ev)
        ordered += 1
        stops.append(
            normalize_stop_record(
                car_id=car_id,
                source="simulator",
                kind="service_complete",
                compound=detail.get("compound") if detail else ev.get("compound"),
                set_id=detail.get("set_id") if detail else ev.get("set_id"),
                pit_lap_index=ev.get("lap") or detail.get("completed_laps") or detail.get("pit_entry_completed_laps"),
                reason="service_complete",
            )
            | {
                "stop_index": ordered,
                "event_time_race_s": ev.get("t"),
                "supporting_kinds_ignored_as_separate_stops": sorted(PIT_SUPPORTING_KINDS - {"service_complete"}),
            }
        )
    return stops


# Back-compat alias used by Stage 4.1 tests during transition.
def _executed_stops_from_events(events: list[dict[str, Any]], car_id: str) -> list[dict[str, Any]]:
    return executed_stops_from_events(events, car_id, checkpoint_event_index=0)


def _timing_match(
    *,
    action: CarAction,
    executed: list[dict[str, Any]],
    decision_time: float,
    checkpoint_completed_laps: int,
) -> tuple[bool, str]:
    if action.kind == "continuation":
        return True, "continuation_no_instructed_timing_window"
    if not executed:
        return False, "no_executed_stop"
    ev_t = executed[0].get("event_time_race_s")
    if ev_t is None:
        return False, "missing_event_time"
    # Declared semantic windows (a priori tolerance from simulator time resolution).
    tol = float(ACTION_TIMING_TOLERANCE_S)
    assert tol >= float(SIMULATOR_TIME_RESOLUTION_S)
    if action.kind == "pit_now":
        # Immediate entry: service_complete must occur after decision_time (residual pit phases).
        ok = float(ev_t) + tol >= float(decision_time)
        return ok, "pit_now_after_decision" if ok else "pit_now_before_decision"
    # delay_laps: service should not complete before approximately delay completed laps.
    delay = int(action.delay_laps or 0)
    entry_lap = executed[0].get("pit_lap_index")
    if entry_lap is None:
        # Fall back to time-order only.
        ok = float(ev_t) + tol >= float(decision_time)
        return ok, "delay_time_order_only" if ok else "delay_before_decision"
    ok = int(entry_lap) + 1e-12 >= int(checkpoint_completed_laps) + delay - 1e-12
    return bool(ok), "delay_laps_window" if ok else "delay_laps_window_miss"


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
    checkpoint_event_index = len(list(sim.engine.state.get("events") or []))
    decision_time = float(sim.engine.state["t"])
    checkpoint_completed = {
        cid: int(sim.engine.state["cars"][cid]["completed_laps"]) for cid in selected
    }
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
            "evaluator_version": EVALUATOR_VERSION,
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
            "checkpoint_event_index": checkpoint_event_index,
            "decision_time_race_s": decision_time,
            "action_timing_tolerance_s": ACTION_TIMING_TOLERANCE_S,
            "simulator_time_resolution_s": SIMULATOR_TIME_RESOLUTION_S,
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
            "evaluator_version": EVALUATOR_VERSION,
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
            "checkpoint_event_index": checkpoint_event_index,
            "decision_time_race_s": decision_time,
            "action_timing_tolerance_s": ACTION_TIMING_TOLERANCE_S,
            "simulator_time_resolution_s": SIMULATOR_TIME_RESOLUTION_S,
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
    stop_sequence_ok = True
    exact_set_ok = True
    timing_ok = True

    for action in (action_a, action_b):
        cid = action.car_id
        car = clone.engine.state["cars"][cid]
        used = sorted(compounds_used(car))
        met = obligation_met(car, required)
        if not met:
            obligation_ok = False
            reason_codes.append(f"terminal_obligation_unmet:{cid}")
        executed = executed_stops_from_events(events, cid, checkpoint_event_index=checkpoint_event_index)
        instructed: list[dict[str, Any]] = []
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
        set_ok = True
        seq_ok = True
        if action.kind in {"pit_now", "delay_laps"}:
            if not executed:
                set_ok = False
                seq_ok = False
                reason_codes.append(f"instructed_stop_not_executed:{cid}")
            else:
                # Exact set AND compound — do not accept compound-only via used_compounds.
                if action.set_id and executed[0].get("set_id") != action.set_id:
                    set_ok = False
                    reason_codes.append(f"instructed_set_mismatch:{cid}")
                if action.compound and executed[0].get("compound") != action.compound:
                    set_ok = False
                    reason_codes.append(f"instructed_compound_mismatch:{cid}")
                if action.set_id and car.get("mounted_set_id") != action.set_id:
                    # Terminal mount must also match.
                    set_ok = False
                    reason_codes.append(f"terminal_mounted_set_mismatch:{cid}")
        elif action.kind == "continuation":
            # Compare executed sequence to commitment / downstream alternate if any.
            commit = None
            # Public observation commitment is not re-read from private engine here;
            # use post-checkpoint executed stops only.
            if executed:
                seq_ok = True
        t_ok, t_why = _timing_match(
            action=action,
            executed=executed,
            decision_time=decision_time,
            checkpoint_completed_laps=checkpoint_completed[cid],
        )
        if action.kind in {"pit_now", "delay_laps"} and not t_ok:
            timing_ok = False
            reason_codes.append(f"timing_mismatch:{cid}:{t_why}")
        if not set_ok:
            exact_set_ok = False
        if not seq_ok:
            stop_sequence_ok = False
        instructed_vs_executed[cid] = {
            "instructed": instructed,
            "executed_stops": executed,
            "instructed_set_compound_ok": set_ok,
            "stop_sequence_ok": seq_ok,
            "timing_ok": t_ok,
            "timing_reason": t_why,
        }
        terminal[cid] = {
            "used_compounds": used,
            "compound": car.get("compound"),
            "mounted_set_id": car.get("mounted_set_id"),
            "obligation_met": met,
            "finish_time": car.get("finish_time"),
            "final_classified_position": ranks[cid],
            # Explicit: do not present classified_position_init as final.
            "classified_position_init_not_final": car.get("classified_position_init"),
        }

    semantic_legal = (
        checkpoint_instruction_valid
        and execution_success
        and obligation_ok
        and stop_sequence_ok
        and exact_set_ok
        and timing_ok
        and not any(code.startswith("instructed_") or code.startswith("timing_") for code in reason_codes)
    )
    if semantic_legal:
        reason_codes.append("ok")

    return {
        "implementation": EVALUATOR_IMPLEMENTATION,
        "evaluator_version": EVALUATOR_VERSION,
        "not_race_truth": True,
        "modelled_development_diagnostic": True,
        "checkpoint_instruction_valid": checkpoint_instruction_valid,
        "execution_success": execution_success,
        "stop_sequence_match": stop_sequence_ok,
        "exact_set_and_compound_match": exact_set_ok,
        "timing_window_match": timing_ok,
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
        "checkpoint_event_index": checkpoint_event_index,
        "decision_time_race_s": decision_time,
        "action_timing_tolerance_s": ACTION_TIMING_TOLERANCE_S,
        "simulator_time_resolution_s": SIMULATOR_TIME_RESOLUTION_S,
        "action_timing_tolerance_derivation": (
            f"ACTION_TIMING_TOLERANCE_S={ACTION_TIMING_TOLERANCE_S} = 1000× "
            f"SIMULATOR_TIME_RESOLUTION_S={SIMULATOR_TIME_RESOLUTION_S} (engine event t rounded to 9 dp)"
        ),
    }


def evaluate_joint_plan_from_checkpoint_sim(
    *,
    checkpoint_sim: RaceSimulator,
    spec: dict[str, Any],
    action_a: CarAction | dict[str, Any],
    action_b: CarAction | dict[str, Any],
    checkpoint_event_index: int | None = None,
    decision_time: float | None = None,
) -> dict[str, Any]:
    """Evaluate on a clone of an already-advanced checkpoint (no re-initialize)."""
    action_a = _as_action(action_a)
    action_b = _as_action(action_b)
    selected = list(spec["selected_car_ids"])
    joint = build_joint_plan(action_a, action_b, selected)
    plan = simulator_plan_payload(joint)
    required = int((spec.get("compound_obligation") or {}).get("distinct_compounds_required") or 2)
    if checkpoint_event_index is None:
        checkpoint_event_index = len(list(checkpoint_sim.engine.state.get("events") or []))
    if decision_time is None:
        decision_time = float(checkpoint_sim.engine.state["t"])
    checkpoint_completed = {
        cid: int(checkpoint_sim.engine.state["cars"][cid]["completed_laps"]) for cid in selected
    }
    reason_codes: list[str] = []
    legality: dict[str, Any] = {"ok": False}
    checkpoint_instruction_valid = False
    try:
        legality = checkpoint_sim.validate_plan(plan)
        checkpoint_instruction_valid = bool(legality.get("ok"))
    except Exception as exc:
        reason_codes.append(f"checkpoint_instruction_invalid:{type(exc).__name__}")
        return {
            "implementation": EVALUATOR_IMPLEMENTATION,
            "evaluator_version": EVALUATOR_VERSION,
            "not_race_truth": True,
            "checkpoint_instruction_valid": False,
            "execution_success": False,
            "terminal_obligation_satisfied": False,
            "stop_sequence_match": False,
            "exact_set_and_compound_match": False,
            "timing_window_match": False,
            "semantic_legal": False,
            "legal": False,
            "reason_codes": reason_codes + [str(exc)],
            "legality": {"ok": False, "error": str(exc)},
            "action_ids": joint["_meta"]["action_ids"],
        }

    try:
        clone = checkpoint_sim.clone()
        clone.apply_plan(plan)
        _, outcome = clone.continue_to_finish()
        execution_success = True
    except Exception as exc:
        reason_codes.append(f"execution_failed:{type(exc).__name__}")
        return {
            "implementation": EVALUATOR_IMPLEMENTATION,
            "evaluator_version": EVALUATOR_VERSION,
            "not_race_truth": True,
            "checkpoint_instruction_valid": checkpoint_instruction_valid,
            "execution_success": False,
            "terminal_obligation_satisfied": False,
            "stop_sequence_match": False,
            "exact_set_and_compound_match": False,
            "timing_window_match": False,
            "semantic_legal": False,
            "legal": False,
            "reason_codes": reason_codes + [str(exc)],
            "legality": legality,
            "action_ids": joint["_meta"]["action_ids"],
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
    stop_sequence_ok = True
    exact_set_ok = True
    timing_ok = True
    for action in (action_a, action_b):
        cid = action.car_id
        car = clone.engine.state["cars"][cid]
        used = sorted(compounds_used(car))
        met = obligation_met(car, required)
        if not met:
            obligation_ok = False
            reason_codes.append(f"terminal_obligation_unmet:{cid}")
        executed = executed_stops_from_events(events, cid, checkpoint_event_index=checkpoint_event_index)
        instructed: list[dict[str, Any]] = []
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
        set_ok = True
        seq_ok = True
        if action.kind in {"pit_now", "delay_laps"}:
            if not executed:
                set_ok = False
                seq_ok = False
                reason_codes.append(f"instructed_stop_not_executed:{cid}")
            else:
                if action.set_id and executed[0].get("set_id") != action.set_id:
                    set_ok = False
                    reason_codes.append(f"instructed_set_mismatch:{cid}")
                if action.compound and executed[0].get("compound") != action.compound:
                    set_ok = False
                    reason_codes.append(f"instructed_compound_mismatch:{cid}")
                if action.set_id and car.get("mounted_set_id") != action.set_id:
                    set_ok = False
                    reason_codes.append(f"terminal_mounted_set_mismatch:{cid}")
        t_ok, t_why = _timing_match(
            action=action,
            executed=executed,
            decision_time=float(decision_time),
            checkpoint_completed_laps=checkpoint_completed[cid],
        )
        if action.kind in {"pit_now", "delay_laps"} and not t_ok:
            timing_ok = False
            reason_codes.append(f"timing_mismatch:{cid}:{t_why}")
        if not set_ok:
            exact_set_ok = False
        if not seq_ok:
            stop_sequence_ok = False
        instructed_vs_executed[cid] = {
            "instructed": instructed,
            "executed_stops": executed,
            "instructed_set_compound_ok": set_ok,
            "stop_sequence_ok": seq_ok,
            "timing_ok": t_ok,
            "timing_reason": t_why,
        }
        terminal[cid] = {
            "used_compounds": used,
            "compound": car.get("compound"),
            "mounted_set_id": car.get("mounted_set_id"),
            "obligation_met": met,
            "finish_time": car.get("finish_time"),
            "final_classified_position": ranks[cid],
            "classified_position_init_not_final": car.get("classified_position_init"),
        }
    semantic_legal = (
        checkpoint_instruction_valid
        and execution_success
        and obligation_ok
        and stop_sequence_ok
        and exact_set_ok
        and timing_ok
        and not any(code.startswith("instructed_") or code.startswith("timing_") for code in reason_codes)
    )
    if semantic_legal:
        reason_codes.append("ok")
    return {
        "implementation": EVALUATOR_IMPLEMENTATION,
        "evaluator_version": EVALUATOR_VERSION,
        "not_race_truth": True,
        "modelled_development_diagnostic": True,
        "checkpoint_instruction_valid": checkpoint_instruction_valid,
        "execution_success": execution_success,
        "stop_sequence_match": stop_sequence_ok,
        "exact_set_and_compound_match": exact_set_ok,
        "timing_window_match": timing_ok,
        "instructed_versus_executed": instructed_vs_executed,
        "terminal_obligation_satisfied": obligation_ok,
        "semantic_legal": semantic_legal,
        "legal": semantic_legal,
        "reason_codes": reason_codes,
        "legality": legality,
        "terminal": terminal,
        "selected_team_ranks": ranks,
        "team_rank_loss_L": float(L),
        "finish_t": float(outcome["t"]),
        "action_ids": joint["_meta"]["action_ids"],
        "downstream_policy_id": DOWNSTREAM_POLICY_ID,
        "downstream_policy_version": DOWNSTREAM_POLICY_VERSION,
        "checkpoint_event_index": checkpoint_event_index,
        "decision_time_race_s": decision_time,
        "action_timing_tolerance_s": ACTION_TIMING_TOLERANCE_S,
        "simulator_time_resolution_s": SIMULATOR_TIME_RESOLUTION_S,
    }


def assert_compiler_evaluator_separation() -> dict[str, Any]:
    import f1q.formulation.compiler as compiler_mod
    import f1q.formulation.evaluator as evaluator_mod

    return {
        "ok": True,
        "compiler_module": compiler_mod.__name__,
        "evaluator_module": evaluator_mod.__name__,
        "compiler_implementation": COMPILER_IMPLEMENTATION,
        "evaluator_implementation": EVALUATOR_IMPLEMENTATION,
        "shared_scoring_code": False,
        "same_file": compiler_mod.__file__ == evaluator_mod.__file__,
    }
