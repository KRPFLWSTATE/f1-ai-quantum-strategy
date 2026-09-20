# Stage 4 Closure Report v2 — timing-provenance corrected bounded engineering closure

> Canonical corrected package. Supersedes `STAGE_4_CLOSURE_REPORT.md` / `STAGE_4_CLOSURE_REVIEW.zip` (v1). The failed timing attempt under `evidence/formulation/artifacts/stage4_closure_failed_timing_attempt_1/` is preserved as an unsuccessful verification attempt only.

```text
STAGE_4_ENGINEERING: CLOSED_WITH_DOCUMENTED_LIMITATIONS
LEGACY_EXHAUSTIVE_GATE: PARTIAL
LEGACY_GATE_ACTION: ARCHIVED_DO_NOT_RESUME
PROXY_HEADROOM: ZERO
STAGE_5_DESIGN_READY: true
QPU_EXECUTION_AUTHORISED: false
REVIEWED_SOURCE_COMMIT: 945d30d533ea0fadfcabb2ad17da134b73141b6d
SRC_TREE_SHA256: 687c4214bb41d83113138214a302e6e4eed445f4e6bd2bbc2b9650aa3b74b8df
ROOT_CAUSE_CLASS: C
ROOT_CAUSE: Dirty-tree engine.py pit_entry/_log omitted detail.pit_entry_completed_laps; restored producer logging + strict pit_entry↔service_complete pairing
DIAGNOSTIC_EPISODE: f1q.dev.block.v2/fam.green_pit_high.tyre_near_linear.traffic_dense/0000/episode/00/SC
CHECKPOINT_EVENT_INDEX: 150
OBSERVED_PIT_ENTRY_LAPS: 32/32
TIMING_REGRESSION_TESTS: 4 passed EXIT 0
FOCUSED_TESTS: 29 passed EXIT 0 (test_stage4_closure + test_stage4_2_repair)
CORRECTED_BOUNDED_CLOSURE: PASS 64/64 analytical; 64/64 semantic-legal terminals
SCHEDULED_WITNESSES: 81/81 delay_laps with non-null observed entry-lap evidence
CONTINUATION_WITNESSES: 47/47
REAL_ROUND_TRIP: 12322/12322
HAND_CASES: 12/12
MILP_QUBO_CHECKS: PASS (all 64)
PROXY_HEADROOM: ZERO (min=max=mean=0; zero_count=64)
SIMULATOR_INTERFACE: 1.0.4 / 3.1.0
LEGACY_COUNTS: e85ee977=40; 41c28597=21 archived (git-tracked); no resume
FAILED_TIMING_ATTEMPT: preserved; not scientific evidence; not canonical
ARCHIVE_VERIFY: STAGE_4_CLOSURE_REVIEW_v2.zip bytes=2018802 sha256=e30c6a6d7e12f01d6e42d59fa38a341d6aeebb7bd44635955838924130830f91; members=640; aggregate=a4467d88477793024bb1e16e11ad2e72efe6d820c45f31c5905cc83176240ff0; sidecar sha256=df808efaf9ac335bf871de5e2a98985e2af77e1592c3f210e0b2bbd5a8948318; FINAL_VERIFY ok=true
PACKAGE_CONTENTS: development_specs=64; closure_records=64; historical_matrix_records=61 (40+21); failed_timing_attempt_closures=64
CLEAN_EXTRACT_PYTEST: 29 passed docs/evidence/stage4_closure/pytest_clean_extract_v2.txt EXIT 0
SCIENTIFIC_PROTOCOL: DRAFT
HARDWARE_EXECUTION_ENABLED: false
PUSH_PERFORMED: pending_package_commit
```

## Narrative (evidence-labelled)

Class-C producer defect: simulator state retained `pit_entry_completed_laps` but event detail omitted it, so the evaluator fail-closed with `missing_pit_entry_completed_laps` on all 81 scheduled `delay_laps` witnesses. Restored logging from commit `83f480a` and added strict post-checkpoint pit_entry↔service_complete pairing without weakening semantic or timing gates. One corrected bounded closure passed all counters. Legacy exhaustive Gate C remains PARTIAL and archived. Zero proxy headroom remains. QPU execution unauthorised.

## Deliverables

```text
STAGE_4_CLOSURE_REPORT_v2.md
docs/STAGE_4_CLOSURE_REPORT_v2.md
STAGE_4_CLOSURE_REVIEW_v2.zip
STAGE_4_CLOSURE_REVIEW_v2.manifest.json
STAGE_4_CLOSURE_FINAL_VERIFY_v2.json
docs/evidence/stage4_closure_correction/
evidence/formulation/artifacts/stage4_closure/
evidence/formulation/artifacts/stage4_closure_failed_timing_attempt_1/
```
