"""Deterministic Stage 3.3 post-repair diagnostic generator.

Engineering fixtures only. Not an experimental observation, F1 calibration, or
research result. Calls live production simulator handlers; does not hand-edit
scientific payload numbers.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from f1q.errors import RejectionError
from f1q.hashing import sha256_file, sha256_json
from f1q.simulator.classification import classify
from f1q.simulator.config import INTERFACE_VERSION, SIMULATOR_VERSION, load_simulator_config
from f1q.simulator.engine import OVERTAKE_ORDER_SNAP_LAPS, distance
from f1q.simulator.followup import evaluate_resolution_row
from f1q.simulator.hand_specs import build_hand_spec
from f1q.simulator.interface import RaceSimulator
from f1q.snapshot import git_state, take_source_snapshot

CORRECTED_DIAGNOSTIC_RELPATH = "docs/evidence/stage3_3/post_repair_diagnostic.corrected.json"
HISTORICAL_STAGE3_3_SHA256 = "10fe73b81f7580163ef29ff5d2125614dd8ee0c98a8f6c568d766e908915fa35"
# Stage 4.2+: never overwrite the immutable historical Stage 3.3 identity.
STAGE4_2_DIAGNOSTIC_RELPATH = "docs/evidence/stage4_2/stage3_3_regression_diagnostic.json"
STALE_DIAGNOSTIC_RELPATH = "docs/evidence/stage3_2/post_repair_diagnostic.json"
ERRATUM_RELPATH = "docs/evidence/stage3_3/stage3_2_post_repair_diagnostic_erratum.json"

# Declared upper check for genuine-crossing order snap (matches Stage 3.2 review).
CROSSING_SNAP_UPPER_BOUND_LAPS = 2e-12


def _fresh(cfg: dict[str, Any]) -> RaceSimulator:
    sim = RaceSimulator(cfg)
    sim.initialize(build_hand_spec(obligation=1))
    return sim


def assert_r2_individual_finish_invariants(out: dict[str, Any], *, field_size: int = 20) -> dict[str, Any]:
    """Semantic invariants for the repaired leader-triggered finish model.

    These checks fail the historical all-cars/shared-leader-time shape.
    Engineering fixture only; not an experimental observation.
    """
    fts = out["finish_time"]
    if len(fts) != field_size:
        raise AssertionError(f"expected field_size={field_size}, got {len(fts)}")
    defined = {cid: v for cid, v in fts.items() if v is not None}
    absent = [cid for cid, v in fts.items() if v is None]
    if len(defined) != 1:
        raise AssertionError(
            f"expected exactly one defined individual finish_time, got {len(defined)} "
            f"(historical shared-leader stamp would define all {field_size})"
        )
    if len(absent) != field_size - 1:
        raise AssertionError(f"expected {field_size - 1} absent finish times, got {len(absent)}")
    leader_id = out.get("leader_finish_car_id")
    leader_t = out.get("leader_finish_t")
    if leader_id is None or leader_t is None:
        raise AssertionError("leader_finish_car_id and leader_finish_t must be defined")
    if leader_id not in defined:
        raise AssertionError(f"leader {leader_id} must have a defined individual finish_time")
    if abs(float(defined[leader_id]) - float(leader_t)) > 1e-9:
        raise AssertionError("leader individual finish_time must equal leader_finish_t within 1e-9 s")
    for cid in absent:
        if fts[cid] is not None:
            raise AssertionError(f"unfinished car {cid} must remain None, not a stamped time")
    ranking = classify(out["progress"], fts)
    if ranking["ranks"] != out["ranking"]["ranks"]:
        raise AssertionError("classify(progress, finish_time) must match reported ranking.ranks")
    if ranking["order"] != out["ranking"]["order"]:
        raise AssertionError("classify order must match reported ranking.order")
    return {
        "n_defined": len(defined),
        "n_absent": len(absent),
        "leader_finish_car_id": leader_id,
        "leader_finish_t": float(leader_t),
        "leader_individual_finish_t": float(defined[leader_id]),
        "classification_consistent": True,
        "ranking_keys": ranking["ranking_keys"],
        "classification_model": out.get("classification_model"),
    }


def historical_shared_leader_stamp_would_fail(leader_finish_t: float, field_size: int = 20) -> bool:
    """True when the Stage 3.3 R2 invariant rejects the pre-repair shared-stamp shape."""
    fake_progress = {f"car.{i:02d}": float(field_size - i) for i in range(field_size)}
    fake_fts = {cid: float(leader_finish_t) for cid in fake_progress}
    fake_out = {
        "finish_time": fake_fts,
        "progress": fake_progress,
        "leader_finish_t": float(leader_finish_t),
        "leader_finish_car_id": "car.00",
        "ranking": classify(fake_progress, fake_fts),
        "classification_model": "historical_shared_leader_stamp_fixture",
    }
    try:
        assert_r2_individual_finish_invariants(fake_out, field_size=field_size)
    except AssertionError:
        return True
    return False


def build_scientific_payload(cfg: dict[str, Any], cfg_hash: str) -> dict[str, Any]:
    """Build the deterministic scientific payload from live production handlers.

    Source snapshot / git identity belong in generation_metadata so the scientific
    payload stays comparable after documentation-only or packaging edits.
    """
    entry = float(cfg["track"]["pit_entry_frac"])
    box = float(cfg["track"]["pit_box_frac"])
    exit_f = float(cfg["track"]["pit_exit_frac"])

    # R1 — pit geometry phase trace
    sim = _fresh(cfg)
    e = sim.engine
    car = next(iter(e.state["cars"].values()))
    cid = car["car_id"]
    car.update(
        completed_laps=10,
        frac=entry,
        pit_this_lap=True,
        pending_compound="medium",
        pending_set_id=f"{cid}.set.medium.0",
    )
    e.fire([("pit_entry", cid, {})])
    pit_trace: list[list[Any]] = [[car["pit_phase"], float(e.state["t"]), float(distance(car))]]
    while car["in_pit"]:
        e.state["t"] = car["pit_phase_end"]
        car["pit_clock_t"] = e.state["t"]
        e._advance_pit(car)
        pit_trace.append([car["pit_phase"], float(e.state["t"]), float(distance(car))])

    # R2 — leader-triggered individual finish times on hand fixture
    sim_r2 = _fresh(cfg)
    sim_r2.advance_to_checkpoint()
    _, out_r2 = sim_r2.continue_to_finish()
    r2_summary = assert_r2_individual_finish_invariants(out_r2, field_size=20)
    r2_summary["historical_shared_stamp_rejected_by_invariant"] = historical_shared_leader_stamp_would_fail(
        float(out_r2["leader_finish_t"]), field_size=20
    )

    # R3 — finite gap: must not teleport
    sim_gap = _fresh(cfg)
    e_gap = sim_gap.engine
    ids = list(e_gap.state["cars"])
    ahead, passer = e_gap.state["cars"][ids[0]], e_gap.state["cars"][ids[1]]
    ahead.update(completed_laps=10, frac=0.5, tyre_age_laps=20.0)
    passer.update(completed_laps=10, frac=0.4999, tyre_age_laps=0.0)
    gap_before = {
        "progress": float(distance(passer)),
        "fuel_actual": float(passer["fuel_actual"]),
        "tyre_age_laps": float(passer["tyre_age_laps"]),
        "race_t": float(e_gap.state["t"]),
        "want_pass": passer.get("want_pass"),
    }
    e_gap.fire([("catch_or_pass", ids[1], {"ahead": ids[0]})])
    gap_after = {
        "progress": float(distance(passer)),
        "fuel_actual": float(passer["fuel_actual"]),
        "tyre_age_laps": float(passer["tyre_age_laps"]),
        "race_t": float(e_gap.state["t"]),
        "want_pass": passer.get("want_pass"),
    }
    pass_deltas = [
        gap_after["progress"] - gap_before["progress"],
        gap_after["fuel_actual"] - gap_before["fuel_actual"],
        gap_after["tyre_age_laps"] - gap_before["tyre_age_laps"],
        gap_after["race_t"] - gap_before["race_t"],
    ]
    if pass_deltas != [0.0, 0.0, 0.0, 0.0]:
        raise RuntimeError(
            f"live R3 finite-gap deltas are not exact zeros: {pass_deltas}; "
            "refusing to emit a corrected diagnostic with edited numbers"
        )

    # R3 — genuine crossing: order snap only
    sim_x = _fresh(cfg)
    e_x = sim_x.engine
    ids_x = list(e_x.state["cars"])
    ahead_x, passer_x = e_x.state["cars"][ids_x[0]], e_x.state["cars"][ids_x[1]]
    ahead_x.update(completed_laps=10, frac=0.5, tyre_age_laps=20.0)
    passer_x.update(completed_laps=10, frac=0.5 - OVERTAKE_ORDER_SNAP_LAPS / 2, tyre_age_laps=0.0)
    old_d = float(distance(passer_x))
    e_x.fire([("catch_or_pass", ids_x[1], {"ahead": ids_x[0]})])
    snap_delta = float(distance(passer_x)) - old_d
    if snap_delta > CROSSING_SNAP_UPPER_BOUND_LAPS:
        raise RuntimeError(
            f"live R3 crossing snap {snap_delta} exceeds declared upper bound "
            f"{CROSSING_SNAP_UPPER_BOUND_LAPS}"
        )

    # R4 — common commitment epoch
    sim_r4 = _fresh(cfg)
    ids_r4 = list(sim_r4.engine.state["cars"])
    sim_r4.advance_to_checkpoint()
    t0 = float(sim_r4.engine.state["t"])
    early = sim_r4.clone().consider_recommendation(
        {ids_r4[0]: {"kind": "continuation"}},
        arrival_delay_s=0.05,
        commitment_epoch_race_s=t0 + 0.1,
    )
    late = sim_r4.clone().consider_recommendation(
        {ids_r4[0]: {"kind": "continuation"}},
        arrival_delay_s=0.2,
        commitment_epoch_race_s=t0 + 0.1,
    )
    commitments = [
        {
            "arrival_delay_s": 0.05,
            "timely": bool(early["timely"]),
            "selected_plan": early["selected_plan"],
            "registered_commitment_epoch_race_s": float(early["registered_commitment_epoch_race_s"]),
            "commitment_race_s": float(early["commitment_race_s"]),
            "late_vs_registered_epoch": bool(early.get("late_vs_registered_epoch", False)),
            "fallback_reason": early.get("fallback_reason"),
        },
        {
            "arrival_delay_s": 0.2,
            "timely": bool(late["timely"]),
            "selected_plan": late["selected_plan"],
            "registered_commitment_epoch_race_s": float(late["registered_commitment_epoch_race_s"]),
            "commitment_race_s": float(late["commitment_race_s"]),
            "late_vs_registered_epoch": bool(late.get("late_vs_registered_epoch", False)),
            "fallback_reason": late.get("fallback_reason"),
        },
    ]

    # R5 — plan validation + atomicity
    sim_r5 = _fresh(cfg)
    ids_r5 = list(sim_r5.engine.state["cars"])
    selected = list(sim_r5.engine.state["selected_car_ids"])
    prior = copy.deepcopy(sim_r5.engine.state["policies"])
    mismatched_set: dict[str, Any]
    try:
        sim_r5.validate_plan(
            {selected[0]: {"kind": "pit_now", "compound": "hard", "set_id": f"{selected[0]}.set.medium.0"}}
        )
        mismatched_set = {"ok": True}
    except RejectionError as exc:
        mismatched_set = {"ok": False, "code": exc.code, "reason": exc.reason}
    rival = next(c for c in ids_r5 if c not in selected)
    rival_control: dict[str, Any]
    try:
        sim_r5.validate_plan({rival: {"kind": "continuation"}})
        rival_control = {"ok": True}
    except RejectionError as exc:
        rival_control = {"ok": False, "code": exc.code, "reason": exc.reason}
    bad = {
        selected[0]: {"kind": "continuation"},
        selected[1]: {"kind": "pit_now", "compound": "hard", "set_id": f"{selected[1]}.set.medium.0"},
    }
    atomic_rollback = False
    try:
        sim_r5.apply_plan(bad)
    except RejectionError:
        atomic_rollback = sim_r5.engine.state["policies"] == prior

    # R6 — resolution gate (injected checker fixtures)
    def base_row() -> dict[str, Any]:
        events = {("pit_entry", "car.a"): [100.0], ("pit_exit", "car.a"): [110.0]}
        return {
            "finish_times": {"car.a": 200.0, "car.b": 201.0},
            "progress": {"car.a": 34.0, "car.b": 33.5},
            "ranks": {"car.a": 1, "car.b": 2},
            "events": events,
            "classification_order": ["car.a", "car.b"],
            "legality_ok": True,
        }

    h = base_row()
    h2 = copy.deepcopy(h)
    h4 = copy.deepcopy(h)
    ok_row = evaluate_resolution_row(episode_id="inj.ok", family_id="inj", regime="SC", h=h, h2=h2, h4=h4)
    missing = copy.deepcopy(h4)
    missing["events"] = {("pit_entry", "car.a"): [100.0]}
    bad_missing = evaluate_resolution_row(
        episode_id="inj.missing", family_id="inj", regime="SC", h=h, h2=h2, h4=missing
    )
    illegal = copy.deepcopy(h4)
    illegal["legality_ok"] = False
    bad_leg = evaluate_resolution_row(
        episode_id="inj.leg", family_id="inj", regime="SC", h=h, h2=h2, h4=illegal
    )
    flip = copy.deepcopy(h4)
    flip["ranks"] = {"car.a": 2, "car.b": 1}
    flip["classification_order"] = ["car.b", "car.a"]
    flip["progress"] = {"car.a": 33.0, "car.b": 34.0}
    flip["finish_times"] = {"car.a": 210.0, "car.b": 200.0}
    bad_rank = evaluate_resolution_row(
        episode_id="inj.rank", family_id="inj", regime="SC", h=h, h2=h2, h4=flip
    )

    return {
        "kind": "stage3_3_post_repair_diagnostic_corrected",
        "evidence_class": "engineering_fixture",
        "not_experimental_observation": True,
        "not_f1_calibration": True,
        "simulator_version": SIMULATOR_VERSION,
        "interface_version": INTERFACE_VERSION,
        "simulator_config_hash": cfg_hash,
        "overtake_order_snap_laps": OVERTAKE_ORDER_SNAP_LAPS,
        "crossing_snap_upper_bound_laps": CROSSING_SNAP_UPPER_BOUND_LAPS,
        "pit_geometry": {
            "pit_entry_frac": entry,
            "pit_box_frac": box,
            "pit_exit_frac": exit_f,
        },
        "r1_pit_trace": pit_trace,
        "r2_finish": r2_summary,
        "r3_finite_gap": {
            "pre_pass_gap_laps": 0.0001,
            "before": gap_before,
            "after": gap_after,
            "pass_deltas": pass_deltas,
            "pass_deltas_exact_zeros": True,
        },
        "r3_genuine_crossing": {
            "snap_delta_laps": snap_delta,
            "declared_upper_bound_laps": CROSSING_SNAP_UPPER_BOUND_LAPS,
            "within_bound": snap_delta <= CROSSING_SNAP_UPPER_BOUND_LAPS,
            "order_snap_laps_constant": OVERTAKE_ORDER_SNAP_LAPS,
        },
        "r4_commitments": commitments,
        "r5_plan_validation": {
            "mismatched_set": mismatched_set,
            "rival_control": rival_control,
            "atomic_rollback_on_two_car_failure": atomic_rollback,
        },
        "r6_resolution_gate": {
            "valid_row_status": ok_row["row_status"],
            "valid_pit_gate": ok_row["pit_gate"],
            "missing_pit_events_pit_gate": bad_missing["pit_gate"],
            "missing_pit_events_row_status": bad_missing["row_status"],
            "legality_failure_row_status": bad_leg["row_status"],
            "legality_stable": bad_leg["legality_stable"],
            "rank_flip_detected": bad_rank["rank_flip_h_h2_h4"],
            "rank_flip_row_status": bad_rank["row_status"],
        },
    }


def build_diagnostic_document(root: Path) -> dict[str, Any]:
    cfg, cfg_hash = load_simulator_config(root)
    snapshot = take_source_snapshot(root)
    commit, dirty = git_state(root)
    scientific = build_scientific_payload(cfg, cfg_hash)
    return {
        "scientific_payload": scientific,
        "scientific_payload_sha256": sha256_json(scientific),
        "generation_metadata": {
            "generator_module": "f1q.simulator.stage3_3_diagnostic",
            "command": "python -m f1q simulator diagnostic-stage3-3",
            "git_commit": commit,
            "git_dirty": dirty,
            "source_snapshot_hash": snapshot["hash"],
            "documentation_hash": snapshot.get("documentation_hash"),
            "simulator_version": SIMULATOR_VERSION,
            "interface_version": INTERFACE_VERSION,
            "simulator_config_hash": cfg_hash,
            "note": (
                "Timestamps intentionally omitted from scientific_payload for determinism. "
                "Source snapshot and git identity live here so evidence stays associated "
                "with the tested tree without making the scientific payload non-reproducible "
                "under documentation packaging edits."
            ),
        },
    }


def restore_historical_stage3_3_bytes(root: Path, *, source_commit: str = "5c94976") -> dict[str, Any]:
    """Restore immutable Stage 3.3 corrected diagnostic byte-for-byte from pre-Stage-4.1 history."""
    import hashlib
    import subprocess

    rel = CORRECTED_DIAGNOSTIC_RELPATH
    blob = subprocess.check_output(["git", "show", f"{source_commit}:{rel}"], cwd=root)
    digest = hashlib.sha256(blob).hexdigest()
    if digest != HISTORICAL_STAGE3_3_SHA256:
        raise AssertionError(
            f"historical blob sha {digest} != expected {HISTORICAL_STAGE3_3_SHA256}"
        )
    out = root / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    return {
        "path": rel,
        "sha256": digest,
        "source_commit": source_commit,
        "restored": True,
        "immutable": True,
    }


def verify_historical_stage3_3(root: Path) -> dict[str, Any]:
    import hashlib

    path = root / CORRECTED_DIAGNOSTIC_RELPATH
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": CORRECTED_DIAGNOSTIC_RELPATH,
        "sha256": digest,
        "expected": HISTORICAL_STAGE3_3_SHA256,
        "ok": digest == HISTORICAL_STAGE3_3_SHA256,
        "immutable_identity": True,
    }


def write_corrected_diagnostic(root: Path, *, path: Path | None = None) -> dict[str, Any]:
    """Write a *current* regression diagnostic. Refuses the immutable Stage 3.3 identity path."""
    out_path = path or (root / STAGE4_2_DIAGNOSTIC_RELPATH)
    if out_path.resolve() == (root / CORRECTED_DIAGNOSTIC_RELPATH).resolve():
        raise ValueError(
            "refusing to overwrite immutable Stage 3.3 evidence identity; "
            f"write current diagnostics to {STAGE4_2_DIAGNOSTIC_RELPATH}"
        )
    doc = build_diagnostic_document(root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    return {
        "path": str(out_path.relative_to(root)),
        "sha256": sha256_file(out_path),
        "scientific_payload_sha256": doc["scientific_payload_sha256"],
        "document": doc,
        "historical_path_untouched": CORRECTED_DIAGNOSTIC_RELPATH,
    }


def load_checked_in_corrected(root: Path) -> dict[str, Any]:
    path = root / CORRECTED_DIAGNOSTIC_RELPATH
    return json.loads(path.read_text(encoding="utf-8"))


def scientific_payload_matches_live(root: Path, *, path: Path | None = None) -> tuple[bool, dict[str, Any]]:
    """Compare a Stage 4.2 current diagnostic to a fresh live generation.

    Historical Stage 3.3 file is verified by hash only (verify_historical_stage3_3).
    """
    checked_path = path or (root / STAGE4_2_DIAGNOSTIC_RELPATH)
    checked = json.loads(checked_path.read_text(encoding="utf-8"))
    live = build_diagnostic_document(root)
    match = checked["scientific_payload"] == live["scientific_payload"]
    hist = verify_historical_stage3_3(root)
    detail = {
        "match": match,
        "checked_scientific_payload_sha256": checked.get("scientific_payload_sha256"),
        "live_scientific_payload_sha256": live["scientific_payload_sha256"],
        "checked_file_sha256": sha256_file(checked_path),
        "checked_path": str(checked_path.relative_to(root)) if checked_path.is_relative_to(root) else str(checked_path),
        "historical_stage3_3": hist,
    }
    return match, detail
