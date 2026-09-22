# Phase 6 completion report

**Document class:** A4 local pre-test mechanism and resource pilot, written from frozen artifacts after independent verification.  
**PHASE_6_STATUS / PHASE_6_ENGINEERING:** `INCOMPLETE_ENGINEERING_RESOURCE_LIMIT`  
**Authoritative run:** `0b697910-e8a2-474b-bc77-bc69ebb8e9c3`  
**START_COMMIT:** `443c6365777965438e1cd57439a58770227ae513`  
**REVIEWED_SOURCE_COMMIT:** `a38bb29664b78cd5cb74a075f210f706878a0a9b`  
**Evidence directory:** `evidence/stage6_a4/0b697910-e8a2-474b-bc77-bc69ebb8e9c3/`  
**QPU_EXECUTION_AUTHORISED:** false · **QPU_JOBS:** 0 · **QPU_USAGE_SECONDS:** 0 · **FINAL_TEST_ACCESSED:** false · **PHASE_7_AUTHORISED:** false · **Phase 7 started:** false

Evidence labels used below: implemented, verified by a named check, simulated. Nothing in this run is physically measured, F1-calibrated, or a quantum-advantage result. A test fixture is not an experimental observation. Admission, software repair, and local simulations do not establish scientific novelty.

---

## 1. Executive verdict

The authorised completion prompt defines exactly four terminal engineering states. This run is **`INCOMPLETE_ENGINEERING_RESOURCE_LIMIT`**. That state means: the A4 implementation and the real admission measurement are valid enough to project cost from measured probes, but even the predeclared minimum complete corpus (120 training parents, 80 tuning parents, 24 calibration parents, five budgets, three policy seeds, 2,048-world calibration start) cannot fit the prospective 86,400 CPU-second and 11,520-second wall ceilings after a 20% wall reserve. A last-resort limited-resource pilot was therefore executed and independently verified. That pilot is **not** a completed 120/80/24 Phase 6 scientific corpus.

It is **not** `CLOSED_READY_FOR_PHASE7_BOUNDARY` and **not** `CLOSED_NOT_READY_FOR_PHASE7`, because those states require the complete required Phase 6 data. It is **not** `INCOMPLETE_ENGINEERING` in the software-failure sense: the limited pilot produced analysis, gates, a report, a manifest, and independent verification rather than stopping at `campaign_raw_complete`.

Software Gate E on the limited sample is `PASS_BOUNDARY_MECHANISM` (`RUN_RECEIPT.json` / `CLAIMS_LEDGER.json`) because eight calibration rows recorded quantum-incremental candidates evaluated inside matched K. That is a **limited-pilot diagnostic**, not confirmatory Gate E on the registered corpus. Executed-plan differences between classical and hybrid arms were **zero** (`BOUNDARY_RESULTS.json` `n_executed_diff=0`). Superiority is closed: `SUPERIORITY_PATH_AVAILABLE=false` because proxy headroom is zero. Gate F is `FAIL` because calibration parents are 2/24, admission of the full ladders failed, and Phase 7 resource/precision readiness is false.

Phase 7 was not started. Readiness is not permission.

## 2. Authority, amendments, commits, and clean-tree proof

Governing authority, descending: the authorised Cursor Phase 6 completion prompt; `docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf` (v3.1, SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33 pages, unchanged); `docs/A3_INVALIDATION_AND_A4_PROTOCOL_AMENDMENT.md`; Phase 6 freeze documents; then `AGENTS.md` after this attempt.

Prospective, pre-outcome amendment: `docs/PHASE_6_A4_IMPLEMENTATION_AND_RESOURCE_AMENDMENT.md` and `IMPLEMENTATION_RESOURCE_AMENDMENT.json`. It records that the previous 75-minute campaign ceiling and 60-minute admission threshold were implementation-added constraints, not the dossier’s canonical ceiling. This attempt used dossier RAM ≤ 60%, checkpoint-bounded units, a 24 CPU-hour ceiling, plus a user-protection 4-hour wall (14,400 s) and an admission threshold of 11,520 s.

