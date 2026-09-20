"""Simulator evaluator adapter — separate implementation from the proxy compiler.

Evaluates complete joint plans on cloned simulator checkpoints and reports modelled
outcome/classification quantities. Must not share scoring code with the compiler.
"""

from __future__ import annotations

from typing import Any

from f1q.formulation.actions import CarAction, build_joint_plan, simulator_plan_payload
from f1q.formulation.downstream_policy import (
    compounds_used,
    normalize_stop_record,
    obligation_met,
    select_obligation_set,
)
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


def _numeric_field(container: dict[str, Any], *keys: str) -> int | None:
    """Read an integer field without truthiness traps (preserve explicit zero)."""
    for key in keys:
        if key in container and container[key] is not None:
            return int(container[key])
    return None


def pit_entry_completed_laps_from_events(
    events: list[dict[str, Any]],
    car_id: str,
    *,
    checkpoint_event_index: int = 0,
) -> int | None:
    """Return entry-lap from the first strictly paired post-checkpoint stop, if any."""
    stops = executed_stops_from_events(
        events, car_id, checkpoint_event_index=checkpoint_event_index
    )
    if not stops:
        return None
    return _numeric_field(stops[0], "pit_entry_completed_laps", "pit_lap_index")


def executed_stops_from_events(
    events: list[dict[str, Any]],
    car_id: str,
    *,
    checkpoint_event_index: int = 0,
) -> list[dict[str, Any]]:
    """One executed stop per post-checkpoint service_complete, paired with prior pit_entry.

    Scheduled stops require a post-checkpoint pit_entry with explicit
    detail.pit_entry_completed_laps (completed_laps is same-event compatibility only).
    Continuation of service already in progress at the checkpoint may use the
    service_complete copy of the entry lap, labelled distinctly, because the
    pit_entry legitimately predates the checkpoint boundary.
    """
    stops: list[dict[str, Any]] = []
    ordered = 0
    pending_entry: dict[str, Any] | None = None
    for abs_idx in range(int(checkpoint_event_index), len(events)):
        ev = events[abs_idx]
        if ev.get("car_id") != car_id:
            continue
        kind = _event_kind(ev)
        detail = _detail(ev) or {}
        if kind == "pit_entry":
            entry = _numeric_field(detail, "pit_entry_completed_laps")
            source = "pit_entry.detail.pit_entry_completed_laps"
            if entry is None:
                entry = _numeric_field(detail, "completed_laps")
                source = "pit_entry.detail.completed_laps_compat"
            pending_entry = {
                "pit_entry_event_index": abs_idx,
                "pit_entry_completed_laps": entry,
                "evidence_source": source,
            }
            continue
        if kind != "service_complete":
            continue
        ordered += 1
        sc_entry = _numeric_field(detail, "pit_entry_completed_laps")
        if pending_entry is not None:
            pit_lap = pending_entry.get("pit_entry_completed_laps")
            evidence_source = str(pending_entry.get("evidence_source"))
            entry_idx = pending_entry.get("pit_entry_event_index")
            if pit_lap is not None and sc_entry is not None and int(pit_lap) != int(sc_entry):
                pit_lap = None
                evidence_source = "contradictory_pit_entry_and_service_complete"
            pending_entry = None
            provenance = "post_checkpoint_pit_entry_paired"
        else:
            # No post-checkpoint pit_entry: in-progress continuation only.
            pit_lap = sc_entry
            evidence_source = (
                "continuation_pre_checkpoint_entry_via_service_complete.detail.pit_entry_completed_laps"
            )
            entry_idx = None
            provenance = "continuation_pre_checkpoint_service_complete"
        stops.append(
            normalize_stop_record(
                car_id=car_id,
                source="simulator",
                kind="service_complete",
                compound=detail.get("compound") if detail else ev.get("compound"),
                set_id=detail.get("set_id") if detail else ev.get("set_id"),
                pit_lap_index=pit_lap,
                reason="service_complete",
            )
            | {
                "stop_index": ordered,
                "event_time_race_s": ev.get("t"),
                "pit_entry_completed_laps": pit_lap,
                "pit_entry_event_index": entry_idx,
                "service_complete_event_index": abs_idx,
                "evidence_source": evidence_source,
                "entry_lap_provenance": provenance,
                "supporting_kinds_ignored_as_separate_stops": sorted(
                    PIT_SUPPORTING_KINDS - {"service_complete"}
                ),
            }
        )
    return stops


