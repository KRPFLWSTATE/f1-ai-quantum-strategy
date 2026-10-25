# Design R six-hour attempt — engineering closure

Run `ed37296f-55c5-44e5-8ffd-77410d4789de` was **not admitted**. The registered 120/80/24 corpus was not started. Design F was not launched. Phase 7 was not started. This is not a completed Phase 6 scientific result, not Gate E, and not Gate F.

The amendment was written and committed before this measurement. It did not relabel the earlier 13,981.679-second estimate as an authorised admission.

## Decision

`NONE_RESOURCE_LIMIT`. `admitted=false`.

Failing gates, from `evidence/stage6_a4/ed37296f-55c5-44e5-8ffd-77410d4789de/ADMISSION_DECISION.json`:

| Gate | Result | Observed |
|---|---|---|
| Literal parity | pass | 3,072/3,072 exact signatures, 0 mismatches |
| Kernel `compiled-event-loop-2` | pass | sha256 `a763fe1bc041f77a4ed7f06978eaf2dfd48a468205d8b675988224afd8a7818f` |
| Candidate path scalar fallback | pass | 0 `continue_to_finish` calls on the candidate side |
| Crafted quantum plan executed | pass | engineering fixture, 2 worlds, kernel `compiled-event-loop-2` |
| Doctor | pass | exit 0 |
| Clean-extract miniature | pass | exit 0, tuning freeze present |
| K applied once | pass | plan-world evaluations 202,016 |
| Numba 0.68.0 | pass | |
| Eight workers | pass | |
| Design F not launched | pass | |
| RAM | pass | simultaneous RSS 4,181,278,720 bytes; 60% of 25,769,803,776 is 15,461,882,265 |
| Preflight wall of the completed process | pass | 3,371.024 s, under 7,200 s |
| Full tests | fail | pytest exit 1 |
| Sealed split | fail | six registered parents opened by engineering miniatures |
| Conservative CPU | fail | 87,554.494 s against 86,400 s |
| Admission wall | fail | 28,414.701 s against 17,280 s |
| Campaign wall | fail | 28,414.701 s against 21,600 s |
| Disk reserve | fail | formula storage 175,246,046,400 bytes; 80% of free disk 111,525,814,272 is 89,220,651,418 |

Any one of the resource failures was enough to stop. The corpus was not started.

## Source

Worktree `/Users/kawinperera/f1-ai-quantum-strategy-design-r-six-hour`, branch `phase6-design-r-six-hour`, created from `origin/route1-parity-capacity-decision` at `20a3729213e756d58223beacdaa7700d077e82f4`. That remote had no later descendants. `origin/main` was `53ce10d187c2140511c7419863b5447119496a77`.

Reviewed source commit for the admission: `79899879809bbd63774b0c27f8a7b7be315c18a4`. Amendment commit: `d12be15362dcea5381baff1ca3fe323645044ad2`.

Amendment file sha256 `791b949d5982e9f5d91d35c88a901f790f25e7343c1854d893c7a172d09e0c1b`. Configuration sha256 `9754ae22adbcefe554766de8a6c64a43870a772e262364ca532b8be72135b97a`. Decision sha256 `46bedf5eecc3800a9ae852707a0661c1a157b004205c7f7913301d09421f7771`.

The evidence commit that adds this report is not written into this file.

## What was remeasured

Synthetic `engperf` fixtures only. No `a4.v2` parent was used for the rate panel.

Steady paired ratios on 16 family×regime checkpoints, 3 plans × 8 worlds, after one warmup cell: minimum 10.977800873883242, maximum 22.25159999640642. The carried 22.902642628995448 ratio was not used. The slowest measured compiled cell was 0.05439143054536544 seconds. Race cells 965,048 × that cell time = 52,490.341 accelerated seconds.

Distribution builds, three repetitions, conservative maximum: C0 depth 1, 2.522303916979581 s; C0 depth 2, 2.592881709104404 s; C1 depth 1, 0.06775095919147134 s; C1 depth 2, 0.004628750029951334 s. Charged builds 3,840. Build CPU 4,980.063 s.

Thirty C0 depth-2 resamples of 1,024 draws: conservative 0.0860315840691328 s each. Charged resamples 116,800. Resample CPU 10,048.489 s.

Eight-worker efficiency was recomputed from the Route 1 raw waves, not from the fresh RSS probe: minimum of three steady ratios, 0.46288885835714266. Cold-start wall from those waves: 42.503465499030426 s. Ten workers were not reused. Twelve were not measured.

Under-prediction multiplier kept at 26010/20752 = 1.253373168851195. A smaller factor was not used.

Optimiser charge uses the Route 1 raw conservative fit times, 120 × each of the four depths: 2,299.162 s. Prepare stays the carried 36.157 s.

Fresh eight-worker simultaneous RSS on the 192-cell mix: 4,181,278,720 bytes. Scalar continuation calls in that probe were 0.

## Ledger the checker recounted

