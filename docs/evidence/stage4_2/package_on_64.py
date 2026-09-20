"""Non-blocking Stage 4.2 packager. Polls 41c28597 matrix files; freezes only at 64/64 + completed receipt."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path("/Users/kawinperera/f1-ai-quantum-strategy")
RUN = "41c28597-0ce0-428f-8230-ba2ca973c5b7"
PRIOR_E85 = "e85ee977-8a35-40c1-b690-02724dea3228"
MATRIX = ROOT / f"evidence/formulation/artifacts/{RUN}/formulation.development_matrix"
RECEIPT = ROOT / f"evidence/formulation/receipts/{RUN}.json"
SUMMARY = MATRIX / "development_matrix_summary.json"
LOCK = ROOT / "docs/evidence/stage4_2/package_on_64.lock"
LOG = ROOT / "docs/evidence/stage4_2/package_on_64.log"
DONE = ROOT / "docs/evidence/stage4_2/package_on_64.done"

sys.path.insert(0, str(ROOT / "src"))


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line, flush=True)


def count_records() -> int:
    return len(list(MATRIX.glob("*.record.json")))


def ready() -> tuple[bool, str]:
    n = count_records()
    if n < 64:
        return False, f"records={n}/64"
    if not RECEIPT.is_file():
        return False, f"records={n}/64 no_receipt"
    rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
    status = rec.get("status")
    if status != "completed":
        return False, f"records={n}/64 receipt={status}"
    if not SUMMARY.is_file():
        return False, f"records={n}/64 no_summary"
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    completed = int(summary.get("completed") or 0)
    planned = int(summary.get("planned") or 0)
    ok = bool(summary.get("ok"))
    if not (completed == 64 and planned == 64 and ok):
        return False, (
            f"records={n}/64 summary_completed={completed} planned={planned} "
            f"ok={ok} status={summary.get('status')}"
        )
    return True, f"records={n}/64 receipt=completed summary=64/64_ok"


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def panel_tie_counts(panel: dict) -> dict[str, int]:
    raw = Counter()
    for case in panel.get("cases") or []:
        rel = case.get("order_relation") or (case.get("tie_aware_comparison") or {}).get("relation")
        if rel:
            raw[rel] += 1
    agreement = int(raw.get("agreement", 0)) + int(raw.get("agreement_with_ties", 0))
    return {
        "agreement": agreement,
        "reversal": int(raw.get("reversal", 0)),
        "tie_loss": int(raw.get("tie_loss_of_discrimination", 0)),
        "insufficient": int(raw.get("insufficient_unique_plans", 0)),
        "raw": dict(raw),
    }


def write_status_docs(*, run_id: str, gate_c: str, matrix_line: str) -> None:
    agents = ROOT / "AGENTS.md"
    text = agents.read_text(encoding="utf-8")
    text = text.replace(
        "Active stage: **4.2 -- Gate C semantic closure and packaging repair (PARTIAL matrix; awaiting independent review)**.",
        f"Active stage: **4.2 -- Gate C semantic closure and packaging repair (`{run_id}`; GATE_C={gate_c}; awaiting independent review)**.",
    )
    if "41c28597-0ce0-428f-8230-ba2ca973c5b7" not in text:
        text = text.replace(
            "Stage 4.2 run `e85ee977-8a35-40c1-b690-02724dea3228` is interrupted PARTIAL at development matrix 40/64; resume is checksum-safe only while the source snapshot fingerprint matches.",
            "Stage 4.2 run `41c28597-0ce0-428f-8230-ba2ca973c5b7` is the authorised complete-matrix run. Interrupted PARTIAL run `e85ee977-8a35-40c1-b690-02724dea3228` (40/64) is preserved and fingerprint-blocked.",
        )
    agents.write_text(text, encoding="utf-8")

    (ROOT / "docs" / "STAGE_4_2_PREPACKAGE_REPORT.md").write_text(
        (
            "# Stage 4.2 prepackage report\n\n"
            "Internal staging snapshot before ZIP freeze. **Not** the final external report "
            "(`docs/STAGE_4_2_REPORT.md`).\n\n"
            f"- Authorised run: `{run_id}` (`formulation_gate_c_closure_check`)\n"
            f"- {matrix_line}\n"
            f"- Preserved: e8b87881, 1c5b0748, c4d0a199, e85ee977 (40/64 fingerprint-blocked)\n"
            "- Stage 5 / QPU / push: not authorised / not performed\n"
        ),
        encoding="utf-8",
    )


def write_report(ctx: dict) -> None:
    pairs = ctx["pairs"]
    panel = ctx["panel_counts"]
    zip_meta = ctx["zip"]
    body = f"""# Stage 4.2 Report — Gate C semantic closure and packaging repair

