# Stage 3.3 report — evidence correction and regression hardening

Evidence from the local ledger, named artifacts, and pytest. Chat recollection is not evidence. Claims are labeled. These checks are engineering validation of the restricted independent model. They do not establish F1 calibration, tyre science, SC/VSC physical validity, or quantum readiness.

Stage 3.2 JSON `docs/evidence/stage3_2/post_repair_diagnostic.json` is **stale/superseded**. Original bytes preserved. Erratum: `docs/evidence/stage3_3/stage3_2_post_repair_diagnostic_erratum.json`. Corrected live-generated artifact: `docs/evidence/stage3_3/post_repair_diagnostic.corrected.json`.

Prior runs preserved (identifiers not reused): Stage 3 `e2258740-1d08-4427-8305-b149ed504a73`, Stage 3.1 `4388ad68-6bd3-4a43-9099-32e52f56eb28`, Stage 3.2 `62b1e5ee-3f13-44be-98e0-8af018eb286b`, Stage 2 preview `8f292588-a328-4232-b425-c36c610a29f5`.

```text
STAGE_3_3_STATUS: COMPLETE
STARTING_GIT_STATE: HEAD 358a17b1a03d53248c5dd81305c24db384691f9b dirty=true (uncommitted Stage 3.1/3.2 stack present); doctor ok; hardware_execution_enabled false; scientific_protocol DRAFT; ledger runs include 62b1e5ee-… simulator_repair completed
ENDING_GIT_STATE_AND_LOCAL_COMMIT: see report closing section after packaging
PRODUCTION_BEHAVIOR_CHANGED: false — Stage 3.3 changed diagnostic tooling, tests, evidence erratum/corrected artifact, and documentation/status only; simulator.v1 remains 1.0.2; no new simulator_repair run
STALE_ARTIFACT_PRESERVED: docs/evidence/stage3_2/post_repair_diagnostic.json SHA-256 d5d63fc2d5f832485ada3318c34d38acc832df8fe7c9b06e1a1bd0e85fa4472c; erratum docs/evidence/stage3_3/stage3_2_post_repair_diagnostic_erratum.json
CORRECTED_DIAGNOSTIC: docs/evidence/stage3_3/post_repair_diagnostic.corrected.json SHA-256 10fe73b81f7580163ef29ff5d2125614dd8ee0c98a8f6c568d766e908915fa35; generation `python -m f1q simulator diagnostic-stage3-3 --write`; verify `python -m f1q simulator diagnostic-stage3-3 --verify` (match=true); scientific_payload_sha256 0d5ef101a6da5f2d133c8d6b06a0916fd4a3c779fd9441981da1aba0c680a115
R1_PIT_GEOMETRY: live pit_entry_frac=0.95 box=0.0 exit=0.02; phase progress 10.95 → 11.0 → 11.0 → 11.02 nondecreasing. Verified by named pytest and corrected diagnostic.
R2_FINISH_REGRESSION: hand fixture yields exactly 1 defined individual finish_time and 19 None; leader individual time equals leader_finish_t; classify(progress, finish_time) matches ranking; historical all-cars/shared-leader-time fixture fails assert_r2_individual_finish_invariants. Verified by test_r2_* and corrected diagnostic.
R3_MOVEMENT_CONSERVATION: finite-gap pass_deltas [0.0, 0.0, 0.0, 0.0] exact; genuine-crossing snap_delta_laps ≈ 1.4992451724538114e-12 within declared upper bound 2e-12. Stale Stage 3.2 JSON had pass_deltas[0] ≈ 1e-4 and is superseded. Verified by live generator + pytest.
R4_COMMON_COMMITMENT: delay 0.05 timely recommendation at registered epoch; delay 0.2 late_vs_registered_epoch with fallback_continuation; epoch unmoved. Verified by named pytest and corrected diagnostic.
R5_PLAN_VALIDATION_AND_ATOMICITY: compound/set mismatch and rival control rejected ILLEGAL_PLAN; two-car apply failure restores prior policies. Verified by named pytest and corrected diagnostic.
R6_RESOLUTION_GATE: valid row PASS; missing pit events FAIL; legality failure FAIL; well-separated rank flip FAIL. Verified by named pytest and corrected diagnostic.
FULL_REGRESSION_RESULT: pytest 88 passed in 22.34s (docs/evidence/stage3_3/pytest.txt); includes strengthened R2 and Stage 3.3 live-diagnostic comparison
DOCTOR_AND_STATUS: doctor status=ok hardware_execution_enabled=false scientific_protocol=DRAFT; status readiness=stage3_3-complete-pending-stage4
PRIOR_STAGE_3_2_RUN_PRESERVED: 62b1e5ee-3f13-44be-98e0-8af018eb286b (receipt + artifacts retained; not recomputed)
NEW_SIMULATOR_REPAIR_RUN: none (production behavior unchanged)
REVIEW_BUNDLE_PATH_SHA256_AND_CLEAN_EXTRACT: review/STAGE_3_3_REVIEW.zip sha256 71a25e50278e2b3666e066e37f6e325a9e81dfa269766eb2e9669b97ac3bc277 (210 members including inner MANIFEST.sha256.json); sidecar review/STAGE_3_3_REVIEW.manifest.json; clean extract verified 209 members + aggregate; targeted pytest exit 0 (13 passed); diagnostic live-match True
SCIENTIFIC_PROTOCOL: DRAFT
RESERVED_PARTITIONS_MATERIALIZED: none
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0
QPU_USAGE_SECONDS: 0
PUSH_PERFORMED: false
STAGE_4_PREREQUISITES: PASS — software/evidence gate for Stage 3.3 closed; F1 calibration, reserved partitions, hardware readiness, and protocol freeze remain later-stage limitations (not failures of this narrow correction)
```

## Defects corrected

| ID | Defect | Action | Label |
| --- | --- | --- | --- |
| E1 | Stale post-repair diagnostic still showed finite-gap progress jump | Preserved bytes + erratum; live-generated corrected JSON | verified by named check |
| E2 | R2 unit test assertions passed historical shared-stamp shape | Semantic invariants + historical-failure fixture | verified by named check |

## Production behavior

No production simulator source, model configuration, action validation, simulator version, or resolution logic was changed in Stage 3.3 solely to reconcile evidence. The prior Stage 3.2 64-case matrix, eight interventions, and refinement panel remain the preserved scientific/engineering package under run `62b1e5ee-…`.

## Commands actually run

| Command | Exit |
| --- | --- |
| `python -m f1q doctor` | 0 |
| `python -m f1q status` | 0 |
| `python -m f1q simulator diagnostic-stage3-3 --write` | 0 |
| `python -m f1q simulator diagnostic-stage3-3 --verify` | 0 |
| `python -m pytest` | 0 (88 passed in 22.34s) |
| clean-extract targeted pytest + diagnostic verify | 0 |

No `git push`. No IBM/QPU/provider call. No Stage 4 QUBO/action-model work.

## Closing git note

Local commit created for the authorized Stage 3.1/3.2/3.3 software and evidence stack that was sitting uncommitted on HEAD `358a17b…`. Push was not performed.