| Field | Value | Source |
|---|---|---|
| START_COMMIT | `443c6365777965438e1cd57439a58770227ae513` | `START_STATE.json` |
| REVIEWED_SOURCE_COMMIT | `a38bb29664b78cd5cb74a075f210f706878a0a9b` | `START_STATE.json`, `ADMISSION_RECEIPT.json` |
| Authoritative run | `0b697910-e8a2-474b-bc77-bc69ebb8e9c3` | `START_STATE.json` |
| Package / A4 / schema | 0.9.0 / 0.9.0 / a4.v2 | `START_STATE.json`, `src/f1q/__init__.py` |
| Simulator / interface | 1.0.4 / 3.1.0 | `START_STATE.json` |
| Config hash | `013cb04fbb7d29aa11f72df2e88defe46e7e0e24489927c2c05cec1f91ded633` | `RESOLVED_CONFIG.json` |

Source was committed and pushed to `origin/main` before this campaign (`0b12032` then `a38bb29`). The campaign ran from a clean sibling worktree at `a38bb29` (`f1-ai-quantum-strategy-phase6-a4-auth`). Diagnostic miniature runs under other UUIDs were not used as scientific outcomes.

## 3. Historical lineage

Run `3de109c7-30d9-4cb0-827f-dbd82c4c509d` is **`SUPERSEDED_RESOURCE_MODEL_ONLY`**. Its files were not modified. Its truthful statement that no 120/80/24 corpus ran remains valid. Its non-admission is not treated as a scientific negative on quantum candidates, because it reported workers without a real `ProcessPoolExecutor`, divided by an assumed parallel factor, and probed a non-representative C0-p1 / 64-draw path.

Run `09806343-f940-4f33-9e0f-eb2855d0714b` is preserved as the hash-verified 24-anchor / 288-start donor source. Fits were copied, not refit. A3 `a5fdb488-9a90-47f9-a4f5-7f77a74180a6` remains `SUPERSEDED_INVALID_IMPLEMENTATION`. A2 residual `e437fa3d-…` is not an A4 continuation. Historical Phase 6 `bd83cb22` and corrected `2a3fb275`, and Phase 5 `e6b3588b` (`PASS_WITH_DOCUMENTED_LIMITATIONS`), are unchanged. Archived Stage 4 runs `e85ee977`, `41c28597`, and ledger-listed `fcbb3e38` were not resumed.

## 4. Defect → source fix → test → evidence

| Prompt defect | Source repair | Test | Evidence |
|---|---|---|---|
| PreparedCase ignored by decision path | `loop.decide_and_evaluate(..., prepared=)` skips simulator reinit | `test_prepared_case_once_across_arms_budgets` | `PREPARED_CASES.jsonl` 20 rows; coordinator counters after campaign `prepare_case_calls=25` in `MECHANISM_RESULTS.json` (includes latency/offline extras) |
| Sequential loops; assumed 0.55 | `pool.run_pool` uses spawn `ProcessPoolExecutor`; `choose_workers` uses measured RSS × 1.5 | `test_real_process_pool_pids_and_byte_equivalent_order`; `test_choose_workers_uses_measured_rss_not_512mib` | Train pool 8 distinct PIDs; tune 8; calib 4; `false_worker_claim=false` (`CAMPAIGN_RESOURCES.json`) |
| Admission probe too narrow | Admission exercises four family/depths, donor policies, five budgets, offline, calib worlds, one-vs-W | `test_config_1024_five_budgets_four_depths_seed_hierarchy` | `ADMISSION_PROBES.jsonl` 27 rows |
| C1 dense 2^n | `simulate_c1(..., allocate_dense=False)` | `test_c1_legal_subspace_no_dense_2n` | `IDEAL_DISTRIBUTIONS_INDEX.jsonl` |
| Hidden 64/256 draws | `POOL_DRAWS=1024` in scientific pools; miniature only uses 64 | config test | Limited-pilot mechanism pools record `pool_draws` 1024 in `MECHANISM_POOL_RESULTS.jsonl` |
| Energy-proxy donor labels | Sampled normalised regret from resampled pools | `test_donor_selector_labels_are_sampled_regret` | `DONOR_SELECTOR_TRAINING.jsonl` `label=sampled_normalised_regret_1024` |
| CLI stopped at `campaign_raw_complete` | Execute runs analysis, gates, report, manifest, verify | `test_cli_does_not_treat_raw_complete_as_success` | `RUN_RECEIPT.json` `not_campaign_raw_complete=true`; status is not `campaign_raw_complete` |
| Stale report filenames | `write_completion_report` reads `*_OPTION_RESULTS.jsonl` | `test_report_reader_option_results_filename` | this document |
| Projection used case-unit × n only | Component projection from measured per-world and circuit times | checksum_ok true on all ladders | `ADMISSION_RECEIPT.json` `formulas`, `projections.*.checksum_ok` |
| Copied 09806343 PARTITIONS schema | Always `build_a4_partitions()` | live `train`/`tune`/`calib` lists | `PARTITIONS.json` |

