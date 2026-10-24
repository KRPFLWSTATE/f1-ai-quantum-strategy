# Route 1 parity and capacity decision

Engineering check only. This file does not replace `docs/SIMULATOR_PERFORMANCE_FEASIBILITY_REPORT.md` and does not alter run `3c44b59e-7065-4899-9977-1fae0cb9d88f`.

**Decision: `ENGINEERING_NOT_FEASIBLE_WITHIN_CURRENT_ENVELOPE`.**

Literal event-signature parity on the existing 32-checkpoint panel is 3,072/3,072. Production selection still defaults to the scalar `RaceEngine`. No measured worker count puts a complete conservative Design R estimate inside every frozen limit. Design F still fails the 86,400-second CPU cap. Design F and Design R were not admitted. Phase 7 was not started. The registered 120/80/24 corpus was not executed.

The failing gate is admission wall. At the conservative eight-worker efficiency 0.46288885835714266, Design R admission wall is 13,981.679 seconds against the frozen 11,520-second limit. At ten workers the conservative efficiency is 0.3565956968715956 and the admission wall is 14,549.330 seconds. Design R CPU at that count is 43,085.633 seconds. Twelve workers were not measured: this machine has 10 physical and 10 logical CPUs.

## Source provenance

Worktree branch `route1-parity-capacity-decision`, created from `5b7b28c96790d3571a684ff3959cfd9754ef7979` (`origin/simulator-performance-feasibility`). Remote `https://github.com/KRPFLWSTATE/f1-ai-quantum-strategy.git`. `origin/main` remains `53ce10d187c2140511c7419863b5447119496a77`.

Kernel correction commit: `179b95197395044b8dcb5f9c39b032c13518f75a`. Kernel file sha256 `a763fe1bc041f77a4ed7f06978eaf2dfd48a468205d8b675988224afd8a7818f`. Kernel version `compiled-event-loop-2`. The exponent 2 is a Python argument into the compiled entry so Numba does not rewrite it to a multiply. Numba 0.68.0, llvmlite 0.50.0, NumPy 2.5.3. `fastmath` remains disabled.

Evidence directory: `evidence/performance_feasibility_followup/1d1b3499-2ff1-440a-ba33-d45212b31b83/`. The commit that adds this report is the evidence commit; this file cannot contain that hash.

## Parity

| Panel | Cells | Exact event-signature matches | Mismatches |
|---|---:|---:|---:|
| Previous, commit `6796a144` | 3,072 | 3,071 | 1 |
| This correction, commit `179b951` | 3,072 | 3,072 | 0 |

The previous mismatch remains on the preserved receipt: `engperf.corr.fam.green_pit_low.tyre_nonlinear.traffic_dense.SC.r1`, plan index 1, world seed 810007. Loss was identical. Commitment was `recommendation`. Event count was 262. Rounded event times and event order matched. Four detail fields differed.

The new panel used the same fixture plan shape (`engperf.fixture.v1` identifiers, 32 checkpoints, three plans, 32 worlds). Loss tolerance stayed 1e-12 and was not used to accept a signature. `PARITY_SUMMARY.json` records `exact_signature_mismatches: 0`. Paired checkpoint ratios on this run span 3.1706 to 34.137 and include cold compilation in the worker pool. They are not a steady speedup and are not substituted for the prior steady minimum 22.902642628995448.

Candidate waves in the capacity measurement recorded `scalar_continue_calls: 0`. The default backend remains legacy. The cache key includes `compiled-event-loop-2`.

## First divergence

On the uncorrected kernel, binary search of scalar ticks against compiled steps found the first state difference at continuation step 1542. The only difference was `car.fictional.redcliff.a` speed, 0.010719300096899897 versus 0.010719300096899895. The state after step 1541 matched, including time 1281.5646651770023 seconds and regime GREEN. The last equal event was an overtake at 1249.564665177 seconds.