```text
STAGE_4_2_STATUS: {ctx["status"]}
STARTING_HEAD_AND_TREE: {ctx["starting_head"]} (dirty Stage 4.2 working tree at start); evidence docs/evidence/stage4_2/starting_state.txt
REVIEWED_LOCAL_COMMIT_AND_TREE: {ctx["reviewed_commit"]}
PRIOR_STAGE_4_AND_4_1_EVIDENCE_PRESERVED: yes — e8b87881-74a6-46c7-b48e-6b2496a5d586; 1c5b0748-5406-4933-8e41-4f943f4296c7; c4d0a199-9cea-4214-83ab-97964f2bf1ac; e85ee977-8a35-40c1-b690-02724dea3228 (40/64 fingerprint-blocked, preserved); Stage 4.1 report/ZIP/manifest/FINAL_VERIFY retained
STAGE_4_1_ERRATUM: evidence/formulation/artifacts/{RUN}/formulation.pre_repair_erratum/stage4_1_independent_review_erratum.json (+ docs/evidence/stage4_2/pre_repair_reproduction.json)
PRE_REPAIR_REPRODUCTIONS: docs/evidence/stage4_2/pre_repair_reproduction.json (F1–F9 from Stage 4.1 source/artifacts before closure repairs)
HISTORICAL_STAGE_3_3_SHA_RESTORED: yes — docs/evidence/stage3_3/post_repair_diagnostic.corrected.json SHA-256 10fe73b81f7580163ef29ff5d2125614dd8ee0c98a8f6c568d766e908915fa35 (verified by verify_historical_stage3_3)
CURRENT_STAGE_4_2_DIAGNOSTIC: docs/evidence/stage4_2/stage3_3_regression_diagnostic.json (new identity; historical path untouched)
VERSION_BUMPS: ACTION_MODEL/COMPILER/QUBO/CLASSICAL_REF/FORMULATION/DOWNSTREAM_POLICY/EVALUATOR 1.2.0; INTERFACE 3.1.0; SIMULATOR 1.0.4; REVIEW_PACKAGE_FORMAT 4.2.0; package 0.4.2
PUBLIC_IN_PIT_COMMITMENT_SCHEMA: DecisionObservation exposes typed committed_pit_service (compound, set_id, phase, residual timings, crew occupancy) via src/f1q/simulator/commitment.py — verified by tests/formulation/test_stage4_2_repair.py::test_in_pit_continuation_exposes_and_compiles_commitment
IN_PIT_COMPILER_SEMANTICS: residual in-progress stop from decision instant; planned_stops source=in_progress_commitment; no elapsed double-charge — verified by same test + compiler unit
EVALUATOR_EVENT_AND_EXACT_SET_SEMANTICS: reads kind; one stop per service_complete; post-checkpoint only; exact set+compound match; ACTION_TIMING_TOLERANCE_S=1e-6 a priori — verified by test_event_extraction_uses_kind_and_service_complete_post_checkpoint / test_exact_set_mismatch_fails_even_same_compound
CONTINUATION_ADMISSION: stable exclusion reasons for obligation/horizon/entry/commitment/inventory/nonpositive distance — verified by test_continuation_admission_rejects_impossible_cases
ACTION_REDUCTION_PROOF: independent unary/planned-stop/pair/validator/witness checks under kind_delay_compound_age_set.v2 (different ages/sets not merged)
PAIR_INTERACTION_DERIVATION: observable service-interval overlap only; zero with explicit reason if public timing insufficient; adjacent-lap half-service deleted
ALL_PAIR_CROSS_CHECK: expected/validated/round_tripped/terminal_executed/semantic_passed/failed = {pairs["expected"]}/{pairs["validated"]}/{pairs["round_tripped"]}/{pairs["terminal_executed"]}/{pairs["semantic_passed"]}/{pairs["failed"]}
TIE_AWARE_PANEL: agreement/reversal/tie_loss/insufficient = {panel["agreement"]}/{panel["reversal"]}/{panel["tie_loss"]}/{panel["insufficient"]} (raw: {panel["raw"]})
QUBO_ISING_AND_PENALTY_REVALIDATION: formulation.qubo_ising_gate ok={ctx["qubo_ok"]}
ENUMERATION_MILP_DP_AGREEMENT: formulation.independent_references milp_agreements={ctx["milp"]} ok={ctx["refs_ok"]}
HEURISTIC_AND_TIMING_ACCOUNTING: heuristic call/incumbent accounting retained; timing_window_matches on completed matrix pairs
DEVELOPMENT_MATRIX: planned/completed/failed = {ctx["planned"]}/{ctx["completed"]}/{ctx["failed"]}; development only; status {ctx["matrix_status"]}
PROXY_HEADROOM_AND_GATE_E: {ctx["headroom_line"]}
FULL_REGRESSION: packaging verifier + clean-extract origin recorded in review/STAGE_4_2_FINAL_VERIFY.json
NEW_RUN_ID_AND_RECEIPT: {RUN} — evidence/formulation/receipts/{RUN}.json (status completed). Preserved interrupted e85ee977 (40/64). Abandoned 90e50d03 preserved.
RESOURCE_USAGE: QPU_USAGE_SECONDS=0; workers=1; local classical only
REVIEWED_SOURCE_COMMIT: {ctx["reviewed_commit"]}
FROZEN_REVIEW_ZIP_BYTES_AND_SHA256: {zip_meta["bytes"]} bytes; {zip_meta["sha256"]}
INNER_MANIFEST_MEMBERS_AND_CANONICAL_AGGREGATE: {ctx["inner_members"]} members; {ctx["inner_aggregate"]} (algorithm canonical_row_v1_bytes_path_sha256)
EXTERNAL_SIDECAR_SHA256: {ctx["sidecar_sha256"]}
FINAL_VERIFY_SHA256: {ctx["final_verify_sha256"]}
CLEAN_EXTRACT_SOURCE_ORIGIN: {ctx["origin"]}
CLEAN_EXTRACT_TESTS: {ctx["extract_tests"]}
GATE_C_FORMULATION: {ctx["gate_c"]}
GATE_E_PROXY_HEADROOM: BLOCKED
STAGE_5_AUTHORISED: false
SCIENTIFIC_PROTOCOL: DRAFT
RESERVED_PARTITIONS_MATERIALIZED: none
LEARNED_MODELS_TRAINED: 0
QUANTUM_CIRCUITS_EXECUTED: 0
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0
QPU_USAGE_SECONDS: 0
IBM_OR_OTHER_CREDENTIAL_REQUESTED_OR_USED: false
PUSH_PERFORMED: false
NEXT_PERMITTED_WORK: independent review of Stage 4.2 only; Stage 5 and IBM credential entry remain blocked
```