# Back-compat alias used by Stage 4.1 tests during transition.
def _executed_stops_from_events(events: list[dict[str, Any]], car_id: str) -> list[dict[str, Any]]:
    return executed_stops_from_events(events, car_id, checkpoint_event_index=0)


def expected_continuation_stops(
    *,
    action: CarAction,
    commitment: dict[str, Any] | None,
    car_at_checkpoint: dict[str, Any],
    required_compounds: int,
) -> list[dict[str, Any]]:
    """Build expected post-checkpoint stops from commitment / downstream policy (not execution)."""
    if action.kind != "continuation":
        return []
    if commitment:
        if commitment.get("service_already_completed") or commitment.get("pit_phase") == "transit_out":
            # Already mounted; expect no new post-checkpoint service_complete.
            return []
        return [
            normalize_stop_record(
                car_id=action.car_id,
                source="commitment",
                kind="committed_service",
                compound=commitment.get("target_compound"),
                set_id=commitment.get("set_id"),
                pit_lap_index=_numeric_field(commitment, "pit_entry_completed_laps"),
                reason="in_progress_commitment",
            )
        ]
    # On-track continuation: authoritative compound_obligation.v1 alternate stop when unmet.
    if obligation_met(car_at_checkpoint, required_compounds):
        return []
    try:
        compound, set_id = select_obligation_set(car_at_checkpoint)
    except Exception:
        return []
    return [
        normalize_stop_record(
            car_id=action.car_id,
            source="downstream_policy",
            kind="policy_pit_now",
            compound=compound,
            set_id=set_id,
            pit_lap_index=0,
            reason="compound_obligation.v1",
        )
    ]


def _timing_match(
    *,
    action: CarAction,
    executed: list[dict[str, Any]],
    decision_time: float,
    checkpoint_completed_laps: int,
    pit_entry_completed_laps: int | None,
) -> tuple[bool, str]:
    """Exact entry-lap timing: lower-bound time-order alone is not an action window."""
    if action.kind == "continuation":
        return True, "continuation_timing_via_expected_sequence"
    if not executed:
        return False, "no_executed_stop"
    stop0 = executed[0]
    if stop0.get("evidence_source") == "contradictory_pit_entry_and_service_complete":
        return False, "contradictory_pit_entry_and_service_complete"
    if action.kind in {"pit_now", "delay_laps"}:
        if stop0.get("pit_entry_event_index") is None:
            return False, "missing_post_checkpoint_pit_entry_event"
        if stop0.get("entry_lap_provenance") != "post_checkpoint_pit_entry_paired":
            return False, "scheduled_stop_requires_post_checkpoint_pit_entry"
    # Required timing evidence: supporting pit-entry completed-lap counter.
    if pit_entry_completed_laps is None:
        pit_entry_completed_laps = _numeric_field(stop0, "pit_entry_completed_laps", "pit_lap_index")
    if pit_entry_completed_laps is None:
        return False, "missing_pit_entry_completed_laps"

    if action.kind == "pit_now":
        expected = int(checkpoint_completed_laps)
        ok = int(pit_entry_completed_laps) == expected
        return ok, "pit_now_exact_entry_lap" if ok else "pit_now_entry_lap_mismatch"
    if action.kind == "delay_laps":
        delay = int(action.delay_laps if action.delay_laps is not None else 0)
        expected = int(checkpoint_completed_laps) + delay
        ok = int(pit_entry_completed_laps) == expected
        return ok, "delay_laps_exact_entry_lap" if ok else "delay_laps_entry_lap_mismatch"
    return False, f"unsupported_action_kind:{action.kind}"


