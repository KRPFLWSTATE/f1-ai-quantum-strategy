# Simulator performance feasibility

Engineering task only. Run directory `evidence/performance_feasibility/3c44b59e-7065-4899-9977-1fae0cb9d88f`. Candidate source commit `6796a144bd0b3da4eeeaa0dbd27f2c64497192fc`. This file cannot contain the commit that adds it.

**Decision: `ENGINEERING_FEASIBILITY_NOT_DEMONSTRATED`.**

Exact event-signature parity fails on 1 of 3,072 synthetic cells. Design F's race term, after the slowest paired speedup, is already above 86,400 CPU seconds. Design R's conservative CPU is inside 86,400 seconds, and its campaign wall is inside 14,400 seconds, but its admission wall at the measured eight-worker efficiency is 14,072 seconds, above the 11,520-second admission limit. No tolerance was widened. Design F and Design R were not launched. Phase 7 was not started. The registered 120/80/24 corpus was not executed.

## What was implemented

The historical projection in `f1q.a4.completion._project_from_probes` is unchanged, so published receipts still reproduce.

A separate model, `f1q.a4.corrected_cost`, counts each plan-world evaluation once, separates distribution builds from resamples, and refuses a wall claim at a worker count whose efficiency was not measured.

The production default remains the scalar `RaceEngine`. `evaluate_candidates_on_bank` calls that path unless `select_evaluation_backend("candidate")` is set. The candidate is a Numba event loop (`f1q.simulator.compiled_kernel`, version `compiled-event-loop-1`, `fastmath=False`, Numba 0.68.0, llvmlite 0.50.0, NumPy 2.5.3). It replaces `continue_to_finish` after the checkpoint. Commitment and the short pre-commit advance stay on the scalar engine. The scalar engine source was not rewritten. There is no silent scalar fallback inside the candidate: an unsupported state raises.

The pre-implementation profile (`PROFILE_SUMMARY.json`) put 19.6 of 20.2 seconds inside `continue_to_finish` / `tick` (23,847 ticks). `update_intents`, `speeds`, `step_motion`, and `next_events` dominate. Deep copy and restore were not in the top of the profile.

## Preserved model behaviour

Timestep, event priority, tyre and fuel formulae, pit deadlines, crew stacking, and the hidden-world rule are the same operations the scalar engine uses. `apply_hidden_world` still varies only interruption duration. Traffic remains a family factor. Service duration remains deterministic. Fast-math contraction was disabled. Logging was not removed. The candidate cache key adds the kernel version and does not change the legacy cache-key bytes.

## Parity and coverage

Fixture plan `engperf.fixture.v1` (sha256 `ca66ad0c35ae29fa7ff9ca99708bc98bfb37638d89178e5afe71232ea62c3453`): eight families, SC and VSC, 32 checkpoints, three legal plans, 32 world seeds. Identifiers use the `engperf` prefix and are disjoint from registered scientific parents.

| Panel | Cells | Exact event-signature matches | Mismatches |
|---|---:|---:|---:|
| Correctness, 32 checkpoints × 3 plans × 32 worlds | 3,072 | 3,071 | 1 |

The mismatch is `engperf.corr.fam.green_pit_low.tyre_nonlinear.traffic_dense.SC.r1`, plan index 1, world seed 810007. Loss is identical (`0.02631578947368421`). Commitment is `recommendation` on both sides. Event count is 262 on both sides. Rounded event times and event order match. Four detail fields differ: three `pre_pass_gap_laps` values differ by about 1.8e-15 laps, and the leader-finish detail time differs by about 9e-13 seconds (`1978.9803415187453` versus `1978.9803415187462`). The same difference appears with Numba disabled, so it is in the reimplemented arithmetic, not only in code generation. The project's exact `event_ordering` equality fails. The 1e-12 numeric tolerance was not used to declare that cell a pass.

Pytest on this commit's tests: `tests/a4/test_corrected_cost.py` and `tests/a4/test_simulator_performance_feasibility.py`, 22 passed. Those tests reject a perturbed loss, a swapped event, and the old K-again multiplier, each independently. A candidate call did not enter `RaceEngine.continue_to_finish`. Cold import of the candidate module in a fresh process succeeded. Shared-crew pit entry and service completion matched the scalar path on the unit fixture. No unsupported-path fallback was taken on the 3,072-cell panel.

## Corrected costs

Enumerated from the saved `fc5f0e00` partition metadata, without executing parents. Aggregates match the published ledgers: Design R planning evaluations 202,016 and evaluation worlds 750,232; Design F 403,808 and 3,235,096. Mechanism rows are 72,000. Unique build identities, keeping donor-policy names distinct because parameters are not stored as equal, are 2,400. Resamples are 72,000. The historical `120 × 4 × 8 = 3,840` expression is a different formula and is not the unique-key count.

