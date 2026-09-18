from __future__ import annotations

import copy

import pytest

from f1q.errors import RejectionError
from f1q.generator.config import load_generator_config, sorted_families
from f1q.generator.spec import generate_block
from f1q.generator.validate import assert_structural, structural_errors


def _valid_spec(project_root):
    config, _, _ = load_generator_config(project_root)
    family = sorted_families(config)[0]
    block = generate_block(
        config, family, namespace="development", block_index=0, declared_unit_seed=11
    )
    return copy.deepcopy(block["episodes"][0])


def test_generated_specs_are_structurally_valid(project_root):
    spec = _valid_spec(project_root)
    assert structural_errors(spec) == []
    assert spec["weather"] == "dry"
    assert spec["compound_obligation"]["not_an_invented_fia_rule"] is True
    assert spec["team_service"]["stacking_policy"] == "delay_cost_not_prohibition"


def test_duplicate_positions_rejected(project_root):
    spec = _valid_spec(project_root)
    spec["field"][1]["classified_position"] = spec["field"][0]["classified_position"]
    codes = [code for code, _ in structural_errors(spec)]
    assert "DUPLICATE_POSITION" in codes


def test_wet_excluded(project_root):
    spec = _valid_spec(project_root)
    spec["weather"] = "wet"
    codes = [code for code, _ in structural_errors(spec)]
    assert "WET_EXCLUDED" in codes


def test_negative_tyre_age_rejected(project_root):
    spec = _valid_spec(project_root)
    spec["field"][0]["tyre_age_laps"] = -1
    codes = [code for code, _ in structural_errors(spec)]
    assert "NEGATIVE_TYRE_AGE" in codes


def test_horizon_inconsistent_rejected(project_root):
    spec = _valid_spec(project_root)
    spec["initialization"]["remaining_laps"] += 5
    codes = [code for code, _ in structural_errors(spec)]
    assert "HORIZON_INCONSISTENT" in codes


def test_scientific_partition_rejected_on_preview_spec(project_root):
    spec = _valid_spec(project_root)
    spec["partition"] = "training"
    codes = [code for code, _ in structural_errors(spec)]
    assert "DEVELOPMENT_IN_SCIENTIFIC_SPLIT" in codes
    with pytest.raises(RejectionError):
        assert_structural(spec)


def test_tyre_set_must_include_mounted(project_root):
    spec = _valid_spec(project_root)
    spec["field"][0]["mounted_set_id"] = "not-in-inventory"
    codes = [code for code, _ in structural_errors(spec)]
    assert "TYRE_SET_INCONSISTENT" in codes