def check_action_semantics(
    *,
    action: CarAction,
    executed: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    decision_time: float,
    checkpoint_completed_laps: int,
    pit_entry_completed_laps: int | None,
    terminal_car: dict[str, Any],
) -> dict[str, Any]:
    """Shared semantic checker used by both evaluator entry points."""
    reason_codes: list[str] = []
    set_ok = True
    seq_ok = True
    t_ok = True
    t_why = "n/a"
    cid = action.car_id

    if action.kind in {"pit_now", "delay_laps"}:
        expected = [
            normalize_stop_record(
                car_id=cid,
                source="instruction",
                kind=action.kind,
                compound=action.compound,
                set_id=action.set_id,
                pit_lap_index=(
                    0
                    if action.kind == "pit_now"
                    else int(action.delay_laps if action.delay_laps is not None else 0)
                ),
            )
        ]
        if len(executed) != 1:
            seq_ok = False
            set_ok = False
            if len(executed) == 0:
                reason_codes.append(f"instructed_stop_not_executed:{cid}")
            elif len(executed) > 1:
                reason_codes.append(f"extra_unplanned_mount:{cid}")
            else:
                reason_codes.append(f"stop_count_mismatch:{cid}")
        else:
            if action.set_id is not None and executed[0].get("set_id") != action.set_id:
                set_ok = False
                reason_codes.append(f"instructed_set_mismatch:{cid}")
            if action.compound is not None and executed[0].get("compound") != action.compound:
                set_ok = False
                reason_codes.append(f"instructed_compound_mismatch:{cid}")
            if action.set_id is not None and terminal_car.get("mounted_set_id") != action.set_id:
                set_ok = False
                reason_codes.append(f"terminal_mounted_set_mismatch:{cid}")
        t_ok, t_why = _timing_match(
            action=action,
            executed=executed,
            decision_time=decision_time,
            checkpoint_completed_laps=checkpoint_completed_laps,
            pit_entry_completed_laps=pit_entry_completed_laps,
        )
        if not t_ok:
            reason_codes.append(f"timing_mismatch:{cid}:{t_why}")

    elif action.kind == "continuation":
        # Exact ordered stop count / set / compound vs independently constructed expectation.
        if len(executed) != len(expected):
            seq_ok = False
            if len(executed) > len(expected):
                reason_codes.append(f"extra_unplanned_mount:{cid}")
            else:
                reason_codes.append(f"omitted_expected_mount:{cid}")
        for i, exp in enumerate(expected):
            if i >= len(executed):
                set_ok = False
                break
            got = executed[i]
            if exp.get("set_id") is not None and got.get("set_id") != exp.get("set_id"):
                set_ok = False
                reason_codes.append(f"continuation_set_mismatch:{cid}")
            if exp.get("compound") is not None and got.get("compound") != exp.get("compound"):
                set_ok = False
                reason_codes.append(f"continuation_compound_mismatch:{cid}")
        t_ok, t_why = True, "continuation_sequence_checked"
    else:
        set_ok = False
        seq_ok = False
        reason_codes.append(f"unsupported_action_kind:{cid}:{action.kind}")

    return {
        "instructed": expected if action.kind in {"pit_now", "delay_laps"} else expected,
        "expected_stops": expected,
        "executed_stops": executed,
        "instructed_set_compound_ok": set_ok,
        "stop_sequence_ok": seq_ok,
        "timing_ok": t_ok,
        "timing_reason": t_why,
        "reason_codes": reason_codes,
    }


def _checkpoint_car_view(sim: RaceSimulator, car_id: str) -> dict[str, Any]:
    car = sim.engine.state["cars"][car_id]
    return {
        "car_id": car_id,
        "compound": car["compound"],
        "mounted_set_id": car.get("mounted_set_id"),
        "used_compounds": list(car.get("used_compounds") or []),
        "inventory": list(car.get("inventory") or []),
        "in_pit": bool(car.get("in_pit")),
        "pit_phase": car.get("pit_phase"),
        "pending_compound": car.get("pending_compound"),
        "pending_set_id": car.get("pending_set_id"),
        "pit_entry_completed_laps": car.get("pit_entry_completed_laps"),
        "tyre_age_laps": car.get("tyre_age_laps"),
    }


def _commitment_from_checkpoint(sim: RaceSimulator, car_id: str) -> dict[str, Any] | None:
    from f1q.simulator.commitment import project_committed_pit_service

    st = sim.engine.state
    car = st["cars"][car_id]
    if not car.get("in_pit"):
        return None
    return project_committed_pit_service(
        car=car,
        decision_time_race_s=float(st["t"]),
        pit_parts=st["pit_parts"],
        crew_free_at_race_s=st["crew_free_at"].get(st["selected_team_id"]),
        selected_team_id=st["selected_team_id"],
    )


