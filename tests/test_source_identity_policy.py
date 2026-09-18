from __future__ import annotations

from f1q.hashing import sha256_json
from f1q.snapshot import DOCUMENTATION_GLOBS, SNAPSHOT_GLOBS, take_source_snapshot


def test_documentation_edit_does_not_change_primary_hash(project_root):
    before = take_source_snapshot(project_root)
    (project_root / "PROJECT_STATUS.md").write_text("# status changed\n", encoding="utf-8")
    (project_root / "docs").mkdir(exist_ok=True)
    (project_root / "docs" / "NOTE.md").write_text("narrative only\n", encoding="utf-8")
    after = take_source_snapshot(project_root)
    assert before["hash"] == after["hash"]
    assert after["identity_policy"]["documentation_does_not_invalidate_primary_hash"] is True
    assert after["documentation_hash"] != before["documentation_hash"]


def test_code_edit_changes_primary_hash(project_root):
    before = take_source_snapshot(project_root)
    src = project_root / "src" / "f1q" / "placeholder.py"
    src.write_text("# code identity change\n", encoding="utf-8")
    after = take_source_snapshot(project_root)
    assert after["hash"] != before["hash"]
    assert after["hash"] == sha256_json({"files": after["files"]})


def test_identity_policy_globs_are_explicit():
    assert "src/**/*.py" in SNAPSHOT_GLOBS
    assert "docs/**/*.md" in DOCUMENTATION_GLOBS
    assert "docs/**/*.md" not in SNAPSHOT_GLOBS
    assert "PROJECT_STATUS.md" in DOCUMENTATION_GLOBS
