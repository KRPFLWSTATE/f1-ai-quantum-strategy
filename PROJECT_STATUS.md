# Project status

Updated after **Phase 6 A4 measured non-admission** (run `3de109c7-30d9-4cb0-827f-dbd82c4c509d`). Chat recollection is not evidence. Do not treat A3 numbers as accepted results. Do not treat this non-admission as a scientific negative result on quantum candidates.

## Active stage

`active_stage`: **6 (A4 repair+admission complete; corpus not admitted; Phase 7 not authorised)**.  
**SELECTED_ARCHITECTURE:** A4 checkpoint candidate-generation / downstream-reranking.  
**A3_SCIENTIFIC_RESULT:** `SUPERSEDED_INVALID_IMPLEMENTATION`.  
**PHASE_6_STATUS:** `INCOMPLETE_ENGINEERING`.  
**PHASE_6_ENGINEERING:** `FAIL`.  
**GATE_E_SCIENTIFIC_VALUE:** `FAIL`.  
**GATE_F_LOCAL_PRECISION_AND_RESOURCES:** `FAIL`.  
**OPERATIONAL_DOWNSTREAM_HEADROOM:** `ZERO`.  
**PHASE_7_BOUNDARY_STUDY_READY:** false.  
**PHASE_7_OPERATIONAL_READY:** false.  
**PHASE_7_SUPERIORITY_READY:** false.  
**QPU_EXECUTION_AUTHORISED:** false. **QPU_JOBS:** 0.  
**FINAL_TEST_ACCESSED:** false.  
**AUTHORITATIVE_RUN_ID:** `3de109c7-30d9-4cb0-827f-dbd82c4c509d`.  
**REVIEWED_SOURCE_COMMIT:** `f3c3c88ab1e9ab2dc95458e4ab775b284aded41f`.  
**ADMISSION:** `NOT_ADMITTED` (no world-count ladder ≤ 60 minutes after 20% reserve).

A2 lineage preserved. A3 artifacts preserved as an unsuccessful implementation. Prior A4 run `09806343-…` preserved. Historical `docs/PHASE_6_A4_FINAL_REPORT.md` is not overwritten.

## Completed work with evidence

- Phases 1–5 preserved under prior identifiers
- Phase 6 historical `bd83cb22-…` and corrected `2a3fb275-…` preserved
- A2 residual histograms/native-basis noise under `evidence/stage6_a2_residual/e437fa3d-…`
- A3 freeze/pilot under `evidence/a3/a5fdb488-…` (scientifically superseded)
- Prior A4 freeze/anchors/native-noise under `evidence/stage6_a4/09806343-…`
- A4 source repair + measured admission under `evidence/stage6_a4/3de109c7-…` (`INCOMPLETE_ENGINEERING`)

## Next authorised unit

**NONE automatic.** Phase 7 not authorised. Do not open final-test. Not hardware. Do not start the 120/80/24 corpus under the failed admission receipt. Do not resume `e85ee977-…`, `41c28597-…`, or `fcbb3e38-…`.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/PHASE_6_A4_CLOSURE_REPORT.md`
4. `docs/PHASE_6_A4_FINAL_REPORT.md` (historical 09806343)
5. `docs/A3_INVALIDATION_AND_A4_PROTOCOL_AMENDMENT.md`
6. `docs/PHASES_1_TO_6_FINAL_ACCEPTANCE_REPORT_v3.md`
7. `python -m f1q status` and `python -m f1q doctor`
