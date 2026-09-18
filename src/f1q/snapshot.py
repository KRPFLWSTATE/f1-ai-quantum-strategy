from __future__ import annotations

import subprocess
from pathlib import Path

from f1q.hashing import canonical_json, sha256_file, sha256_json
from f1q.paths import resolve_within

SNAPSHOT_GLOBS = (
    "src/**/*.py",
    "configs/**/*",
    "pyproject.toml",
    "requirements.lock",
    "tests/**/*.py",
    "docs/protocol/SOURCE_HASH.md",
)


def git_state(root: Path) -> tuple[str | None, bool]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = None
    dirty = True
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        dirty = bool(status.strip()) or commit is None
    except (subprocess.CalledProcessError, FileNotFoundError):
        dirty = True
    return commit, dirty


def take_source_snapshot(root: Path) -> dict:
    files: list[dict[str, str]] = []
    seen: set[str] = set()
    for pattern in SNAPSHOT_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = str(path.relative_to(root))
            if rel in seen:
                continue
            if any(part.startswith(".") and part not in {".cursor"} for part in path.parts):
                continue
            seen.add(rel)
            files.append({"path": rel, "sha256": sha256_file(path)})
    payload = {
        "kind": "source_snapshot",
        "excludes": ["evidence/var", ".venv", "__pycache__", ".git", "credentials"],
        "files": files,
    }
    payload["hash"] = sha256_json({"files": files})
    return payload


def write_snapshot(root: Path, run_id: str, snapshot: dict) -> Path:
    out = resolve_within(root, Path("evidence") / "bootstrap" / "snapshots" / f"{run_id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    from f1q.hashing import atomic_write_bytes

    atomic_write_bytes(out, canonical_json(snapshot) + b"\n")
    return out
