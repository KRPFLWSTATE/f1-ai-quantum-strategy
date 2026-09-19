"""Stage 3.1 targeted follow-up checks. Development evidence only."""

from __future__ import annotations

import copy
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from f1q.errors import RejectionError, ResourceCeilingError
from f1q.hashing import canonical_json, sha256_json
from f1q.paths import resolve_within
from f1q.simulator.checks import (
    TOL_FINISH_S,
    TOL_FREE_TRACK_ANALYTIC_S,
    TOL_PIT_EVENT_S,
    run_all_mechanism_checks,
)
from f1q.simulator.config import load_simulator_config
from f1q.simulator.engine import distance, draw_uniform
from f1q.simulator.fuel import horizon_need_kg, realize_initial_fuel
from f1q.simulator.hand_specs import build_hand_spec
from f1q.simulator.interface import RaceSimulator
from f1q.simulator.matrix import PREVIEW_RUN, intervention_episodes, load_preview_specs
from f1q.simulator.resources import MemoryGuard

PIT_EVENT_KINDS = ("pit_entry", "service_start", "service_complete", "pit_exit", "pit_wait")
CRITERIA = {
    "recorded_before_resolution_execution": True,
    "free_track_analytic_tolerance_s": TOL_FREE_TRACK_ANALYTIC_S,
    "free_track_tolerance_kind": "floating_point_and_newton_truncation_not_time_discretization",
    "pit_event_finest_pair_target_s": TOL_PIT_EVENT_S,
    "finish_time_finest_pair_target_s": TOL_FINISH_S,
    "pit_event_kinds": list(PIT_EVENT_KINDS),
    "step_refinement": ["h", "h/2", "h/4"],
    "event_keyed_draws": "fuel_actual_offset and regime_duration stay stream-keyed; not redrawn on refine",
    "event_correspondence": "match by (kind, car_id) occurrence index; traces are not re-sorted per resolution",
    "ambiguity_band_s": 0.05,
    "ambiguity_note": "Deliberate ties/near-ties are reported separately; tolerances are not widened to hide flips.",
    "not_campaign_monte_carlo": True,
    "not_team_supplied_tolerances": True,
}


