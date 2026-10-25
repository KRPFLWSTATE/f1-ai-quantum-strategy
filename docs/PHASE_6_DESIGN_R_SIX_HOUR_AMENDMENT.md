# Prospective six-hour Design R amendment

Written before any registered `a4.v2` training, tuning, or calibration outcome of run `ed37296f-55c5-44e5-8ffd-77410d4789de` is opened. This file does not rewrite the dossier, does not edit run `fc5f0e00-d9e0-4f89-9eea-498461094969`, and does not relabel that run's 13,981.679-second admission-wall estimate as an authorised admission.

## What changes

One local resource limit changes.

| Limit | Previous frozen value | This attempt |
|---|---:|---:|
| Campaign CPU | 86,400 s | 86,400 s (retained) |
| RAM | 60% of physical | 60% (retained) |
| Disk reserve | 20% of free disk | 20% (retained) |
| Wall reserve | 20% | 20% (retained) |
| Campaign wall | 14,400 s | **21,600 s (six hours)** |
| Admission wall | 11,520 s | **17,280 s = 0.8 × 21,600** |

Design F stays excluded. It still exceeds 86,400 CPU seconds on the corrected ledger. Design R remains the specified 120/80/24 boundary study: one outcome-blind checkpoint per parent, five budgets, three train/tune policy seeds, 1,024 draws, matched K=4, four family/depth candidates, a 120-case mechanism panel with 30 resampling seeds, calibration primary at 30 seconds with 2,048 paired worlds, exploratory 128-world sensitivities excluded from the primary q, and the one-sided 95% q equal to the maximum of 24 parent-block maxima. It does not test quantum superiority.

## Identity

- Amendment id: `design_r_six_hour_20261025`
- Run id: `ed37296f-55c5-44e5-8ffd-77410d4789de`
- Machine-readable configuration: `configs/stage6_a4_design_r_six_hour.yaml`
- Source branch created from `origin/route1-parity-capacity-decision` at `20a3729213e756d58223beacdaa7700d077e82f4`. That remote branch had no later descendants at the fetch performed before this file was written. `origin/main` was `53ce10d187c2140511c7419863b5447119496a77`.
- Kernel required for every campaign worker: `compiled-event-loop-2`, source sha256 `a763fe1bc041f77a4ed7f06978eaf2dfd48a468205d8b675988224afd8a7818f`, commit `179b95197395044b8dcb5f9c39b032c13518f75a`. The scalar `RaceEngine` remains the default outside this campaign. A scalar continuation fallback, a missing Numba import, `KernelUnsupported`, or a mixed kernel version fails admission.
- Workers: 8. Ten-worker efficiency on the Route 1 raw waves was worse. Twelve workers are not measured on this 10-logical-CPU machine.
- Eight-worker efficiency is recomputed from `evidence/performance_feasibility_followup/1d1b3499-2ff1-440a-ba33-d45212b31b83/CAPACITY.json` as the minimum of the three steady solo/parallel ratios. It is not refit from a new favourable sample.
- The under-prediction multiplier stays `26010/20752` unless a fresh engineering probe is larger. A smaller factor is not used.
- Race-speed ratio and distribution build/resample rates are remeasured on synthetic `engperf` fixtures during preflight. The carried 22.902642628995448 ratio is not an admission input.

## Historical status

Run `fc5f0e00-d9e0-4f89-9eea-498461094969` remains `INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED`, `SELECTED_DESIGN NONE_RESOURCE_LIMIT`. Its Gate E is `UNCLAIMED_RESOURCE_LIMIT` and its Gate F is `FAIL`. Run `0b697910-e8a2-474b-bc77-bc69ebb8e9c3` remains `PRESERVED_LIMITED_DIAGNOSTIC_INVALID_FOR_PHASE6_CLOSURE_OR_GATES`. Route 1 remains `ENGINEERING_NOT_FEASIBLE_WITHIN_CURRENT_ENVELOPE` under the old 11,520-second admission wall. Those packets are not overwritten.

The main checkout ledger at the time of this amendment still marked `fcbb3e38-727f-4132-8043-11a16c404c57` as running. It was not resumed. This worktree had no `evidence/var/ledger.sqlite`. `python -m f1q status` therefore reported an absent ledger and `next_permitted_work` of bootstrap. That status line is not authorisation. Authorisation is this amendment, made under the user instruction that pasted the six-hour prompt.

## What this amendment does not do

Phase 7 is not authorised. Final-test and shift partitions are not materialised. No QPU job is submitted. No money is spent. A passed admission is not Gate E, not Gate F, and not `PHASE_7_DESIGN_READY`. Proxy headroom remains zero, which bars a superiority claim and is not a precomputed downstream effect. Preflight, including tests and synthetic probes, is capped at 7,200 seconds and is not added to the six-hour campaign allowance. The campaign wall is measured from foreground campaign start through completed scientific evidence and analysis.

## Supersession

This attempt is a new run id. It links to `fc5f0e00`, `1d1b3499`, and `20a3729213e756d58223beacdaa7700d077e82f4` as prior evidence. It does not complete those runs retroactively.
