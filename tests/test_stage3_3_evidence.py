"""Stage 3.3 evidence-correction regressions. Engineering fixtures, not experimental observations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from f1q.hashing import sha256_file
from f1q.simulator.stage3_3_diagnostic import (
    CORRECTED_DIAGNOSTIC_RELPATH,
    ERRATUM_RELPATH,
    HISTORICAL_STAGE3_3_SHA256,
    STAGE4_2_DIAGNOSTIC_RELPATH,
    STALE_DIAGNOSTIC_RELPATH,
    build_diagnostic_document,
    scientific_payload_matches_live,
    verify_historical_stage3_3,
    write_corrected_diagnostic,
)

ROOT = Path(__file__).resolve().parents[1]


def test_stale_stage3_2_diagnostic_preserved_byte_for_byte():
    stale = ROOT / STALE_DIAGNOSTIC_RELPATH
    erratum_path = ROOT / ERRATUM_RELPATH
    assert stale.is_file()
    assert erratum_path.is_file()
    erratum = json.loads(erratum_path.read_text(encoding="utf-8"))
    assert erratum["status"] == "stale_superseded"
    assert erratum["stale_artifact_path"] == STALE_DIAGNOSTIC_RELPATH
    assert erratum["stale_artifact_sha256"] == sha256_file(stale)
    payload = json.loads(stale.read_text(encoding="utf-8"))
    # Named defect: finite-gap progress jump still recorded in the stale file.
    assert payload["pass_deltas"][0] != 0.0


def test_corrected_diagnostic_matches_live_production():
    # Historical Stage 3.3 identity is immutable and hash-verified.
    hist = verify_historical_stage3_3(ROOT)
    assert hist["ok"] is True
    assert hist["sha256"] == HISTORICAL_STAGE3_3_SHA256
    assert (ROOT / CORRECTED_DIAGNOSTIC_RELPATH).is_file()
    # Current regression diagnostic lives under Stage 4.2 identity only.
    written = write_corrected_diagnostic(ROOT)
    assert written["path"] == STAGE4_2_DIAGNOSTIC_RELPATH
    match, detail = scientific_payload_matches_live(ROOT)
    assert match, detail
    doc = json.loads((ROOT / STAGE4_2_DIAGNOSTIC_RELPATH).read_text(encoding="utf-8"))
    sci = doc["scientific_payload"]
    assert sci["r3_finite_gap"]["pass_deltas"] == [0.0, 0.0, 0.0, 0.0]
    assert sci["r3_finite_gap"]["pass_deltas_exact_zeros"] is True
    assert sci["r2_finish"]["n_defined"] == 1
    assert sci["r2_finish"]["n_absent"] == 19
    assert sci["r2_finish"]["historical_shared_stamp_rejected_by_invariant"] is True
    assert sci["r3_genuine_crossing"]["within_bound"] is True
    assert sci["r5_plan_validation"]["mismatched_set"]["ok"] is False
    assert sci["r5_plan_validation"]["rival_control"]["ok"] is False
    assert sci["r5_plan_validation"]["atomic_rollback_on_two_car_failure"] is True
    assert sci["r6_resolution_gate"]["valid_row_status"] == "PASS"
    assert sci["r6_resolution_gate"]["missing_pit_events_pit_gate"] == "FAIL"
    assert sci["simulator_version"] == "1.0.4"


def test_live_diagnostic_build_has_required_fields():
    doc = build_diagnostic_document(ROOT)
    sci = doc["scientific_payload"]
    for key in (
        "pit_geometry",
        "r1_pit_trace",
        "r2_finish",
        "r3_finite_gap",
        "r3_genuine_crossing",
        "r4_commitments",
        "r5_plan_validation",
        "r6_resolution_gate",
        "simulator_version",
        "interface_version",
        "simulator_config_hash",
    ):
        assert key in sci
    assert "source_snapshot_hash" in doc["generation_metadata"]
    assert len(sci["r1_pit_trace"]) >= 3
    assert sci["simulator_version"] == "1.0.4"