Published point rates kept for the race terms: 0.5963212737939708 seconds per planning/offline continuation and 0.5969806534829445 seconds per evaluation world. The extra factor of K is removed. The slowest steady paired checkpoint ratio, 22.902642628995448, is applied to those race terms. It is not the fastest family (35.05) and not the compile-contaminated checkpoints.

Synthetic build times on one engineering menu (`n = 20`): C0 depth 1, 2.612 seconds; C0 depth 2, 3.087 seconds; C1 depth 1, 0.00757 seconds; C1 depth 2, 0.00997 seconds. Six hundred builds of each family/depth give 3,430 seconds. Thirty resamples of a C0 distribution cost 0.044291 seconds each, so 72,000 resamples cost 3,189 seconds. One C0 depth-2 COBYLA fit used 40 objective evaluations in 12.149 seconds. Applying that single fit time to all 480 best-found fits is an upper bound of 5,832 seconds, not a measurement of every fit. Historical prepare components are kept: 36.16 seconds (R) and 72.31 seconds (F).

The historical under-prediction multiplier 26,010 / 20,752 = 1.253373168851195 is applied once. Eight-worker efficiency is the measured value on 192-cell tasks: solo steady wall 4.290 seconds, slowest concurrent steady wall 8.533 seconds, efficiency 0.5028117175436765, speedup 4.022. A smaller 24-cell task gave efficiency 0.574 and is not the figure used below. Sum of eight peak RSS values on the 192-cell tasks: 3,155,509,248 bytes. Sixty percent of 25,769,803,776 bytes is 15,461,882,266 bytes. The measured sum is inside that limit. It is a sum of peaks, not a simultaneous sample.

| Design | Conservative CPU | Within 86,400 s | Conservative admission wall | Within 11,520 s |
|---|---:|---|---:|---|
| R | 47,171.5 s (13.10 h) | yes | 14,072.3 s (3.91 h) | no |
| F | 134,983.8 s (37.50 h) | no | 40,268.7 s (11.19 h) | no |

Design R campaign wall at the same formula is 14,072 seconds, which is inside 14,400 seconds and outside 11,520 seconds. Dropping the unmeasured optimiser upper bound entirely still leaves Design R's admission wall near 11,891 seconds. The wall failure is not created by that upper bound.

Infinite-kernel floor for Design R, with the same fixed terms and the optimiser upper bound, is 15,651 CPU seconds and 4,669 wall seconds. The floor is inside the envelope. The measured kernel is not. Design F's accelerated race term alone, after the 22.90 ratio and before the multiplier, is 95,173 seconds.

## Speed

Profile panel, cProfile, before the kernel: about 1.7 seconds per cell because the profiler was on. Unprofiled scalar cells on the parity panel average 0.863 seconds. Steady candidate cells on the same checkpoints average 0.0341 seconds. Ratio across 28 compile-excluded checkpoints: 22.90 to 35.05.

Timing fixture `engperf.time.*`, separate identifiers: cold candidate call 13.20 seconds for 12 cells, including compilation. Three steady repetitions of 24 cells: 0.620, 0.625, and 0.619 seconds. Paired scalar on 12 SC cells of that fixture: 6.585 seconds (0.549 seconds per cell). Candidate-only larger batches, three plans, one regime: 128 worlds 8.87 seconds (384 cells), 512 worlds 35.46 seconds (1,536 cells), 2,048 worlds 141.14 seconds (6,144 cells), about 0.023 seconds per cell. No scalar run was launched at 512 or 2,048 worlds.

Whole-workload speed is not the kernel ratio. After the corrected counts, the multiplier, and the measured efficiency, Design R is still outside the admission wall and Design F is outside the CPU cap.

## Limits on the claim

This is not a Phase 6 result, not Gate E, not Gate F, and not a Phase 7 design. Synthetic losses are not scientific effects. The one limited-pilot software Gate E remains invalid for closure. No registered `a4.v2` parent was executed. Final-test outcomes were not opened. No QPU job was submitted. No money was spent. The empirical study was not archived, and `docs/CONTINUATION_CONTRACT_DRAFT.md` was not executed.

`python -m f1q status` in this worktree still reports an older Phase 6 label and `next_permitted_work` of bootstrap. `fc5f0e00` has no `readiness.json`, and `evidence/var/ledger.sqlite` is absent here. That status output is not authorisation. A separate ledger on the older main checkout was read only; it was not modified and its runs were not resumed.

Remaining uncertainty: the 1e-15 lap drift was not removed; C1 variational fits were not timed separately; eight-worker RSS is a sum of peaks; the 22.90 ratio was measured on these synthetic horizons and applied to the historical race totals rather than by re-running the registered parents.

## Precise next decision

Do not admit Design F or Design R on this measurement. Do not start Phase 7. Do not open the corpus. Do not treat this package as a kernel revision authorisation. A further revision would be a new explicit decision, and this task does not start one. The empirical study remains unarchived and unexecuted.
