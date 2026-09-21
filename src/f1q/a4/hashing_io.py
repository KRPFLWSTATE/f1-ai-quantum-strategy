"""Atomic JSON/JSONL helpers shared by A4 campaign code."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from f1q.hashing import atomic_write_text


def write_json(path: Path, obj: Any) -> str:
    return atomic_write_text(path, json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
