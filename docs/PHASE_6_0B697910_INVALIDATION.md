# 0b697910 disposition — preserved limited diagnostic

**Disposition:** `PRESERVED_LIMITED_DIAGNOSTIC_INVALID_FOR_PHASE6_CLOSURE_OR_GATES`

This document does not edit `evidence/stage6_a4/0b697910-e8a2-474b-bc77-bc69ebb8e9c3/`. Files there remain byte-for-byte.

## What remains valid engineering observation

- Real worker processes existed (`PROCESS_AND_MEMORY_EVIDENCE.json`, distinct PIDs).
- Local timing was measured.
- No QPU or final-test access occurred.

## Why it cannot close Phase 6 or pass Gate E/F

The upgraded independent verifier is required to fail this run. Expected failure modes (not an exhaustive scientific result):

1. `limited_resource_pilot=true` skipped 120/80/24 checks.
2. Calibration parents 2, not 24; q is not an n=24 maximum.
3. `TUNING_FREEZE` named C0_p2+C1_p2 while the option path executed C0_p1+C0_p2.
4. Donor labels used `expectation_scaled` rather than decoded 1,024-draw pool metrics.
5. Allocator `runtime=None` on the worker path; ablations were booleans.
6. Operation ledger omitted policy-seed multiplication while claiming three seeds.
7. Cache counters were not persisted; production evaluation used a scalar list comprehension.
8. Full tests skipped; clean-extract e2e deselected; heartbeats used raw `perf_counter` and completed=0 until futures returned.
9. Gate E software pass was candidate-entry-into-K on a 4/4/2 sample.
10. Actual CPU ~26,010 s exceeded projected ~20,752 s (~25%).

The expected-failure audit is `docs/evidence/phase6_validated/0B697910_EXPECTED_FAILURE.json` after the upgraded verifier is executed against the unmodified tree.