## Narrative (evidence-labelled)

Stage 4.2 repairs F1–F9 findings from independent review of Stage 4.1. Public in-pit commitments, evaluator `kind`/`service_complete` extraction, exact-set matching, continuation admission, tie-aware panel classification, historical Stage 3.3 immutability, documentation/version consistency, and a real review-package builder/verifier are **implemented**.

The authorised `formulation_gate_c_closure_check` run `{RUN}` regenerated the development matrix at **{ctx["completed"]}/{ctx["planned"]}**. Interrupted PARTIAL run `e85ee977-…` (40/64) is preserved and was not reused as the final Gate C denominator. Gate C is **{ctx["gate_c"]}**. Gate E remains BLOCKED (zero proxy headroom). No QPU, IBM credential, Stage 5, reserved-partition, learned-model, or push activity occurred.

## File tree (Stage 4.2 deliverables)

```text
docs/STAGE_4_2_REPORT.md
docs/STAGE_4_2_PREPACKAGE_REPORT.md
docs/evidence/stage4_2/
evidence/formulation/receipts/{RUN}.{{json,md}}
evidence/formulation/artifacts/{RUN}/
review/STAGE_4_2_REVIEW.zip
review/STAGE_4_2_REVIEW.manifest.json
review/STAGE_4_2_FINAL_VERIFY.json
```
"""
    (ROOT / "docs" / "STAGE_4_2_REPORT.md").write_text(body, encoding="utf-8")


def write_project_status(ctx: dict) -> None:
    zip_meta = ctx["zip"]
    (ROOT / "PROJECT_STATUS.md").write_text(
        f"""# Project status

