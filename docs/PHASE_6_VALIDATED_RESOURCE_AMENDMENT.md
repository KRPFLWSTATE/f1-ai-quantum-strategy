# Prospective F/R resource amendment

Written **before** opening new training, tuning, or calibration outcomes.

`0b697910-e8a2-474b-bc77-bc69ebb8e9c3` is preserved as `PRESERVED_LIMITED_DIAGNOSTIC_INVALID_FOR_PHASE6_CLOSURE_OR_GATES`. Its 4/4/2 parents are retired to development-only status and are not used to select Design F or Design R.

## Selection rule (resource only)

1. After batched production-path probes, parity, tests, and clean-extract e2e, project Design F and Design R from the **enumerated unit ledger**.
2. Select F if conservative CPU ≤ 86,400 s, wall ≤ 11,520 s, RAM ≤ 60%, disk reserve ≥ 20%.
3. Otherwise select R if it satisfies the same caps.
4. If neither fits, do **not** run another tiny outcome-bearing pilot. Close `INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED`.

Selection is based only on resource probes and parity, never effect signs.

## Status

Prospective. Outcomes remain unopened until admission records the selected design.
