"""Fail-closed engineering isolation.

Engineering and miniature callers may prepare only identities on the fixture
manifest. Protected scientific parent, seed, and specification fingerprints are
rejected before any simulator object is constructed. ``miniature=true`` does
not bypass the check. Report writers cannot target protected historical paths.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator

_ENGINEERING: ContextVar[bool] = ContextVar("f1q_engineering_context", default=False)

ISOLATED_AMENDMENT_ID = "design_r_isolated_preflight_20261025"
ISOLATED_RUN_ID = "ee3945ba-ee39-48e5-a81b-85b981806f2a"
ABORTED_BEFORE_CHECKS_RUN_ID = "9a32a40a-1790-4f5b-a955-ce093b44cddc"
HISTORICAL_SIX_HOUR_RUN_ID = "ed37296f-55c5-44e5-8ffd-77410d4789de"

EXPOSED_MINIATURE_RUNS = (
    "cdd21ec6-9d95-48a5-806b-64fd7e296434",
    "eeb03bdd-4fdf-4e1e-baf6-590b54c11d4a",
)

PROTECTED_RELATIVE = (
    "docs/PHASE_6_COMPLETION_REPORT.md",
    "docs/PHASE_6_VALIDATED_CLOSURE_REPORT.md",
    "docs/evidence/stage4_2/stage3_3_regression_diagnostic.json",
)

PROTECTED_PREFIXES = (
    "evidence/stage5/",
    "evidence/stage6/bd83cb22",
    "evidence/stage6_corrected/",
    "evidence/stage6_a2_residual/",
    "evidence/a3/",
    "evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b/",
    "evidence/stage6_a4/3de109c7-30d9-4cb0-827f-dbd82c4c509d/",
    "evidence/stage6_a4/0b697910-e8a2-474b-bc77-bc69ebb8e9c3/",
    "evidence/stage6_a4/fc5f0e00-d9e0-4f89-9eea-498461094969/",
    "evidence/stage6_a4/ed37296f-55c5-44e5-8ffd-77410d4789de/",
    "evidence/stage6_a4/cdd21ec6-9d95-48a5-806b-64fd7e296434/",
    "evidence/stage6_a4/eeb03bdd-4fdf-4e1e-baf6-590b54c11d4a/",
    "evidence/stage6_a4/engineering_byproducts/",
    "evidence/stage6_a4/9a32a40a-1790-4f5b-a955-ce093b44cddc/",
    "evidence/performance_feasibility/",
    "evidence/performance_feasibility_followup/",
)

FIXTURE_PREFIXES = (
    "engfix.",
    "engperf.",
    "a4.admit.",
    "a4.t.",
    "a4.test.",
    "a4.int.",
    "a4.adv.",
    "a4.variety.",
    "a4.parity.",
    "a4.speed.",
    "a3.smoke.",
    "a3.adv.",
)

EXACT_FIXTURE_IDS = ("a4.train.x", "x", "a4.finaltest.x")

PRESERVED_RUN_IDS = {
    "09806343-f940-4f33-9e0f-eb2855d0714b",
    "3de109c7-30d9-4cb0-827f-dbd82c4c509d",
    "0b697910-e8a2-474b-bc77-bc69ebb8e9c3",
    "fc5f0e00-d9e0-4f89-9eea-498461094969",
    HISTORICAL_SIX_HOUR_RUN_ID,
    ABORTED_BEFORE_CHECKS_RUN_ID,
    *EXPOSED_MINIATURE_RUNS,
}


class IsolationError(RuntimeError):
    """Raised before simulator evaluation or before a protected write."""


def push_engineering(active: bool = True):
    return _ENGINEERING.set(bool(active))


def pop_engineering(token) -> None:
    _ENGINEERING.reset(token)


def engineering_context_active() -> bool:
    if _ENGINEERING.get():
        return True
    if os.environ.get("F1Q_ENGINEERING_ONLY") == "1":
        return True
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return False


def package_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def spec_fingerprint(*, family_id: str, seed: int, index: int, regime: str) -> str:
    """Fingerprint of the specification factors. The block-id string is excluded.

    A renamed identifier that keeps the same family, seed, index, and regime
    collides with this fingerprint.
    """
    return _sha256_json(
        {
            "family_id": str(family_id),
            "seed": int(seed),
            "index": int(index),
            "regime": str(regime),
        }
    )


def _load_json(name: str) -> dict[str, Any]:
    path = package_root() / "configs" / name
    if not path.is_file():
        raise IsolationError(f"required isolation record missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_exposed() -> dict[str, Any]:
    return _load_json("design_r_exposed_identities.json")


def load_registry() -> dict[str, Any]:
    return _load_json("design_r_isolated_registry.json")


def fixture_allows(block_id: str) -> bool:
    if block_id in EXACT_FIXTURE_IDS:
        return True
    return any(str(block_id).startswith(prefix) for prefix in FIXTURE_PREFIXES)


def _protected_ids_seeds_specs() -> tuple[set[str], set[int], set[str]]:
    data = load_exposed()
    ids = set(data.get("block_ids") or [])
    seeds = {int(s) for s in data.get("seeds") or []}
    specs = set(data.get("spec_fingerprints") or [])
    return ids, seeds, specs


def matches_protected(*, block_id: str, seed: int | None, spec_fp: str | None) -> str | None:
    """Return a reason string when the identity is protected, else None."""
    if "finaltest" in str(block_id) or str(block_id).startswith(("shift.", "test.")) or ".shift." in str(block_id):
        return "sealed_partition_id"
    ids, seeds, specs = _protected_ids_seeds_specs()
    if block_id in ids:
        return "protected_parent_id"
    if seed is not None and int(seed) in seeds:
        return "protected_seed"
    if spec_fp and spec_fp in specs:
        return "protected_spec_fingerprint"
    return None


def assert_can_prepare(
    *,
    family_id: str,
    block_id: str,
    regime: str,
    partition: str,
    index: int,
    seed: int,
    miniature: bool = False,
) -> None:
    """Reject a protected or non-fixture identity before the simulator starts.

    ``miniature`` is accepted so callers cannot omit the check. It is not a bypass.
    """
    del miniature  # explicit: miniature=true does not skip this function
    if str(partition) in {"finaltest", "final_test", "shift", "test"}:
        raise IsolationError(f"refusing sealed partition {partition} for {block_id}")
    spec_fp = spec_fingerprint(family_id=family_id, seed=int(seed), index=int(index), regime=regime)
    reason = matches_protected(block_id=str(block_id), seed=int(seed), spec_fp=spec_fp)
    if reason:
        raise IsolationError(f"protected scientific identity rejected before simulator evaluation: {reason}: {block_id}")
    engineering = engineering_context_active() or str(partition) in {"development", "setup_fixture"} or fixture_allows(str(block_id))
    if engineering_context_active() or os.environ.get("F1Q_ENGINEERING_ONLY") == "1":
        if not fixture_allows(str(block_id)):
            raise IsolationError(f"engineering identity is not on the fixture manifest: {block_id}")
        return
    if engineering and fixture_allows(str(block_id)):
        return
    registry = load_registry()
    allowed = set(registry.get("block_ids") or [])
    if str(block_id) not in allowed:
        raise IsolationError(f"parent is not on the frozen isolated scientific registry: {block_id}")
    expected = (registry.get("seed_by_id") or {}).get(str(block_id))
    if expected is None or int(expected) != int(seed):
        raise IsolationError(f"scientific seed does not match the frozen registry: {block_id}")


def assert_can_evaluate(*, spec: dict[str, Any] | None, miniature: bool = False) -> None:
    """Evaluation entry point. Uses the spec identity and does not start a simulator."""
    del miniature
    if not spec:
        raise IsolationError("refusing evaluation without a spec identity")
    block_id = str(spec.get("block_id") or "")
    family_id = str(spec.get("family_id") or "")
    regime = str(spec.get("regime") or spec.get("race_regime") or "")
    seed = spec.get("seed", spec.get("block_seed"))
    index = spec.get("index", 0)
    partition = str(spec.get("namespace") or spec.get("partition") or "")
    if partition.startswith("a4."):
        partition = partition.split(".", 1)[-1]
    if not block_id:
        raise IsolationError("refusing evaluation without a block id")
    if seed is None or not family_id:
        if matches_protected(block_id=block_id, seed=int(seed) if seed is not None else None, spec_fp=None):
            raise IsolationError(f"protected identity rejected before simulator evaluation: {block_id}")
        if engineering_context_active() and not fixture_allows(block_id):
            raise IsolationError(f"engineering evaluation is not on the fixture manifest: {block_id}")
        if not engineering_context_active() and not fixture_allows(block_id):
            allowed = set(load_registry().get("block_ids") or [])
            if block_id not in allowed:
                raise IsolationError(f"evaluation parent is not on the frozen registry: {block_id}")
        return
    assert_can_prepare(
        family_id=family_id,
        block_id=block_id,
        regime=regime or "SC",
        partition=partition if partition in {"development", "setup_fixture", "train", "tune", "calib", "anchor"} else "development",
        index=int(index or 0),
        seed=int(seed),
        miniature=False,
    )


def make_engineering_root(source: Path, dest: Path) -> Path:
    """A writable project root with no scientific registry and no historical reports."""
    import shutil

    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / "configs", dest / "configs", dirs_exist_ok=True)
    (dest / "docs").mkdir(exist_ok=True)
    prior = dest / "evidence" / "stage6_a4" / "09806343-f940-4f33-9e0f-eb2855d0714b"
    src_prior = source / "evidence" / "stage6_a4" / "09806343-f940-4f33-9e0f-eb2855d0714b"
    prior.mkdir(parents=True, exist_ok=True)
    for name in (
        "MANIFEST.json",
        "ANCHOR_FITS.jsonl",
        "NATIVE_NOISE_CORRECTION.json",
        "A3_INVALIDATION.json",
        "PARTITIONS.json",
        "PROTOCOL_AMENDMENT_A4.json",
    ):
        if (src_prior / name).is_file():
            shutil.copy2(src_prior / name, prior / name)
    for name in ("pyproject.toml", "AGENTS.md", "PROJECT_STATUS.md"):
        if (source / name).is_file():
            shutil.copy2(source / name, dest / name)
    return dest


def synthetic_miniature_partitions() -> dict[str, Any]:
    """Two blocks per split on the engineering manifest. Not the registered corpus."""
    from f1q.generator.config import cartesian_family_ids

    families = cartesian_family_ids()
    salt = "engineering.fixture.miniature.v1.not-scientific"

    def blocks(kind: str, n: int) -> list[dict[str, Any]]:
        rows = []
        for i in range(n):
            fam = families[i % len(families)]
            block_id = f"engfix.{kind}.{fam}.{i:04d}"
            seed = int(hashlib.sha256(f"{salt}:{block_id}".encode()).hexdigest()[:16], 16) % (2**31 - 1)
            rows.append(
                {
                    "block_id": block_id,
                    "partition": kind,
                    "family_id": fam,
                    "index": i,
                    "seed": seed,
                    "regimes": ["SC", "VSC"],
                    "parent_block_independent": True,
                    "engineering_fixture": True,
                    "not_a_registered_scientific_parent": True,
                }
            )
        return rows

    train, tune, calib = blocks("train", 2), blocks("tune", 2), blocks("calib", 2)
    return {
        "salt": salt,
        "namespace": "engfix",
        "engineering_fixture": True,
        "not_the_registered_scientific_split": True,
        "train": train,
        "tune": tune,
        "calib": calib,
        "anchors": [],
        "final_test": {"ids": [], "outcomes_materialised": False, "outcomes_opened": False, "n_blocks": 0},
        "ok": True,
        "planned": {"training": 2, "tuning": 2, "calibration": 2},
    }


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _project_relative(path: Path) -> str | None:
    resolved = path.resolve() if path.exists() else path.absolute()
    for candidate in [resolved, *resolved.parents]:
        if (candidate / "configs" / "project.draft.yaml").is_file():
            try:
                return str(resolved.relative_to(candidate.resolve()))
            except ValueError:
                return None
    return None


def is_protected_relative(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    if rel in PROTECTED_RELATIVE:
        return True
    return any(rel.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def guard_output_path(path: Path) -> None:
    """Refuse writes that land on protected historical files or the protected root."""
    protected_env = os.environ.get("F1Q_PROTECTED_ROOT")
    if protected_env:
        prot = Path(protected_env).resolve()
        target = path.resolve() if path.exists() else (path.parent.resolve() / path.name if path.parent.exists() else path.absolute())
        if _under(target, prot):
            raise IsolationError(f"refusing to write inside the protected scientific root: {target}")
    rel = _project_relative(path)
    if rel and is_protected_relative(rel):
        raise IsolationError(f"refusing to write a protected historical path: {rel}")


def child_env(root: Path, base: dict[str, str] | None = None) -> dict[str, str]:
    """Pass an explicit project root into a child. cwd is not sufficient."""
    env = dict(base if base is not None else os.environ)
    env["F1Q_PROJECT_ROOT"] = str(Path(root).resolve())
    env["F1Q_REQUIRE_EXPLICIT_ROOT"] = "1"
    if os.environ.get("F1Q_PROTECTED_ROOT"):
        env["F1Q_PROTECTED_ROOT"] = os.environ["F1Q_PROTECTED_ROOT"]
    if engineering_context_active():
        env["F1Q_ENGINEERING_ONLY"] = "1"
    return env


def refuse_engineering_on_scientific_root(root: Path) -> None:
    """Miniatures must not open a run directory on the real scientific checkout."""
    if not engineering_context_active() and os.environ.get("F1Q_ENGINEERING_ONLY") != "1":
        return
    protected = os.environ.get("F1Q_PROTECTED_ROOT")
    if protected and Path(root).resolve() == Path(protected).resolve():
        raise IsolationError("engineering/miniature run refused on the protected scientific root")
    marker = Path(root) / "evidence" / "stage6_a4" / HISTORICAL_SIX_HOUR_RUN_ID
    if marker.is_dir():
        raise IsolationError("engineering/miniature run refused on a tree that holds the scientific six-hour registry")


def _stream_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_protected(root: Path) -> dict[str, str]:
    """SHA-256 of protected files. Missing optional trees are recorded as absent."""
    root = Path(root)
    out: dict[str, str] = {}
    for rel in PROTECTED_RELATIVE:
        path = root / rel
        out[rel] = _stream_sha256(path) if path.is_file() else "ABSENT"
    for prefix in PROTECTED_PREFIXES:
        base = root / prefix.rstrip("/")
        if not base.exists():
            out[prefix] = "ABSENT"
            continue
        if base.is_file():
            out[prefix] = _stream_sha256(base)
            continue
        digest = hashlib.sha256()
        files = sorted(p for p in base.rglob("*") if p.is_file())
        digest.update(str(len(files)).encode())
        for path in files:
            rel = str(path.relative_to(root))
            digest.update(rel.encode())
            digest.update(bytes.fromhex(_stream_sha256(path)))
        out[prefix] = digest.hexdigest()
    kernel = root / "src/f1q/simulator/compiled_kernel.py"
    if kernel.is_file():
        out["src/f1q/simulator/compiled_kernel.py"] = hashlib.sha256(kernel.read_bytes()).hexdigest()
    parts = root / "src/f1q/a4/partitions.py"
    if parts.is_file():
        out["src/f1q/a4/partitions.py"] = hashlib.sha256(parts.read_bytes()).hexdigest()
    return out


def iter_identity_files(root: Path) -> Iterator[Path]:
    bases = [
        root / "evidence" / "stage6_a4" / run for run in EXPOSED_MINIATURE_RUNS
    ]
    bases.append(root / "evidence" / "stage6_a4" / "engineering_byproducts")
    for base in bases:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                yield path


def extract_exposed_identities(root: Path) -> dict[str, Any]:
    """Union of parent, spec, and seed identities in the miniature outputs and world chunks."""
    from f1q.a4.partitions import build_a4_partitions

    parts = build_a4_partitions()
    known = {row["block_id"]: row for row in parts["anchors"] + parts["train"] + parts["tune"] + parts["calib"]}
    for bid in (parts.get("final_test") or {}).get("ids") or []:
        known.setdefault(bid, {"block_id": bid, "seed": None, "family_id": "", "index": None})
    found_ids: set[str] = set()
    hashes: set[str] = set()
    seeds: set[int] = set()
    sources: list[str] = []
    for path in iter_identity_files(root):
        rel = str(path.relative_to(root))
        text = path.name
        if path.suffix in {".json", ".jsonl", ".md", ".txt"} or path.name.endswith(".json.gz"):
            try:
                if path.name.endswith(".gz"):
                    import gzip

                    text = gzip.open(path, "rt", encoding="utf-8", errors="ignore").read()
                else:
                    text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                text = path.name
        else:
            text = path.name
        for bid in known:
            if bid in text or bid in path.name:
                found_ids.add(bid)
                sources.append(rel)
        for token in ("prepared_case_hash", "spec_hash", "checkpoint_hash"):
            if token in text and path.suffix != ".gz":
                pass
        if path.suffix == ".jsonl" or path.name.endswith(".json"):
            try:
                blob = text
                if path.suffix == ".jsonl":
                    rows = [json.loads(line) for line in blob.splitlines() if line.strip()]
                else:
                    parsed = json.loads(blob)
                    rows = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                rows = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                bid = row.get("block_id")
                if isinstance(bid, str):
                    found_ids.add(bid)
                for key in ("seed", "policy_seed", "block_seed"):
                    if key in row and isinstance(row[key], int):
                        seeds.add(int(row[key]))
                for key in ("prepared_case_hash", "spec_hash", "checkpoint_hash"):
                    if isinstance(row.get(key), str):
                        hashes.add(str(row[key]))
    retired = list(parts.get("retired_diagnostic_parents") or [])
    for bid in retired:
        found_ids.add(bid)
    for bid, row in known.items():
        if bid in found_ids and row.get("seed") is not None:
            seeds.add(int(row["seed"]))
    for bid in (parts.get("final_test") or {}).get("ids") or []:
        found_ids.add(bid)
    for row in parts["anchors"]:
        found_ids.add(row["block_id"])
        seeds.add(int(row["seed"]))
    spec_fps: set[str] = set()
    for bid in found_ids:
        row = known.get(bid)
        if not row or row.get("seed") is None or not row.get("family_id"):
            continue
        for regime in ("SC", "VSC"):
            spec_fps.add(
                spec_fingerprint(
                    family_id=row["family_id"],
                    seed=int(row["seed"]),
                    index=int(row.get("index") or 0),
                    regime=regime,
                )
            )
    try:
        from f1q.generator.config import load_generator_config
        from f1q.generator.splits import build_split_plan

        cfg, _, _ = load_generator_config(root)
        plan = build_split_plan(cfg, test_blocks=80)
        for rec in plan["records"]:
            if rec["partition"] in {"test", "shift"}:
                found_ids.add(rec["block_id"])
                if rec.get("identity_digest"):
                    hashes.add(str(rec["identity_digest"]))
    except Exception as exc:
        hashes.add(f"shift_plan_unavailable:{type(exc).__name__}")
    miniature_parents = sorted(
        bid for bid in found_ids if bid.startswith("a4.v2.") and any(kind in bid for kind in (".train.", ".tune.", ".calib."))
        and "green_pit_high.tyre_near_linear.traffic_dense" in bid
        and bid.rsplit(".", 1)[-1] in {"0000", "0001"}
    )
    return {
        "schema": "design_r_exposed_identities.v1",
        "status": "RETIRED_TO_DEVELOPMENT_HISTORY_NOT_SCIENTIFIC",
        "registered_scientific_parents_executed_by_intended_campaign": 0,
        "distinct_registered_parent_ids_exposed_in_tests": miniature_parents,
        "n_distinct_registered_parents_exposed_in_tests": len(miniature_parents),
        "block_ids": sorted(found_ids),
        "seeds": sorted(seeds),
        "spec_fingerprints": sorted(spec_fps),
        "content_hashes": sorted(hashes),
        "source_run_ids": list(EXPOSED_MINIATURE_RUNS),
        "world_chunk_dir": "evidence/stage6_a4/engineering_byproducts/worlds",
        "evidence_preserved": True,
        "deleted": False,
        "n_source_files_scanned": len(sources),
    }


def scientific_seal_audit(root: Path) -> dict[str, Any]:
    """Read-only audit of the real tree. Does not treat the exposed split as untouched."""
    root = Path(root)
    defects: list[str] = []
    for run in EXPOSED_MINIATURE_RUNS:
        if not (root / "evidence" / "stage6_a4" / run).is_dir():
            defects.append(f"missing_exposed_run:{run}")
    worlds = root / "evidence" / "stage6_a4" / "engineering_byproducts" / "worlds"
    if not worlds.is_dir():
        defects.append("missing_world_chunks")
    historical = root / "evidence" / "stage6_a4" / HISTORICAL_SIX_HOUR_RUN_ID / "ADMISSION_DECISION.json"
    if not historical.is_file():
        defects.append("missing_historical_admission")
    else:
        decision = json.loads(historical.read_text(encoding="utf-8"))
        if decision.get("admitted") is not False:
            defects.append("historical_admission_rewritten")
        if int(decision.get("registered_scientific_parents_executed") or 0) != 0:
            defects.append("historical_parent_count_rewritten")
    registry_path = root / "configs" / "design_r_isolated_registry.json"
    new_hits: list[str] = []
    if registry_path.is_file():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        needles = set(registry.get("block_ids") or [])
        evidence = root / "evidence"
        if evidence.is_dir():
            for path in evidence.rglob("*"):
                if not path.is_file():
                    continue
                name = path.name
                if not any(tok in name for tok in ("TRAINING_OPTION", "TUNING_OPTION", "CALIBRATION_OPTION", "EVALUATION_WORLD")):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for bid in needles:
                    if bid in text:
                        new_hits.append(str(path.relative_to(root)))
                        break
    if new_hits:
        defects.append("new_split_pre_admission_exposure")
    exposed_path = root / "configs" / "design_r_exposed_identities.json"
    n_exposed = None
    if exposed_path.is_file():
        n_exposed = int(json.loads(exposed_path.read_text(encoding="utf-8")).get("n_distinct_registered_parents_exposed_in_tests") or 0)
        if n_exposed != 6:
            defects.append("exposure_ledger_count")
    else:
        defects.append("exposure_ledger_missing")
    return {
        "ok": not defects,
        "defects": defects,
        "exposed_miniature_runs_preserved": all((root / "evidence" / "stage6_a4" / run).is_dir() for run in EXPOSED_MINIATURE_RUNS),
        "new_split_outcome_files": new_hits,
        "n_distinct_registered_parents_exposed_in_tests": n_exposed,
        "registered_scientific_parents_executed_by_intended_campaign": 0,
        "old_split_called_untouched": False,
        "final_test_outcomes_read": False,
    }
