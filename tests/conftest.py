from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

REAL_ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    dest = tmp_path / "proj"
    dest.mkdir()
    shutil.copytree(REAL_ROOT / "configs", dest / "configs")
    shutil.copytree(REAL_ROOT / "docs" / "protocol", dest / "docs" / "protocol")
    if (REAL_ROOT / "fixtures").is_dir():
        shutil.copytree(REAL_ROOT / "fixtures", dest / "fixtures")
    else:
        shutil.copytree(REAL_ROOT / "configs" / "fixtures", dest / "fixtures")
    for name in ("pyproject.toml", "requirements.lock"):
        src = REAL_ROOT / name
        if src.exists():
            shutil.copy2(src, dest / name)
    if not (dest / "requirements.lock").exists():
        (dest / "requirements.lock").write_text("# generated during Stage 1 install\n", encoding="utf-8")
    (dest / "src" / "f1q").mkdir(parents=True)
    (dest / "src" / "f1q" / "placeholder.py").write_text("# snapshot include\n", encoding="utf-8")
    (dest / "tests").mkdir()
    (dest / "evidence" / "bootstrap").mkdir(parents=True)
    return dest


@pytest.fixture
def project_root(project: Path) -> Path:
    return project