Updated after Stage 4.2 Gate C semantic closure and packaging repair (run `{RUN}`). Chat recollection is not evidence.

## Active stage

Stage 4.2 complete as software/evidence with **GATE_C_FORMULATION: {ctx["gate_c"]}** (development matrix {ctx["completed"]}/{ctx["planned"]} under authorised run `{RUN}`). Stage 4.1 is **not independently accepted**. Stage 5 is **not authorised** and remains blocked pending independent review of Stage 4.2 and the Gate E/headroom decision.

## Completed work with evidence

- Isolated repository `f1-ai-quantum-strategy` on `main`, remote origin connected, **not pushed**
- Dossier v3.1 SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33/33 pages extracted
- Stages 1–3.3 preserved under prior run identifiers
- Stage 4 formulation_check run `e8b87881-74a6-46c7-b48e-6b2496a5d586` **preserved**; Gate C PASS claim superseded
- Abandoned Stage 4 attempt `1c5b0748-5406-4933-8e41-4f943f4296c7` preserved as failed
- Stage 4.1 formulation_repair_check run `c4d0a199-9cea-4214-83ab-97964f2bf1ac` **preserved**; independent-review failure registered via Stage 4.2 erratum
- Abandoned Stage 4.2 attempt `90e50d03-371c-4663-94fb-ad1da84a0bcf` preserved (source fingerprint change)
- Interrupted Stage 4.2 run `e85ee977-8a35-40c1-b690-02724dea3228` **preserved** at development matrix 40/64 (fingerprint-blocked); not the Gate C denominator
- Stage 4.2 formulation_gate_c_closure_check run `{RUN}`: F1–F9 repairs, public in-pit commitment schema, evaluator `kind`/`service_complete` semantics, continuation admission, reduction proof, tie-aware panel, QUBO/Ising revalidation, historical Stage 3.3 SHA restored, current diagnostic under `docs/evidence/stage4_2/`, review-package builder/verifier; matrix **{ctx["completed"]}/{ctx["planned"]}**
- Named Stage 4.2 report: `docs/STAGE_4_2_REPORT.md`
- Reviewed source commit: `{ctx["reviewed_commit"]}`
- Receipt: `evidence/formulation/receipts/{RUN}.json`
- Review ZIP SHA-256 `{zip_meta["sha256"]}` ({zip_meta["bytes"]} bytes); sidecar `review/STAGE_4_2_REVIEW.manifest.json`; `review/STAGE_4_2_FINAL_VERIFY.json`

## Protocol state

- scientific_protocol: DRAFT
- frozen: false
- hardware_execution_enabled: false
- research comparison experiments executed: 0
- physical QPU jobs submitted: 0
- QPU usage from this stage: 0 seconds; account balance not queried
- learned models trained: 0
- quantum circuits executed: 0