Focused tests on this commit: 72 passed, 1 deselected e2e (`tests/focused_receipt.json`). Full suite excluding e2e: passed on the development worktree before source push (259 passed / 1 skipped). Doctor exit 0. `pip check` clean.

## 5. Partitions, exclusions, row arithmetic, seeds, final-test

`PARTITIONS.json` registers 120 train / 80 tune / 24 calib / 24 anchors / 80 final-test IDs. Final-test outcomes were not materialised (`outcomes_opened=false`, `outcomes_materialised=false`). This campaign **did not execute** those full denominators.

Limited-pilot spec (`ADMISSION_RECEIPT.json` `limited_pilot_spec`, frozen in `PROTOCOL_FREEZE.json`):

| Quantity | Registered | Executed | Source |
|---|---:|---:|---|
| Train parents | 120 | 4 | `TRAINING_OPTION_RESULTS.jsonl` (8 SC/VSC children, 24 rows) |
| Tune parents | 80 | 4 | `TUNING_OPTION_RESULTS.jsonl` (24 rows) |
| Calib parents | 24 | 2 | `CALIBRATION_OPTION_RESULTS.jsonl` (12 rows) |
| Budgets | 5, 10, 30, 60, 120 | 30 only | freeze `nominal_budgets_s` |
| Policy seeds | 3 | 1 | freeze `n_policy_seeds` |
| Options before freeze | classical + 4 circuits | 3 then frozen C0_p2 + C1_p2 | `TUNING_FREEZE.json` |
| Pool draws | 1024 | 1024 (scientific); miniature diagnostics used 64 | config / mechanism rows |
| Portfolio K | 4 | 4 | freeze |
| Calib eval worlds | 2048 | 2048 | 24,576 stored paired worlds |
| Offline cases | 8 | 1 | `OFFLINE_REFERENCE.jsonl` |
| Noisy 40×4×10 panel | if model validates | 0 cases executed | `LOCAL_SYNTHETIC_NOISE_RESULTS.jsonl` |

Seed hierarchy: Phase 6 policy seed is the outer loop; `circuit_resample_seed` is derived 1:1; not 3×3. Stage 7’s ten seeds were not executed. `DEVIATIONS.json` records `limited_resource_pilot=true`.

## 6. Machine, process pool, memory, CPU, wall, admission

Machine (`CAMPAIGN_RESOURCES.json` `workers`): 10 logical CPUs, Darwin arm64, 25,769,803,776 B RAM, RAM limit 15,461,882,265 B (60%), measured peak worker RSS 1,076,592,640 B, safety 1.5×, 8 workers selected, spawn, BLAS 1 thread/worker. Assumed 512 MiB denominator replaced.

