# Stage 3.3 — evidence correction and regression hardening

Project: `f1-ai-quantum-strategy`. Work in the existing repository. This is a narrow correction to the Stage 3.2 evidence package. Complete the work and return the requested report and bundle; do not respond with a plan alone.

Stage 4 is not authorized by this prompt. Do not implement the action model, objective compiler, QUBO, optimizers, AI components, circuits, provider integrations, or research experiments. Do not request or use IBM credentials. Do not access any quantum provider, submit a physical QPU job, materialize reserved scientific partitions, train a model, or open held-out outcomes. Additional spending remains zero.

## Independent review result

The uploaded `STAGE_3_2_REVIEW.zip` had SHA-256:

```text
b60ad0f186aaf3846e02ae60ebf71d48cdfee5fcf9036cc30d53a8ccb60d3f57
```

The archive extracted safely. Its internal manifest listed 195 other members; each listed path, byte count, and SHA-256 matched the extracted file. The included source was then exercised directly with Python 3.12.14, Pydantic 2.13.5, and PyYAML 6.0.3.

The production repairs R1–R6 behave correctly in those direct checks:

- R1: pit progress was `10.95 -> 11.0 -> 11.0 -> 11.02` and remained nondecreasing.
- R2: the leader-triggered hand fixture produced one defined individual finish time and 19 absent finish times, with ranks for all 20 cars.
- R3: a finite `0.0001`-lap pre-pass gap produced deltas `[0.0, 0.0, 0.0, 0.0]` for progress, fuel, tyre age, and race time. The genuine-crossing order snap was approximately `1.4992451724538114e-12` laps, within the declared `2e-12` upper check.
- R4: a result before the registered epoch was accepted; a result after it retained `fallback_continuation` and `late_vs_registered_epoch=true`.
- R5: compound/set mismatch and rival control were rejected with `ILLEGAL_PLAN`; a failed two-car apply restored the prior policies.
- R6: valid checker input passed; missing pit events, legality failure, and a well-separated rank flip failed.

Two evidence defects prevent accepting the submitted package unchanged.

### E1 — the saved post-repair R3 diagnostic is stale

`docs/evidence/stage3_2/post_repair_diagnostic.json` records:

```json
"pass_deltas": [0.00010000000099985584, 0.0, 0.0, 0.0]
```

That is inconsistent with both the repaired production source and `test_r3_overtake_no_free_distance_on_finite_gap`, which yield an exact progress delta of `0.0`. The file therefore is not valid post-repair evidence. The Stage 3.2 report says R3 was fixed, but the named JSON still displays the prohibited finite-gap teleport.

Do not erase or silently overwrite this discrepancy. Preserve the original file and its SHA-256. Add a machine-readable erratum that identifies it as stale/superseded, explains the cause if it can be established from evidence, and points to a newly generated corrected artifact.

### E2 — the R2 regression does not enforce its stated claim

In `tests/test_stage3_2_repair.py`, `test_r2_individual_finish_times_not_leader_stamp` contains assertions equivalent to:

```python
assert len(set(round(v, 9) for v in defined)) >= 1
assert unfinished or len(defined) == len(fts)
```

For any nonempty `defined` list the first assertion is true, including the old defective case where all 20 cars share the same stamped time. The second is also true whether unfinished cars exist or every car is defined. The direct fixture and `post_repair_r2_finish.json` support the intended one-defined/19-absent behavior, but the named unit test does not protect it.

Strengthen the regression using actual semantic invariants. For the fixed deterministic 20-car hand fixture, require the leader-triggered terminal state to have exactly one defined individual finish time and 19 absent values, require the recorded leader's own time to be defined and equal to `leader_finish_t` within a justified numerical tolerance, require every unfinished car to remain `None`, and require classification computed from progress plus optional individual times to match the reported ranking. Also add a direct regression showing that the historical all-cars/shared-leader-time shape would fail the invariant. Do not manufacture an experimental observation; these are engineering fixtures.

## Required correction

1. Inspect `AGENTS.md`, `PROJECT_STATUS.md`, the ledger/receipts, current Git HEAD and dirty state before writing. Stay within the authorized repository. Record the exact starting state without printing secrets.
2. Preserve all Stage 2, Stage 3, Stage 3.1, and Stage 3.2 reports, run identifiers, raw artifacts, and receipts. Do not reuse a run ID or rewrite an old run to appear successful.
3. Preserve `docs/evidence/stage3_2/post_repair_diagnostic.json` byte-for-byte. Record its SHA-256 in a new erratum such as `docs/evidence/stage3_3/stage3_2_post_repair_diagnostic_erratum.json`.
4. Create a checked-in deterministic diagnostic generator or validation command that calls the current production simulator and handlers. It must generate a new artifact such as `docs/evidence/stage3_3/post_repair_diagnostic.corrected.json`. Avoid a hand-edited result. The artifact must include at least:
   - configured pit entry/box/exit fractions and the phase-by-phase R1 trace;
   - the R2 count of defined and absent individual finish times, leader ID/time, and classification consistency;
   - R3 finite-gap before/after values and deltas for progress, fuel, tyre age, and race time, plus `want_pass` state;
   - R3 genuine-crossing snap delta and its declared upper bound;
   - R4 early/late registered-epoch outcomes;
   - R5 rejection codes/reasons and atomic rollback result;
   - R6 valid and injected-failure gate outcomes;
   - simulator/interface versions, configuration hash, and source identity sufficient to associate the evidence with the tested code.
