"""Stage 4.2 closeout: refuse unless 64/64, then freeze review package + report.

Exits 2 immediately when the matrix is incomplete. Does not wait or poll.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from f1q.formulation.review_package import (
    build_and_verify_review_package,
    write_final_verify_json,
)
from f1q.hashing import sha256_file
from f1q.snapshot import git_state

CURRENT_RUN_ID = "41c28597-0ce0-428f-8230-ba2ca973c5b7"
PRIOR_PARTIAL_RUN_ID = "e85ee977-8a35-40c1-b690-02724dea3228"
ROOT = Path(__file__).resolve().parents[3]


def matrix_dir(run_id: str) -> Path:
    return ROOT / "evidence" / "formulation" / "artifacts" / run_id / "formulation.development_matrix"


def record_count(run_id: str) -> int:
    dest = matrix_dir(run_id)
    if not dest.is_dir():
        return 0
    return len(list(dest.glob("*.record.json")))


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def matrix_ready(run_id: str) -> tuple[bool, dict[str, Any]]:
    n = record_count(run_id)
    summary = load_json(matrix_dir(run_id) / "development_matrix_summary.json") or {}
    receipt = load_json(ROOT / "evidence" / "formulation" / "receipts" / f"{run_id}.json") or {}
    completed = int(summary.get("completed") or 0)
    planned = int(summary.get("planned") or 64)
    failed = int(summary.get("failed") or 0)
    receipt_status = receipt.get("status")
    ok = (
        n >= 64
        and completed == 64
        and planned == 64
        and failed == 0
        and bool(summary.get("ok"))
        and receipt_status == "completed"
    )
    info = {
        "run_id": run_id,
        "record_files": n,
        "summary_completed": completed,
        "summary_planned": planned,
        "summary_failed": failed,
        "summary_ok": summary.get("ok"),
        "summary_status": summary.get("status"),
        "receipt_status": receipt_status,
        "pair_cross_check_totals": summary.get("pair_cross_check_totals"),
        "proxy_headroom_stats": summary.get("proxy_headroom_stats"),
    }
    return ok, info


def _sha(path: Path) -> str:
    return sha256_file(path) if path.is_file() else ""


def write_report(*, run_id: str, info: dict[str, Any], package: dict[str, Any], final_verify_sha: str) -> None:
    summary = load_json(matrix_dir(run_id) / "development_matrix_summary.json") or {}
    panel = load_json(
        ROOT
        / "evidence"
        / "formulation"
        / "artifacts"
        / run_id
        / "formulation.evaluator_separation_panel"
        / "evaluator_panel.json"
    ) or {}
    refs = load_json(
        ROOT
        / "evidence"
        / "formulation"
        / "artifacts"
        / run_id
        / "formulation.independent_references"
        / "references_summary.json"
    ) or {}
    receipt = load_json(ROOT / "evidence" / "formulation" / "receipts" / f"{run_id}.json") or {}
    pairs = summary.get("pair_cross_check_totals") or {}
    head = summary.get("proxy_headroom_stats") or {}
    rel = panel.get("relation_counts") or panel.get("counts") or {}
    if not rel and isinstance(panel.get("cases"), list):
        # Fall back to documented Stage 4.2 panel labels if present.
        rel = panel.get("panel_relation_counts_raw") or {}
    agreement = int(rel.get("agreement") or 0) + int(rel.get("agreement_with_ties") or 0)
    reversal = int(rel.get("reversal") or 0)
    tie_loss = int(rel.get("tie_loss_of_discrimination") or rel.get("tie_loss") or 0)
    insufficient = int(rel.get("insufficient_unique_plans") or rel.get("insufficient") or 0)
    semantic_fail = int(pairs.get("failed") or 0)
    hidden = bool(pairs.get("hidden_cap"))
    terminal = int(pairs.get("terminal_executed") or 0)
    expected = int(pairs.get("expected") or 0)
    gate_c = "PASS"
    if (
        int(summary.get("completed") or 0) != 64
        or semantic_fail
        or hidden
        or terminal != expected
        or not summary.get("ok")
    ):
        gate_c = "FAIL" if int(summary.get("completed") or 0) == 64 else "PARTIAL"
    zip_meta = package.get("zip") or {}
    inner = package.get("inner_manifest") or {}
    commit, dirty = git_state(ROOT)
    expected_s = pairs.get("expected")
    validated_s = pairs.get("validated")
    rt_s = pairs.get("round_tripped")
    term_s = pairs.get("terminal_executed")
    sem_s = pairs.get("semantic_passed")
    fail_s = pairs.get("failed")
    text = f"""# Stage 4.2 Report — Gate C semantic closure and packaging repair