Admission probes (`ADMISSION_PROBES.jsonl`): prepare ~0.056 s; four family/depths ~7–10 s each at 1024-draw scientific pools on the authoritative path; donor policies ~7 s; five classical budgets ~7 s; offline 100 legal plans 242 s class historically / this admission measured `per_world_s≈0.610` and `per_eval_world_s≈0.598` (`projections.limited_resource_pilot.projection.components_s`). One-worker throughput 0.268 units/s; four-worker throughput 0.444; efficiency **0.503** (not 0.55). Distinct admission worker PIDs: 4. `false_worker_claim=false`.

Preferred/baseline/minimum 120/80/24 ladders all failed `projection_fits` (wall). Limited-pilot projection: serial conservative 20,752 s, wall 6,183 s, `fits=true` (`limited_pilot_spec.fit`). Realised campaign CPU 26,010 s (`CAMPAIGN_RESOURCES.json` `cpu_s`; includes children). Calib pool wall 5,949 s / CPU 21,667 s with 4 distinct PIDs. Train pool wall 156 s / 8 PIDs. Tune pool wall 447 s / 8 PIDs. Peak coordinator RSS 8,281,751,552 B. Wall cap 14,400 s; execute finished in ~8,124 s command elapsed. Disk reserve held.

Admission wall itself was 2,108 s including 72 focused tests (519 s).

## 7. Prepared-case, distribution, candidate, and continuation reuse

`PREPARED_CASES.jsonl` has 20 summaries (8 train + 8 tune + 4 calib). Worker `process_case_unit` prepares once per case and fails if `prepare_case_calls != 1` inside the worker. Distributions: 256 mechanism index rows; campaign-end counters `distribution_builds=368`, `resamples=264` (`MECHANISM_RESULTS.json`). Ideal distributions are keyed by prepared-case hash, family, depth, donor parameters, and simulator version. C1 uses legal-subspace probabilities. World outcomes for calibration persist 24,576 paired rows (`EVALUATION_WORLD_OUTCOMES.jsonl`).

## 8. Anchor / donor-bank integrity and donor selector

`REUSED_EVIDENCE.json` verifies `ANCHOR_FITS.jsonl` SHA-256 `b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a` from `09806343-…`. `DONOR_BANK_V2.json` is built from those fits (32 donors, four family/depth keys, ≤8 per key). Donor-selector training: 32 rows of sampled regret. Tuning: 160 policy-score rows. Selected policy by family/depth: all **fixed** (`DONOR_POLICY_SELECTION.json`). Frozen depths: `C0_p2`, `C1_p2` (`TUNING_FREEZE.json`, written 2026-09-22T00:31:09Z, `written_before_calibration=true`, hash `64c82b152ece259fcbf14a9915a7369dc5ec1c8d2323f57e94b5f6e52a2ff163`). In-sample learned scores are fit diagnostics only; the frozen operational donor policy is fixed.

## 9. Ideal mechanism panel and synthetic noise

`MECHANISM_POOL_RESULTS.jsonl` has 256 rows (4 train parents × 2 regimes × 4 family/depths × 8 donors) with 1,024-draw resampled pools and normalised regret versus exact proxy. Best-found variational reference remains a fixed-budget reference, not a certified quantum optimum. Synthetic noise model file was present and labelled `LOCAL_SYNTHETIC_NOISE`; the 40×4×10×1024 panel was **not executed** (`n_cases_executed=0`) because the full preferred corpus was not admitted. That is an exclusion of work, not fabricated IBM/device noise.

## 10. Complete action menu, matched K, quantum-incremental flow

Every prepared case enumerates the legal two-car menu. Matched K is four unique downstream slots including mandatory fallback; hybrid replaces rather than appends. Calibration option rows: 12. `BOUNDARY_RESULTS.json`: `n_portfolio_diff=8`, `n_executed_diff=0`, `harm_blocks=0`. Software Gate E counted `quantum_incremental_evaluated_cases=8` and `n_matched_k=12` (`RUN_RECEIPT.json` `GATE_E`). Portfolios can differ without changing the executed plan. No treatment-effect claim is made for the missing 120/80/24 cells.