def _evaluate_semantics_block(
    *,
    action_a: CarAction,
    action_b: CarAction,
    selected: list[str],
    clone: RaceSimulator,
    checkpoint_sim: RaceSimulator,
    checkpoint_event_index: int,
    decision_time: float,
    required: int,
    outcome: dict[str, Any],
    legality: dict[str, Any],
    checkpoint_instruction_valid: bool,
    execution_success: bool,
) -> dict[str, Any]:
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
    reason_codes: list[str] = []
    checkpoint_completed = {
        cid: int(checkpoint_sim.engine.state["cars"][cid]["completed_laps"]) for cid in selected
    }

    for action in (action_a, action_b):
        cid = action.car_id
        car = clone.engine.state["cars"][cid]
        used = sorted(compounds_used(car))
        met = obligation_met(car, required)
        if not met:
            obligation_ok = False
            reason_codes.append(f"terminal_obligation_unmet:{cid}")
        executed = executed_stops_from_events(events, cid, checkpoint_event_index=checkpoint_event_index)
        entry_laps = pit_entry_completed_laps_from_events(
            events, cid, checkpoint_event_index=checkpoint_event_index
        )
        commitment = _commitment_from_checkpoint(checkpoint_sim, cid)
        car_view = _checkpoint_car_view(checkpoint_sim, cid)
        expected = expected_continuation_stops(
            action=action,
            commitment=commitment,
            car_at_checkpoint=car_view,
            required_compounds=required,
        )
        check = check_action_semantics(
            action=action,
            executed=executed,
            expected=expected,
            decision_time=float(decision_time),
            checkpoint_completed_laps=checkpoint_completed[cid],
            pit_entry_completed_laps=entry_laps,
            terminal_car=car,
        )
        reason_codes.extend(check["reason_codes"])
        if not check["instructed_set_compound_ok"]:
            exact_set_ok = False
        if not check["stop_sequence_ok"]:
            stop_sequence_ok = False
        if action.kind in {"pit_now", "delay_laps"} and not check["timing_ok"]:
            timing_ok = False
        instructed_vs_executed[cid] = {
            "instructed": check["instructed"],
            "expected_stops": check["expected_stops"],
            "executed_stops": check["executed_stops"],
            "instructed_set_compound_ok": check["instructed_set_compound_ok"],
            "stop_sequence_ok": check["stop_sequence_ok"],
            "timing_ok": check["timing_ok"],
            "timing_reason": check["timing_reason"],
            "pit_entry_completed_laps": entry_laps,
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
        and not any(
            code.startswith("instructed_")
            or code.startswith("timing_")
            or code.startswith("extra_")
            or code.startswith("omitted_")
            or code.startswith("continuation_")
            for code in reason_codes
        )
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
        "action_ids": {action_a.car_id: action_a.action_id, action_b.car_id: action_b.action_id},
        "downstream_policy_id": DOWNSTREAM_POLICY_ID,
        "downstream_policy_version": DOWNSTREAM_POLICY_VERSION,
        "checkpoint_event_index": checkpoint_event_index,
        "decision_time_race_s": decision_time,
        "action_timing_tolerance_s": ACTION_TIMING_TOLERANCE_S,
        "simulator_time_resolution_s": SIMULATOR_TIME_RESOLUTION_S,
        "action_timing_tolerance_derivation": (
            f"ACTION_TIMING_TOLERANCE_S={ACTION_TIMING_TOLERANCE_S} = 1000× "
            f"SIMULATOR_TIME_RESOLUTION_S={SIMULATOR_TIME_RESOLUTION_S} (engine event t rounded to 9 dp); "
            "entry-lap identity uses pit_entry completed-lap counter, not service_complete time"
        ),
    }


def evaluate_joint_plan_on_checkpoint(
    *,
    cfg: dict[str, Any],
    spec: dict[str, Any],
    action_a: CarAction | dict[str, Any],
    action_b: CarAction | dict[str, Any],
) -> dict[str, Any]:
    """Modelled development diagnostic — not race truth."""
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
    reason_codes: list[str] = []
    legality: dict[str, Any] = {"ok": False}
    checkpoint_instruction_valid = False
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

    result = _evaluate_semantics_block(
        action_a=action_a,
        action_b=action_b,
        selected=selected,
        clone=clone,
        checkpoint_sim=sim,
        checkpoint_event_index=checkpoint_event_index,
        decision_time=decision_time,
        required=required,
        outcome=outcome,
        legality=legality,
        checkpoint_instruction_valid=checkpoint_instruction_valid,
        execution_success=execution_success,
    )
    result["action_ids"] = joint["_meta"]["action_ids"]
    return result


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

    result = _evaluate_semantics_block(
        action_a=action_a,
        action_b=action_b,
        selected=selected,
        clone=clone,
        checkpoint_sim=checkpoint_sim,
        checkpoint_event_index=int(checkpoint_event_index),
        decision_time=float(decision_time),
        required=required,
        outcome=outcome,
        legality=legality,
        checkpoint_instruction_valid=checkpoint_instruction_valid,
        execution_success=execution_success,
    )
    result["action_ids"] = joint["_meta"]["action_ids"]
    return result


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
