"""Deterministic Stage 4.2 review-package builder and verifier."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from f1q.formulation.versions import INNER_MANIFEST_ALGORITHM_VERSION, REVIEW_PACKAGE_FORMAT_VERSION
from f1q.hashing import sha256_file

EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "review",
    "private",
}
EXCLUDE_FILE_SUFFIXES = {".pyc", ".pyo", ".DS_Store"}
EXCLUDE_FILE_NAMES = {".DS_Store", ".env", "credentials.json", "ibm_token", "secrets.yaml"}


def _is_excluded(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & EXCLUDE_DIR_NAMES:
        return True
    if rel.name in EXCLUDE_FILE_NAMES:
        return True
    if rel.suffix in EXCLUDE_FILE_SUFFIXES:
        return True
    # Mutable ledgers / databases
    if rel.suffix in {".sqlite", ".db", ".sqlite3"}:
        return True
    if "evidence/ledger" in str(rel).replace("\\", "/"):
        return True
    return False


def default_allowlist(root: Path) -> list[str]:
    """Explicit deterministic allowlist of relative POSIX paths."""
    patterns = [
        "AGENTS.md",
        "PROJECT_STATUS.md",
        "README.md",
        "pyproject.toml",
        "requirements.lock",
        "requirements.txt",
        "configs",
        "docs",
        "src/f1q",
        "tests",
        "schemas",
        ".cursor/rules",
    ]
    # Prior receipts required for preservation claims
    receipt_globs = [
        "evidence/formulation/receipts/e8b87881-74a6-46c7-b48e-6b2496a5d586.json",
        "evidence/formulation/receipts/e8b87881-74a6-46c7-b48e-6b2496a5d586.md",
        "evidence/formulation/receipts/1c5b0748-5406-4933-8e41-4f943f4296c7.json",
        "evidence/formulation/receipts/1c5b0748-5406-4933-8e41-4f943f4296c7.md",
        "evidence/formulation/receipts/c4d0a199-9cea-4214-83ab-97964f2bf1ac.json",
        "evidence/formulation/receipts/c4d0a199-9cea-4214-83ab-97964f2bf1ac.md",
        "evidence/formulation/receipts/e85ee977-8a35-40c1-b690-02724dea3228.json",
        "evidence/formulation/receipts/e85ee977-8a35-40c1-b690-02724dea3228.md",
        "evidence/formulation/snapshots/e85ee977-8a35-40c1-b690-02724dea3228.json",
        "evidence/formulation/artifacts/e85ee977-8a35-40c1-b690-02724dea3228/formulation.development_matrix/development_matrix_summary.json",
        "evidence/formulation/artifacts/e85ee977-8a35-40c1-b690-02724dea3228/formulation.evaluator_separation_panel/evaluator_panel.json",
        "evidence/formulation/artifacts/e85ee977-8a35-40c1-b690-02724dea3228/formulation.qubo_ising_gate/qubo_gate_summary.json",
        "evidence/formulation/artifacts/e85ee977-8a35-40c1-b690-02724dea3228/formulation.independent_references/references_summary.json",
        "evidence/formulation/artifacts/e85ee977-8a35-40c1-b690-02724dea3228/formulation.pre_repair_erratum/pre_repair_reproduction.json",
        "evidence/formulation/artifacts/e85ee977-8a35-40c1-b690-02724dea3228/formulation.source_restore/source_snapshot.json",
    ]
    members: list[str] = []
    for pat in patterns:
        path = root / pat
        if path.is_file():
            members.append(pat)
        elif path.is_dir():
            for fp in sorted(path.rglob("*")):
                if not fp.is_file():
                    continue
                rel = fp.relative_to(root)
                if _is_excluded(rel):
                    continue
                if fp.is_symlink():
                    raise ValueError(f"symlink not allowed in review package: {rel}")
                members.append(rel.as_posix())
    for rel in receipt_globs:
        if (root / rel).is_file():
            members.append(rel)
    # Deduplicate preserving order
    seen: set[str] = set()
    out: list[str] = []
    for m in members:
        if m in seen:
            continue
        if "\\" in m or m.startswith("/") or ".." in m.split("/"):
            raise ValueError(f"unsafe path rejected: {m}")
        # case-collision check deferred to freeze
        seen.add(m)
        out.append(m)
    return sorted(out, key=lambda s: s.encode("utf-8"))


def canonical_row(path: str, data: bytes) -> dict[str, Any]:
    return {
        "path": path,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def serialize_rows(rows: list[dict[str, Any]]) -> bytes:
    ordered = sorted(rows, key=lambda r: r["path"].encode("utf-8"))
    return json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_aggregate_sha256(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(serialize_rows(rows)).hexdigest()


def build_staging_tree(root: Path, staging: Path, members: list[str] | None = None) -> list[dict[str, Any]]:
    members = members or default_allowlist(root)
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    lower_map: dict[str, str] = {}
    for rel in members:
        src = root / rel
        if not src.is_file():
            raise FileNotFoundError(rel)
        if src.is_symlink():
            raise ValueError(f"symlink rejected: {rel}")
        key = rel.casefold()
        if key in lower_map and lower_map[key] != rel:
            raise ValueError(f"case-collision: {lower_map[key]} vs {rel}")
        lower_map[key] = rel
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        data = dest.read_bytes()
        rows.append(canonical_row(rel, data))
    return rows


def write_inner_manifest(staging: Path, rows: list[dict[str, Any]], *, reviewed_commit: str) -> dict[str, Any]:
    aggregate = canonical_aggregate_sha256(rows)
    manifest = {
        "format_version": REVIEW_PACKAGE_FORMAT_VERSION,
        "algorithm_version": INNER_MANIFEST_ALGORITHM_VERSION,
        "algorithm": (
            "For every member except MANIFEST.sha256.json, row="
            '{"path":posix,"bytes":int,"sha256":hex}; sort by UTF-8 path; '
            "serialize JSON ensure_ascii=false sort_keys=true separators=(',',':') no trailing newline; "
            "canonical_aggregate_sha256=SHA256(serialized_row_array)"
        ),
        "member_count": len(rows),
        "canonical_aggregate_sha256": aggregate,
        "reviewed_source_commit": reviewed_commit,
        "members": sorted(rows, key=lambda r: r["path"].encode("utf-8")),
    }
    path = staging / "MANIFEST.sha256.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def freeze_zip(staging: Path, zip_path: Path) -> dict[str, Any]:
    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(staging.rglob("*")):
            if not fp.is_file():
                continue
            rel = fp.relative_to(staging).as_posix()
            info = zipfile.ZipInfo(rel)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, fp.read_bytes())
    digest = sha256_file(zip_path)
    return {"path": str(zip_path), "bytes": zip_path.stat().st_size, "sha256": digest}


def verify_zip_and_extract(zip_path: Path, extract_dir: Path) -> dict[str, Any]:
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    failures: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        if any("\\" in n or n.startswith("/") or ".." in n.split("/") for n in names):
            failures.append("unsafe_member_path")
        # Reject duplicate normalized names
        norm = [n.replace("\\", "/") for n in names]
        if len(norm) != len(set(norm)):
            failures.append("duplicate_member")
        zf.extractall(extract_dir)
    manifest_path = extract_dir / "MANIFEST.sha256.json"
    if not manifest_path.is_file():
        failures.append("missing_inner_manifest")
        return {"ok": False, "failures": failures}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    members = [n for n in sorted(p.relative_to(extract_dir).as_posix() for p in extract_dir.rglob("*") if p.is_file()) if n != "MANIFEST.sha256.json"]
    expected_members = {m["path"] for m in manifest["members"]}
    actual_members = set(members)
    if expected_members != actual_members:
        failures.append(f"member_set_mismatch missing={sorted(expected_members-actual_members)[:5]} extra={sorted(actual_members-expected_members)[:5]}")
    rows = []
    for m in manifest["members"]:
        fp = extract_dir / m["path"]
        data = fp.read_bytes()
        row = canonical_row(m["path"], data)
        rows.append(row)
        if row["bytes"] != m["bytes"] or row["sha256"] != m["sha256"]:
            failures.append(f"member_hash_or_bytes_mismatch:{m['path']}")
    aggregate = canonical_aggregate_sha256(rows)
    if aggregate != manifest.get("canonical_aggregate_sha256"):
        failures.append("aggregate_mismatch")
    return {
        "ok": not failures,
        "failures": failures,
        "member_count": len(rows),
        "canonical_aggregate_sha256": aggregate,
        "manifest_aggregate": manifest.get("canonical_aggregate_sha256"),
        "algorithm_version": manifest.get("algorithm_version"),
        "extract_dir": str(extract_dir),
    }


def clean_extract_import_audit(extract_dir: Path, python_exe: str | None = None) -> dict[str, Any]:
    """Prove f1q imports resolve only inside the extracted tree."""
    python_exe = python_exe or sys.executable
    src = extract_dir / "src"
    script = r"""
