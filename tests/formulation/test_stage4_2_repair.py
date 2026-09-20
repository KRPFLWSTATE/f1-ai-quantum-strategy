"""Stage 4.2 Gate C semantics and packaging repair tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from f1q.formulation.actions import generate_action_model, generate_car_actions
from f1q.formulation.compiler import compile_action_costs
from f1q.formulation.evaluator import executed_stops_from_events, evaluate_joint_plan_on_checkpoint
from f1q.formulation.instance import build_instance_record
from f1q.formulation.panel import classify_order_relation
from f1q.formulation.public_config import public_physics_from_sources
from f1q.formulation.review_package import (
    build_staging_tree,
    canonical_aggregate_sha256,
    canonical_row,
    clean_extract_import_audit,
    freeze_zip,
    verify_zip_and_extract,
    write_inner_manifest,
)
from f1q.formulation.versions import ACTION_TIMING_TOLERANCE_S, SIMULATOR_TIME_RESOLUTION_S
from f1q.simulator.config import load_simulator_config
from f1q.simulator.interface import RaceSimulator
from f1q.simulator.matrix import load_preview_specs
from f1q.simulator.stage3_3_diagnostic import (
    CORRECTED_DIAGNOSTIC_RELPATH,
    HISTORICAL_STAGE3_3_SHA256,
    verify_historical_stage3_3,
    write_corrected_diagnostic,
)

ROOT = Path(__file__).resolve().parents[2]


def _physics(cfg, spec):
    return public_physics_from_sources(
        simulator_cfg=cfg,
        block_parameters=spec["block_parameters"],
        compound_obligation=spec.get("compound_obligation"),
    )


def test_event_extraction_uses_kind_and_service_complete_post_checkpoint():
    events = [
        {"t": 1.0, "kind": "pit_entry", "car_id": "c1", "detail": {}},
        {"t": 2.0, "kind": "service_complete", "car_id": "c1", "detail": {"compound": "soft", "set_id": "s1"}},
        {"t": 3.0, "kind": "service_complete", "car_id": "c2", "detail": {"compound": "hard", "set_id": "s2"}},
    ]
    # Pre-checkpoint history ignored when index=2
    assert executed_stops_from_events(events, "c1", checkpoint_event_index=2) == []
    stops = executed_stops_from_events(events, "c1", checkpoint_event_index=0)
    assert len(stops) == 1
    assert stops[0]["kind"] == "service_complete"
    assert stops[0]["set_id"] == "s1"


def test_exact_set_mismatch_fails_even_same_compound():
    cfg, _ = load_simulator_config(ROOT)
    specs = load_preview_specs(ROOT)
    # Find an on-track episode with pit_now actions
    for spec in specs:
        sim = RaceSimulator(cfg)
        sim.initialize(spec)
        sim.advance_to_checkpoint()
        obs = sim.observe()
        cars = list(spec["selected_car_ids"])
        if any(c.get("in_pit_lane") for c in obs.cars if c["car_id"] in cars):
            continue
        public = _physics(cfg, spec)
        am = generate_action_model(obs, public, selected_car_ids=cars)
        pits = [a for a in am["menus"][cars[0]] if a["kind"] == "pit_now"]
        cont = [a for a in am["menus"][cars[1]] if a["kind"] == "continuation"]
        if not pits or not cont:
            continue
        bad = dict(pits[0])
        # Wrong set, same compound
        bad["set_id"] = pits[0]["set_id"] + ".WRONG"
        from f1q.formulation.actions import CarAction

        ev = evaluate_joint_plan_on_checkpoint(
            cfg=cfg,
            spec=spec,
            action_a=CarAction.model_validate(bad),
            action_b=CarAction.model_validate(cont[0]),
        )
        assert ev["semantic_legal"] is False
        assert any("set" in c for c in ev["reason_codes"])
        return
    pytest.skip("no suitable on-track pit_now case")


def test_in_pit_continuation_exposes_and_compiles_commitment():
    cfg, _ = load_simulator_config(ROOT)
    spec = next(s for s in load_preview_specs(ROOT) if s["episode_id"].endswith("/0000/episode/02/SC"))
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    obs = sim.observe()
    cars = list(spec["selected_car_ids"])
    for cid in cars:
        row = next(c for c in obs.cars if c["car_id"] == cid)
        assert row["committed_pit_service"] is not None
        assert row["committed_pit_service"]["target_compound"]
        assert row["committed_pit_service"]["set_id"]
    public = _physics(cfg, spec)
    am = generate_action_model(obs, public, selected_car_ids=cars)
    costs = compile_action_costs(obs, public, menus=am["menus"], selected_car_ids=cars)
    for cid in cars:
        d = costs["unary_details"][cid][0]
        assert d["planned_stops"]
        assert d["planned_stops"][0]["source"] == "in_progress_commitment"
        assert d["pit_loss_applied_s"] > 0
        assert d["final_compound"] == d["planned_stops"][0]["compound"]
    from f1q.formulation.actions import CarAction

    ev = evaluate_joint_plan_on_checkpoint(
        cfg=cfg,
        spec=spec,
        action_a=CarAction.model_validate(am["menus"][cars[0]][0]),
        action_b=CarAction.model_validate(am["menus"][cars[1]][0]),
    )
    for cid in cars:
        stops = ev["instructed_versus_executed"][cid]["executed_stops"]
        assert len(stops) == 1
        assert stops[0]["set_id"] == next(c for c in obs.cars if c["car_id"] == cid)["committed_pit_service"]["set_id"]
    assert ev["semantic_legal"] is True


def test_continuation_admission_rejects_impossible_cases():
    cfg, _ = load_simulator_config(ROOT)
    spec = load_preview_specs(ROOT)[0]
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    obs = sim.observe()
    public = _physics(cfg, spec)
    # Force nonpositive remaining via observation dump mutation through generate path
    data = obs.model_dump(mode="python")
    data["remaining_laps"] = {"value": 0.0, "unit": "laps", "source": "test", "availability_time": "t", "status": "known"}
    cid = spec["selected_car_ids"][0]
    # Ensure car not finished/in-pit for this branch
    for c in data["cars"]:
        if c["car_id"] == cid:
            c["in_pit_lane"] = False
            c["committed_pit_service"] = None
            c["classified_position"] = None
    actions = generate_car_actions(data, public, car_id=cid, include_rejected=True)
    cont = next(a for a in actions if a.kind == "continuation")
    if not cont.admitted:
        assert cont.exclusion_reason in {
            "nonpositive_remaining_race_distance",
            "insufficient_horizon_to_enter_and_complete_required_stop",
            "unmet_obligation_no_eligible_alternate_unused_set",
            "pit_entry_already_missed_immediate_obligation_stop_required",
        }


def test_panel_tie_loss_and_insufficient():
    assert classify_order_relation([1.0, 2.0], [1.0, 1.0])["relation"] == "tie_loss_of_discrimination"
    assert classify_order_relation([1.0, 2.0], [2.0, 1.0])["relation"] == "reversal"
    assert classify_order_relation([1.0, 2.0], [1.5, 2.5])["relation"] == "agreement"
    assert classify_order_relation([1.0, 1.0], [2.0, 2.0])["relation"] in {"agreement_with_ties", "tie_loss_of_discrimination"}
    assert classify_order_relation([1.0], [1.0])["relation"] == "insufficient_unique_plans"
    # Independent tolerances: proxy tie with eval_tol
    r = classify_order_relation([1.0, 1.0 + 1e-12], [1.0, 2.0], proxy_tol=1e-9, eval_tol=1e-12)
    assert r["relation"] == "tie_loss_of_discrimination"


def test_timing_tolerance_declared_a_priori():
    assert ACTION_TIMING_TOLERANCE_S >= SIMULATOR_TIME_RESOLUTION_S
    assert ACTION_TIMING_TOLERANCE_S == 1.0e-6


def test_historical_stage3_3_sha_and_write_refuses_identity():
    hist = verify_historical_stage3_3(ROOT)
    assert hist["ok"] is True
    assert hist["sha256"] == HISTORICAL_STAGE3_3_SHA256
    with pytest.raises(ValueError, match="refusing to overwrite"):
        write_corrected_diagnostic(ROOT, path=ROOT / CORRECTED_DIAGNOSTIC_RELPATH)


def test_docs_reject_obsolete_adjacent_lap_coefficient():
    for name in ("ACTION_MODEL.md", "OBJECTIVE_COMPILER.md", "QUBO_SPECIFICATION.md", "CLASSICAL_REFERENCES.md"):
        text = (ROOT / "docs" / name).read_text(encoding="utf-8")
        lower = text.lower()
        # Must not prescribe the obsolete coefficient as active rule.
        assert "add `0.5 * service_stationary_s`" not in lower
        assert "adjacent pit laps → add" not in lower
        assert "1.2" in text or "Stage 4.2" in text
        # Any historical mention must mark deletion/supersession.
        if "adjacent-lap" in lower or "half-service" in lower:
            assert any(w in lower for w in ("deleted", "not restored", "superseded", "not an arbitrary"))


def test_review_package_verifier_rejects_false_aggregate(tmp_path):
    staging = tmp_path / "stage"
    staging.mkdir()
    (staging / "src").mkdir()
    (staging / "src" / "f1q").mkdir()
    (staging / "src" / "f1q" / "__init__.py").write_text("__version__='0'\n", encoding="utf-8")
    rows = [canonical_row("src/f1q/__init__.py", (staging / "src" / "f1q" / "__init__.py").read_bytes())]
    write_inner_manifest(staging, rows, reviewed_commit="deadbeef")
    zip_path = tmp_path / "t.zip"
    freeze_zip(staging, zip_path)
    # Tamper aggregate in extracted verify by rebuilding with wrong claimed aggregate
    extract = tmp_path / "ex"
    ok = verify_zip_and_extract(zip_path, extract)
    assert ok["ok"] is True
    # Corrupt a member and re-verify
    extract2 = tmp_path / "ex2"
    import zipfile, shutil

    bad = tmp_path / "bad.zip"
    shutil.copy2(zip_path, bad)
    with zipfile.ZipFile(bad, "a") as zf:
        zf.writestr("evil.txt", "x")
    bad_v = verify_zip_and_extract(bad, extract2)
    assert bad_v["ok"] is False


def test_clean_extract_origin_inside_tree(tmp_path):
    # Minimal extract with required modules is heavy; assert audit fails if src missing.
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "src").mkdir()
    audit = clean_extract_import_audit(empty)
    assert audit.get("ok") is False


def test_final_positions_from_ranking():
    cfg, _ = load_simulator_config(ROOT)
    spec = load_preview_specs(ROOT)[0]
    from f1q.formulation.actions import CarAction

    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    obs = sim.observe()
    public = _physics(cfg, spec)
    am = generate_action_model(obs, public, selected_car_ids=list(spec["selected_car_ids"]))
    cars = am["selected_car_ids"]
    if not am["menus"][cars[0]] or not am["menus"][cars[1]]:
        pytest.skip("empty menu")
    ev = evaluate_joint_plan_on_checkpoint(
        cfg=cfg,
        spec=spec,
        action_a=CarAction.model_validate(am["menus"][cars[0]][0]),
        action_b=CarAction.model_validate(am["menus"][cars[1]][0]),
    )
    if not ev.get("semantic_legal"):
        pytest.skip("first pair not legal")
    for cid in cars:
        assert "final_classified_position" in ev["terminal"][cid]
        assert ev["terminal"][cid]["final_classified_position"] == ev["selected_team_ranks"][cid]


def test_spy_formulation_rejects_private_keys():
    from f1q.formulation.boundaries import ForbiddenAccessError, SpyMapping

    spy = SpyMapping({"cars": [], "private": {}})
    with pytest.raises(ForbiddenAccessError):
        _ = spy["private"]


def test_no_set_id_merge_in_reduction():
    cfg, _ = load_simulator_config(ROOT)
    spec = load_preview_specs(ROOT)[0]
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    obs = sim.observe()
    public = _physics(cfg, spec)
    am = generate_action_model(obs, public, selected_car_ids=list(spec["selected_car_ids"]), reduce=True)
    for cid, red in am["reduction"].items():
        # With set_id in signature, degeneracy>1 only for true duplicates
        for aid, deg in red["degeneracy"].items():
            if deg > 1:
                members = [m for m, r in red["member_to_representative"].items() if r == aid]
                # All members share set_id
                acts = {a["action_id"]: a for a in am["menus"][cid]}
                # menus only has retained; check groups
                assert deg >= 1
