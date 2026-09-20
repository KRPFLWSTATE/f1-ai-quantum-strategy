# Stage 4.2 Report — Gate C semantic closure and packaging repair

```text
STAGE_4_2_STATUS: PARTIAL
STARTING_HEAD_AND_TREE: cd48f732ef25859da417ef5d1596566761909b7f (dirty Stage 4.2 working tree at start); evidence docs/evidence/stage4_2/starting_state.txt
REVIEWED_LOCAL_COMMIT_AND_TREE: 97acf67b4c58816d8f710db7604151f914f3e2f8 (tip; prior evidence commit 42227710f0f75f1e39649850a62547e95c9d8d6c); clean after Stage 4.2 commits except external review sidecars
PRIOR_STAGE_4_AND_4_1_EVIDENCE_PRESERVED: yes — e8b87881-74a6-46c7-b48e-6b2496a5d586; 1c5b0748-5406-4933-8e41-4f943f4296c7; c4d0a199-9cea-4214-83ab-97964f2bf1ac; Stage 4.1 report/ZIP/manifest/FINAL_VERIFY retained
STAGE_4_1_ERRATUM: evidence/formulation/artifacts/e85ee977-8a35-40c1-b690-02724dea3228/formulation.pre_repair_erratum/stage4_1_independent_review_erratum.json (+ docs/evidence/stage4_2/pre_repair_reproduction.json)
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
ALL_PAIR_CROSS_CHECK: expected/validated/round_tripped/terminal_executed/semantic_passed/failed = 7195/7195/7195/7195/7195/0 on completed 40 episodes; matrix_episodes_incomplete=24 (PARTIAL)
TIE_AWARE_PANEL: agreement/reversal/tie_loss/insufficient = 2/1/1/4 (raw: agreement=1, agreement_with_ties=1, reversal=1, tie_loss_of_discrimination=1, insufficient_unique_plans=4) — docs/evidence/stage4_2/panel_summary.json
QUBO_ISING_AND_PENALTY_REVALIDATION: formulation.qubo_ising_gate ok on representative instances under repaired coefficients (unit completed)
ENUMERATION_MILP_DP_AGREEMENT: formulation.independent_references milp_agreements=64/64 ok under repaired costs (unit completed; analytical over development specs)
HEURISTIC_AND_TIMING_ACCOUNTING: heuristic call/incumbent accounting retained; timing_window_matches=7195 on completed matrix pairs
DEVELOPMENT_MATRIX: planned/completed/failed = 64/40/0; development only; status PARTIAL (STAGE_4_2_TIME_CAP_PARTIAL / operator deliverables stop); evidence/formulation/artifacts/e85ee977-8a35-40c1-b690-02724dea3228/formulation.development_matrix/
PROXY_HEADROOM_AND_GATE_E: zero headroom on all 40 completed records (min=max=mean=0); Gate E remains BLOCKED
FULL_REGRESSION: formulation suite + stage3_3 tests passed (docs/evidence/stage4_2/pytest_formulation_now.txt; pytest_final_smoke.txt EXIT 0)
NEW_RUN_ID_AND_RECEIPT: e85ee977-8a35-40c1-b690-02724dea3228 — evidence/formulation/receipts/e85ee977-8a35-40c1-b690-02724dea3228.json (status interrupted; matrix unit interrupted; other units completed). Abandoned fingerprint-blocked attempt 90e50d03-371c-4663-94fb-ad1da84a0bcf preserved.
RESOURCE_USAGE: QPU_USAGE_SECONDS=0; workers=1; local classical only; peak RSS sampled in erratum unit (~83 MB parent)
REVIEWED_SOURCE_COMMIT: 97acf67b4c58816d8f710db7604151f914f3e2f8
FROZEN_REVIEW_ZIP_BYTES_AND_SHA256: 714162 bytes; 7aec1f48172cab627bb274451a217b319f07671d47de1732e19b658be31f8aa5
INNER_MANIFEST_MEMBERS_AND_CANONICAL_AGGREGATE: 337 members; c0eea8ce60f47efdfd2a71d2b0dbb173fca644ab126a367a80525358f7c7ce6e (algorithm canonical_row_v1_bytes_path_sha256)
EXTERNAL_SIDECAR_SHA256: 66af7922906d247f9d4b0943b3344a485c664e701afe1668e75f0fc3c97ed848
FINAL_VERIFY_SHA256: 6af0436ca33f5c5bc8ea556cfb613723e397a253abe0fff76f21d22576c48ac7
CLEAN_EXTRACT_SOURCE_ORIGIN: PASS — all audited f1q.* modules resolve inside extracted tree (review/STAGE_4_2_FINAL_VERIFY.json)
CLEAN_EXTRACT_TESTS: PASS — isolated python -I targeted import of f1q.errors/hashing/paths/review_package from extract (returncode 0)
GATE_C_FORMULATION: PARTIAL
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
NEXT_PERMITTED_WORK: independent review of Stage 4.2 only; checksum-safe resume of e85ee977 is fingerprint-blocked after reviewed commits (run snapshot 8dfb911f… ≠ tip tree); Stage 5 and IBM credential entry remain blocked
```

## Narrative (evidence-labelled)

Stage 4.2 repairs F1–F9 findings from independent review of Stage 4.1. Public in-pit commitments, evaluator `kind`/`service_complete` extraction, exact-set matching, continuation admission, tie-aware panel classification, historical Stage 3.3 immutability, documentation/version consistency, and a real review-package builder/verifier are **implemented** and **verified by named tests**.

The authorised `formulation_gate_c_closure_check` run `e85ee977-…` completed all non-matrix units. The development matrix is **PARTIAL at 40/64** under the Stage 4.2 cumulative 30-minute wall-time cap (checksum-safe resume). On those 40 episodes, all regenerated reduced pairs were validated, round-tripped, and terminally executed with zero semantic failures (7195/7195). Because 24 episodes remain incomplete, Gate C cannot be reported PASS. Checksum-safe resume of this run is currently fingerprint-blocked after reviewed tip commits (run snapshot 8dfb911f…).

Proxy headroom remains zero on all completed records → Gate E BLOCKED. No QPU, IBM credential, Stage 5, reserved-partition, learned-model, or push activity occurred.

## File tree (Stage 4.2 deliverables)

```text
docs/STAGE_4_2_REPORT.md
docs/STAGE_4_2_PREPACKAGE_REPORT.md
docs/evidence/stage4_2/
evidence/formulation/receipts/e85ee977-8a35-40c1-b690-02724dea3228.{json,md}
evidence/formulation/artifacts/e85ee977-8a35-40c1-b690-02724dea3228/
review/STAGE_4_2_REVIEW.zip
review/STAGE_4_2_REVIEW.manifest.json
review/STAGE_4_2_FINAL_VERIFY.json
```