At that matched state the car's tyre age was 4.2173155760694305 laps. Scalar `tyre_delta_s` forms the nonlinear term as `(curvature * curve_scale) * (age ** 2)`. The compiled `_free_lap` formed `((curvature * curve_scale) * age) * age`. Those associations differ by 1.1102230246251565e-16 in the quadratic piece and by one unit in the last place of the lap time (1.4210854715202004e-14 seconds on a value near 93.29 seconds). The reciprocal speed then differs by one unit in the last place. The compiled assembly is separate `fmul` and `fadd` instructions, not a fused multiply-add. With `NUMBA_DISABLE_JIT=1` the same source association remains, so the drift is the port's operation order. A literal `** 2` inside `@njit` is rewritten to a multiply and does not match CPython `pow` on every age; the exponent is therefore an argument of the compiled entry.

The three later `pre_pass_gap_laps` differences were 1.7763568394002505e-15, 1.7763568394002505e-15, and 3.552713678800501e-15 laps. The leader-finish detail time differed by 9.094947017729282e-13 seconds (`1978.9803415187453` versus `1978.9803415187462`). After this single change, that cell's literal signatures match under both the compiled kernel and the Numba interpreter, so those four detail gaps are the propagated speed difference, not separate physics changes. The scalar `RaceEngine` and its 1e-12 loss tolerance were not modified. Event details are not rounded. The pace polynomial still uses `age * age` on both sides, matching `_pace_poly`.

`tests/a4/test_simulator_performance_feasibility.py::test_known_signature_mismatch_cell_and_power_boundary` reruns world seeds 810006, 810007, and 810008 on that plan and checks compiled free-lap time against `free_lap_time_s` on ages where `age * age` differs from `age ** 2`. Focused pytest of that module plus `tests/a4/test_corrected_cost.py`: 23 passed.

## Capacity

Machine: 10 physical CPUs, 10 logical CPUs, 25,769,803,776 bytes RAM. Twelve workers would oversubscribe and were not run.

Each task is 192 synthetic candidate cells: eight `engperf` families, SC and VSC, three legal plans, worlds 810000–810003. Three fresh process-pool repetitions. Each repetition ran a one-worker baseline and pools of eight and ten. Each pool ran two waves. Wave 0 includes process startup and compilation. Wave 1 is the steady wave. Efficiency is that repetition's solo steady makespan divided by the parallel steady makespan. The conservative efficiency is the minimum of the three repetitions, not the fastest.

| Workers | Rep 0 | Rep 1 | Rep 2 | Conservative efficiency |
|---:|---:|---:|---:|---:|
| 8 | 0.4628888584 | 0.4684804562 | 0.4943740877 | 0.46288885835714266 |
| 10 | 0.3741512979 | 0.3565956969 | 0.3940335710 | 0.3565956968715956 |
| 12 | not measured | not measured | not measured | excluded |

Solo steady makespans were 4.841103, 4.859839, and 5.136344 seconds. Eight-worker steady makespans were 10.458457, 10.373621, and 10.389589 seconds. Ten-worker steady makespans were 12.938892, 13.628427, and 13.035294 seconds. Ten workers use every logical CPU while the parent blocks in the pool; that configuration was measured and is not an extrapolation from eight.

Simultaneous parent-plus-worker RSS, maximum sample in each configuration: eight workers 3,585,376,256 bytes; ten workers 4,216,307,712 bytes. Sixty percent of RAM is 15,461,882,266 bytes. Both samples are inside that limit. These are simultaneous samples, not sums of peaks.

## Fits and the corrected ledger

Saved Design R ledger `evidence/stage6_a4/fc5f0e00-d9e0-4f89-9eea-498461094969/OPERATION_LEDGER.json`, read only: 87,548 units; planning-world charge 202,016; evaluation worlds 750,232; mechanism resamples 72,000. Best-found rows are 3,600 resamples in each of `C0_p1`, `C0_p2`, `C1_p1`, and `C1_p2`, which is 120 fits per family/depth at 30 resamples per fit, 480 fits. Design F's saved aggregate is planning 403,808 and evaluation worlds 3,235,096, with the same 72,000 resamples. No registered parent was executed.

COBYLA cap 40 objective evaluations, three repetitions, engineering menu `engperf.fit...` (100 legal rows). Conservative time is the slowest repetition:

| Fit | Conservative `fit_s` | Evals on that repetition |
|---|---:|---:|
| C0 depth 1 | 6.642744290875271 | 40 |
| C0 depth 2 | 12.135290416888893 | 40 |
| C1 depth 1 | 0.1898229168727994 | 40 |
| C1 depth 2 | 0.1918244999833405 | 40 |

