from __future__ import annotations

import json

import pytest

from f1q.authorization import load_project_config
from f1q.doctor import _ledger, run_doctor
from f1q.errors import LedgerLocked
from f1q.runner import ledger_paths


def _touch_ledger_db(project_root):
    config, _, _ = load_project_config(project_root)
    db, _lock = ledger_paths(project_root, config)
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_bytes(b"")
    return config


def test_ledger_construction_failure_is_controlled(project_root, monkeypatch):
    config = _touch_ledger_db(project_root)

    def boom(self, *args, **kwargs):
        raise RuntimeError("injected construction failure")

    monkeypatch.setattr("f1q.doctor.Ledger.__init__", boom)
    result = _ledger(project_root, config)
    assert result["ok"] is False
    assert result["name"] == "ledger"
    assert result["message"] == "ledger initialization failed"
    assert result["detail"]["error_type"] == "RuntimeError"
    dumped = json.dumps(result)
    assert "UnboundLocalError" not in dumped


def test_ledger_acquire_failure_is_controlled(project_root, monkeypatch):
    config = _touch_ledger_db(project_root)

    def boom(self, *args, **kwargs):
        raise LedgerLocked("injected lock failure")

    monkeypatch.setattr("f1q.doctor.Ledger.acquire", boom)
    result = _ledger(project_root, config)
    assert result["ok"] is False
    assert result["detail"]["error_type"] == "LedgerLocked"
    assert "UnboundLocalError" not in json.dumps(result)


def test_run_doctor_reports_failed_ledger_without_unbound(project_root, monkeypatch):
    _touch_ledger_db(project_root)

    def boom(self, *args, **kwargs):
        raise RuntimeError("injected construction failure")

    monkeypatch.setattr("f1q.doctor.Ledger.__init__", boom)
    payload = run_doctor(project_root)
    assert payload["status"] == "failed"
    ledger_check = next(c for c in payload["checks"] if c["name"] == "ledger")
    assert ledger_check["ok"] is False
    assert ledger_check["detail"]["error_type"] == "RuntimeError"
    assert "UnboundLocalError" not in json.dumps(payload)
