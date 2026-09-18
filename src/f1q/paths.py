from __future__ import annotations

from pathlib import Path

from f1q.errors import BoundaryError

MARKER = "configs/project.draft.yaml"


def resolve_project_root(explicit: str | Path | None = None) -> Path:
    import os

    if explicit is not None:
        root = Path(explicit).expanduser().resolve()
        _require_marker(root)
        return root
    env = os.environ.get("F1Q_PROJECT_ROOT")
    if env:
        root = Path(env).expanduser().resolve()
        _require_marker(root)
        return root
    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / MARKER).is_file():
            return candidate
    raise BoundaryError(
        "Could not locate project root (missing configs/project.draft.yaml). "
        "Set F1Q_PROJECT_ROOT or run from the f1-ai-quantum-strategy tree."
    )


def _require_marker(root: Path) -> None:
    if not (root / MARKER).is_file():
        raise BoundaryError(f"Not a permitted project root: {root}")


def resolve_within(root: Path, user_path: str | Path, *, must_exist: bool = False) -> Path:
    """Resolve a path and reject traversal or symlink escape from root."""
    root_r = root.resolve()
    raw = Path(user_path)
    if raw.is_absolute():
        candidate = raw
    else:
        candidate = root_r / raw
    resolved = _resolve_no_escape(root_r, candidate)
    if must_exist and not resolved.exists():
        raise BoundaryError(f"Path does not exist inside project: {user_path}")
    return resolved


def _resolve_no_escape(root: Path, candidate: Path) -> Path:
    # Walk components so a symlink at any level cannot leave the root.
    current = root
    parts = candidate.parts
    root_parts = root.parts
    if candidate.is_absolute():
        if parts[: len(root_parts)] != root_parts:
            raise BoundaryError(f"Absolute path escapes project root: {candidate}")
        rel_parts = parts[len(root_parts) :]
    else:
        rel_parts = candidate.parts

    current = root
    for part in rel_parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise BoundaryError("Path traversal '..' is not permitted")
        nxt = current / part
        if nxt.is_symlink():
            target = nxt.resolve()
            if not _is_relative_to(target, root):
                raise BoundaryError(f"Symlink escapes project root: {nxt} -> {target}")
            current = target
        else:
            current = nxt
    resolved = current.resolve() if current.exists() else current
    if current.exists() and not _is_relative_to(resolved, root):
        raise BoundaryError(f"Resolved path escapes project root: {resolved}")
    if not _is_relative_to(current if not current.exists() else resolved, root):
        # For not-yet-created files, check the parent chain stayed inside root.
        probe = current.parent if not current.exists() else resolved
        if not _is_relative_to(probe.resolve(), root):
            raise BoundaryError(f"Path escapes project root: {candidate}")
    return current if not current.exists() else resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve() if path.exists() else path
        path.relative_to(root)
        return True
    except ValueError:
        return False


def safe_relpath(root: Path, path: Path) -> str:
    resolved = path if path.is_absolute() else (root / path)
    try:
        return str(resolved.resolve().relative_to(root.resolve()))
    except ValueError as exc:
        raise BoundaryError(f"Path is not inside project: {path}") from exc
