# Stage 4 Closure Report — bounded engineering closure

> **SUPERSEDED.** This v1 report and `STAGE_4_CLOSURE_REVIEW.zip` are historical. Canonical deliverables are `STAGE_4_CLOSURE_REPORT_v2.md`, `STAGE_4_CLOSURE_REVIEW_v2.zip`, and companions. Do not treat v1 as the corrected timing-provenance closure.

```text
STAGE_4_ENGINEERING: CLOSED_WITH_DOCUMENTED_LIMITATIONS
LEGACY_EXHAUSTIVE_GATE: PARTIAL
PROXY_HEADROOM: ZERO
STAGE_5_DESIGN_READY: true
QPU_EXECUTION_AUTHORISED: false
GIT_HEAD: 2950c1b217ff2f97376fcbab4b91217c92b91710
GIT_DIRTY_AT_REPORT: true
SRC_TREE_SHA256: d66aec8612b7ee62501fa69c87be52389d6a00ffc0edbbc21b8338f9ced97e9a
AUDITED_SNAPSHOT_COMPARED: 97acf67b4c58816d8f710db7604151f914f3e2f8 (retained already-correct Stage 4.2 fixes; current main tip 2950c1b is newer; no reset to older snapshot)
STOPPED_TASKS_AND_PIDS: packager_task_ref=6969647f-ef3c-420a-b4b7-4029de333799 (requested cancel); zsh/python PIDs stopped=46713,46723,47780,48032,48039; docs/evidence/stage4_closure/stopped_workers.json
PRESERVED_RUN_IDS: e8b87881-74a6-46c7-b48e-6b2496a5d586 (Stage 4); c4d0a199-9cea-4214-83ab-97964f2bf1ac (Stage 4.1); e85ee977-8a35-40c1-b690-02724dea3228 (40/64 PARTIAL); 41c28597-0ce0-428f-8230-ba2ca973c5b7 (20/64 interrupted after leftover unauthorised resume was stopped; not completed; not merged)
DEFECT_A_TIMING_CONTINUATION: fixed now — exact pit-entry lap via supporting pit_entry metadata; shared check_action_semantics; expected continuation from commitment/policy; tests/formulation/test_stage4_closure.py
DEFECT_B_SERVICE_ALREADY_COMPLETED: fixed now — transit_out uses mounted compound/set + service_already_completed; residual exit only; age preserved; evidence hand_cases pit_phase_transit_out + commitment unit
DEFECT_C_MIXED_PIT_TIMING: fixed now — single service_interval_absolute_race_s coordinate; public t_in_s for on-track; incremental wait minus committed unary wait; hand_cases mixed_crew_*
RESUME_WEAK_HASH: documented + fail-closed — prior matrix resume trusted nonempty record_hash covering selected math fields only; automatic resume now rejects with RESUME_FAIL_CLOSED; stage4_2_closeout and package_on_64 disabled
LEDGERLOCKED_CAUSE: documented — competing resume/packager/closeout watchers held evidence/var/ledger.sqlite.lock (20 LedgerLocked errors in Stage 4.2 logs); workers stopped once; no LedgerLocked retry loop in this closure
VALIDATION_AMENDMENT: exhaustive all-pair terminal Cartesian development matrix WITHDRAWN for engineering closure; replaced by bounded 64 analytical + 64 lex-first terminal witnesses + ≤12 hand cases (docs/evidence/stage4_closure/coverage_checklist.json)
ANALYTICAL_64_COVERAGE: 64/64 PASS (admission/validation/encode-decode/costs/enumeration/MILP/QUBO-Ising algebraic) — evidence/formulation/artifacts/stage4_closure/*.closure.json
TERMINAL_WITNESS_64_COVERAGE: 64/64 PASS (lexicographically first tied optimum; failures kept; none failed)
HAND_CASES: 12/12 PASS (committed list docs/evidence/stage4_closure/hand_cases_committed.json)
HISTORICAL_EXHAUSTIVE: still PARTIAL — e85ee977 40/64 (7195 historical pairs under old checker; not proof corrected checker passed); 41c28597 14/64 interrupted
FOCUSED_REGRESSION: 19 passed (test_stage4_closure + test_stage4_2_repair) docs/evidence/stage4_closure/pytest_focused.txt EXIT 0
CLEAN_EXTRACT_PYTEST: 19 passed from extract tree; modules resolve inside extract; docs/evidence/stage4_closure/pytest_clean_extract.txt EXIT 0
COMMAND_ELAPSED_S: closure_gate≈105.7; focused_pytest≈6; hand_repair≈1; package+verify≈9; doctor/status≈1; aggregate_wall_under_600
TIMEOUT_OR_FAILURE: none on bounded closure cases
ARCHIVE_VERIFY: STAGE_4_CLOSURE_REVIEW.zip bytes=1748016 sha256=4f018415ed13eebd13d2d8439a193ebf80b5a2ef18e2b6c34561909f2f46b3ab; members=544; aggregate=a1ef62779c7856dd…; sidecar sha256=e00e7f14aa07295864ca72e60293963521a5d6543633c05572a4e5d1b399c708; FINAL_VERIFY ok=true
PACKAGE_CONTENTS: development_specs=64; closure_records=64; historical_matrix_records=58; not an import-only smoke check
GATE_C_FORMULATION_LEGACY_FIELD: not PASS — scope amended; use STAGE_4_ENGINEERING above
GATE_E_PROXY_HEADROOM: BLOCKED (zero headroom on all 64 closure witnesses; min=max=mean=0)
SCIENTIFIC_PROTOCOL: DRAFT
HARDWARE_EXECUTION_ENABLED: false
PUSH_PERFORMED: false
STAGE_5_QAOA_IBM_RESERVED_SPLITS: not done / not authorised by this closure beyond design-ready flag
NEXT_USER_ACTION: Stage 5 architecture decision must address zero-headroom (exact classical enumeration already solves this small action space) before committing to circuits; independent scientific review of this closure package; push only on separate instruction
```

## Narrative (evidence-labelled)

Competing Stage 4.2 workers (formulation_gate_c_closure_check PID 46723 on run `41c28597-…`, closeout watcher PID 47780, packager PID 48039) were stopped gracefully. Historical PARTIAL evidence is preserved separately and was not merged or renamed completed.

Defects A–C from the independent audit are **implemented** and **verified by named tests**. The former exhaustive development Cartesian matrix requirement is an explicit **engineering validation amendment** (withdrawn), not a change to a scientific test set. Bounded closure criteria all passed under a hard in-process timeout with one worker and no automatic retry.

Proxy headroom remains **zero** on all 64 witnesses. Stage 5 is design-ready only in the sense that engineering closure is documented; it must begin with an architecture decision that does not bypass the zero-headroom finding or invent artificial difficulty. QPU execution remains unauthorised. No push was performed.

## Deliverables

```text
STAGE_4_CLOSURE_REPORT.md
STAGE_4_CLOSURE_REVIEW.zip
STAGE_4_CLOSURE_REVIEW.manifest.json
STAGE_4_CLOSURE_FINAL_VERIFY.json
docs/STAGE_4_CLOSURE_REPORT.md
review/STAGE_4_CLOSURE_REVIEW.zip
review/STAGE_4_CLOSURE_REVIEW.manifest.json
review/STAGE_4_CLOSURE_FINAL_VERIFY.json
docs/evidence/stage4_closure/
evidence/formulation/artifacts/stage4_closure/
```