import importlib, json, os, sys
root = sys.argv[1]
src = os.path.join(root, "src")
# Clear any preloaded f1q
for k in list(sys.modules):
    if k == "f1q" or k.startswith("f1q."):
        del sys.modules[k]
# Keep third-party site-packages (may live under the project .venv path).
# Strip only checkout/editable project source trees, never the extracted src.
filtered = []
for p in sys.path:
    norm = os.path.realpath(p).replace("\\\\", "/")
    if norm == os.path.realpath(src):
        continue
    if norm.rstrip("/").endswith("/src") and "f1-ai-quantum-strategy" in norm and "/.venv/" not in norm:
        continue
    if "/site-packages" in norm or "/lib-dynload" in norm or "python3." in norm or norm.endswith(".zip"):
        filtered.append(p)
        continue
    if "f1-ai-quantum-strategy" in norm and "/.venv/" not in norm:
        continue
    filtered.append(p)
sys.path = [src] + filtered
import f1q
mods = {}
ok = True
failures = []
# Import key transitive modules
for name in [
    "f1q", "f1q.errors", "f1q.hashing", "f1q.paths", "f1q.formulation",
    "f1q.formulation.actions", "f1q.formulation.compiler", "f1q.formulation.evaluator",
    "f1q.simulator", "f1q.simulator.interface",
]:
    mod = importlib.import_module(name)
    path = getattr(mod, "__file__", None)
    mods[name] = path
    if not path or not os.path.realpath(path).startswith(os.path.realpath(src)):
        ok = False
        failures.append({"module": name, "file": path})