Optimiser total: 120 times each of those values = 2,299.162 seconds. The previous single C0 depth-2 time of 12.149 seconds applied to all 480 fits (5,831.741 seconds) is not reused.

Donor-policy selection on a four-donor list, 100 calls each: the slowest mean was `random` at 1.2142499908804893e-5 seconds per call. Charged once per mechanism row: 72,000 times that value = 0.874 seconds. One ridge ranker fit was 0.000710 seconds; four family/depth fits are 0.002838 seconds.

Distribution-build and resample seconds are the previous engineering measurements, not repeated here: builds 3,430.012 seconds (600 of each family/depth) and resamples 3,188.950 seconds. Prepare stays 36.157 seconds for R and 72.314 seconds for F. Offline expansion stays the published closure count `n_legal_measured = 100`: 8 cases times 100 plans times 16 worlds = 12,800 continuations at the planning rate. Race seconds before the speedup reconcile to the previous corrected total, 575,973.340 seconds for R.

The race term is divided by the previous steady minimum speedup 22.902642628995448. The historical under-prediction factor 26,010 / 20,752 = 1.253373168851195 is applied once. Steady wall is `conservative_cpu / (workers * efficiency) * 1.20`. The measured cold-start wall, `max(cold makespan - steady makespan)`, is then added once. Dropping that startup term still leaves the eight-worker admission wall at 13,939.176 seconds.

| Design | Workers | Conservative CPU | Within 86,400 s | Admission wall | Within 11,520 s | Campaign wall | Within 14,400 s | Simultaneous RSS within 60% |
|---|---:|---:|---|---:|---|---:|---|---|
| R | 8 | 43,015.261 s | yes | 13,981.679 s | no | 13,981.679 s | yes | yes |
| R | 10 | 43,085.633 s | yes | 14,549.330 s | no | 14,549.330 s | no | yes |
| F | 8 | 130,827.546 s | no | 42,437.414 s | no | 42,437.414 s | no | yes |
| F | 10 | 130,897.918 s | no | 44,099.530 s | no | 44,099.530 s | no | yes |

Design F was not launched. The ten-worker and twelve-worker planning thresholds 0.4914 and 0.4095 are not measured efficiencies. The measured ten-worker efficiency is below 0.4914.

## Engineering time

Previous Route 1 package: 1,455.79 wall seconds and 5,404.79 CPU seconds. This continuation, including compilation, tests, short probes, the parity panel (`/usr/bin/time`: 765.41 real, 2,938.98 user, 27.15 sys), and the capacity command (538.26 real, 2,404.44 user, 122.23 sys): 1,400.258 wall seconds and 5,586.258 CPU seconds. Cumulative: 2,856.048 wall seconds and 10,991.048 CPU seconds, inside 7,200 and 14,400. Short probes without separate process-time records are charged at wall.

## What this does not claim

This is not Gate E, not Gate F, and not a Phase 7 design. Synthetic losses are not scientific effects. No registered `a4.v2` parent was executed. Final-test outcomes were not opened. No QPU job was submitted. No money was spent. The empirical study was not archived.

`PHASE_7_DESIGN_READY=false`. `REGISTERED_SCIENTIFIC_PARENTS_EXECUTED=0`. `FINAL_TEST_ACCESSED=false`. `QPU_JOBS=0`.

Preserved hashes, rechecked after this work: feasibility report sha256 `8696f92a4ce6c0a587203e5ad0721cdb8c3805b437a16703b54bd1dbf5881bf7`; manifest `b934fc0c09551d567450b63275ce33d9cc258e460f4f964f2719c878bd700cbd`; fixture plan `ca66ad0c35ae29fa7ff9ca99708bc98bfb37638d89178e5afe71232ea62c3453`. Sibling checkouts `simulator-performance-feasibility` at `5b7b28c` and `post-phase6-evidence-disposition` at `85c5d88` were clean. `git diff 5b7b28c` on the frozen evidence paths in this worktree is empty.

Residual uncertainty: build and resample times were not repeated; the 22.90 race ratio was not remeasured on steady paired cells of this commit; offline legal-plan count 100 is the published closure figure; ten workers leave no idle logical CPU for the operating system; the fit sample is three repetitions of one engineering menu.
