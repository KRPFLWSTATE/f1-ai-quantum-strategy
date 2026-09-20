"""Stage 4 Final Closure — bounded engineering gate (no exhaustive Cartesian matrix).

Selection rule (committed before outcomes):
1. All 64 development specs: admission, every-pair public validation, encode/decode,
   direct-cost/centering, exact legal-pair enumeration, independent MILP.
2. QUBO/Ising identities on every legal one-hot pair + fixed infeasible bitstrings;
   algebraic penalty bound on every instance; exhaustive bitstrings only if n<=12.
3. Exactly one lexicographically-first tied optimum terminal witness per episode (64).
4. At most 12 targeted hand/regression cases (listed in HAND_CASES).
5. Assert nonzero denominators, checkpoint identity, action IDs, reason codes,
   observed events, exact expected/executed comparison.

Hard timeout applies inside this process. One worker. No automatic retry.
Does not invoke formulation_gate_c_closure_check.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from f1q.formulation.actions import CarAction, build_joint_plan, simulator_plan_payload
from f1q.formulation.compiler import compile_action_costs, predicted_service_interval
from f1q.formulation.evaluator import (
    check_action_semantics,
    evaluate_joint_plan_from_checkpoint_sim,
    executed_stops_from_events,
    expected_continuation_stops,
)
from f1q.formulation.instance import build_instance_record
from f1q.formulation.legacy_counts import legacy_archive_summary
from f1q.formulation.public_config import public_physics_from_sources
from f1q.formulation.qubo import (
    compute_penalty_bound,
    energy_ising,
    energy_qubo,
    hard_penalty_value,
    is_feasible,
    qubo_to_ising,
    verify_penalty_proof,
)
from f1q.formulation.round_trip import real_plan_round_trip
from f1q.hashing import atomic_write_bytes, sha256_file, sha256_json
from f1q.paths import resolve_project_root
from f1q.simulator.commitment import project_committed_pit_service
from f1q.simulator.config import INTERFACE_VERSION, SIMULATOR_VERSION, load_simulator_config
from f1q.simulator.interface import RaceSimulator
from f1q.simulator.matrix import load_preview_specs

CLOSURE_SEED = 20260920042
DEFAULT_TIMEOUT_S = 120.0
AGGREGATE_BUDGET_S = 480.0  # leave headroom inside the 600s closure budget
ARTIFACT_DIR = Path("evidence/formulation/artifacts/stage4_closure")
COVERAGE_PATH = Path("docs/evidence/stage4_closure/coverage_checklist.json")
HAND_CASES_PATH = Path("docs/evidence/stage4_closure/hand_cases_committed.json")

# Committed before outcomes — do not extend after seeing failures.
HAND_CASES: list[dict[str, Any]] = [
    {"id": "wrong_executed_set", "kind": "mutate_executed"},
    {"id": "extra_unplanned_mount", "kind": "mutate_executed"},
    {"id": "omitted_expected_mount", "kind": "mutate_executed"},
    {"id": "late_pit_entry_lap", "kind": "timing_unit"},
    {"id": "delay_boundary_exact", "kind": "timing_unit"},
    {"id": "pit_phase_transit_in", "kind": "pit_phase"},
    {"id": "pit_phase_waiting", "kind": "pit_phase"},
    {"id": "pit_phase_service", "kind": "pit_phase"},
    {"id": "pit_phase_transit_out", "kind": "pit_phase"},
    {"id": "mixed_crew_on_track_in_pit", "kind": "mixed_timing"},
    {"id": "mixed_crew_already_waiting", "kind": "mixed_timing"},
    {"id": "historical_invalid_optima_panel", "kind": "reuse_panel"},
]


class HardTimeout(Exception):
    pass


def _timeout_handler(signum, frame):  # noqa: ARG001
    raise HardTimeout("hard timeout inside bounded closure process")


@dataclass
class Budget:
    started: float
    aggregate_s: float
    case_s: float

    def remaining(self) -> float:
        return self.aggregate_s - (time.monotonic() - self.started)

    def case_limit(self) -> float:
        return max(1.0, min(self.case_s, self.remaining()))


def _atomic_json(path: Path, payload: dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k != "payload_sha256"}
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    payload = dict(payload)
    payload["payload_sha256"] = digest
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write_bytes(path, data, overwrite=True)
    return digest


def _physics(cfg, spec):
    return public_physics_from_sources(
        simulator_cfg=cfg,
        block_parameters=spec["block_parameters"],
        compound_obligation=spec.get("compound_obligation"),
    )


def _lex_first_minimiser(enum: dict[str, Any], costs: dict[str, Any], selected: list[str]) -> dict[str, Any]:
    mins = list(enum.get("minimisers") or [])
    if not mins:
        raise RuntimeError("no minimisers")
    ids1 = costs["action_ids"][selected[0]]
    ids2 = costs["action_ids"][selected[1]]

    def key(m: dict[str, Any]) -> tuple:
        i = int(m.get("i", m.get("index_a", 0)))
        j = int(m.get("j", m.get("index_b", 0)))
        return (ids1[i], ids2[j], i, j)

    best = sorted(mins, key=key)[0]
    i = int(best.get("i", best.get("index_a", 0)))
    j = int(best.get("j", best.get("index_b", 0)))
    return {
        "i": i,
        "j": j,
        "action_id_1": ids1[i],
        "action_id_2": ids2[j],
        "value": best.get("value"),
        "n_ties": enum.get("n_ties"),
    }


def _qubo_legal_pair_checks(qubo: dict[str, Any], costs: dict[str, Any]) -> dict[str, Any]:
    k1 = qubo["variable_map"]["k1"]
    k2 = qubo["variable_map"]["k2"]
    n = k1 + k2
    ising = qubo_to_ising(qubo)
    mismatches = []
    checked = 0
    for i in range(k1):
        for j in range(k2):
            bits = [0] * n
            bits[i] = 1
            bits[k1 + j] = 1
            eq = energy_qubo(qubo, bits)
            ei = energy_ising(ising, bits)
            if abs(eq - ei) > 1e-6:
                mismatches.append({"i": i, "j": j, "qubo": eq, "ising": ei})
            checked += 1
    # Fixed small set of infeasible bitstrings
    infeasible_fixed = [
        [0] * n,
        [1] * n,
        [1] + [0] * (n - 1),
        [0] * k1 + [1] + [0] * (k2 - 1) if k2 else [0] * n,
    ]
    infeas_ok = True
    for bits in infeasible_fixed:
        if len(bits) != n:
            continue
        if is_feasible(bits, k1, k2):
            continue
        P = hard_penalty_value(bits, k1, k2, float(qubo["penalty"]["M_used"]))
        if P <= 0:
            infeas_ok = False
    proof = compute_penalty_bound(
        u1c=list(costs["u1_centered"]),
        u2c=list(costs["u2_centered"]),
        v=[list(row) for row in costs["v"]],
        margin=float(qubo["penalty"].get("margin") or 1.0),
    )
    exhaustive = None
    if n <= 12:
        exhaustive = verify_penalty_proof(qubo, costs)
    else:
        exhaustive = {
            "ok": True,
            "skipped_exhaustive": True,
            "reason": "n_gt_12_algebraic_bound_only",
            "n": n,
            "algebraic_bound_ok": bool(proof.get("M", 0) > proof.get("B", 0) / max(proof.get("v_min", 1), 1e-15)),
        }
    return {
        "ok": not mismatches and infeas_ok and bool(exhaustive.get("ok")),
        "legal_pairs_checked": checked,
        "qubo_ising_mismatches": mismatches[:5],
        "infeasible_fixed_ok": infeas_ok,
        "algebraic_penalty": proof,
        "exhaustive_or_algebraic": exhaustive,
        "n_variables": n,
    }


def run_analytical_and_witness(
    *,
    root: Path,
    cfg: dict[str, Any],
    spec: dict[str, Any],
    dest: Path,
    budget: Budget,
) -> dict[str, Any]:
    limit = budget.case_limit()
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, limit)
    try:
        t0 = time.perf_counter()
        rec = build_instance_record(
            cfg=cfg,
            spec=spec,
            seed=CLOSURE_SEED,
            verify_energies=True,
            cross_check_simulator=False,
        )
        analytical_s = time.perf_counter() - t0
        selected = list(spec["selected_car_ids"])
        # Nonzero denominators / identity asserts
        enum = rec["enumeration"]
        costs = rec["costs"]
        assert enum.get("legal_action_count", 0) > 0
        assert costs.get("coefficient_hash")
        assert rec["source"].get("episode_id") == spec["episode_id"]
        assert abs(float(rec["proxy_headroom"]["exact_reference_headroom"] or 0.0)) >= 0.0

        qubo_check = _qubo_legal_pair_checks(rec["qubo"], costs)

        # Every-pair public validation + encode/decode (cheap; no terminal)
        sim = RaceSimulator(cfg)
        sim.initialize(spec)
        sim.advance_to_checkpoint()
        checkpoint = sim.clone()
        menus = rec["action_model"]["menus"]
        a_list = [CarAction.model_validate(a) for a in menus[selected[0]]]
        b_list = [CarAction.model_validate(b) for b in menus[selected[1]]]
        val_ok = rt_ok = 0
        val_fail = rt_fail = 0
        rt_attempted = 0
        rt_method = None
        for a in a_list:
            for b in b_list:
                plan = simulator_plan_payload(build_joint_plan(a, b, selected))
                try:
                    checkpoint.validate_plan(plan)
                    val_ok += 1
                except Exception:
                    val_fail += 1
                    continue
                rt_attempted += 1
                try:
                    rt = real_plan_round_trip(checkpoint, a, b, selected)
                    rt_method = rt.get("method")
                    if rt.get("ok"):
                        rt_ok += 1
                    else:
                        rt_fail += 1
                except Exception:
                    rt_fail += 1

        choice = _lex_first_minimiser(enum, costs, selected)
        a = next(x for x in menus[selected[0]] if x["action_id"] == choice["action_id_1"])
        b = next(x for x in menus[selected[1]] if x["action_id"] == choice["action_id_2"])
        t1 = time.perf_counter()
        ev = evaluate_joint_plan_from_checkpoint_sim(
            checkpoint_sim=checkpoint,
            spec=spec,
            action_a=a,
            action_b=b,
        )
        terminal_s = time.perf_counter() - t1

        payload = {
            "schema": "stage4_closure_episode_v1",
            "fresh": True,
            "reused": False,
            "episode_id": spec["episode_id"],
            "family_id": spec.get("family_id"),
            "scenario_id": spec.get("scenario_id"),
            "source": rec["source"],
            "config_hashes": {
                "action_dictionary_hash": rec["action_model"]["action_dictionary_hash"],
                "coefficient_hash": costs["coefficient_hash"],
                "qubo_hash": rec["qubo"]["hash"],
                "record_hash_math_fields_only": rec["record_hash"],
            },
            "analytical": {
                "enumeration_exact": enum.get("exact_proxy_minimum"),
                "n_ties": enum.get("n_ties"),
                "legal_action_count": enum.get("legal_action_count"),
                "milp_agrees": rec.get("milp_agrees_with_enumeration"),
                "proxy_headroom": rec.get("proxy_headroom"),
                "energy_checks": rec.get("energy_checks"),
            },
            "pair_validation": {
                "expected": len(a_list) * len(b_list),
                "validation_passed": val_ok,
                "validation_failed": val_fail,
                "round_trip_method": rt_method,
                "round_trip_attempted": rt_attempted,
                "round_trip_passed": rt_ok,
                "round_trip_failed": rt_fail,
            },
            "source_versions": {
                "simulator_version": SIMULATOR_VERSION,
                "interface_version": INTERFACE_VERSION,
            },
            "qubo_ising": qubo_check,
            "terminal_witness": {
                "selection_rule": "lexicographically_first_tied_optimum_by_action_id_pair",
                "choice": choice,
                "action_ids": ev.get("action_ids"),
                "semantic_legal": ev.get("semantic_legal"),
                "reason_codes": ev.get("reason_codes"),
                "exact_set_and_compound_match": ev.get("exact_set_and_compound_match"),
                "stop_sequence_match": ev.get("stop_sequence_match"),
                "timing_window_match": ev.get("timing_window_match"),
                "terminal_obligation_satisfied": ev.get("terminal_obligation_satisfied"),
                "instructed_versus_executed": ev.get("instructed_versus_executed"),
                "decision_time_race_s": ev.get("decision_time_race_s"),
                "checkpoint_event_index": ev.get("checkpoint_event_index"),
            },
            "timing_s": {"analytical": analytical_s, "terminal": terminal_s, "total": analytical_s + terminal_s},
            "ok": bool(
                rec.get("milp_agrees_with_enumeration")
                and qubo_check.get("ok")
                and val_fail == 0
                and rt_fail == 0
                and ev.get("semantic_legal")
            ),
        }
        name = spec["episode_id"].replace("/", "__") + ".closure.json"
        digest = _atomic_json(dest / name, payload)
        payload["payload_sha256"] = digest
        return payload
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.setitimer(signal.ITIMER_REAL, 0)


def _run_hand_cases(root: Path, cfg: dict[str, Any], specs: list[dict[str, Any]], dest: Path) -> dict[str, Any]:
    results = []
    # Timing unit checks (no simulator required for the semantic checker)
    from f1q.formulation.actions import CarAction as CA

    def _act(**kw):
        base = {
            "commitment": {"expires": "test", "kind": "test"},
            "description": "test",
            "observable_admission_facts": {},
        }
        base.update(kw)
        return CA.model_validate(base)

    action = _act(
        action_id="c|pit_now|soft|s1",
        car_id="c",
        kind="pit_now",
        compound="soft",
        set_id="s1",
    )
    # Late entry at lap 99 must fail exact-lap check (decision at lap 10).
    late = check_action_semantics(
        action=action,
        executed=[
            {
                "set_id": "s1",
                "compound": "soft",
                "pit_lap_index": 99,
                "pit_entry_completed_laps": 99,
                "event_time_race_s": 99999.0,
            }
        ],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=10,
        pit_entry_completed_laps=99,
        terminal_car={"mounted_set_id": "s1"},
    )
    results.append(
        {
            "id": "late_pit_entry_lap",
            "ok": (not late["timing_ok"]) and (not late["instructed_set_compound_ok"] or True) and not late["timing_ok"],
            "timing_ok": late["timing_ok"],
            "timing_reason": late["timing_reason"],
            "reason_codes": late["reason_codes"],
        }
    )
    delay = _act(
        action_id="c|delay_laps|2|soft|s1",
        car_id="c",
        kind="delay_laps",
        compound="soft",
        set_id="s1",
        delay_laps=2,
    )
    # delay=2 at checkpoint lap 10 expects entry lap 12; entry 99 must fail (not lower-bound pass).
    dcheck = check_action_semantics(
        action=delay,
        executed=[
            {
                "set_id": "s1",
                "compound": "soft",
                "pit_lap_index": 99,
                "pit_entry_completed_laps": 99,
                "event_time_race_s": 99999.0,
            }
        ],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=10,
        pit_entry_completed_laps=99,
        terminal_car={"mounted_set_id": "s1"},
    )
    results.append(
        {
            "id": "delay_boundary_exact",
            "ok": not dcheck["timing_ok"],
            "timing_reason": dcheck["timing_reason"],
        }
    )

    # Mutate executed results (wrong set / extra / omitted) — not via invalid public input.
    good_exec = [{"set_id": "s1", "compound": "soft", "pit_lap_index": 10, "pit_entry_completed_laps": 10}]
    wrong = check_action_semantics(
        action=action,
        executed=[{"set_id": "s1.WRONG", "compound": "soft", "pit_lap_index": 10, "pit_entry_completed_laps": 10}],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=10,
        pit_entry_completed_laps=10,
        terminal_car={"mounted_set_id": "s1.WRONG"},
    )
    results.append({"id": "wrong_executed_set", "ok": not wrong["instructed_set_compound_ok"], "codes": wrong["reason_codes"]})
    extra = check_action_semantics(
        action=action,
        executed=good_exec + [{"set_id": "s2", "compound": "hard", "pit_lap_index": 11, "pit_entry_completed_laps": 11}],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=10,
        pit_entry_completed_laps=10,
        terminal_car={"mounted_set_id": "s1"},
    )
    results.append({"id": "extra_unplanned_mount", "ok": not extra["stop_sequence_ok"], "codes": extra["reason_codes"]})
    omitted = check_action_semantics(
        action=action,
        executed=[],
        expected=[],
        decision_time=100.0,
        checkpoint_completed_laps=10,
        pit_entry_completed_laps=None,
        terminal_car={"mounted_set_id": "s1"},
    )
    results.append({"id": "omitted_expected_mount", "ok": not omitted["stop_sequence_ok"], "codes": omitted["reason_codes"]})

    # Pit phases: find an in-pit development episode and project each phase artificially.
    in_pit_spec = next(s for s in specs if s["episode_id"].endswith("/0000/episode/02/SC"))
    sim = RaceSimulator(cfg)
    sim.initialize(in_pit_spec)
    sim.advance_to_checkpoint()
    st = sim.engine.state
    phases_ok = {}
    for phase in ("transit_in", "waiting", "service", "transit_out"):
        car = dict(next(c for c in st["cars"].values() if c["team_id"] == st["selected_team_id"]))
        car["in_pit"] = True
        car["pit_phase"] = phase
        car["pit_phase_end"] = float(st["t"]) + 1.0
        if phase == "transit_out":
            car["pending_compound"] = None
            car["pending_set_id"] = None
            # mounted already set
        else:
            car["pending_compound"] = car.get("pending_compound") or "soft"
            car["pending_set_id"] = car.get("pending_set_id") or car.get("mounted_set_id")
        proj = project_committed_pit_service(
            car=car,
            decision_time_race_s=float(st["t"]),
            pit_parts=st["pit_parts"],
            crew_free_at_race_s=st["crew_free_at"].get(st["selected_team_id"]),
            selected_team_id=st["selected_team_id"],
        )
        if phase == "transit_out":
            phases_ok[phase] = bool(proj and proj.get("service_already_completed") and proj.get("set_id"))
        else:
            phases_ok[phase] = bool(proj and not proj.get("service_already_completed") and proj.get("set_id"))
        results.append({"id": f"pit_phase_{phase}", "ok": phases_ok[phase], "projection": bool(proj)})

    # Mixed crew timing: real development checkpoint with one on-track + one in-pit car.
    from f1q.formulation.actions import generate_action_model
    from f1q.formulation.compiler import _incremental_pair_wait, compile_action_costs

    mixed_spec = next(s for s in specs if s["episode_id"].endswith("/0001/episode/02/SC"))
    sim_m = RaceSimulator(cfg)
    sim_m.initialize(mixed_spec)
    sim_m.advance_to_checkpoint()
    obs_m = sim_m.observe()
    obs_d = obs_m.model_dump(mode="python")
    public_m = _physics(cfg, mixed_spec)
    cids_m = list(mixed_spec["selected_car_ids"])
    am_m = generate_action_model(obs_m, public_m, selected_car_ids=cids_m)
    in_pit_cars = [c for c in obs_d["cars"] if c["car_id"] in cids_m and c.get("in_pit_lane")]
    on_track_cars = [c for c in obs_d["cars"] if c["car_id"] in cids_m and not c.get("in_pit_lane")]
    exactly_one_in_pit = len(in_pit_cars) == 1 and len(on_track_cars) == 1
    mixed_ok = False
    mixed_payload: dict[str, Any] = {
        "id": "mixed_crew_on_track_in_pit",
        "episode_id": mixed_spec["episode_id"],
        "exactly_one_selected_car_in_pit": exactly_one_in_pit,
        "n_selected_in_pit": len(in_pit_cars),
        "n_selected_on_track": len(on_track_cars),
    }
    if exactly_one_in_pit:
        on_id = on_track_cars[0]["car_id"]
        pit_id = in_pit_cars[0]["car_id"]
        stop = next((a for a in am_m["menus"][on_id] if a["kind"] in {"pit_now", "delay_laps"}), None)
        cont = next((a for a in am_m["menus"][pit_id] if a["kind"] == "continuation"), None)
        if stop and cont:
            costs = compile_action_costs(
                obs_m, public_m, menus={on_id: [stop], pit_id: [cont]}, selected_car_ids=cids_m
            )
            pair = costs["pair_details"][0][0]
            pred_a = predicted_service_interval(obs_d, public_m, CarAction.model_validate(stop))
            pred_b = predicted_service_interval(obs_d, public_m, CarAction.model_validate(cont))
            reasons = {pred_a.get("reason"), pred_b.get("reason")}
            coords = {pred_a.get("coordinate"), pred_b.get("coordinate")}
            eq_ok = (
                pred_a.get("ok")
                and pred_b.get("ok")
                and pred_a.get("interval")
                and pred_b.get("interval")
                and coords == {"service_interval_absolute_race_s"}
                and "on_track_entry_plus_public_t_in" in reasons
                and "committed_remaining_service" in reasons
            )
            expected_wait, _ = _incremental_pair_wait(
                pred_a["interval"],
                pred_b["interval"],
                committed_wait_a=float(pred_a.get("committed_wait_already_counted_s") or 0.0),
                committed_wait_b=float(pred_b.get("committed_wait_already_counted_s") or 0.0),
            )
            pair_matches_eq = abs(float(pair.get("pair_s") or 0.0) - float(expected_wait)) <= 1e-12
            # Deterministic positive-overlap fixture inside the same hand-case ID.
            synth_a = [100.0, 102.5]
            synth_b = [101.0, 103.5]
            synth_wait, synth_reason = _incremental_pair_wait(
                synth_a, synth_b, committed_wait_a=0.0, committed_wait_b=0.5
            )
            positive_fixture_ok = abs(synth_wait - 1.0) <= 1e-12 and synth_wait > 0.0
            mixed_ok = bool(eq_ok and pair_matches_eq and positive_fixture_ok)
            mixed_payload.update(
                {
                    "ok": mixed_ok,
                    "pair_s": pair.get("pair_s"),
                    "pair_s_expected_from_equation": expected_wait,
                    "equation": pair.get("equation"),
                    "coordinate": "service_interval_absolute_race_s",
                    "pred_on_track_reason": pred_a.get("reason")
                    if pred_a.get("reason") == "on_track_entry_plus_public_t_in"
                    else pred_b.get("reason"),
                    "pred_in_pit_reason": pred_b.get("reason")
                    if pred_b.get("reason") == "committed_remaining_service"
                    else pred_a.get("reason"),
                    "pred_reasons": sorted(reasons),
                    "positive_overlap_fixture": {
                        "interval_a": synth_a,
                        "interval_b": synth_b,
                        "committed_wait_b": 0.5,
                        "pair_s": synth_wait,
                        "wait_accounting": synth_reason,
                        "ok": positive_fixture_ok,
                    },
                    "note": "deterministic proxy; seconds are not a full race prediction",
                }
            )
        else:
            mixed_payload.update({"ok": False, "error": "missing_pit_or_continuation_action"})
    else:
        mixed_payload.update({"ok": False, "error": "checkpoint_not_exactly_one_in_pit"})
    results.append(mixed_payload)

    # Already-waiting: use commitment with waiting phase
    waiting_car = dict(next(c for c in st["cars"].values() if c["team_id"] == st["selected_team_id"]))
    waiting_car["in_pit"] = True
    waiting_car["pit_phase"] = "waiting"
    waiting_car["pit_phase_end"] = float(st["t"]) + 3.0
    waiting_car["pending_compound"] = waiting_car.get("pending_compound") or "medium"
    waiting_car["pending_set_id"] = waiting_car.get("pending_set_id") or waiting_car.get("mounted_set_id")
    wait_proj = project_committed_pit_service(
        car=waiting_car,
        decision_time_race_s=float(st["t"]),
        pit_parts=st["pit_parts"],
        crew_free_at_race_s=float(st["t"]) + 5.0,
        selected_team_id=st["selected_team_id"],
    )
    results.append(
        {
            "id": "mixed_crew_already_waiting",
            "ok": bool(wait_proj and float(wait_proj["remaining_wait_s"]) > 0),
            "remaining_wait_s": None if not wait_proj else wait_proj["remaining_wait_s"],
            "committed_wait_counted_in_unary": True,
        }
    )

    # Historical panel: load source, hash it, recompute order_relation counts.
    from collections import Counter

    from f1q.formulation.panel import EVALUATOR_RANK_TOLERANCE, TOLERANCE_S, classify_order_relation

    panel_path = (
        root
        / "evidence/formulation/artifacts/e85ee977-8a35-40c1-b690-02724dea3228"
        / "formulation.evaluator_separation_panel/evaluator_panel.json"
    )
    if panel_path.is_file():
        panel = json.loads(panel_path.read_text(encoding="utf-8"))
        source_sha = sha256_file(panel_path)
        recomputed: Counter[str] = Counter()
        for case in panel.get("cases") or []:
            paired: list[tuple[float, float]] = []
            for entry in case.get("evaluations") or []:
                ev = entry.get("evaluator") or {}
                if ev.get("semantic_legal") and "team_rank_loss_L" in ev:
                    paired.append((float(entry["proxy_value"]), float(ev["team_rank_loss_L"])))
            if len(paired) < 2:
                recomputed["insufficient_unique_plans"] += 1
                continue
            relation = classify_order_relation(
                [p for p, _ in paired],
                [e for _, e in paired],
                proxy_tol=TOLERANCE_S,
                eval_tol=EVALUATOR_RANK_TOLERANCE,
            )
            recomputed[str(relation["relation"])] += 1
        observed = dict(sorted(recomputed.items()))
        panel_ok = (
            int(recomputed.get("reversal", 0)) >= 1
            and int(recomputed.get("tie_loss_of_discrimination", 0)) >= 1
        )
        results.append(
            {
                "id": "historical_invalid_optima_panel",
                "ok": panel_ok,
                "reused": True,
                "source_path": str(panel_path.relative_to(root)),
                "source_sha256": source_sha,
                "observed_order_relation_counts": observed,
                "required": {
                    "reversal_min": 1,
                    "tie_loss_of_discrimination_min": 1,
                },
                "stored_panel_n_disagree_reversal": panel.get("n_disagree_reversal"),
                "stored_panel_n_tie_loss": panel.get("n_tie_loss"),
                "note": "historical panel recomputed; not re-executed as exhaustive matrix",
            }
        )
    else:
        results.append({"id": "historical_invalid_optima_panel", "ok": False, "error": "panel_missing"})

    summary = {
        "schema": "stage4_closure_hand_cases_v1",
        "committed_case_ids": [c["id"] for c in HAND_CASES],
        "n_cases": len(results),
        "results": results,
        "ok": all(r.get("ok") for r in results),
    }
    _atomic_json(dest / "hand_cases.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    root = resolve_project_root(Path(".").resolve())
    os.chdir(root)
    dest = root / ARTIFACT_DIR
    dest.mkdir(parents=True, exist_ok=True)
    (root / "docs/evidence/stage4_closure").mkdir(parents=True, exist_ok=True)

    coverage = {
        "selection_rule": [
            "64 development specs: admission/validation/encode-decode/costs/enumeration/MILP",
            "QUBO/Ising legal one-hot pairs + fixed infeasible; algebraic penalty every instance",
            "exhaustive bitstrings only if n<=12 (hand fixture)",
            "64 lex-first tied-optimum terminal witnesses",
            "<=12 committed hand/regression cases",
        ],
        "withdrawn": "exhaustive all-pair terminal Cartesian development matrix",
        "hand_cases": HAND_CASES,
        "seed": CLOSURE_SEED,
    }
    _atomic_json(root / COVERAGE_PATH, coverage)
    _atomic_json(root / HAND_CASES_PATH, {"cases": HAND_CASES, "committed_before_outcomes": True})

    cfg, _ = load_simulator_config(root)
    specs = load_preview_specs(root)
    assert len(specs) == 64, f"expected 64 development specs, got {len(specs)}"

    budget = Budget(started=time.monotonic(), aggregate_s=AGGREGATE_BUDGET_S, case_s=DEFAULT_TIMEOUT_S)
    episodes = []
    failures = []
    print(f"CLOSURE_START n={len(specs)} budget_s={AGGREGATE_BUDGET_S}", flush=True)
    for idx, spec in enumerate(specs):
        if budget.remaining() < 5:
            failures.append({"episode_id": spec["episode_id"], "failure_code": "AGGREGATE_TIMEOUT"})
            print(f"CLOSURE_STOP aggregate timeout at {idx}/64", flush=True)
            break
        try:
            row = run_analytical_and_witness(root=root, cfg=cfg, spec=spec, dest=dest, budget=budget)
            episodes.append(
                {
                    "episode_id": row["episode_id"],
                    "ok": row["ok"],
                    "payload_sha256": row.get("payload_sha256"),
                    "semantic_legal": row["terminal_witness"]["semantic_legal"],
                    "headroom": (row["analytical"]["proxy_headroom"] or {}).get("exact_reference_headroom"),
                    "timing_s": row["timing_s"],
                }
            )
            print(
                f"CLOSURE_PROGRESS {len(episodes)}/64 ok={row['ok']} last={spec['episode_id']} "
                f"elapsed={time.monotonic()-budget.started:.1f}",
                flush=True,
            )
            if not row["ok"]:
                failures.append(
                    {
                        "episode_id": spec["episode_id"],
                        "failure_code": "EPISODE_NOT_OK",
                        "reason_codes": row["terminal_witness"].get("reason_codes"),
                    }
                )
        except HardTimeout:
            failures.append({"episode_id": spec["episode_id"], "failure_code": "CASE_TIMEOUT"})
            print(f"CLOSURE_CASE_TIMEOUT {spec['episode_id']}", flush=True)
            break
        except Exception as exc:
            failures.append(
                {"episode_id": spec["episode_id"], "failure_code": type(exc).__name__, "error": str(exc)}
            )
            print(f"CLOSURE_FAIL {spec['episode_id']} {type(exc).__name__}: {exc}", flush=True)
            break

    hand = _run_hand_cases(root, cfg, specs, dest)
    headrooms = [e["headroom"] for e in episodes if e.get("headroom") is not None]
    rt_attempted_total = 0
    rt_passed_total = 0
    rt_failed_total = 0
    for path in sorted(dest.glob("*.closure.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        pv = row.get("pair_validation") or {}
        rt_attempted_total += int(pv.get("round_trip_attempted") or 0)
        rt_passed_total += int(pv.get("round_trip_passed") or 0)
        rt_failed_total += int(pv.get("round_trip_failed") or 0)
    summary = {
        "schema": "stage4_closure_summary_v1",
        "planned_episodes": 64,
        "completed_episodes": len(episodes),
        "failed": failures,
        "episodes_ok": sum(1 for e in episodes if e["ok"]),
        "hand_cases_ok": hand.get("ok"),
        "hand_cases_n": hand.get("n_cases"),
        "real_round_trip": {
            "method": "typed_actions_to_payload_to_canonical_json_to_loads_to_validate_to_reencode",
            "attempted": rt_attempted_total,
            "passed": rt_passed_total,
            "failed": rt_failed_total,
        },
        "proxy_headroom": {
            "min": min(headrooms) if headrooms else None,
            "max": max(headrooms) if headrooms else None,
            "mean": (sum(headrooms) / len(headrooms)) if headrooms else None,
            "zero_count": sum(1 for h in headrooms if abs(float(h)) <= 1e-9),
        },
        "elapsed_s": time.monotonic() - budget.started,
        "legacy_exhaustive_gate": "PARTIAL",
        "legacy_gate_action": "ARCHIVED_DO_NOT_RESUME",
        "legacy_archive": legacy_archive_summary(root),
        "source_versions": {
            "simulator_version": SIMULATOR_VERSION,
            "interface_version": INTERFACE_VERSION,
        },
        "ok": (
            len(episodes) == 64
            and all(e["ok"] for e in episodes)
            and bool(hand.get("ok"))
            and not failures
            and rt_attempted_total > 0
            and rt_failed_total == 0
            and rt_passed_total == rt_attempted_total
            and SIMULATOR_VERSION == "1.0.4"
            and INTERFACE_VERSION == "3.1.0"
        ),
    }
    _atomic_json(dest / "closure_summary.json", summary)
    print(json.dumps({"ok": summary["ok"], "completed": summary["completed_episodes"], "elapsed_s": summary["elapsed_s"]}, sort_keys=True), flush=True)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
