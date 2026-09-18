from __future__ import annotations

import pytest

from f1q.authorization import authorize_plan, fingerprints_match, reject_unsupported_mode
from f1q.errors import AuthorizationError, UnsupportedModeError
from f1q.runner import resume_run, run_bootstrap
from f1q.schemas import parse_project_config

from conftest import load_yaml


class NS:
    def __init__(self, **kwargs):
        self.__dict__.update({"plan": "bootstrap", "mode": None, "provider": None, "backend": None, "hardware": False})
        self.__dict__.update(kwargs)


def test_hardware_flag_rejected():
    with pytest.raises(UnsupportedModeError, match="no provider submission path"):
        reject_unsupported_mode(NS(hardware=True))


def test_ibm_backend_rejected():
    with pytest.raises(UnsupportedModeError):
        reject_unsupported_mode(NS(backend="ibm"))


def test_campaign_plan_not_authorized(project_root):
    data = load_yaml(project_root / "configs" / "project.draft.yaml")
    config = parse_project_config(data)
    with pytest.raises(AuthorizationError, match="not in authorization"):
        authorize_plan(config, "campaign")


def test_changed_fingerprint_blocks_resume(project_root):
    first = run_bootstrap(project_root)
    src = project_root / "src" / "f1q" / "placeholder.py"
    src.write_text("# changed snapshot\n", encoding="utf-8")
    with pytest.raises(AuthorizationError, match="source snapshot fingerprint"):
        resume_run(project_root, first["run_id"])


def test_fingerprint_helper():
    with pytest.raises(AuthorizationError, match="configuration fingerprint"):
        fingerprints_match(
            expected_config_hash="a",
            actual_config_hash="b",
            expected_source_hash="s",
            actual_source_hash="s",
        )
