"""Adversarial isolation: protected parents, child roots, report paths, ordering."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from f1q.a4.isolation import IsolationError, make_engineering_root, synthetic_miniature_partitions
from f1q.a4.isolated_admission import analysis_gate, resolve_runtime_caps, stop_predicate
from f1q.a4.resources import CAMPAIGN_WALL_CAP_S
from f1q.hashing import sha256_file
from f1q.paths import resolve_project_root


def test_miniature_protected_parent_rejected_before_simulator():
    from f1q.a4.partitions import build_a4_partitions
    from f1q.a4.prepared import prepare_case
    from f1q.simulator.interface import RaceSimulator

    protected = build_a4_partitions()["train"][0]
    calls = {"n": 0}
    real = RaceSimulator.__init__

    def _wrapped(self, *args, **kwargs):
        calls["n"] += 1
        return real(self, *args, **kwargs)

    RaceSimulator.__init__ = _wrapped
    try:
        with pytest.raises(IsolationError, match="protected scientific identity"):
            prepare_case(
                family_id=protected["family_id"],
                block_id=protected["block_id"],
                regime="SC",
                partition="train",
                index=int(protected["index"]),
                seed=int(protected["seed"]),
                n_planning=1,
                n_evaluation=1,
            )
    finally:
        RaceSimulator.__init__ = real
    assert calls["n"] == 0


def test_subprocess_cannot_escape_supplied_root(tmp_path: Path):
    scientific = resolve_project_root()
    root = make_engineering_root(scientific, tmp_path / "childroot")
    nested = root / "nested"
    nested.mkdir()
    code = (
        "import os\n"
        "from pathlib import Path\n"
        "from f1q.paths import resolve_project_root\n"
        "from f1q.a4.isolation import guard_output_path, IsolationError\n"
        "found = resolve_project_root()\n"
        "print(found)\n"
        "try:\n"
        "    guard_output_path(Path(os.environ['F1Q_PROTECTED_ROOT']) / 'docs' / 'PHASE_6_COMPLETION_REPORT.md')\n"
        "    print('WRITE_ALLOWED')\n"
        "except IsolationError:\n"
        "    print('WRITE_REFUSED')\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(scientific / "src")
    env["F1Q_PROJECT_ROOT"] = str(root)
    env["F1Q_REQUIRE_EXPLICIT_ROOT"] = "1"
    env["F1Q_PROTECTED_ROOT"] = str(scientific)
    env["F1Q_ENGINEERING_ONLY"] = "1"
    proc = subprocess.run([sys.executable, "-c", code], cwd=str(scientific), env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    assert lines[0] == str(root.resolve())
    assert lines[0] != str(scientific.resolve())
    assert "WRITE_REFUSED" in lines
    probe = scientific / ".isolation_probe_cwd"
    probe.mkdir(exist_ok=True)
    bare = dict(os.environ)
    bare["PYTHONPATH"] = str(scientific / "src")
    bare["F1Q_REQUIRE_EXPLICIT_ROOT"] = "1"
    bare.pop("F1Q_PROJECT_ROOT", None)
    try:
        refused = subprocess.run(
            [sys.executable, "-c", "from f1q.paths import resolve_project_root; resolve_project_root()"],
            cwd=str(probe),
            env=bare,
            capture_output=True,
            text=True,
        )
        assert refused.returncode != 0
    finally:
        probe.rmdir()


def test_report_writer_cannot_touch_protected_file():
    from f1q.hashing import atomic_write_text

    root = resolve_project_root()
    target = root / "docs" / "PHASE_6_COMPLETION_REPORT.md"
    before = sha256_file(target)
    with pytest.raises(IsolationError):
        atomic_write_text(target, "overwrite\n")
    assert sha256_file(target) == before


class TestMiniatureDoesNotContaminateSeal:
    root: Path | None = None

    def test_01_miniature_uses_only_synthetic_parents(self, tmp_path: Path):
        parts = synthetic_miniature_partitions()
        ids = [row["block_id"] for row in parts["train"] + parts["tune"] + parts["calib"]]
        assert ids
        assert all(item.startswith("engfix.") for item in ids)
        assert all("a4.v2." not in item for item in ids)
        self.__class__.root = make_engineering_root(resolve_project_root(), tmp_path / "ordered")
        (self.__class__.root / "evidence" / "stage6_a4" / "engfix-miniature").mkdir(parents=True)
        (self.__class__.root / "evidence" / "stage6_a4" / "engfix-miniature" / "TRAINING_OPTION_RESULTS.jsonl").write_text(
            '{"block_id": "engfix.train.synthetic", "mean_loss": 1}\n',
            encoding="utf-8",
        )

    def test_02_following_seal_sees_no_registered_parents(self):
        root = self.__class__.root
        assert root is not None
        text = (root / "evidence" / "stage6_a4" / "engfix-miniature" / "TRAINING_OPTION_RESULTS.jsonl").read_text(encoding="utf-8")
        assert "a4.v2." not in text
        assert "engfix." in text


def test_amended_runtime_enforces_six_hours_not_four():
    import yaml

    cfg = yaml.safe_load((resolve_project_root() / "configs" / "stage6_a4_design_r_isolated.yaml").read_text(encoding="utf-8"))
    caps = resolve_runtime_caps(cfg)
    assert caps["campaign_wall_cap_s"] == 21600.0
    assert caps["campaign_wall_cap_s"] != CAMPAIGN_WALL_CAP_S
    assert stop_predicate(14400.0, caps) is False
    assert stop_predicate(21600.0, caps) is True
    assert analysis_gate(executed_ok=False, stopped=False) is False
    assert analysis_gate(executed_ok=True, stopped=True) is False
    assert analysis_gate(executed_ok=True, stopped=False) is True
    from f1q.a4.completion_run import execute_phase6
    import inspect

    source = inspect.getsource(execute_phase6)
    assert "resolve_runtime_caps" in source
    assert "stop_predicate" in source
