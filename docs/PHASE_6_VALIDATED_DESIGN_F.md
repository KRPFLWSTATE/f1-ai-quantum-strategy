# Design F — full A4 pilot (preferred, prospective)

This document is written **before** opening new training/tuning/calibration outcomes. It does not select Design F. Selection is only by corrected resource admission after batched production-path probes.

## Registered panel

- 120 fresh training parents, two checkpoints each (SC and VSC)
- 80 fresh tuning parents, two checkpoints each
- 24 fresh calibration parents, two checkpoints each
- Five budgets: 5, 10, 30, 60, 120 s
- Three Phase 6 policy seeds
- 1,024 draws, matched K=4
- Mechanism: 120 outcome-blind training cases, four family/depths, five donor policies, 30 resampling seeds
- Synthetic-noise diagnostic: 40 balanced development cases if the model validates
- Eight all-plan offline references
- Six cases × two frozen packages isolated latency

## Partitions

Fresh `a4.v2.*` IDs, salt `a4.partitions.v2.20260922.validated`. Retired diagnostic parents from `0b697910` are development-only and are not in the live train/tune/calib sets. Anchors reuse the hash-verified 09806343 bank. Final-test IDs/hashes are integrity-checked only; outcomes stay sealed.

## Calibration

Primary 30 s package at 2,048 paired evaluation worlds. Non-primary budgets may use the Design R 128-world sensitivity rule only if prospectively frozen before outcomes. q is the finite-sample one-sided 95% order statistic over 24 parent-block maxima (the maximum at n=24).

## Status

Prospective. Not executed unless admission selects F.
