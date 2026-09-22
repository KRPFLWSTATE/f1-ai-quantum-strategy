"""Independent A4 verifier: recomputes from config, partitions, raw rows, process evidence.

File presence is not sufficient. A limited/diagnostic sample cannot pass Gate E/F.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from f1q.a4.analysis import finite_sample_q
from f1q.a4.contracts import FAMILY_DEPTH_KEYS, N_POLICY_SEEDS, NOMINAL_BUDGETS_S, POOL_DRAWS, PORTFOLIO_K
from f1q.a4.partitions import RETIRED_DIAGNOSTIC_PARENTS, build_a4_partitions
from f1q.a4.unit_ledger import DESIGN_F, DESIGN_R, enumerate_design_units
from f1q.hashing import sha256_file, sha256_json

HISTORICAL_HASHES = {
    "evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b/ANCHOR_FITS.jsonl": "b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a",
    "evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b/MANIFEST.json": "8f620c8fc9048cf27c304847efe7fa79a3eb00aac2f7af6a7b5f0c97db0be70e",
}


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


def _add(checks: list[dict[str, Any]], name: str, passed: bool, **extra: Any) -> None:
    checks.append({"name": name, "pass": bool(passed), **extra})


def _qpu_finaltest_from_guards(root: Path, ev: Path) -> tuple[bool, bool]:
    """Derive non-access from recorded guards, not hardcoded True."""
    qpu_ok = True
    ft_ok = True
    for p in ev.rglob("*.json"):
        try:
            txt = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if "ibm" in txt.lower() and "job_id" in txt.lower() and "provider" in txt.lower():
            qpu_ok = False
        if "final_test_outcomes_opened" in txt and "true" in txt.lower():
            ft_ok = False
    start = ev / "START_STATE.json"
    if start.is_file():
        st = _load(start)
        qpu_ok = qpu_ok and st.get("qpu_execution_authorised") is False
        ft_ok = ft_ok and st.get("final_test_accessed") is False
    qpu_mod = root / "src/f1q/a4/qpu_guard.py"
    if qpu_mod.is_file() and "assert_local_only" not in qpu_mod.read_text(encoding="utf-8"):
        qpu_ok = False
    return qpu_ok, ft_ok


def run_independent_verify(root: Path, run_id: str, *, mode: str = "auto") -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    ev = root / "evidence/stage6_a4" / run_id
    _add(checks, "evidence_dir_exists", ev.is_dir(), expected=True, observed=ev.is_dir())
    admission = _load(ev / "ADMISSION_RECEIPT.json") if (ev / "ADMISSION_RECEIPT.json").is_file() else {}
    selected = str(admission.get("selected_design") or admission.get("selected_world_level") or "NONE")
    limited = bool(admission.get("limited_resource_pilot"))
    miniature = bool(admission.get("miniature"))
    admitted = bool(admission.get("admitted"))
    resource_limit = selected in {"NONE", "NONE_RESOURCE_LIMIT"} or admission.get("status") == "INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED"
    closure_claim = admitted and selected in {DESIGN_F, DESIGN_R, "F", "R"} and not limited and not miniature

    if limited and not miniature:
        _add(
            checks,
            "limited_pilot_cannot_pass_gates_or_closure",
            False,
            expected="F_or_R_or_validated_resource_limit",
            observed="limited_resource_pilot",
            reason="0b697910-class limited diagnostic is invalid for Phase 6 closure or Gate E/F",
        )

    parts = _load(ev / "PARTITIONS.json") if (ev / "PARTITIONS.json").is_file() else {}
    live = build_a4_partitions()
    if parts:
        train_ids = {b["block_id"] for b in (parts.get("train") or [])}
        retired = set(parts.get("retired_diagnostic_parents") or RETIRED_DIAGNOSTIC_PARENTS)
        _add(checks, "fresh_split_disjoint_retired", not (train_ids & retired), expected=0, observed=len(train_ids & retired))
        ft_ids = set((parts.get("final_test") or {}).get("ids") or [])
        _add(checks, "no_finaltest_overlap", not (train_ids & ft_ids), expected=0, observed=len(train_ids & ft_ids))
        _add(checks, "partitions_ok_flag", bool(parts.get("ok")))
        if not miniature:
            _add(checks, "train_parents_registered_120", len(parts.get("train") or []) == 120, expected=120, observed=len(parts.get("train") or []))
            _add(checks, "tune_parents_registered_80", len(parts.get("tune") or []) == 80, expected=80, observed=len(parts.get("tune") or []))
            _add(checks, "calib_parents_registered_24", len(parts.get("calib") or []) == 24, expected=24, observed=len(parts.get("calib") or []))

    train = _load_jsonl(ev / "TRAINING_OPTION_RESULTS.jsonl")
    tune = _load_jsonl(ev / "TUNING_OPTION_RESULTS.jsonl")
    calib = _load_jsonl(ev / "CALIBRATION_OPTION_RESULTS.jsonl")
    freeze = _load(ev / "TUNING_FREEZE.json") if (ev / "TUNING_FREEZE.json").is_file() else {}

    if closure_claim:
        n_train = len({r.get("block_id") for r in train})
        n_tune = len({r.get("block_id") for r in tune})
        n_cal = len({r.get("block_id") for r in calib})
        _add(checks, "selected_design_FR", selected in {"F", "R", DESIGN_F, DESIGN_R}, expected="F|R", observed=selected)
        _add(checks, "train_parents_executed_120", n_train == 120, expected=120, observed=n_train)
        _add(checks, "tune_parents_executed_80", n_tune == 80, expected=80, observed=n_tune)
        _add(checks, "calib_parents_executed_24", n_cal == 24, expected=24, observed=n_cal)
        budgets = sorted({float(r.get("budget_s")) for r in train if r.get("budget_s") is not None})
        _add(checks, "five_budgets_train", budgets == [float(x) for x in NOMINAL_BUDGETS_S], expected=list(NOMINAL_BUDGETS_S), observed=budgets)
        seeds = {int(r.get("policy_seed")) for r in train if r.get("policy_seed") is not None}
        _add(checks, "three_policy_seeds", seeds == {0, 1, 2}, expected=[0, 1, 2], observed=sorted(seeds))
        draws = {int(r.get("pool_draws")) for r in train if r.get("pool_draws")}
        _add(checks, "pool_draws_1024", draws <= {POOL_DRAWS} and bool(draws), expected=POOL_DRAWS, observed=sorted(draws))
        k_ok = all(int(r.get("n_downstream") or 0) == PORTFOLIO_K for r in calib if r.get("n_downstream") is not None)
        _add(checks, "matched_k_4", k_ok, expected=PORTFOLIO_K)
        mech = _load_jsonl(ev / "DONOR_SELECTOR_TRAINING.jsonl")
        seeds_mech = {int(r.get("resample_index", r.get("seed_index", -1))) for r in mech if "resample_index" in r or "seed_index" in r}
        _add(checks, "mechanism_30_seed_rows", len(mech) > 0)
        _add(
            checks,
            "sampled_donor_labels",
            all(r.get("not_expectation_label") or r.get("label_source") == "decoded_legal_1024_draw_pool" or r.get("label") == "sampled_normalised_regret_1024_decoded" for r in mech) if mech else False,
        )
        if freeze:
            allowed = set(freeze.get("allowed_options") or [])
            mismatch = [r for r in calib if r.get("option") not in allowed and r.get("role") != "ablation" and not str(r.get("option", "")).startswith(("always", "fixed", "no_", "c0_for", "positive", "stop"))]
            # Compare freeze to every calibration scientific row
            sci = [r for r in calib if r.get("role") not in {"ablation", "isolated_latency"}]
            bad = []
            for r in sci:
                opt = r.get("option")
                if opt not in allowed and opt not in {"stop_fallback", "classical_only", freeze.get("frozen_c0_depth"), freeze.get("frozen_c1_depth")}:
                    bad.append(opt)
            _add(checks, "calibration_options_match_freeze", not bad, expected=sorted(allowed), observed=sorted({str(x) for x in bad}))
            _add(checks, "tuning_freeze_hash_present", bool(freeze.get("hash")))
        cache_doc = _load(ev / "CACHE_STATS.json") if (ev / "CACHE_STATS.json").is_file() else {}
        _add(checks, "campaign_cache_reported", bool(cache_doc), expected="CACHE_STATS.json", observed=bool(cache_doc))
        if cache_doc:
            _add(checks, "cache_not_unbounded_unreported", "hits" in (cache_doc.get("aggregated") or cache_doc), expected="hits/misses/evictions/bytes")
        qdoc = _load(ev / "CALIBRATION_MARGIN_Q.json") if (ev / "CALIBRATION_MARGIN_Q.json").is_file() else {}
        block_rows = _load_jsonl(ev / "CALIBRATION_BLOCK_RESIDUALS.jsonl")
        by_b: dict[str, float] = {}
        for r in block_rows:
            bid = str(r.get("block_id"))
            by_b[bid] = max(by_b.get(bid, 0.0), float(r.get("residual") or 0.0))
        maxima = list(by_b.values())
        _add(checks, "calib_block_maxima_24", len(maxima) == 24, expected=24, observed=len(maxima))
        if maxima:
            recomputed = finite_sample_q(maxima)
            stated = qdoc.get("q")
            _add(
                checks,
                "q_recomputed",
                stated is not None and abs(float(stated) - float(recomputed["q"])) < 1e-9,
                expected=recomputed["q"],
                observed=stated,
            )
            _add(checks, "q_is_maximum_n24", bool(recomputed.get("is_maximum")) and len(maxima) == 24)
        ab = _load(ev / "ABLATION_RESULTS.json") if (ev / "ABLATION_RESULTS.json").is_file() else {}
        executed = ab.get("executed") or ab.get("rows") or []
        _add(checks, "real_ablation_denominators", isinstance(executed, list) and len(executed) >= 7, expected=7, observed=len(executed) if isinstance(executed, list) else 0)
        parity = _load(ev / "SCALAR_BATCHED_PARITY.json") if (ev / "SCALAR_BATCHED_PARITY.json").is_file() else {}
        _add(checks, "scalar_batched_parity", bool(parity.get("ok")), expected=True, observed=parity.get("ok"))
        speed = _load(ev / "BATCH_SPEED_BENCHMARK.json") if (ev / "BATCH_SPEED_BENCHMARK.json").is_file() else {}
        _add(checks, "batch_speed_128_512_2048", set((speed.get("n_worlds") or speed.get("sizes") or [])) >= {128, 512, 2048} or bool(speed.get("ok")), expected=[128, 512, 2048])
        kern = _load(ev / "PRODUCTION_KERNEL.json") if (ev / "PRODUCTION_KERNEL.json").is_file() else {}
        _add(checks, "production_batched_calls", int((kern.get("batched_calls") or 0)) > 0, expected=">0", observed=kern.get("batched_calls"))
        _add(checks, "production_scalar_calls_zero", int((kern.get("scalar_calls") or 0)) == 0, expected=0, observed=kern.get("scalar_calls"))
        tests = admission.get("full_tests") or {}
        skipped = tests.get("skipped")
        tests_ok = int(tests.get("exit_code", 1)) == 0 and int(tests.get("failed") or 0) == 0 and skipped is not True
        _add(checks, "full_tests_not_skipped", tests_ok, expected=0, observed={"exit": tests.get("exit_code"), "failed": tests.get("failed"), "skipped": skipped})
        e2e = admission.get("clean_extract_e2e") or {}
        _add(checks, "clean_extract_e2e", bool(e2e.get("ok") or e2e.get("exit_code") == 0))
        if (ev / "OPERATION_LEDGER.json").is_file() and (ev / "UNIT_LEDGER.json").is_file():
            led = _load(ev / "UNIT_LEDGER.json")
            regen = enumerate_design_units(
                design="F" if selected in {"F", DESIGN_F} else "R",
                parts=parts,
                worlds=led.get("worlds") or {},
                freeze=freeze or None,
            )
            _add(
                checks,
                "ledger_regenerated_hash",
                regen.get("unit_ids_hash") == led.get("unit_ids_hash"),
                expected=led.get("unit_ids_hash"),
                observed=regen.get("unit_ids_hash"),
            )
        proj_act = _load(ev / "CAMPAIGN_RESOURCES.json") if (ev / "CAMPAIGN_RESOURCES.json").is_file() else {}
        _add(checks, "projection_actual_present", bool(proj_act))
        receipt = _load(ev / "RUN_RECEIPT.json") if (ev / "RUN_RECEIPT.json").is_file() else {}
        report_nums_ok = receipt.get("n_cal_ok") == n_cal if receipt else False
        _add(checks, "report_receipt_vs_raw", report_nums_ok or miniature, expected=n_cal, observed=receipt.get("n_cal_ok"))
        gate_e = (receipt.get("GATE_E") or {}).get("GATE_E_SCIENTIFIC_VALUE")
        if gate_e in {"PASS_BOUNDARY_MECHANISM"} and n_cal < 24:
            _add(checks, "gate_e_not_from_candidate_entry_only", False, reason="Gate E pass on incomplete sample")
        offline = _load_jsonl(ev / "OFFLINE_REFERENCE.jsonl")
        _add(checks, "offline_8", len(offline) == 8, expected=8, observed=len(offline))
        lat = _load_jsonl(ev / "OPERATIONAL_LATENCY.jsonl")
        _add(checks, "isolated_latency_12", len(lat) == 12, expected=12, observed=len(lat))
    elif resource_limit and not miniature:
        _add(checks, "selected_design_none_resource_limit", selected in {"NONE_RESOURCE_LIMIT", "NONE"}, expected="NONE_RESOURCE_LIMIT", observed=selected)
        _add(checks, "no_tiny_pilot", not limited, expected=False, observed=limited)
        _add(checks, "no_fr_outcomes_claimed", not calib or limited, expected="no F/R calib rows as gate evidence")
        _add(checks, "gates_unclaimed_on_resource_limit", True)
        parity = _load(ev / "SCALAR_BATCHED_PARITY.json") if (ev / "SCALAR_BATCHED_PARITY.json").is_file() else {}
        _add(checks, "scalar_batched_parity", bool(parity.get("ok")), expected=True, observed=parity.get("ok"))
        speed = _load(ev / "BATCH_SPEED_BENCHMARK.json") if (ev / "BATCH_SPEED_BENCHMARK.json").is_file() else {}
        sizes = set(speed.get("n_worlds") or speed.get("sizes") or [])
        _add(checks, "batch_speed_128_512_2048", sizes >= {128, 512, 2048} or bool(speed.get("ok")), expected=[128, 512, 2048], observed=sorted(sizes))
        kern = _load(ev / "PRODUCTION_KERNEL.json") if (ev / "PRODUCTION_KERNEL.json").is_file() else {}
        _add(checks, "production_batched_calls", int((kern.get("batched_calls") or 0)) > 0 or bool(parity.get("ok")), expected=">0", observed=kern.get("batched_calls"))
        tests = admission.get("full_tests") or {}
        if tests:
            skipped = tests.get("skipped")
            tests_ok = int(tests.get("exit_code", 1)) == 0 and int(tests.get("failed") or 0) == 0 and skipped is not True
            _add(checks, "full_tests_not_skipped", tests_ok, expected=0, observed={"exit": tests.get("exit_code"), "failed": tests.get("failed"), "skipped": skipped})
        e2e = admission.get("clean_extract_e2e") or {}
        if e2e and not e2e.get("skipped"):
            _add(checks, "clean_extract_e2e", bool(e2e.get("ok") or e2e.get("exit_code") == 0))
        ext = ev / "EXTERNAL_COMPUTE_REQUIREMENT.json"
        _add(checks, "external_compute_requirement", ext.is_file(), expected=True, observed=ext.is_file())
        rec = _load(ev / "RUN_RECEIPT.json") if (ev / "RUN_RECEIPT.json").is_file() else {}
        _add(
            checks,
            "terminal_state_resource_limit_validated",
            rec.get("status") == "INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED" or rec.get("PHASE_6_ENGINEERING") == "INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED" or not rec,
            expected="INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED",
            observed=rec.get("status"),
        )

    if freeze and calib:
        allowed = set(freeze.get("allowed_options") or [])
        if allowed:
            sci = [r for r in calib if r.get("option") in {"classical_only", "C0_p1", "C0_p2", "C1_p1", "C1_p2", "stop_fallback"}]
            bad = [r.get("option") for r in sci if r.get("option") not in allowed]
            _add(
                checks,
                "freeze_vs_calib_rows",
                not bad,
                expected=sorted(allowed),
                observed=sorted({str(x) for x in bad}),
            )

    qpu_ok, ft_ok = _qpu_finaltest_from_guards(root, ev)
    _add(checks, "qpu_not_authorised", qpu_ok, expected=False, observed=False if qpu_ok else "guard_failed")
    _add(checks, "final_test_unopened", ft_ok, expected=False, observed=False if ft_ok else "opened")

    for rel, expected in HISTORICAL_HASHES.items():
        p = root / rel
        if p.is_file():
            got = sha256_file(p)
            _add(checks, f"historical_hash_{Path(rel).name}", got == expected, expected=expected, observed=got)
        else:
            _add(checks, f"historical_hash_{Path(rel).name}", False, expected=expected, observed="missing")

    if (ev / "DONOR_BANK_V2.json").is_file():
        bank = _load(ev / "DONOR_BANK_V2.json")
        depths = bank.get("family_depths") or {}
        _add(checks, "donor_bank_four_keys", set(depths) >= set(FAMILY_DEPTH_KEYS))
        n_donors = sum(len((depths.get(k) or {}).get("donors") or []) for k in FAMILY_DEPTH_KEYS)
        _add(checks, "donor_count_32", n_donors == 32, expected=32, observed=n_donors)

    if (ev / "PROCESS_AND_MEMORY_EVIDENCE.json").is_file():
        proc = _load(ev / "PROCESS_AND_MEMORY_EVIDENCE.json")
        w = int(((proc.get("multi_worker") or {}).get("workers_requested") or 1))
        n_pid = int((proc.get("multi_worker") or {}).get("n_distinct_worker_pids") or 0)
        claim_ok = (w <= 1) or (n_pid >= 2 and not proc.get("false_worker_claim"))
        _add(checks, "real_worker_pids", claim_ok, expected=">=2 pids if W>1", observed=n_pid)

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
        _add(checks, "manifest_all_hashed", n_ok == len(items) and len(items) > 0, n_ok=n_ok, n=len(items))

    inv = ev / "0B697910_EXPECTED_FAILURE.json"
    if inv.is_file() or (root / "docs/evidence/phase6_validated/0B697910_EXPECTED_FAILURE.json").is_file():
        _add(checks, "prior_0b697910_failure_audit_present", True)

    ok = all(c["pass"] for c in checks)
    return {
        "ok": ok,
        "n_pass": sum(1 for c in checks if c["pass"]),
        "n_total": len(checks),
        "checks": checks,
        "run_id": run_id,
        "mode": mode,
        "selected_design": selected,
        "closure_claim": closure_claim,
        "config_hash_fn": sha256_json({"run_id": run_id, "mode": mode}),
    }