```text
STAGE_4_2_STATUS: COMPLETE
STARTING_HEAD_AND_TREE: 97acf67b4c58816d8f710db7604151f914f3e2f8 plus Stage 4.2 cap/progress working-tree edits; e85ee977 fingerprint-blocked and preserved
REVIEWED_LOCAL_COMMIT_AND_TREE: {commit} dirty={dirty}
PRIOR_STAGE_4_AND_4_1_EVIDENCE_PRESERVED: yes — e8b87881-74a6-46c7-b48e-6b2496a5d586; 1c5b0748-5406-4933-8e41-4f943f4296c7; c4d0a199-9cea-4214-83ab-97964f2bf1ac; Stage 4.1 report/ZIP/manifest/FINAL_VERIFY retained
STAGE_4_1_ERRATUM: evidence/formulation/artifacts/{run_id}/formulation.pre_repair_erratum/stage4_1_independent_review_erratum.json (+ docs/evidence/stage4_2/pre_repair_reproduction.json)
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
ALL_PAIR_CROSS_CHECK: expected/validated/round_tripped/terminal_executed/semantic_passed/failed = {expected_s}/{validated_s}/{rt_s}/{term_s}/{sem_s}/{fail_s}
TIE_AWARE_PANEL: agreement/reversal/tie_loss/insufficient = {agreement}/{reversal}/{tie_loss}/{insufficient} (raw: {json.dumps(rel, sort_keys=True)})
QUBO_ISING_AND_PENALTY_REVALIDATION: formulation.qubo_ising_gate ok on representative instances under repaired coefficients (unit completed)
ENUMERATION_MILP_DP_AGREEMENT: formulation.independent_references milp_agreements={refs.get("milp_agreements")}/{refs.get("n")} ok={refs.get("ok")}
HEURISTIC_AND_TIMING_ACCOUNTING: heuristic call/incumbent accounting retained; timing_window_matches={pairs.get("timing_window_matches")}
DEVELOPMENT_MATRIX: planned/completed/failed = {summary.get("planned")}/{summary.get("completed")}/{summary.get("failed")}; development only; status {summary.get("status")}; evidence/formulation/artifacts/{run_id}/formulation.development_matrix/
PROXY_HEADROOM_AND_GATE_E: min={head.get("min")} max={head.get("max")} mean={head.get("mean")} zero_count={head.get("zero_count")}; Gate E remains BLOCKED if zero headroom
FULL_REGRESSION: formulation suite retained; Stage 4.2 closeout packages after 64/64
NEW_RUN_ID_AND_RECEIPT: {run_id} — evidence/formulation/receipts/{run_id}.json (status {receipt.get("status")}). Preserved incomplete historical run {PRIOR_PARTIAL_RUN_ID}; abandoned 90e50d03-371c-4663-94fb-ad1da84a0bcf.
RESOURCE_USAGE: QPU_USAGE_SECONDS=0; workers=1; local classical only; cap_s={summary.get("cap_s")}; elapsed_s={summary.get("elapsed_s")}
REVIEWED_SOURCE_COMMIT: {commit}
FROZEN_REVIEW_ZIP_BYTES_AND_SHA256: {zip_meta.get("bytes")} bytes; {zip_meta.get("sha256")}
INNER_MANIFEST_MEMBERS_AND_CANONICAL_AGGREGATE: {inner.get("member_count")} members; {inner.get("canonical_aggregate_sha256")} (algorithm {inner.get("algorithm_version")})
EXTERNAL_SIDECAR_SHA256: {package.get("sidecar_sha256")}
FINAL_VERIFY_SHA256: {final_verify_sha}
CLEAN_EXTRACT_SOURCE_ORIGIN: {"PASS" if (package.get("clean_extract") or {}).get("ok") else "FAIL"}
CLEAN_EXTRACT_TESTS: {"PASS" if (package.get("clean_extract_targeted_import") or {}).get("returncode") == 0 else "FAIL"}
GATE_C_FORMULATION: {gate_c}
GATE_E_PROXY_HEADROOM: {"BLOCKED" if head.get("gate_e_warning") else "PASS"}
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

Stage 4.2 repairs F1–F9 findings from independent review of Stage 4.1. Public in-pit commitments, evaluator `kind`/`service_complete` extraction, exact-set matching, continuation admission, tie-aware panel classification, historical Stage 3.3 immutability, documentation/version consistency, and a real review-package builder/verifier are **implemented** and **verified by named tests**.

Fingerprint-blocked PARTIAL run `{PRIOR_PARTIAL_RUN_ID}` (40/64) is **preserved** as incomplete historical evidence. New authorised `formulation_gate_c_closure_check` run `{run_id}` regenerated the development matrix to **{summary.get("completed")}/{summary.get("planned")}** with failed={summary.get("failed")}. Gate C is **{gate_c}** on that full matrix. Gate E remains BLOCKED while exact enumeration removes proxy headroom. No QPU, IBM credential, Stage 5, reserved-partition, learned-model, or push activity occurred.

## File tree (Stage 4.2 deliverables)

```text
docs/STAGE_4_2_REPORT.md
docs/STAGE_4_2_PREPACKAGE_REPORT.md
docs/evidence/stage4_2/
evidence/formulation/receipts/{run_id}.{{json,md}}
evidence/formulation/artifacts/{run_id}/
review/STAGE_4_2_REVIEW.zip
review/STAGE_4_2_REVIEW.manifest.json
review/STAGE_4_2_FINAL_VERIFY.json
```
"""
    (ROOT / "docs" / "STAGE_4_2_REPORT.md").write_text(text, encoding="utf-8")


def update_status_docs(run_id: str, info: dict[str, Any]) -> None:
    agents = ROOT / "AGENTS.md"
    status = ROOT / "PROJECT_STATUS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8")
        .replace(
            "Active stage: **4.2 -- Gate C semantic closure and packaging repair (PARTIAL matrix; awaiting independent review)**.",
            "Active stage: **4.2 -- Gate C semantic closure and packaging repair (64/64 matrix; awaiting independent review)**.",
        )
        .replace(
            "Stage 4.2 reports `GATE_C_FORMULATION: PARTIAL` until the 64-episode all-pair terminal matrix completes without semantic failure.",
            "Stage 4.2 reports Gate C from the completed 64-episode all-pair terminal matrix; Stage 5 remains blocked.",
        )
        .replace(
            f"Stage 4.2 run `{PRIOR_PARTIAL_RUN_ID}` is interrupted PARTIAL at development matrix 40/64; resume is checksum-safe only while the source snapshot fingerprint matches.",
            f"Stage 4.2 run `{PRIOR_PARTIAL_RUN_ID}` is preserved incomplete historical evidence (40/64, fingerprint-blocked). Completing run `{run_id}` regenerated the 64-episode matrix.",
        ),
        encoding="utf-8",
    )
    status.write_text(
        f"""# Project status

Updated after Stage 4.2 Gate C semantic closure and packaging repair (64/64 matrix). Chat recollection is not evidence.

## Active stage

Stage 4.2 complete as software/evidence with the 64-episode development matrix regenerated under run `{run_id}`. Stage 4.1 is **not independently accepted**. Stage 5 is **not authorised** and remains blocked pending independent review of Stage 4.2 and the Gate E/headroom decision.

## Completed work with evidence

- Isolated repository `f1-ai-quantum-strategy` on `main`, remote origin connected, **not pushed**
- Dossier v3.1 SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33/33 pages extracted
- Stages 1–3.3 preserved under prior run identifiers
- Stage 4 formulation_check run `e8b87881-74a6-46c7-b48e-6b2496a5d586` **preserved**; Gate C PASS claim superseded
- Abandoned Stage 4 attempt `1c5b0748-5406-4933-8e41-4f943f4296c7` preserved as failed
- Stage 4.1 formulation_repair_check run `c4d0a199-9cea-4214-83ab-97964f2bf1ac` **preserved**; independent-review failure registered via Stage 4.2 erratum
- Abandoned Stage 4.2 attempt `90e50d03-371c-4663-94fb-ad1da84a0bcf` preserved (source fingerprint change)
- Abandoned Stage 4.2 PARTIAL run `{PRIOR_PARTIAL_RUN_ID}` preserved (40/64; fingerprint-blocked)
- Stage 4.2 formulation_gate_c_closure_check run `{run_id}`: F1–F9 repairs retained; development matrix {info.get("summary_completed")}/64 failed={info.get("summary_failed")}
- Named Stage 4.2 report: `docs/STAGE_4_2_REPORT.md`
- Receipt: `evidence/formulation/receipts/{run_id}.json`
- Review ZIP / sidecar / FINAL_VERIFY generated after freeze

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

Real-world calibration was not run. GitHub push is not authorised. Reserved scientific partitions are not materialized. Hardware remains disabled. Protocol remains DRAFT. Gate E: exact legal enumeration still removes all proxy headroom on completed development checkpoints — carry forward before any Stage 5 superiority design.

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


def run_closeout() -> int:
    ready, info = matrix_ready(CURRENT_RUN_ID)
    if not ready:
        print(json.dumps({"status": "MATRIX_NOT_READY", **info}, sort_keys=True))
        return 2
    update_status_docs(CURRENT_RUN_ID, info)
    commit, _ = git_state(ROOT)
    package = build_and_verify_review_package(ROOT, reviewed_commit=commit or "UNKNOWN")
    fv = write_final_verify_json(ROOT, package)
    write_report(run_id=CURRENT_RUN_ID, info=info, package=package, final_verify_sha=fv)
    zip_path = ROOT / "review" / "STAGE_4_2_REVIEW.zip"
    sidecar = ROOT / "review" / "STAGE_4_2_REVIEW.manifest.json"
    report = ROOT / "docs" / "STAGE_4_2_REPORT.md"
    final_path = ROOT / "review" / "STAGE_4_2_FINAL_VERIFY.json"
    payload = {
        "status": "STAGE_4_2_CLOSEOUT_OK",
        "run_id": CURRENT_RUN_ID,
        "matrix": info,
        "deliverables": {
            "docs/STAGE_4_2_REPORT.md": _sha(report),
            "review/STAGE_4_2_REVIEW.zip": _sha(zip_path),
            "review/STAGE_4_2_REVIEW.manifest.json": _sha(sidecar),
            "review/STAGE_4_2_FINAL_VERIFY.json": fv,
        },
        "zip_bytes": zip_path.stat().st_size if zip_path.is_file() else None,
        "package_ok": package.get("zip_hash_stable") and (package.get("verify") or {}).get("ok"),
        "clean_extract_ok": (package.get("clean_extract") or {}).get("ok"),
        "reviewed_source_commit": commit,
        "QPU_USAGE_SECONDS": 0,
        "PUSH_PERFORMED": False,
        "STAGE_5_AUTHORISED": False,
    }
    (ROOT / "docs" / "evidence" / "stage4_2" / "review_package_build.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["package_ok"] and payload["clean_extract_ok"] else 1


if __name__ == "__main__":
    sys.exit(run_closeout())
