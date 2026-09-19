# Stage 3.2 report — simulator defect repair

Evidence from the local ledger, named artifacts, and pytest. Chat recollection is not evidence. Claims are labeled. These checks are engineering validation of the restricted independent model. They do not establish F1 calibration, tyre science, SC/VSC physical validity, or quantum readiness.

Prior runs preserved (identifiers not reused): Stage 3 `e2258740-1d08-4427-8305-b149ed504a73`, Stage 3.1 `4388ad68-6bd3-4a43-9099-32e52f56eb28`, Stage 2 preview `8f292588-a328-4232-b425-c36c610a29f5`.

```text
STAGE_3_2_STATUS: COMPLETE
SOURCE_COMMIT_AND_RECOVERABLE_SNAPSHOT: git HEAD 358a17b1a03d53248c5dd81305c24db384691f9b dirty=true at the simulator_repair run; source snapshot hash 54e73c80dd0cd287827825e69d4061388cec3c564739a076a270d0dc638151ff (99 primary reconstructed files matched); pre-repair aggregate manifest evidence/simulator/pre_repair_stage3_2/source_manifest.json aggregate_sha256 87e22f9c64bc0c548202410cdc912b296447918c0fa02f70556fc6682b6fbd4c (88 files). Stage 3.1 snapshot 2b562327… and Stage 3 snapshot 26ed935c… remain identities of their runs and were not overwritten.
R1_PIT_GEOMETRY: reproduced (pre-repair pit_trace transit_in 10.95 → service 11.95 → exit 11.02; docs/evidence/stage3_2/pre_repair_diagnostic.json); fixed (post-repair box at 11.0, exit 11.02; configured entry/box/exit geometry); independent evidence tests/test_stage3_2_repair.py::test_r1_pit_box_progress_uses_configured_geometry and queued-stop check. Verified by named pytest.
R2_FINISH_AND_CLASSIFICATION: reproduced (all 20 cars shared one finish time 3755.732088… at h and 3755.732084… at h/4 on fam.…0002/episode/03/SC; docs/evidence/stage3_2/pre_repair_r2_finish.json); model definition = leader-triggered end with individual finish_time only on horizon crossing, unfinished absent, rank_at_leader_finish diagnostic (docs/SIMULATOR_MODEL.md §10); post-repair same episode: 1 defined finish (leader), 19 absent, ranks stable bluehaven.a=10 / windrow.b=11 at h and h/4 (docs/evidence/stage3_2/post_repair_r2_finish.json). Verified by named pytest and resolution panel.
R3_MOVEMENT_CONSERVATION: reproduced (pass_deltas progress 0.0006507 with fuel/tyre/time 0); fixed (finite-gap fire no longer teleports; genuine crossing uses OVERTAKE_ORDER_SNAP_LAPS=1e-12 only; pass_clearance_s is post-pass traffic); independent evidence test_r3_overtake_*. Verified by named pytest.
R4_COMMON_COMMITMENT: reproduced (delays 0.05 and 0.2 both timely; commits at 1015.8847 and 1015.9847); fixed (0.05 timely recommendation at registered epoch; 0.2 late_vs_registered, fallback at registered epoch, epoch unmoved); boundary evidence test_r4_*; non-finite/negative/out-of-window rejected. Verified by named pytest.
R5_PLAN_VALIDATION_AND_ATOMICITY: reproduced (mismatched hard/medium set and rival continuation accepted); fixed (both rejected ILLEGAL_PLAN before mutation; atomic apply restores policies on failure; remount fitted set rejected). Verified by named pytest.
R6_RESOLUTION_GATE: injected-checker failures detected (missing event / count mismatch / legality flip → FAIL; well-separated rank flip → non-PASS; test_r6_injected_checker_failures); actual panel outcome PASS, 0 rank/order flips, max_pit_event_error_h2_h4_s 9.65e-07, max_finish_error_h2_h4_s 1.62e-07 (individual finish times), episodes_with_no_pit_events 0. Evidence evidence/simulator/artifacts/62b1e5ee-3f13-44be-98e0-8af018eb286b/simulator.repair.resolution/unit.json.
NEW_64_CASE_MATRIX: admitted 64 / rejected 0 / pending 0 / incomplete_cap false; resume_max_time_error_s 0.0; resume discrepancies 0. Preview specs 8f292588-… not overwritten.
EIGHT_INTERVENTIONS: count 8; ok 3; rejected 5 (honest ILLEGAL_PLAN: expired pit_now past entry, or already in pit); failures listed, episodes not replaced with favourable cases. Not a powered comparison.
REFINEMENT_RESULTS_AND_GENUINE_AMBIGUITIES: panel PASS; no rank/order flips; prior Stage 3.1 near-tie on …0002/episode/03/SC no longer flips under corrected finish/progress classification (same-run ranks stable). Two levels still do not prove convergence. No remaining genuine ambiguity requiring PARTIAL on this panel.
REGRESSIONS_AND_REPAIR_FAILURES: pytest 84 passed in 21.51s (docs/evidence/stage3_2/pytest.txt); run_all_mechanism_checks ok=true failed=[]; doctor status ok; scientific_protocol DRAFT; hardware_execution_enabled false. Intervention unit records 5 rejected plans (expected under repaired validation), not pytest failures.
SUPERSEDED_CLAIMS_AND_PRESERVED_RUNS: Preserved runs e2258740-… (1.0.0), 4388ad68-… (1.0.1), 8f292588-…. Superseded claims: (1) pit progress ℓ+entry after box arrival; (2) shared leader finish_time as individual finishing measurement / near-tie metric; (3) overtake clearance teleport as physical progress; (4) arrival after registered epoch still timely and able to move commit time; (5) validate_plan accepting compound/set mismatch or rival cars; (6) resolution N/A for mismatched events and ignoring legality. Production code is simulator.v1 1.0.2.
RESOURCE_USAGE: max_workers 1; stage3_2 repair elapsed 138.487 s of 1800 s cap; incomplete_cap false; RAM 60% ceiling not separately sampled on this repair run (Stage 3.1 sampling method unchanged).
REVIEW_BUNDLE_PATH_AND_CLEAN_EXTRACT_CHECK: review/STAGE_3_2_REVIEW.zip (sha256 b60ad0f186aaf3846e02ae60ebf71d48cdfee5fcf9036cc30d53a8ccb60d3f57, 196 members including inner MANIFEST.sha256.json); review/STAGE_3_2_REVIEW.manifest.json; clean extract member hashes matched; targeted pytest tests/test_stage3_2_repair.py exit 0 (9 passed) with PYTHONPATH=extracted/src; omitted .git/.venv/ledger/reserved partitions/full preview corpus as stated in inner manifest.
SCIENTIFIC_PROTOCOL: DRAFT
RESERVED_PARTITIONS_MATERIALIZED: none
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0
PUSH_PERFORMED: false
STAGE_4_PREREQUISITES: PARTIAL — software repair gates for Stage 3.2 (R1–R6, matrix, resolution panel) PASS with listed intervention rejections; still not F1-calibrated; reserved partitions not materialized; hardware disabled; protocol DRAFT; Stage 4 QUBO/action-model work not authorised.
```

