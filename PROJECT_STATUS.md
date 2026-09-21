# Project status

Updated after **Phase 6 A4 scientific supersession** (run `09806343-f940-4f33-9e0f-eb2855d0714b`). Chat recollection is not evidence. Do not treat A3 numbers as accepted results.

## Active stage

`active_stage`: **6 (A4 attempted; Gates E/F FAIL; Phase 7 not authorised)**.  
**SELECTED_ARCHITECTURE:** A4 checkpoint candidate-generation / downstream-reranking.  
**A3_SCIENTIFIC_RESULT:** `SUPERSEDED_INVALID_IMPLEMENTATION`.  
**GATE_E_SCIENTIFIC_VALUE:** `FAIL` (A4; no calibration primary; training hybrid failed).  
**GATE_F_PRECISION_AND_RESOURCES:** `FAIL` (`minima_fit=false`; stop-before-calibration; tune 47/80).  
**OPERATIONAL_DOWNSTREAM_HEADROOM:** `ZERO_OR_UNMEASURED_ON_OFFLINE_SUBSET`.  
**PROTOCOL_STATUS:** `A4_PROTOCOL_FROZEN_BEFORE_CALIBRATION` (calibration not opened).  
**PHASE_7_BOUNDARY_STUDY_READY:** false.  
**PHASE_7_OPERATIONAL_READY:** false.  
**PHASE_7_SUPERIORITY_READY:** false.  
**QPU_EXECUTION_AUTHORISED:** false. **QPU_JOBS:** 0.  
**FINAL_TEST_ACCESSED:** false.

A2 lineage preserved. A3 artifacts preserved as an unsuccessful implementation. A4 is not an A3 continuation.

## Completed work with evidence

- Phases 1–5 preserved under prior identifiers
- Phase 6 historical `bd83cb22-…` and corrected `2a3fb275-…` preserved
- A2 residual histograms/native-basis noise under `evidence/stage6_a2_residual/e437fa3d-…` (method-validation subset)
- A3 freeze/pilot under `evidence/a3/a5fdb488-…` (scientifically superseded)
- A4 freeze, 24-anchor fits, native-noise panel, failed training hybrid, partial tuning under `evidence/stage6_a4/09806343-…`

## Next authorised unit

**NONE automatic.** Phase 7 not authorised. Do not open final-test. Not hardware. Do not rerun A4 inside the A4 prompt; a later prompt would be required to repair the donor-bank wiring and/or resource design.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/PHASE_6_A4_FINAL_REPORT.md`
4. `docs/A3_INVALIDATION_AND_A4_PROTOCOL_AMENDMENT.md`
5. `docs/PHASES_1_TO_6_FINAL_ACCEPTANCE_REPORT_v2.md`
6. `docs/PHASE_5_6_SCIENTIFIC_REDESIGN_REPORT.md` (A3 historical; not accepted A4)
7. `python -m f1q status` and `python -m f1q doctor`