## 11. Allocator, labels, tuning freeze

`ALLOCATOR_TRAINING_LABELS.jsonl`: 16 labels (independent-evaluation benefit, including zeros). Features include remaining laps, menu size, QUBO statistics, budget, and modelled latency (`option_feature_row`). `ALLOCATOR_MODEL.json` is a ridge fit (l2=1.0). Tuning freeze precedes calibration access (verifier `tuning_freeze_before_calibration` pass). Allowed options after freeze: `stop_fallback`, `classical_only`, `C0_p2`, `C1_p2`. Primary lambda 0. Dispatch threshold 0. Tie rule: min planning mean then lex plan hash. Strongest classical comparator: `classical_only`.

## 12. Calibration residual, q, MC allowance

`CALIBRATION_BLOCK_RESIDUALS.jsonl`: 8 child residuals. `CALIBRATION_MARGIN_Q.json`: n=2 block maxima, both 0.0, q=0.0, formula `ceil((n+1)*0.95)` clipped to n, `not_numpy_interpolated_percentile=true`, `is_maximum=true`. For a complete n=24 panel this index is the maximum residual; this run does not have 24 maxima. Independent verify recomputed q=0.0. Half-widths stored in `PRECISION_AND_STAGE7_SIZING.json` are all 0.0 on this tiny paired sample and must not be read as Monte Carlo certainty for Stage 7.

## 13. Offline all-plan reference and proxy disagreement

One offline case (`a4.calib.fam.green_pit_high.tyre_near_linear.traffic_dense.0000`, SC): `n_legal=100`, `n_legal_evaluated=100`, `all_plan_coverage=true`, `copied_from_arm=false`, planning and evaluation loss 0.02631578947368421 (`OFFLINE_REFERENCE.jsonl`). Eight registered offline cases were not run. Proxy/evaluation-simulator disagreement is central when proxy headroom is zero; this single case does not fill that table.

## 14. Timing composition, deadlines, isolated latency

Frozen scenario latency is keyed by case/option/budget/seed (`loop.py` / `timing.py`) and is not raw noisy wall time. Isolated local operational latency: 8 rows in `OPERATIONAL_LATENCY.jsonl` (`not_provider_latency=true`), two frozen packages × four of six intended cases (limited `latency_cases=2` in the spec vs 8 rows from 4 blocks × 2 packages in execute — execute used `lat_cases = train_blocks[:3] if miniature else train_blocks[:6]` even on the limited pilot, producing 4×2=8 measurements on the four train parents). No artificial sleeping to consume budgets. No paired turnaround divided by two.

## 15. Primary 30-second development/calibration effect

`PRIMARY_ANALYSIS.json`: parent-block effects `[0.0, 0.0]`, mean 0.0, 95% stratified block-bootstrap interval `[0.0, 0.0]`, n_boot=2000, seed `20260921`, n_blocks=2, budget 30 s, label `development_calibration_not_final_test`. With two identical zero effects the interval is degenerate. This is **not** final-test confirmation and **not** a powered development result.

## 16. Required ablations

`ABLATION_RESULTS.json` notes that ablation rows live in TUNING/TRAINING option results. Always-classical is the comparator. No-learned-donor is the actual frozen policy (fixed). Always-quantum is not an operational recommendation and was not a separate executed arm beyond diagnostic circuit options.

## 17. Per-family/regime boundary table and F1 meaning

On this limited green-flag high-pit near-linear dense family slice: portfolio differences 8, executed-plan differences 0, harm blocks 0. Simulated restricted-model checkpoints are not historical races. Zero executed-plan difference means the downstream scorer did not change the committed recommendation relative to classical on these four calibration children. That is an integration-boundary observation, not F1 operational readiness.

