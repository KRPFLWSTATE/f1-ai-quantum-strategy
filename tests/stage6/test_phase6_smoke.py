"""Inexpensive Stage 6 smoke tests (not historical campaign)."""

from __future__ import annotations

from f1q.stage6.config import default_phase6_config
from f1q.stage6.splits import build_calibration_splits
from f1q.stage6.novelty import build_novelty_comparison
from f1q.stage6.sizing import mechanism_precision_targets_predeclared


def test_calibration_splits_isolated():
    s = build_calibration_splits(source_hash="dossier", phase5_source_hash="phase5")
    assert s["audit"]["ok"]
    assert s["audit"]["calibration_blocks"] == 24
    assert s["audit"]["cases_total"] == 48
    assert s["audit"]["final_test_accessed"] is False
    assert not s["audit"]["overlap_with_phase5_train_tune"]
    assert all(b["block_id"].startswith("phase6.calib.") for b in s["calibration"])


def test_precision_targets_predeclared():
    cfg = default_phase6_config()
    t = mechanism_precision_targets_predeclared(cfg)
    assert t["declared_before_calibration_outcomes"] is True
    assert t["operational_endpoints"]["status"] == "NOT_ELIGIBLE"


def test_gate_e_zero_headroom_scope():
    n = build_novelty_comparison(pilot_headroom="ZERO", causal_operational_ready=False)
    assert n["GATE_E_SCIENTIFIC_VALUE"] == "PASS_FOR_DEFINED_SCOPE"
    assert n["no_absolute_novelty_claims"] is True
    assert n["contribution_assessment"]["surviving_research_question"]