## Explicit limitations

Real-world calibration was not run. GitHub push is not authorised. Reserved scientific partitions are not materialized. Hardware remains disabled. Protocol remains DRAFT. Gate E: exact legal enumeration still removes all proxy headroom on completed development checkpoints — carry forward before any Stage 5 superiority design. Stage 4.2 Gate C is {ctx["gate_c"]}.

## Next authorised unit

Independent review of Stage 4.2 only. Stage 5 blocked. No hardware credentials requested.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/STAGE_4_2_REPORT.md`
4. `docs/STAGE_4_1_REPORT.md` (historical; not independently accepted)
5. `docs/STAGE_4_REPORT.md` (historical; Gate C claim superseded)
6. `docs/ACTION_MODEL.md`
7. `docs/OBJECTIVE_COMPILER.md`
8. `docs/QUBO_SPECIFICATION.md`
9. `docs/CLASSICAL_REFERENCES.md`
10. `docs/evidence/stage4_2/pre_repair_reproduction.json`
11. `python -m f1q status` and `python -m f1q doctor`
""",
        encoding="utf-8",
    )


def package() -> None:
    from f1q.formulation.review_package import build_and_verify_review_package, write_final_verify_json
    from f1q.hashing import sha256_file
    from f1q.snapshot import git_state

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    pairs = summary.get("pair_cross_check_totals") or {}
    head = summary.get("proxy_headroom_stats") or {}
    panel_path = ROOT / f"evidence/formulation/artifacts/{RUN}/formulation.evaluator_separation_panel/evaluator_panel.json"
    panel = json.loads(panel_path.read_text(encoding="utf-8")) if panel_path.is_file() else {}
    panel_counts = panel_tie_counts(panel)
    qubo_path = ROOT / f"evidence/formulation/artifacts/{RUN}/formulation.qubo_ising_gate/qubo_gate_summary.json"
    qubo = json.loads(qubo_path.read_text(encoding="utf-8")) if qubo_path.is_file() else {}
    refs_path = ROOT / f"evidence/formulation/artifacts/{RUN}/formulation.independent_references/references_summary.json"
    refs = json.loads(refs_path.read_text(encoding="utf-8")) if refs_path.is_file() else {}

    completed = int(summary.get("completed") or 0)
    planned = int(summary.get("planned") or 0)
    failed = int(summary.get("failed") or 0)
    expected = int(pairs.get("expected") or 0)
    validated = int(pairs.get("validated") or 0)
    round_tripped = int(pairs.get("round_tripped") or 0)
    terminal = int(pairs.get("terminal_executed") or 0)
    semantic = int(pairs.get("semantic_passed") or pairs.get("checked") or 0)
    pair_failed = int(pairs.get("failed") or 0)
    matrix_ok = bool(summary.get("ok")) and completed == 64 and planned == 64 and failed == 0
    pairs_ok = expected > 0 and expected == validated == round_tripped == terminal == semantic and pair_failed == 0

    commit, _dirty = git_state(ROOT)
    reviewed = commit or "UNKNOWN"
    matrix_line = f"Development matrix {completed}/{planned}; pair totals expected={expected} terminal_executed={terminal} failed={pair_failed}"
    write_status_docs(run_id=RUN, gate_c="PENDING_VERIFY", matrix_line=matrix_line)

    log("PACKAGING_START freeze_zip")
    result = build_and_verify_review_package(ROOT, reviewed_commit=reviewed)
    fv_sha = write_final_verify_json(ROOT, result)
    zip_path = ROOT / "review" / "STAGE_4_2_REVIEW.zip"
    zip_sha = sha256_file(zip_path)
    zip_bytes = zip_path.stat().st_size
    if zip_sha != result["zip"]["sha256"] or zip_sha != result.get("zip_sha256_recheck"):
        raise RuntimeError(f"clean-extract zip hash mismatch zip={zip_sha} meta={result['zip']}")
    sidecar_path = ROOT / "review" / "STAGE_4_2_REVIEW.manifest.json"
    sidecar_sha = sha256_path(sidecar_path)
    fv_path = ROOT / "review" / "STAGE_4_2_FINAL_VERIFY.json"
    fv_recheck = sha256_path(fv_path)
    if fv_recheck != fv_sha:
        raise RuntimeError("FINAL_VERIFY hash drift after write")

    verify_ok = bool(result.get("verify", {}).get("ok")) and bool(result.get("zip_hash_stable"))
    origin_ok = bool((result.get("clean_extract") or {}).get("ok"))
    targeted_ok = int((result.get("clean_extract_targeted_import") or {}).get("returncode") or 1) == 0
    gate_c = "PASS" if (matrix_ok and pairs_ok and verify_ok and origin_ok and targeted_ok) else (
        "FAIL" if (not matrix_ok or not pairs_ok or not verify_ok) else "PARTIAL"
    )
    status = "COMPLETE" if gate_c == "PASS" else gate_c

    zero_head = int(head.get("zero_count") or 0) == completed and completed == 64
    headroom_line = (
        f"zero headroom on all {completed} records (min={head.get('min')} max={head.get('max')} mean={head.get('mean')}); Gate E remains BLOCKED"
        if zero_head
        else f"headroom stats {head}; Gate E remains BLOCKED"
    )
    ctx = {
        "status": status,
        "starting_head": "cd48f732ef25859da417ef5d1596566761909b7f",
        "reviewed_commit": reviewed,
        "pairs": {
            "expected": expected,
            "validated": validated,
            "round_tripped": round_tripped,
            "terminal_executed": terminal,
            "semantic_passed": semantic,
            "failed": pair_failed,
        },
        "panel_counts": panel_counts,
        "qubo_ok": qubo.get("ok"),
        "milp": f"{refs.get('milp_agreements')}/{refs.get('n')}",
        "refs_ok": refs.get("ok"),
        "planned": planned,
        "completed": completed,
        "failed": failed,
        "matrix_status": summary.get("status"),
        "headroom_line": headroom_line,
        "zip": {"bytes": zip_bytes, "sha256": zip_sha},
        "inner_members": (result.get("inner_manifest") or {}).get("member_count"),
        "inner_aggregate": (result.get("inner_manifest") or {}).get("canonical_aggregate_sha256"),
        "sidecar_sha256": sidecar_sha,
        "final_verify_sha256": fv_sha,
        "origin": "PASS" if origin_ok else "FAIL",
        "extract_tests": "PASS" if targeted_ok else "FAIL",
        "gate_c": gate_c,
    }
    write_report(ctx)
    write_project_status(ctx)
    write_status_docs(run_id=RUN, gate_c=gate_c, matrix_line=matrix_line)
    DONE.write_text(
        json.dumps(
            {
                "run_id": RUN,
                "gate_c": gate_c,
                "matrix": f"{completed}/{planned}",
                "zip_sha256": zip_sha,
                "zip_bytes": zip_bytes,
                "sidecar_sha256": sidecar_sha,
                "final_verify_sha256": fv_sha,
                "receipt_status": receipt.get("status"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    log(
        f"PACKAGING_COMPLETE gate_c={gate_c} zip={zip_sha} bytes={zip_bytes} "
        f"sidecar={sidecar_sha} final_verify={fv_sha} matrix={completed}/{planned}"
    )


def main() -> int:
    if LOCK.exists():
        log("WATCHER_SKIP lock_exists")
        return 0
    LOCK.write_text(str(time.time()), encoding="utf-8")
    log(f"WATCHER_START run={RUN} records={count_records()}/64")
    try:
        while True:
            ok, reason = ready()
            log(f"POLL {reason}")
            if ok:
                break
            time.sleep(20)
        package()
        return 0
    except Exception as exc:
        log(f"PACKAGING_FAILED {type(exc).__name__}: {exc}")
        raise
    finally:
        if LOCK.exists():
            LOCK.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
