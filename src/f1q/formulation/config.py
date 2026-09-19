"""Load Stage 4 formulation configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from f1q.authorization import load_yaml
from f1q.hashing import sha256_file
from f1q.paths import resolve_within


def load_formulation_config(root: Path) -> tuple[dict[str, Any], str]:
    path = resolve_within(root, "configs/formulation/formulation.v1.yaml", must_exist=True)
    data = load_yaml(path)
    return data, sha256_file(path)
