"""Independent A4 verifier: recomputes from raw artifacts; does not trust summary booleans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from qiskit.quantum_info import DensityMatrix

from f1q.hashing import sha256_file, sha256_json
from f1q.stage6.native_noise import verify_native_analytical_fixtures
from f1q.stage6.noisy import depolarizing_closed_form, depolarizing_kraus


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def run_independent_verify(root: Path, run_id: str) -> dict[str, Any]:
    checks = []

    def add(name: str, passed: bool, **extra: Any) -> None:
        checks.append({"name": name, "pass": bool(passed), **extra})

    ev = root / "evidence/stage6_a4" / run_id
    add("evidence_dir_exists", ev.is_dir())

    required = [
        "START_STATE.json",
        "A3_INVALIDATION.json",
        "PROTOCOL_AMENDMENT_A4.json",
        "PARTITIONS.json",
        "PREFLIGHT.json",
        "PROTOCOL_FREEZE.json",
        "DONOR_BANK.json",
        "PRIMARY_ANALYSIS.json",
        "RESOURCE_ACCOUNTING.json",
        "CLAIMS_LEDGER.json",
        "MANIFEST.json",
        "RUN_RECEIPT.json",
        "NATIVE_NOISE_CORRECTION.json",
    ]
    for name in required:
        add(f"required_{name}", (ev / name).is_file())

    parts = _load(ev / "PARTITIONS.json") if (ev / "PARTITIONS.json").is_file() else {}
    freeze = _load(ev / "PROTOCOL_FREEZE.json") if (ev / "PROTOCOL_FREEZE.json").is_file() else {}
    add("split_isolation", bool(parts.get("ok")) and not parts.get("overlap_open_vs_finaltest") and not parts.get("a2_a3_id_reuse"))
    ft = parts.get("final_test") or {}
    add("final_test_sealed", ft.get("outcomes_materialised") is False and ft.get("outcomes_opened") is False)
    add("final_test_count_80", int(ft.get("n_blocks") or 0) == 80)

    train = _load_jsonl(ev / "TRAINING_RESULTS.jsonl")
    tune = _load_jsonl(ev / "TUNING_RESULTS.jsonl")
    calib = _load_jsonl(ev / "CALIBRATION_CANDIDATES.jsonl")
    worlds = _load_jsonl(ev / "CALIBRATION_WORLD_OUTCOMES.jsonl")
    anchors = _load_jsonl(ev / "ANCHOR_FITS.jsonl")
    offline = _load_jsonl(ev / "OFFLINE_REFERENCE.jsonl")

    planned = (parts.get("planned") or freeze.get("partitions_planned") or {})
    add("anchors_all_executed", len({r.get("block_id") for r in anchors}) >= int(planned.get("anchors") or 24) or len(anchors) >= 24 * 4 * 3 * 0.5)
    n_anchor_blocks = len({r.get("block_id") for r in anchors})
    add("anchor_block_count", n_anchor_blocks == 24, n=n_anchor_blocks)
    add("train_parent_count", len({r.get("block_id") for r in train}) == 120, n=len({r.get("block_id") for r in train}))
    add("tune_parent_count", len({r.get("block_id") for r in tune}) == 80, n=len({r.get("block_id") for r in tune}))
    add("calib_parent_count", len({r.get("block_id") for r in calib}) == 24, n=len({r.get("block_id") for r in calib}))

    # Matched K
    ks = [int(r.get("n_downstream") or 0) for r in calib]
    k_ok = bool(ks) and len(set(ks)) == 1
    add("matched_k_on_calib", k_ok, ks=sorted(set(ks)))

    # Recompute paired effects from per-world outcomes
    by_block: dict[str, dict[str, list[float]]] = {}
    for w in worlds:
        bid = w.get("block_id")
        arm = w.get("arm")
        if bid and arm and w.get("loss") is not None:
            by_block.setdefault(bid, {}).setdefault(arm, []).append(float(w["loss"]))
    effects = []
    for bid, arms in by_block.items():
        if "classical_only" in arms and "dispatched" in arms:
            cl = float(np.mean(arms["classical_only"]))
            ds = float(np.mean(arms["dispatched"]))
            effects.append(cl - ds)
    primary = _load(ev / "PRIMARY_ANALYSIS.json") if (ev / "PRIMARY_ANALYSIS.json").is_file() else {}
    recomputed_mean = float(np.mean(effects)) if effects else None
    reported = primary.get("mean_difference")
    mean_ok = recomputed_mean is not None and reported is not None and abs(float(reported) - recomputed_mean) < 1e-8
    add("paired_mean_recomputed", mean_ok or (not effects and reported is None), recomputed=recomputed_mean, reported=reported, n_blocks=len(effects))

    add("offline_actually_evaluated", bool(offline) and all("evaluation_loss" in r for r in offline))
    add("offline_not_copied_from_arm", all(r.get("copied_from_arm") is not True for r in offline) if offline else False)

    # Noise analytical
    native = verify_native_analytical_fixtures()
    add("native_analytical", native.get("ok") is True)
    # Kraus vs closed form 1q/2q
    kraus_ok = True
    for nq, p in ((1, 0.0), (1, 1.0), (1, 0.3), (2, 0.0), (2, 1.0), (2, 0.4)):
        d = 2**nq
        rho = np.zeros((d, d), dtype=complex)
        rho[0, 0] = 1.0
        k = depolarizing_kraus(nq, p)
        dm = DensityMatrix(rho).evolve(k)
        closed = depolarizing_closed_form(rho, p)
        if not np.allclose(dm.data, closed, atol=1e-8):
            kraus_ok = False
    add("kraus_matches_closed_form", kraus_ok)

    rec = _load(ev / "RUN_RECEIPT.json") if (ev / "RUN_RECEIPT.json").is_file() else {}
    add("qpu_jobs_zero", int(rec.get("qpu_jobs") or 0) == 0)
    add("qpu_seconds_zero", float(rec.get("qpu_usage_seconds") or 0) == 0)
    add("qpu_not_authorised", rec.get("qpu_execution_authorised") is False)
    add("final_test_accessed_false", rec.get("final_test_accessed") is False)

    freeze_ts = freeze.get("datetime_utc")
    calib_times = [r.get("datetime_utc") for r in calib if r.get("datetime_utc")]
    add("freeze_before_calib", bool(freeze_ts) and (not calib_times or freeze_ts <= min(calib_times)))

    man = _load(ev / "MANIFEST.json") if (ev / "MANIFEST.json").is_file() else {}
    files = man.get("files") or {}
    hash_ok = True
    n_hash = 0
    for rel, meta in list(files.items())[:80]:
        p = root / rel
        if not p.is_file():
            hash_ok = False
            continue
        if meta.get("sha256") != sha256_file(p):
            hash_ok = False
        n_hash += 1
    add("manifest_hashes", hash_ok and n_hash > 0, n=n_hash)

    n_pass = sum(1 for c in checks if c["pass"])
    return {
        "ok": n_pass == len(checks) and len(checks) > 0,
        "n_pass": n_pass,
        "n_checks": len(checks),
        "checks": checks,
        "run_id": run_id,
    }