## 18. Monte Carlo precision, block variance, Stage 7 sizing

`PRECISION_AND_STAGE7_SIZING.json` recommends 2,048 worlds and 80 Stage 7 blocks with classification `powered_boundary_candidate` from n_observed_blocks=2 and s=0.0. **That classification is not scientifically usable**: s=0 from two zero effects under-states variance. Gate F correctly fails. If a later complete calibration panel were run, Stage 7 block sizing must be recomputed from 24 block effects using the dossier formulae, floor 80, ceiling 160.

## 19. Gate E derivation

Zero proxy headroom disables superiority (`PROXY_HEADROOM: ZERO`; `SUPERIORITY_PATH_AVAILABLE=false`). Software Gate E is `PASS_BOUNDARY_MECHANISM` because quantum-incremental candidates reached K on 8/12 matched calibration cells. Independently, executed plans did not differ from classical. Honest scientific reading: a **candidate-generation / reranking boundary question remains open as a design question**, but Phase 6 has **not** produced a complete matched-K experiment on the registered 120/80/24 panel. Do not advertise Gate E PASS as a completed negative/null Phase 6 on the full corpus.

## 20. Gate F derivation

`GATE_F_LOCAL_PRECISION_AND_RESOURCES=FAIL`. Reasons: 2/24 calibration parents; full ladders not admitted; limited-pilot q is n=2 not n=24; precision/sizing from a degenerate two-block sample; `PHASE_7_BOUNDARY_STUDY_READY=false`, operational false, superiority false. Resource basis: measured per-eval-world ≈ 0.60 s; 48 calib cases × 2048 worlds × five options cannot fit 86,400 CPU-s. The limited pilot’s 4 calib children × 2048 worlds × 3 options did fit the 4-hour wall (calib pool 5,949 s).

## 21. Claims allowed, prohibited, not yet literature-verified

Allowed (`CLAIMS_LEDGER.json`): local simulator mechanism description; engineering repair and admission measurement; development/calibration block effects labelled as such; a boundary-mechanism **question** for a future Phase 7 design.  
Prohibited: quantum advantage; F1 calibration; hardware readiness; unverified scientific novelty; IBM/device noise; provider latency; certified quantum optimum; final-test confirmation; superiority with zero proxy headroom.  
Novelty status: **not yet literature-verified**.

## 22. Failures, exclusions, deviations, unresolved limitations

- Full 120/80/24 corpus not executed.  
- Budgets 5/10/60/120 s not executed.  
- Policy seeds 2 and 3 not executed.  
- Offline 7/8 cases missing.  
- Noisy diagnostic 0/40 cases.  
- Calibration q uses n=2, not n=24.  
- Primary effect interval degenerate.  
- Pool heartbeat `completed` stayed 0 until futures returned (STALL dumps); workers were nevertheless running (verified by PIDs and later `n_ok`).  
- Heartbeat `elapsed_wall_s` used raw `perf_counter` (large offset), not campaign-relative time.  
- `LOCAL_SYNTHETIC_NOISE` panel skipped under the resource cap.  
- Missing observations were not replaced with zeros or copied historical values.  
- Miniature diagnostic UUIDs (`19a6c926`, `9e33748a`, others) are not this scientific run.

## 23. Tests, independent verification, manifests, hashes, reproduction

| Check | Result | Source |
|---|---|---|
| Focused A4+residual tests | 72 passed, 1 deselected, 519 s | `tests/focused_receipt.json` |
| Full suite except e2e | passed on source worktree before push | development worktree pytest |
| Doctor | ok | `tests/checks/doctor.txt` |
| pip check | no broken requirements | `tests/checks/pip_check.txt` |
| Independent verify | 45/45, ok | `FINAL_VERIFY.json`; CLI `--verify-run` |
| Pre-report verify | ok | `PRE_REPORT_VERIFY.json` |
| Manifest hashed files | 55/55 | `FINAL_VERIFY.json` `manifest_all_hashed` |
| Manifest SHA-256 | `5c85fd241f26572880605bb95b13ef5e2ddfc2d245e1ac326cb2a662d5865d8e` | `FINAL_PACKAGE_VERIFY.json` |
| Historical 09806343/3de109c7 | immutable, present | hash guards / verifier |

