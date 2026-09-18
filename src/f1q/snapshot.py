from __future__ import annotations

import subprocess
from pathlib import Path

from f1q.hashing import canonical_json, sha256_file, sha256_json
from f1q.paths import resolve_within

# Primary/code identity. Documentation-only edits must not change this hash.
SNAPSHOT_GLOBS = (
    "src/**/*.py",
    "configs/**/*",
    "pyproject.toml",
    "requirements.lock",
    "tests/**/*.py",
    "docs/protocol/SOURCE_HASH.md",
)

# Separate documentation identity. Changing these files does not invalidate
# scientific/code identity recorded in snapshot["hash"].
DOCUMENTATION_GLOBS = (
    "AGENTS.md",
    "PROJECT_STATUS.md",
    "README.md",
    "NOTICE",
    "docs/**/*.md",
    "docs/**/*.txt",
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


def _collect_files(root: Path, globs: tuple[str, ...]) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    seen: set[str] = set()
    for pattern in globs:
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
    return files


def take_source_snapshot(root: Path) -> dict:
    files = _collect_files(root, SNAPSHOT_GLOBS)
    documentation_files = _collect_files(root, DOCUMENTATION_GLOBS)
    pdf = root / "docs" / "protocol" / "F1_AI_Quantum_Research_Dossier_v3_1.pdf"
    payload = {
        "kind": "source_snapshot",
        "excludes": ["evidence/var", ".venv", "__pycache__", ".git", "credentials"],
        "files": files,
        "identity_policy": {
            "version": "1.1.0",
            "primary_hash_globs": list(SNAPSHOT_GLOBS),
            "documentation_globs": list(DOCUMENTATION_GLOBS),
            "documentation_does_not_invalidate_primary_hash": True,
            "note": (
                "snapshot['hash'] is the code/config/tests/lock/SOURCE_HASH identity. "
                "Narrative documentation uses documentation_hash. Git HEAD is recorded "
                "separately and does not identify a dirty tree by itself."
            ),
        },
        "documentation_files": documentation_files,
        "documentation_hash": sha256_json({"files": documentation_files}),
        "protocol_pdf_sha256": sha256_file(pdf) if pdf.is_file() else None,
    }
    payload["hash"] = sha256_json({"files": files})
    return payload


def write_snapshot(root: Path, run_id: str, snapshot: dict, *, evidence_subdir: str = "bootstrap") -> Path:
    out = resolve_within(root, Path("evidence") / evidence_subdir / "snapshots" / f"{run_id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    from f1q.hashing import atomic_write_bytes

    atomic_write_bytes(out, canonical_json(snapshot) + b"\n")
    return out