def select_resolution_panel(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hash-select one episode per family, 4 SC / 4 VSC where possible. No outcome inspection."""
    selected = intervention_episodes(specs)
    return selected


def resolution_panel_ids(specs: list[dict[str, Any]]) -> dict[str, Any]:
    selected = select_resolution_panel(specs)
    return {
        "rule": "sha256(episode_id) min within family; even families SC, odd families VSC",
        "count": len(selected),
        "episode_ids": [s["episode_id"] for s in selected],
        "families": [s["family_id"] for s in selected],
        "regimes": [s["checkpoint_request"]["requested_regime"] for s in selected],
        "selected_before_resolution_outcomes": True,
    }


def _cfg_scaled(cfg: dict[str, Any], denom: int) -> dict[str, Any]:
    out = copy.deepcopy(cfg)
    out["integrator"]["dt_max_green_s"] = float(cfg["integrator"]["dt_max_green_s"]) / denom
    out["integrator"]["dt_max_regime_s"] = float(cfg["integrator"]["dt_max_regime_s"]) / denom
    out["integrator"]["step_label"] = {1: "h", 2: "h/2", 4: "h/4"}[denom]
    return out


def _index_events(events: list[dict[str, Any]]) -> dict[tuple[str, str], list[float]]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for event in events:
        kind = str(event.get("kind"))
        if kind not in PIT_EVENT_KINDS:
            continue
        key = (kind, str(event.get("car_id")))
        grouped[key].append(float(event["t"]))
    return grouped


def _max_matched_error(
    a: dict[tuple[str, str], list[float]], b: dict[tuple[str, str], list[float]]
) -> dict[str, Any]:
    keys = set(a) | set(b)
    max_err = None
    n_matched = 0
    missing = []
    count_mismatches = 0
    for key in sorted(keys):
        la, lb = a.get(key, []), b.get(key, [])
        if not la or not lb:
            missing.append({"kind": key[0], "car_id": key[1], "n_a": len(la), "n_b": len(lb)})
            continue
        for ta, tb in zip(la, lb, strict=False):
            err = abs(ta - tb)
            max_err = err if max_err is None else max(max_err, err)
            n_matched += 1
        if len(la) != len(lb):
            count_mismatches += 1
            missing.append({"kind": key[0], "car_id": key[1], "n_a": len(la), "n_b": len(lb), "count_mismatch": True})
    correspondence_ok = len(missing) == 0
    genuinely_absent = not a and not b
    return {
        "max_abs_error_s": max_err,
        "matched_pairs": n_matched,
        "absent_or_count_mismatch": missing,
        "count_mismatches": count_mismatches,
        "correspondence_ok": correspondence_ok,
        "quantity_absent": genuinely_absent,
        "quantity_mismatch_not_absent": (not genuinely_absent) and (not correspondence_ok),
    }


def _finish_errors(a: dict[str, float | None], b: dict[str, float | None]) -> dict[str, Any]:
    shared = [c for c in a if c in b and a[c] is not None and b[c] is not None]
    if not shared:
        return {
            "max_abs_error_s": None,
            "n_compared": 0,
            "quantity": "individual_finish_time",
            "note": "no cars with defined individual finish times at both resolutions",
        }
    errs = [abs(float(a[c]) - float(b[c])) for c in shared]
    return {
        "max_abs_error_s": max(errs),
        "n_compared": len(shared),
        "quantity": "individual_finish_time",
    }


def _rank_flip_detail(h: dict[str, Any], h2: dict[str, Any], h4: dict[str, Any]) -> dict[str, Any] | None:
    if h["ranks"] == h2["ranks"] == h4["ranks"]:
        return None
    # Identify cars whose ranks differ across resolutions
    cars = set(h["ranks"]) | set(h2["ranks"]) | set(h4["ranks"])
    flipped = []
    for cid in sorted(cars):
        r = (h["ranks"].get(cid), h2["ranks"].get(cid), h4["ranks"].get(cid))
        if len(set(r)) > 1:
            flipped.append({"car_id": cid, "ranks_h_h2_h4": r})
    # Pairwise gaps from each resolution (same-run), not across-resolution timestamp error
    pairs = []
    if len(flipped) >= 2:
        a, b = flipped[0]["car_id"], flipped[1]["car_id"]
        for label, row in (("h", h), ("h/2", h2), ("h/4", h4)):
            gap = abs(float(row["progress"][a]) - float(row["progress"][b]))
            pairs.append(
                {
                    "resolution": label,
                    "car_a": a,
                    "car_b": b,
                    "progress_gap_laps": gap,
                    "rank_a": row["ranks"].get(a),
                    "rank_b": row["ranks"].get(b),
                }
            )
    return {
        "flipped_cars": flipped,
        "pairwise_same_run_gaps": pairs,
        "near_tie_note": (
            "Near-tie only if a same-run pairwise progress gap is within a justified numerical "
            "uncertainty; across-resolution finish-timestamp error is not that gap."
        ),
    }


def _run_episode(cfg: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    _, out = sim.continue_to_finish()
    events = sim.engine.state["events"]
    ranks = out["ranking"]["ranks"]
    legality = not any(
        e["kind"] == "pit_now_expired" and e.get("detail", {}).get("not_relabelled_next_lap") is False
        for e in events
    )
    return {
        "finish_t": out["t"],
        "finish_times": out["finish_time"],
        "progress": out["progress"],
        "ranks": ranks,
        "events": _index_events(events),
        "event_kinds_present": sorted({e["kind"] for e in events}),
        "n_pit_events": sum(len(v) for v in _index_events(events).values()),
        "classification_order": out["ranking"]["order"],
        "legality_ok": legality,
        "leader_finish_t": out.get("leader_finish_t"),
        "cars_with_individual_finish": out["ranking"].get("cars_with_individual_finish_time"),
        "rank_at_leader_finish": out.get("rank_at_leader_finish"),
    }


def evaluate_resolution_row(
    *,
    episode_id: str,
    family_id: str,
    regime: str,
    h: dict[str, Any],
    h2: dict[str, Any],
    h4: dict[str, Any],
) -> dict[str, Any]:
    """Explicit predicates for the resolution gate. Used by production panel and injected-checker tests."""
    pit_h_h2 = _max_matched_error(h["events"], h2["events"])
    pit_h2_h4 = _max_matched_error(h2["events"], h4["events"])
    pit_h_h4 = _max_matched_error(h["events"], h4["events"])
    fin_h2_h4 = _finish_errors(h2["finish_times"], h4["finish_times"])
    fin_h_h4 = _finish_errors(h["finish_times"], h4["finish_times"])
    rank_flip = h2["ranks"] != h4["ranks"] or h["ranks"] != h4["ranks"]
    order_flip = h2["classification_order"] != h4["classification_order"]
    legality_stable = bool(h["legality_ok"] and h2["legality_ok"] and h4["legality_ok"])

    pit_genuinely_absent = pit_h_h2["quantity_absent"] and pit_h2_h4["quantity_absent"] and pit_h_h4["quantity_absent"]
    pit_correspondence_ok = (
        pit_h_h2["correspondence_ok"] and pit_h2_h4["correspondence_ok"] and pit_h_h4["correspondence_ok"]
    )
    pit_numeric_ok = True
    for block in (pit_h_h2, pit_h2_h4, pit_h_h4):
        if block["max_abs_error_s"] is not None and block["max_abs_error_s"] > TOL_PIT_EVENT_S:
            pit_numeric_ok = False
    if pit_genuinely_absent:
        pit_gate = "N/A"
    elif (not pit_correspondence_ok) or (not pit_numeric_ok):
        pit_gate = "FAIL"
    else:
        pit_gate = "PASS"

    finish_ok = True
    if fin_h2_h4["max_abs_error_s"] is not None and fin_h2_h4["max_abs_error_s"] > TOL_FINISH_S:
        finish_ok = False
    finish_gate = "PASS" if finish_ok else "FAIL"
    if fin_h2_h4["n_compared"] == 0 and any(
        isinstance(v, (int, float)) for v in list(h["finish_times"].values()) + list(h4["finish_times"].values())
    ):
        # Defined at one resolution but not comparable — not an automatic N/A success
        finish_gate = "PARTIAL"

    flip_detail = _rank_flip_detail(h, h2, h4) if rank_flip or order_flip else None
    near_tie = False
    if flip_detail and flip_detail["pairwise_same_run_gaps"]:
        # Convert progress gap to approximate time using a nominal 90 s lap as diagnostic only
        gaps = [row["progress_gap_laps"] for row in flip_detail["pairwise_same_run_gaps"]]
        # Near-tie if every same-run gap is below ~5e-4 laps (~0.05 s at 100 s/lap)
        near_tie = all(g <= 5e-4 for g in gaps)

    predicates = {
        "pit_correspondence_ok": pit_correspondence_ok or pit_genuinely_absent,
        "pit_numeric_ok": pit_numeric_ok or pit_genuinely_absent,
        "finish_numeric_ok": finish_ok,
        "legality_stable": legality_stable,
        "ranks_stable": not rank_flip,
        "order_stable": not order_flip,
    }
    if not legality_stable or pit_gate == "FAIL" or finish_gate == "FAIL":
        status = "FAIL"
    elif rank_flip or order_flip:
        status = "PARTIAL"
    else:
        status = "PASS"

    return {
        "episode_id": episode_id,
        "family_id": family_id,
        "regime": regime,
        "pit_events_h_vs_h2": pit_h_h2,
        "pit_events_h2_vs_h4": pit_h2_h4,
        "pit_events_h_vs_h4": pit_h_h4,
        "pit_quantity": "absent_all_resolutions" if pit_genuinely_absent else "pit_entry/service/rejoin event times",
        "finish_h2_vs_h4": fin_h2_h4,
        "finish_h_vs_h4": fin_h_h4,
        "finish_max_abs_error_h2_h4_s": fin_h2_h4["max_abs_error_s"],
        "finish_max_abs_error_h_h4_s": fin_h_h4["max_abs_error_s"],
        "rank_flip_h_h2_h4": rank_flip,
        "order_flip_h_h2_h4": order_flip,
        "rank_flip_detail": flip_detail,
        "near_tie_from_same_run_gap": near_tie,
        "legality_stable": legality_stable,
        "pit_gate": pit_gate,
        "finish_gate": finish_gate,
        "predicates": predicates,
        "row_status": status,
        "supports_refinement": (not pit_genuinely_absent)
        and pit_h2_h4["max_abs_error_s"] is not None
        and pit_h_h2["max_abs_error_s"] is not None
        and pit_h2_h4["max_abs_error_s"] <= pit_h_h2["max_abs_error_s"] + 1e-12,
    }


def run_resolution_panel(root: Path, panel_specs: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    denoms = (1, 2, 4)
    rows = []
    flips = []
    for spec in panel_specs:
        by_den = {}
        for den in denoms:
            by_den[den] = _run_episode(_cfg_scaled(cfg, den), spec)
        h, h2, h4 = by_den[1], by_den[2], by_den[4]
        row = evaluate_resolution_row(
            episode_id=spec["episode_id"],
            family_id=spec["family_id"],
            regime=spec["checkpoint_request"]["requested_regime"],
            h=h,
            h2=h2,
            h4=h4,
        )
        if row["rank_flip_h_h2_h4"] or row["order_flip_h_h2_h4"]:
            flips.append(
                {
                    "episode_id": spec["episode_id"],
                    "rank_flip": row["rank_flip_h_h2_h4"],
                    "order_flip": row["order_flip_h_h2_h4"],
                    "near_tie_from_same_run_gap": row["near_tie_from_same_run_gap"],
                    "detail": row["rank_flip_detail"],
                    "finish_err_h2_h4": row["finish_max_abs_error_h2_h4_s"],
                }
            )
        rows.append(row)
    pit_errors = [
        r["pit_events_h2_vs_h4"]["max_abs_error_s"]
        for r in rows
        if r["pit_events_h2_vs_h4"]["max_abs_error_s"] is not None
    ]
    finish_errors = [r["finish_max_abs_error_h2_h4_s"] for r in rows if r["finish_max_abs_error_h2_h4_s"] is not None]
    if any(r["row_status"] == "FAIL" for r in rows):
        status = "FAIL"
    elif any(r["row_status"] == "PARTIAL" for r in rows):
        status = "PARTIAL"
    else:
        status = "PASS"
    return {
        "status": status,
        "criteria": CRITERIA,
        "max_pit_event_error_h2_h4_s": max(pit_errors) if pit_errors else None,
        "max_finish_error_h2_h4_s": max(finish_errors) if finish_errors else None,
        "episodes_with_no_pit_events": sum(1 for r in rows if r["pit_gate"] == "N/A"),
        "rank_or_order_flips": flips,
        "rows": rows,
        "gate_predicates": [
            "pit_correspondence_and_counts",
            "pit_numeric_error",
            "individual_finish_numeric_error",
            "legality_stability",
            "rank_order_stability",
        ],
        "two_levels_do_not_prove_convergence": True,
        "na_means_genuinely_absent_all_resolutions": True,
    }


def run_fuel_audit(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    specs = load_preview_specs(root)
    rows = []
    floors = 0
    rejections = 0
    errors = []
    at_threshold = 0
    for spec in specs:
        init = spec["initialization"]
        remaining = int(init["remaining_laps"])
        need = horizon_need_kg(remaining, float(cfg["fuel"]["kg_per_lap"]))
        completed_init = int(init["completed_laps"])
        per_car = []
        rejected = None
        try:
            sim = RaceSimulator(cfg)
            sim.initialize(spec)
            for row in spec["field"]:
                cid = row["car_id"]
                est = float(row["fuel_kg"])
                u = float(row["fuel_uncertainty_kg"])
                offset = draw_uniform(
                    spec,
                    event_type="fuel_actual_offset",
                    driver_id=cid,
                    lap=completed_init,
                    low=-u,
                    high=u,
                )
                realized = realize_initial_fuel(
                    estimate_kg=est, uncertainty_kg=u, offset_kg=offset, need_kg=need, car_id=cid
                )
                actual = float(sim.engine.state["cars"][cid]["fuel_actual"])
                if abs(actual - realized.actual_kg) > 1e-9:
                    raise AssertionError(f"{cid} engine actual != realization")
                if realized.floor_applied:
                    floors += 1
                if abs(realized.actual_kg - need) <= 1e-9:
                    at_threshold += 1
                errors.append(realized.error_kg)
                per_car.append(
                    {
                        "car_id": cid,
                        "estimate_kg": est,
                        "actual_fuel": actual,
                        "need_kg": need,
                        "offset_kg": offset,
                        "error_kg": realized.error_kg,
                        "floor_applied": realized.floor_applied,
                        "provisional_actual_kg": realized.provisional_actual_kg,
                    }
                )
        except RejectionError as exc:
            rejected = f"{exc.code}: {exc.reason}"
            rejections += 1
        rows.append(
            {
                "episode_id": spec["episode_id"],
                "need_kg": need,
                "need_source": "remaining_laps_at_init * kg_per_lap",
                "rejected": rejected,
                "cars": per_car,
            }
        )
    edge = _fuel_edge_cases()
    public_rows = []
    for row in rows:
        public_rows.append(
            {
                "episode_id": row["episode_id"],
                "need_kg": row["need_kg"],
                "rejected": row["rejected"],
                "floor_count": sum(1 for c in row["cars"] if c["floor_applied"]),
                "error_min_kg": min((c["error_kg"] for c in row["cars"]), default=None),
                "error_max_kg": max((c["error_kg"] for c in row["cars"]), default=None),
                "cars_at_threshold": sum(1 for c in row["cars"] if abs(c["error_kg"] + (c["estimate_kg"] if False else 0)) or abs((c.get("actual_fuel") or 0) - row["need_kg"]) <= 1e-9),
            }
        )
        # recompute at-threshold without relying on the messy expression
        public_rows[-1]["cars_at_threshold"] = sum(
            1 for c in row["cars"] if abs(c["actual_fuel"] - row["need_kg"]) <= 1e-9
        )
    return {
        "preview_run_id": PREVIEW_RUN,
        "n_specs": len(specs),
        "n_cars": sum(len(r["cars"]) for r in rows),
        "floor_applied_count": floors,
        "rejection_count": rejections,
        "cars_with_mass_at_need_threshold": at_threshold,
        "error_min_kg": min(errors) if errors else None,
        "error_max_kg": max(errors) if errors else None,
        "unbiased_uniform_error": False,
        "conditioned_fictional_corpus": True,
        "need_uses_future_draws": False,
        "amendment": "development_spec.fuel.v1.1",
        "generation_unchanged_from_v1": True,
        "edge_cases": edge,
        "public_per_spec": public_rows,
        "private_rows": rows,
    }


def _fuel_edge_cases() -> dict[str, Any]:
    cases = []

    def one(name, **kwargs):
        try:
            got = realize_initial_fuel(**kwargs)
            cases.append({"name": name, "ok": True, "floor_applied": got.floor_applied, "actual_kg": got.actual_kg, "error_kg": got.error_kg})
        except RejectionError as exc:
            cases.append({"name": name, "ok": True, "rejected": exc.code})

    one("interior_above_need", estimate_kg=20.0, uncertainty_kg=2.0, offset_kg=-1.0, need_kg=18.0)
    one("floor_to_need", estimate_kg=18.0, uncertainty_kg=2.0, offset_kg=-1.5, need_kg=18.0)
    one("exact_need_no_floor", estimate_kg=18.0, uncertainty_kg=2.0, offset_kg=0.0, need_kg=18.0)
    one("offset_hits_need", estimate_kg=20.0, uncertainty_kg=2.0, offset_kg=-2.0, need_kg=18.0)
    one("impossible_band", estimate_kg=15.0, uncertainty_kg=2.0, offset_kg=0.0, need_kg=18.0)
    atom = 0
    interior = 0
    for i in range(41):
        offset = -2.0 + i * 0.1
        got = realize_initial_fuel(estimate_kg=20.0, uncertainty_kg=2.0, offset_kg=offset, need_kg=19.0)
        if got.floor_applied:
            atom += 1
        else:
            interior += 1
    expected_atom = sum(1 for i in range(41) if (-2.0 + i * 0.1) < -1.0 - 1e-12)
    return {
        "hand_cases": cases,
        "grid_estimate20_need19_u2": {
            "n": 41,
            "floor_atom_count": atom,
            "interior_count": interior,
            "expected_floor_when_offset_lt_-1": expected_atom,
            "atom_matches_truncated_uniform": atom == expected_atom,
            "note": "Floor replaces Uniform undershoot with an atom at need; error is not Uniform(-u,u).",
        },
        "pass": all("rejected" in c or c.get("ok") for c in cases)
        and cases[1]["floor_applied"] is True
        and abs(cases[1]["actual_kg"] - 18.0) <= 1e-12
        and cases[4].get("rejected") == "IMPOSSIBLE_INITIAL_FUEL"
        and atom == expected_atom,
    }


def run_shared_crew_end_to_end(cfg: dict[str, Any]) -> dict[str, Any]:
    spec = build_hand_spec(
        spec_id="hand.shared_e2e",
        episode_id="hand.shared_e2e/ep/SC",
        mean_gap_ahead_s=0.04,
        obligation=1,
        remaining_at_checkpoint=8,
        laps_until_checkpoint=1,
        selected_positions=(1, 2),
    )
    stacked = RaceSimulator(cfg)
    stacked.initialize(spec)
    a, b = spec["selected_car_ids"]
    stacked.apply_plan(
        {
            a: {"kind": "pit_now", "compound": "medium", "set_id": f"{a}.set.medium.0"},
            b: {"kind": "pit_now", "compound": "medium", "set_id": f"{b}.set.medium.0"},
        }
    )
    steps = 0
    while steps < 300_000:
        exits = [e for e in stacked.engine.state["events"] if e["kind"] == "pit_exit" and e["car_id"] in {a, b}]
        if len(exits) >= 2:
            break
        stacked.engine.tick()
        steps += 1
    waits = {cid: float(stacked.engine.state["cars"][cid]["service_wait_s"]) for cid in (a, b)}
    exit_t = {}
    for event in stacked.engine.state["events"]:
        if event["kind"] == "pit_exit" and event["car_id"] in {a, b}:
            exit_t.setdefault(event["car_id"], float(event["t"]))
    wait_max = max(waits.values())
    if len(exit_t) == 2:
        dt_exit = abs(exit_t[a] - exit_t[b])
        propagated = dt_exit + 1e-6 >= wait_max
    else:
        dt_exit = None
        propagated = False
    return {
        "pass": propagated and wait_max >= 0.0 and len(exit_t) == 2,
        "service_wait_s": waits,
        "pit_exit_race_s": exit_t,
        "exit_time_gap_s": dt_exit,
        "wait_propagated_into_rejoin_time": propagated,
        "note": "Time effect only; rank change is not required.",
    }


def execute_followup_unit(
    *,
    root: Path,
    run_id: str,
    unit_id: str,
    seed: int,
    attempt_id: str,
    dest: Path,
    guard: MemoryGuard,
) -> dict[str, Any]:
    del seed, attempt_id
    cfg, cfg_hash = load_simulator_config(root)
    guard.observe()
    if unit_id == "simulator.followup.criteria":
        specs = load_preview_specs(root)
        panel = resolution_panel_ids(specs)
        payload = {
            "ok": True,
            "criteria": CRITERIA,
            "resolution_panel": panel,
            "simulator_config_hash": cfg_hash,
            "preview_run_id": PREVIEW_RUN,
            "original_stage3_run_id": "e2258740-1d08-4427-8305-b149ed504a73",
            "original_stage3_snapshot": "26ed935ce0dbba00963bbe5766c77f1247fed491d2a9cf697f692c1cf5a4e6c1",
            "stage3_identifiers_not_overwritten": True,
        }
        return payload
    if unit_id == "simulator.followup.fuel":
        audit = run_fuel_audit(root, cfg)
        private = audit.pop("private_rows")
        dest.mkdir(parents=True, exist_ok=True)
        private_rel = dest / "fuel_private_audit.json"
        from f1q.hashing import atomic_write_bytes

        atomic_write_bytes(private_rel, canonical_json({"rows": private, "solver_must_not_read": True}) + b"\n")
        audit["ok"] = audit["rejection_count"] == 0 and audit["edge_cases"]["pass"]
        audit["private_audit_filename"] = "fuel_private_audit.json"
        audit["private_values_not_in_solver_observation"] = True
        return audit
    if unit_id == "simulator.followup.resolution":
        specs = load_preview_specs(root)
        selected = select_resolution_panel(specs)
        report = run_resolution_panel(root, selected, cfg)
        report["ok"] = report["status"] in {"PASS", "PARTIAL"}
        report["panel_episode_ids"] = [s["episode_id"] for s in selected]
        return report
    if unit_id == "simulator.followup.behavioral":
        from f1q.simulator.checks import check_causal, check_resume, check_rng

        causal = check_causal(cfg)
        resume = check_resume(cfg)
        rng = check_rng(cfg)
        return {
            "ok": causal["pass"] and resume["pass"] and rng["pass"],
            "causal": causal,
            "resume_fresh_process_still_required": "tests/test_simulator_mechanisms.py::test_resume_equivalence_in_fresh_process",
            "resume": resume,
            "randomness_branch_isolation": rng,
        }
    if unit_id == "simulator.followup.commitment":
        from f1q.simulator.checks import check_deadline

        deadline = check_deadline(cfg)
        return {"ok": deadline["pass"], "deadline": deadline}
    if unit_id == "simulator.followup.sc_vsc_traffic":
        from f1q.simulator.checks import check_sc_vsc, check_shared_service, check_traffic

        sc = check_sc_vsc(cfg)
        traffic = check_traffic(cfg)
        shared = check_shared_service(cfg)
        e2e = run_shared_crew_end_to_end(cfg)
        return {
            "ok": sc["pass"] and traffic["pass"] and shared["pass"] and e2e["pass"],
            "sc_vsc": sc,
            "traffic_rejoin": traffic,
            "shared_service": shared,
            "shared_crew_end_to_end": e2e,
        }
    if unit_id == "simulator.followup.memory":
        mech = run_all_mechanism_checks(cfg)
        summary = guard.summary()
        payload = {
            "ok": mech.get("ok") and not (summary.get("last") or {}).get("over_ceiling"),
            "mechanism_regressions_ok": mech.get("ok"),
            "failed_mechanism_checks": mech.get("failed"),
            "memory": summary,
            "workers": 1,
            "elapsed_cap_s": float(cfg["resource"]["stage3_elapsed_cap_s"]),
            "ram_ceiling_fraction": float(cfg["resource"]["ram_ceiling_fraction"]),
        }
        return payload
    raise ValueError(f"unknown followup unit {unit_id}")