| Quantity | Count |
|---|---:|
| Train / tune / calib parents in the frozen split | 120 / 80 / 24 |
| Parents executed by this run | 0 / 0 / 0 |
| Plan-world evaluations, K applied once | 202,016 |
| Evaluation worlds | 750,232 |
| Offline all-plan continuations | 12,800 = 8 × 100 × 16 |
| Mechanism policy rows | 72,000 |
| Mechanism checkpoints | 120 |
| Donor-label resamples charged inside the 116,800 | 115,200 |
| Unique parameter builds | 3,840 |
| 2,400 builds proven by complete identities | no |
| Ablation specifications | 7 |
| Ablation rows in the unit ledger | 168 |
| Best-found fit charge | 480 |
| Portfolio K | 4 |
| Pool draws | 1,024 |
| Budgets | 5, 10, 30, 60, 120 |
| Train/tune policy seeds | 3 |
| Calibration policy seeds in the Design R ledger | 1 |
| Primary calibration worlds | 2,048 |
| Sensitivity worlds | 128 |

Point CPU 69,855.089 s. Conservative CPU 87,554.494 s. Steady wall 28,372.197 s. Admission wall, including cold start, 28,414.701 s.

There is no campaign actual, so projection error is not defined. q is not defined. The paired block estimand is not defined.

## Sealed-split defect

Pytest during preflight wrote two miniature engineering runs into this worktree, `cdd21ec6-9d95-48a5-806b-64fd7e296434` and `eeb03bdd-4fdf-4e1e-baf6-590b54c11d4a`. Each has `miniature=true` and `selected_design=MINIATURE`. Each opened these six registered parents:

- `a4.v2.train.fam.green_pit_high.tyre_near_linear.traffic_dense.0000`
- `a4.v2.train.fam.green_pit_high.tyre_near_linear.traffic_dense.0001`
- `a4.v2.tune.fam.green_pit_high.tyre_near_linear.traffic_dense.0000`
- `a4.v2.tune.fam.green_pit_high.tyre_near_linear.traffic_dense.0001`
- `a4.v2.calib.fam.green_pit_high.tyre_near_linear.traffic_dense.0000`
- `a4.v2.calib.fam.green_pit_high.tyre_near_linear.traffic_dense.0001`

Those files are engineering fixtures. They are not the Design R corpus and their losses are not effects. Because registered outcomes were opened, this split is not clean for a later scientific use. A fresh disjoint 120/80/24 split was not built. The CPU and wall gates had already failed, and the prompt forbids an automatic retry. World chunks from that miniature were moved, not deleted, to `evidence/stage6_a4/engineering_byproducts/worlds`.

The same pytest overwrote `docs/PHASE_6_COMPLETION_REPORT.md`, `docs/PHASE_6_VALIDATED_CLOSURE_REPORT.md`, and `docs/evidence/stage4_2/stage3_3_regression_diagnostic.json`. Those three files were restored from `79899879809bbd63774b0c27f8a7b7be315c18a4` before this report was added. Historical evidence trees for Stage 5, the earlier Phase 6 runs, A3, the feasibility packet, and the Route 1 packet were not modified.

Full pytest: exit 1. The only failure was `tests/a4/test_six_hour_amendment.py::test_registered_split_is_sealed`, which observed the miniature files above. The progress line showed two skips.

## Time

Completed admission process: wall 3,371.024 s, CPU 4,972.329 s. An earlier process crashed after the parity panel and the first rate panel because the scalar timing leg was counted as a fallback. That process lasted about 2,206 s and did not open the corpus. Cumulative foreground engineering wall is about 5,577 s, inside the 7,200-second preflight cap. None of that time is campaign time.

Campaign CPU, campaign wall, and campaign RAM were not measured because the campaign did not start.

## Gates and readiness

`PROXY_HEADROOM: ZERO`.

`GATE_E_SCIENTIFIC_VALUE: UNCLAIMED_RESOURCE_LIMIT`. No Design R rows exist from which to derive it.

`GATE_F_LOCAL_PRECISION_AND_RESOURCES: FAIL`. The projected Design R envelope does not fit the amended caps.

`PHASE_7_DESIGN_READY: false`. `PHASE_7_AUTHORISED: false`. `PHASE_7_BOUNDARY_STUDY_READY: false`. `PHASE_7_SUPERIORITY_READY: false`.

`FINAL_TEST_ACCESSED: false`. Final-test id sha256 `0053bce4f6001e51e3382df82691451392b458bb7328a84e577c661d87adb74e`. Outcomes were not read.

`QPU_JOBS: 0`. `QPU_EXECUTION_AUTHORISED: false`. No money was spent.

`REGISTERED_SCIENTIFIC_PARENTS_EXECUTED: 0` for this run id. The six parent ids above were opened only inside the two miniatures.

## What this does not claim

The study was not executed. A negative quantum result was not produced. The earlier resource stop `fc5f0e00-d9e0-4f89-9eea-498461094969` remains historical and incomplete. The Route 1 decision remains `ENGINEERING_NOT_FEASIBLE_WITHIN_CURRENT_ENVELOPE` under the old 11,520-second wall. This attempt does not complete either of them.