5. The corrected finite-gap R3 values must be obtained from live code and must show exact zero deltas for progress, fuel, tyre age, and time. The crossing case may use only the declared tiny order snap and must record its bound. If the live result differs, stop and report the defect instead of editing the number.
6. Add a regression that regenerates or computes the deterministic diagnostic from production code and verifies the checked-in corrected JSON. Exclude only inherently variable metadata; preferably keep the scientific payload deterministic and put timestamps outside it. A static JSON file and a test that never compares it with live behavior are insufficient.
7. Strengthen the R2 regression as described above. Check the classification keys and `None` handling explicitly. Keep the model labeled honestly as leader-triggered classification at the leader's finish; do not relabel absent individual finish times as observed finishes.
8. Rerun all affected R1–R6 regressions and the complete test suite. Run `python -m f1q doctor` and `python -m f1q status`. Record exact commands, exits, test count, and failures.
9. Do not change production simulator behavior merely to make evidence agree. If only diagnostic tooling, tests, evidence, and documentation change, the previous 64-case matrix, eight interventions, and refinement run remain preserved and need not be recomputed. If any production source, model configuration, action validation, simulator version, or resolution logic changes, rerun `simulator_repair` under a new run ID and repeat its 64-case matrix, eight fixed interventions, and h/h2/h4 panel. Report this branch honestly.
10. Add `docs/STAGE_3_3_REPORT.md`. It must identify the Stage 3.2 JSON as stale, cite the old and corrected hashes, state whether production behavior changed, give the live R1–R6 outcomes, list all checks, and distinguish engineering validation from F1 calibration or research evidence.
11. Update `PROJECT_STATUS.md`, `README.md`, and `AGENTS.md` only as needed to record that Stage 3.3 closes this evidence correction and that Stage 4 still awaits a separate authorization prompt. Do not describe lack of F1 calibration, unmaterialized reserved partitions, disabled hardware, or the DRAFT protocol as failures of this evidence-correction task. They remain explicit limitations and later-stage gates.
12. If all current tracked modifications are solely the authorized Stage 3.2/3.3 work and tests pass, create a local Git commit with a clear message. Do not include unknown pre-existing changes. If a safe isolated commit is not possible, leave the tree uncommitted and report the exact reason and changed paths. Never push.

## Review bundle

Create `review/STAGE_3_3_REVIEW.zip` containing the current relevant source, tests, diagnostic generator, configurations, dependency files, Stage 3.2 and 3.3 reports, the original stale artifact, its erratum, the corrected artifact, named test output, and the preserved Stage 3.2 receipts/artifacts needed to assess the claims.

Include `MANIFEST.sha256.json` inside the ZIP. It must cover every other archive member with path, byte count, and SHA-256 and must document exactly how any aggregate digest is computed. Put the ZIP's own SHA-256 in an external sidecar manifest because an archive cannot reliably contain its own final digest.

Extract the ZIP into a fresh temporary directory. Verify every member against the internal manifest, install/use the documented environment without relying on the original repository, run the targeted Stage 3.3 checks, and record the exact clean-extract command and result. Exclude credentials, `.git`, environments/caches, the mutable ledger database, reserved research data, and unrelated files.

## Acceptance gate

Stage 3.3 is `COMPLETE` only if all of the following hold:

- the stale artifact is preserved and explicitly superseded;
- the corrected diagnostic is generated from live production code and records finite-gap R3 deltas of exactly zero;
- the R2 regression would fail the historical shared timestamp behavior;
- R1–R6 targeted checks pass;
- the full test suite, doctor, and status checks pass;
- the bundle manifest and clean-extract verification pass;
- no production change is hidden behind an evidence-only label;
- no QPU/provider call, reserved split access, training, Stage 4 implementation, push, or extra spending occurs.

Once these conditions pass, report `STAGE_4_PREREQUISITES: PASS` for the software/evidence gate. Carry real-world calibration, protocol freeze, reserved partitions, and hardware readiness forward as later-stage limitations rather than using them to mark this narrow gate `PARTIAL`.

## Required return

Return the report and bundle, then stop:

```text
STAGE_3_3_STATUS: COMPLETE | PARTIAL | BLOCKED
STARTING_GIT_STATE:
ENDING_GIT_STATE_AND_LOCAL_COMMIT:
PRODUCTION_BEHAVIOR_CHANGED: true | false, with paths/reason
STALE_ARTIFACT_PRESERVED: path, SHA-256, erratum path
CORRECTED_DIAGNOSTIC: path, SHA-256, generation command
R1_PIT_GEOMETRY:
R2_FINISH_REGRESSION:
R3_MOVEMENT_CONSERVATION:
R4_COMMON_COMMITMENT:
R5_PLAN_VALIDATION_AND_ATOMICITY:
R6_RESOLUTION_GATE:
FULL_REGRESSION_RESULT:
DOCTOR_AND_STATUS:
PRIOR_STAGE_3_2_RUN_PRESERVED:
NEW_SIMULATOR_REPAIR_RUN: none expected unless production changed
REVIEW_BUNDLE_PATH_SHA256_AND_CLEAN_EXTRACT:
SCIENTIFIC_PROTOCOL: DRAFT
RESERVED_PARTITIONS_MATERIALIZED: none
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0
QPU_USAGE_SECONDS: 0
PUSH_PERFORMED: false
STAGE_4_PREREQUISITES: PASS | PARTIAL | FAIL, software/evidence reasons only
```

Do not begin Stage 4. Do not ask for an IBM API key. The user will return `docs/STAGE_3_3_REPORT.md` and `review/STAGE_3_3_REVIEW.zip` for independent review.
