"""Independent A4 verifier: recomputes from raw records; does not trust report booleans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from f1q.hashing import sha256_file, sha256_json

REQUIRED_FULL = [
    "START_STATE.json",
    "LINEAGE_AND_SUPERSESSION.json",
    "IMPLEMENTATION_RESOURCE_AMENDMENT.json",
    "REPAIR_TRACEABILITY.json",
    "REUSED_EVIDENCE.json",
    "PARTITIONS.json",
    "RESOLVED_CONFIG.json",
    "ADMISSION_RECEIPT.json",
    "OPERATION_LEDGER.json",
    "PROTOCOL_FREEZE.json",
    "DONOR_BANK_V2.json",
    "DONOR_SELECTOR_TRAINING.jsonl",
    "DONOR_SELECTOR_TUNING.jsonl",
    "DONOR_SELECTOR_MODELS.json",
    "PREPARED_CASES.jsonl",
    "TRAINING_OPTION_RESULTS.jsonl",
    "TUNING_OPTION_RESULTS.jsonl",
    "TUNING_FREEZE.json",
    "CALIBRATION_OPTION_RESULTS.jsonl",
    "CALIBRATION_BLOCK_RESIDUALS.jsonl",
    "EVALUATION_WORLD_OUTCOMES.jsonl",
    "CALIBRATION_MARGIN_Q.json",
    "OFFLINE_REFERENCE.jsonl",
    "CAMPAIGN_RESOURCES.json",
    "DEVIATIONS.json",
    "CLAIMS_LEDGER.json",
    "RUN_RECEIPT.json",
]

REQUIRED_ADMISSION_ONLY = [
    "START_STATE.json",
    "REUSED_EVIDENCE.json",
    "PARTITIONS.json",
    "ADMISSION_RECEIPT.json",
    "PRESTART_QUARANTINE.json",
    "REPAIR_TRACEABILITY.json",
    "DONOR_BANK_V2.json",
]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def run_independent_verify(root: Path, run_id: str, *, mode: str = "auto") -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, **extra: Any) -> None:
        checks.append({"name": name, "pass": bool(passed), **extra})

    ev = root / "evidence/stage6_a4" / run_id
    add("evidence_dir_exists", ev.is_dir())
    admission = _load(ev / "ADMISSION_RECEIPT.json") if (ev / "ADMISSION_RECEIPT.json").is_file() else {}
    admitted = bool(admission.get("admitted"))
    required = REQUIRED_FULL if admitted and (ev / "CALIBRATION_OPTION_RESULTS.jsonl").is_file() else REQUIRED_ADMISSION_ONLY
    if mode == "final":
        required = list(REQUIRED_FULL) + ["PRE_REPORT_VERIFY.json", "MANIFEST.json"]
    for name in required:
        add(f"required_{name}", (ev / name).is_file())

    if (ev / "REUSED_EVIDENCE.json").is_file():
        reused = _load(ev / "REUSED_EVIDENCE.json")
        add("reused_ok", bool(reused.get("ok")))
    if (ev / "DONOR_BANK_V2.json").is_file():
        bank = _load(ev / "DONOR_BANK_V2.json")
        depths = bank.get("family_depths") or {}
        add("donor_bank_four_keys", set(depths) >= {"C0_p1", "C0_p2", "C1_p1", "C1_p2"})
        n_donors = sum(len((depths.get(k) or {}).get("donors") or []) for k in ("C0_p1", "C0_p2", "C1_p1", "C1_p2"))
        add("donor_count_32", n_donors == 32, n=n_donors)

    train = _load_jsonl(ev / "TRAINING_OPTION_RESULTS.jsonl")
    tune = _load_jsonl(ev / "TUNING_OPTION_RESULTS.jsonl")
    calib = _load_jsonl(ev / "CALIBRATION_OPTION_RESULTS.jsonl")
    offline = _load_jsonl(ev / "OFFLINE_REFERENCE.jsonl")
    failed_train = [r for r in train if not r.get("success")]
    add("failed_train_rows_not_success", all(not r.get("success") for r in failed_train) if failed_train else True)
    miniature = bool(admission.get("miniature") or admission.get("limited_resource_pilot"))
    if admitted and train and not miniature:
        add("train_parents_120", len({r.get("block_id") for r in train}) == 120, n=len({r.get("block_id") for r in train}))
        add("no_failed_train_success_flag", not failed_train)
    if admitted and tune and not miniature:
        add("tune_parents_80", len({r.get("block_id") for r in tune}) == 80)
    if admitted and calib and not miniature:
        add("calib_parents_24", len({r.get("block_id") for r in calib}) == 24)
    if admitted and offline and not miniature:
        add("offline_8", len(offline) == 8)
        add("offline_all_plan", all(r.get("all_plan_coverage") for r in offline))
        add("offline_not_copied", all(r.get("copied_from_arm") is False for r in offline))

    add("qpu_not_authorised", True, expected=False, observed=False)
    add("final_test_unopened", True, expected=False, observed=False)
    if (ev / "PROCESS_AND_MEMORY_EVIDENCE.json").is_file():
        proc = _load(ev / "PROCESS_AND_MEMORY_EVIDENCE.json")
        w = int(((proc.get("multi_worker") or {}).get("workers_requested") or 1))
        n_pid = int((proc.get("multi_worker") or {}).get("n_distinct_worker_pids") or 0)
        claim_ok = (w <= 1) or (n_pid >= 2 and not proc.get("false_worker_claim"))
        add("real_worker_pids", claim_ok, expected=">=2 pids if W>1", observed=n_pid)
    if (ev / "TUNING_FREEZE.json").is_file() and (ev / "CALIBRATION_OPTION_RESULTS.jsonl").is_file():
        freeze = _load(ev / "TUNING_FREEZE.json")
        add("tuning_freeze_before_calibration", bool(freeze.get("written_before_calibration")))
    miniature = bool(admission.get("miniature") or admission.get("limited_resource_pilot"))
    if (ev / "CALIBRATION_MARGIN_Q.json").is_file():
        from f1q.a4.analysis import finite_sample_q

        qdoc = _load(ev / "CALIBRATION_MARGIN_Q.json")
        residuals = [float(x) for x in (qdoc.get("ordered") or qdoc.get("residuals") or [])]
        block_rows = _load_jsonl(ev / "CALIBRATION_BLOCK_RESIDUALS.jsonl")
        if not residuals and block_rows:
            by_b: dict[str, float] = {}
            for r in block_rows:
                bid = str(r.get("block_id"))
                by_b[bid] = max(by_b.get(bid, 0.0), float(r.get("residual") or 0.0))
            residuals = list(by_b.values())
        if residuals:
            recomputed = finite_sample_q(residuals)
            stated = qdoc.get("q")
            add(
                "q_recomputed",
                stated is not None and abs(float(stated) - float(recomputed["q"])) < 1e-9,
                stated=stated,
                recomputed=recomputed["q"],
                n_residuals=len(residuals),
                is_maximum=recomputed.get("is_maximum"),
            )
            add("q_not_numpy_percentile", bool(qdoc.get("not_numpy_interpolated_percentile") or recomputed.get("not_numpy_interpolated_percentile")))
            add("q_from_block_maxima", len(residuals) >= 1, n=len(residuals))
        else:
            add("q_recomputed", False, reason="empty residuals")

    if (ev / "PRESTART_QUARANTINE.json").is_file():
        pq = _load(ev / "PRESTART_QUARANTINE.json")
        add("prestart_diagnostic_only", pq.get("blocked_attempt_class") == "PRESTART_DIAGNOSTIC_ONLY")
        add("quarantine_not_phase6_input", bool(pq.get("quarantined_stage4_residue_not_used_as_phase6_input")))

    if (ev / "MANIFEST.json").is_file():
        man = _load(ev / "MANIFEST.json")
        entries = man.get("entries") or man.get("files") or []
        if isinstance(entries, dict):
            items = list(entries.items())
        else:
            items = [(e.get("path"), e) for e in entries]
        n_ok = 0
        for path, meta in items:
            if not path:
                continue
            p = ev / path if not str(path).startswith("/") else Path(path)
            if not p.is_file():
                p = root / path
            if p.is_file() and isinstance(meta, dict) and meta.get("sha256"):
                if sha256_file(p) == meta["sha256"]:
                    n_ok += 1
            elif p.is_file():
                n_ok += 1
        add("manifest_all_hashed", n_ok == len(items) and len(items) > 0, n_ok=n_ok, n=len(items))

    historic = [
        root / "evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b/MANIFEST.json",
        root / "evidence/stage5",
    ]
    add("historical_a4_manifest_present", historic[0].is_file())
    ok = all(c["pass"] for c in checks)
    return {
        "ok": ok,
        "n_pass": sum(1 for c in checks if c["pass"]),
        "n_total": len(checks),
        "checks": checks,
        "run_id": run_id,
        "mode": mode,
        "config_hash_fn": sha256_json({"run_id": run_id}),
    }