print(json.dumps({"ok": ok, "failures": failures, "modules": mods, "f1q_file": f1q.__file__, "sys_path_head": sys.path[:6]}))
"""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    # Use -I for isolated mode
    proc = subprocess.run(
        [python_exe, "-I", "-c", script, str(extract_dir)],
        capture_output=True,
        text=True,
        env=env,
        cwd=tempfile.gettempdir(),
    )
    if proc.returncode != 0:
        return {
            "ok": False,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return {"ok": False, "parse_error": str(exc), "stdout": proc.stdout, "stderr": proc.stderr}
    payload["returncode"] = proc.returncode
    payload["command"] = [python_exe, "-I", "-c", "<audit>", str(extract_dir)]
    return payload


def write_external_sidecar(
    *,
    sidecar_path: Path,
    zip_path: Path,
    zip_meta: dict[str, Any],
    inner_manifest: dict[str, Any],
    reviewed_commit: str,
    generation_command: str,
) -> str:
    sidecar = {
        "format_version": REVIEW_PACKAGE_FORMAT_VERSION,
        "zip_name": zip_path.name,
        "zip_bytes": zip_meta["bytes"],
        "zip_sha256": zip_meta["sha256"],
        "inner_manifest_algorithm_version": INNER_MANIFEST_ALGORITHM_VERSION,
        "inner_member_count": inner_manifest["member_count"],
        "inner_canonical_aggregate_sha256": inner_manifest["canonical_aggregate_sha256"],
        "reviewed_source_commit": reviewed_commit,
        "generation_command": generation_command,
        "generation_version": REVIEW_PACKAGE_FORMAT_VERSION,
    }
    sidecar_path.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(sidecar_path.read_bytes()).hexdigest()


def build_and_verify_review_package(
    root: Path,
    *,
    reviewed_commit: str,
    zip_name: str = "STAGE_4_2_REVIEW.zip",
) -> dict[str, Any]:
    staging = root / "review" / "_stage4_2_staging"
    zip_path = root / "review" / zip_name
    rows = build_staging_tree(root, staging)
    # Optional prepackage report inside staging with unambiguous name
    pre = staging / "docs" / "STAGE_4_2_PREPACKAGE_REPORT.md"
    if not pre.parent.exists():
        pre.parent.mkdir(parents=True, exist_ok=True)
    pre.write_text(
        "# Stage 4.2 prepackage report\n\nInternal staging snapshot before ZIP freeze. Not the final external report.\n",
        encoding="utf-8",
    )
    rows = [canonical_row(p.relative_to(staging).as_posix(), p.read_bytes()) for p in staging.rglob("*") if p.is_file() and p.name != "MANIFEST.sha256.json"]
    inner = write_inner_manifest(staging, rows, reviewed_commit=reviewed_commit)
    zip_meta = freeze_zip(staging, zip_path)
    sidecar_path = root / "review" / "STAGE_4_2_REVIEW.manifest.json"
    sidecar_sha = write_external_sidecar(
        sidecar_path=sidecar_path,
        zip_path=zip_path,
        zip_meta=zip_meta,
        inner_manifest=inner,
        reviewed_commit=reviewed_commit,
        generation_command="python -m f1q.formulation.review_package",
    )
    # Re-check frozen ZIP hash immediately
    recheck = sha256_file(zip_path)
    extract_dir = Path(tempfile.mkdtemp(prefix="f1q_stage42_extract_"))
    verify = verify_zip_and_extract(zip_path, extract_dir)
    origin = clean_extract_import_audit(extract_dir)
    return {
        "zip": zip_meta,
        "zip_sha256_recheck": recheck,
        "zip_hash_stable": recheck == zip_meta["sha256"],
        "sidecar_path": str(sidecar_path.relative_to(root)),
        "sidecar_sha256": sidecar_sha,
        "inner_manifest": {
            "member_count": inner["member_count"],
            "canonical_aggregate_sha256": inner["canonical_aggregate_sha256"],
            "algorithm_version": inner["algorithm_version"],
        },
        "verify": verify,
        "clean_extract": origin,
        "extract_dir": str(extract_dir),
        "reviewed_source_commit": reviewed_commit,
    }


if __name__ == "__main__":
    from f1q.snapshot import git_state

    root = Path(__file__).resolve().parents[3]
    commit, _ = git_state(root)
    result = build_and_verify_review_package(root, reviewed_commit=commit or "UNKNOWN")
    print(json.dumps({k: result[k] for k in result if k != "inner_manifest"}, indent=2, sort_keys=True))
