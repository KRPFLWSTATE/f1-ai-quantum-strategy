from __future__ import annotations

import copy
import math

import pytest

from f1q.errors import SchemaError
from f1q.schemas import parse_checkpoint, parse_project_config

from conftest import load_json, load_yaml


def test_valid_draft_config_parses(project_root):
    data = load_yaml(project_root / "configs" / "project.draft.yaml")
    config = parse_project_config(data)
    assert config.protocol_frozen is False
    assert config.hardware_execution_enabled is False


def test_invalid_type_rejected(project_root):
    data = load_yaml(project_root / "configs" / "project.draft.yaml")
    data["active_stage"] = "one"
    with pytest.raises(SchemaError):
        parse_project_config(data)


def test_negative_budget_rejected(project_root):
    data = load_yaml(project_root / "configs" / "project.draft.yaml")
    data["qpu"]["reported_balance_seconds"] = -1
    with pytest.raises(SchemaError):
        parse_project_config(data)


def test_unsafe_path_rejected(project_root):
    data = load_yaml(project_root / "configs" / "project.draft.yaml")
    data["paths"]["ledger_relpath"] = "../outside/ledger.sqlite"
    with pytest.raises(SchemaError):
        parse_project_config(data)


def test_unsupported_mode_rejected(project_root):
    data = load_yaml(project_root / "configs" / "project.draft.yaml")
    data["mode"] = "ibm"
    with pytest.raises(SchemaError):
        parse_project_config(data)


def test_future_only_state_rejected(project_root):
    data = load_json(project_root / "fixtures" / "fictional_checkpoint.json")
    data["future_sc_duration"] = {"value": 12, "unit": "s", "source": "x", "availability_time": "later", "status": "known"}
    with pytest.raises(SchemaError, match="not permitted in decision input"):
        parse_checkpoint(data)


def test_nan_rejected(project_root):
    data = load_json(project_root / "fixtures" / "fictional_checkpoint.json")
    data["race_time_s"] = copy.deepcopy(data["race_time_s"])
    data["race_time_s"]["value"] = math.nan
    with pytest.raises(SchemaError):
        parse_checkpoint(data)