Reproduction **without rerunning the campaign**, from commit `a38bb29664b78cd5cb74a075f210f706878a0a9b` plus this evidence directory:

```text
python -m f1q.a4 --verify-run 0b697910-e8a2-474b-bc77-bc69ebb8e9c3
python -m f1q doctor
```

Do not resume `e85ee977`, `41c28597`, `fcbb3e38`, `3de109c7`, or `09806343`.

## 24. Phase 7 recommendation (not authorised)

**PHASE_7_AUTHORISED is false.** Phase 7 was not started. This attempt does not recommend opening final-test, hardware, or a superiority design. A later complete calibration panel would be required before any powered boundary study, and even then proxy headroom remains zero so superiority stays closed. A separate explicit user prompt is required for any Phase 7 work. Feasibility of a 4-hour limited pilot is not permission.

## Artifact index

All paths are under `evidence/stage6_a4/0b697910-e8a2-474b-bc77-bc69ebb8e9c3/` unless noted. Human report: `docs/PHASE_6_COMPLETION_REPORT.md`. Prospective amendment: `docs/PHASE_6_A4_IMPLEMENTATION_AND_RESOURCE_AMENDMENT.md`.

START_STATE.json, LINEAGE_AND_SUPERSESSION.json, IMPLEMENTATION_RESOURCE_AMENDMENT.json, REPAIR_TRACEABILITY.json, REUSED_EVIDENCE.json, PARTITIONS.json, RESOLVED_CONFIG.json, PROTOCOL_FREEZE.json, OPERATION_LEDGER.json, ADMISSION_PROBES.jsonl, ADMISSION_RECEIPT.json, PROCESS_AND_MEMORY_EVIDENCE.json, PREPARED_CASES.jsonl, DONOR_BANK_V2.json, IDEAL_DISTRIBUTIONS_INDEX.jsonl, DONOR_SELECTOR_TRAINING.jsonl, DONOR_SELECTOR_TUNING.jsonl, DONOR_SELECTOR_MODELS.json, DONOR_POLICY_SELECTION.json, MECHANISM_POOL_RESULTS.jsonl, LOCAL_SYNTHETIC_NOISE_RESULTS.jsonl, ALLOCATOR_TRAINING_LABELS.jsonl, ALLOCATOR_MODEL.json, TRAINING_OPTION_RESULTS.jsonl, TUNING_OPTION_RESULTS.jsonl, TUNING_FREEZE.json, CALIBRATION_OPTION_RESULTS.jsonl, CALIBRATION_BLOCK_RESIDUALS.jsonl, CALIBRATION_MARGIN_Q.json, EVALUATION_WORLD_OUTCOMES.jsonl, OFFLINE_REFERENCE.jsonl, OPERATIONAL_LATENCY.jsonl, PRIMARY_ANALYSIS.json, MECHANISM_RESULTS.json, ABLATION_RESULTS.json, BOUNDARY_RESULTS.json, PRECISION_AND_STAGE7_SIZING.json, CAMPAIGN_RESOURCES.json, DEVIATIONS.json, CLAIMS_LEDGER.json, PRE_REPORT_VERIFY.json, RUN_RECEIPT.json, MANIFEST.json, FINAL_VERIFY.json, FINAL_PACKAGE_VERIFY.json, HEARTBEATS.jsonl, tests/focused_receipt.json.

---

Generated from verified artifacts under `evidence/stage6_a4/0b697910-e8a2-474b-bc77-bc69ebb8e9c3/` after `python -m f1q.a4 --verify-run 0b697910-e8a2-474b-bc77-bc69ebb8e9c3` returned ok.