## Commands actually run (this repair)

| Command | Exit |
| --- | --- |
| `python -m f1q doctor` | 0 |
| `python -m f1q status` | 0 |
| pre-repair diagnostic (R1/R3/R4/R5) | 0 |
| pre-repair R2 episode finish table | 0 |
| `python -m pytest --tb=line` | 0 (84 passed in 21.51s) |
| `python -m f1q run --plan simulator_repair` | 0 (run `62b1e5ee-3f13-44be-98e0-8af018eb286b`) |

No `git push`. No IBM/QPU/provider call. No Stage 4 QUBO/action-model work.

## What was a defect vs retained modelling

| Topic | Classification | Action |
| --- | --- | --- |
| Pit progress jump to ℓ+entry after box | production defect | Fixed coordinate convention; independent phase checks |
| Shared finish_time stamp | production defect / mislabeled quantity | Individual finishes; leader stamp removed |
| Overtake clearance teleport | production defect | Order snap only; clearance = traffic target |
| Late arrival moves commitment | production protocol defect | Registered epoch immovable; late → fallback |
| validate_plan too weak | production defect | Full pre-apply validation + atomicity |
| Resolution gate N/A/mismatch/legality | checker defect | Explicit predicates; injected tests |
| Fuel conditioned floor | retained provisional assumption | Unchanged (v1.1) |
| Intervention illegal pit_now | correct rejection under repaired validation | Listed; episodes not replaced |
