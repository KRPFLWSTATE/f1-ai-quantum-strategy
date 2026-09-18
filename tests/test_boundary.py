from __future__ import annotations

from pathlib import Path

import pytest

from f1q.errors import BoundaryError
from f1q.paths import resolve_within


def test_path_traversal_rejected(project_root, tmp_path):
    with pytest.raises(BoundaryError, match="traversal"):
        resolve_within(project_root, "../../etc/passwd")


def test_symlink_escape_rejected(project_root, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "secret.txt"
    target.write_text("not-in-project", encoding="utf-8")
    link = project_root / "escape-link"
    link.symlink_to(outside)
    with pytest.raises(BoundaryError, match="escapes"):
        resolve_within(project_root, "escape-link/secret.txt")
    assert target.read_text(encoding="utf-8") == "not-in-project"


def test_relative_inside_ok(project_root):
    path = resolve_within(project_root, "configs/project.draft.yaml", must_exist=True)
    assert path.is_file()
    assert path.resolve().is_relative_to(project_root.resolve())
