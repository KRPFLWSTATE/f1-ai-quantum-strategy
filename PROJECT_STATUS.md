# Project status

Updated after **Phase 6 A4 limited-resource campaign** (run `0b697910-e8a2-474b-bc77-bc69ebb8e9c3`). Chat recollection is not evidence. Do not treat A3 numbers as accepted results. Do not treat the limited pilot as a completed 120/80/24 corpus or as quantum advantage.

## Active stage

`active_stage`: **6 closed (`INCOMPLETE_ENGINEERING_RESOURCE_LIMIT`; Phase 7 not authorised)**.  
**SELECTED_ARCHITECTURE:** A4 checkpoint candidate-generation / downstream-reranking.  
**A3_SCIENTIFIC_RESULT:** `SUPERSEDED_INVALID_IMPLEMENTATION`.  
**PHASE_6_STATUS:** `INCOMPLETE_ENGINEERING_RESOURCE_LIMIT`.  
**PHASE_6_ENGINEERING:** `INCOMPLETE_ENGINEERING_RESOURCE_LIMIT`.  
**GATE_E_SCIENTIFIC_VALUE:** limited-pilot diagnostic `PASS_BOUNDARY_MECHANISM` (8/12 quantum-incremental-in-K cells; 0 executed-plan differences); **not** confirmatory on the registered 120/80/24 corpus.  
**GATE_F_LOCAL_PRECISION_AND_RESOURCES:** `FAIL`.  
**OPERATIONAL_DOWNSTREAM_HEADROOM:** `ZERO`.  
**SUPERIORITY_PATH_AVAILABLE:** false.  
**PHASE_7_BOUNDARY_STUDY_READY:** false.  
**PHASE_7_OPERATIONAL_READY:** false.  
**PHASE_7_SUPERIORITY_READY:** false.  
**QPU_EXECUTION_AUTHORISED:** false. **QPU_JOBS:** 0.  
**FINAL_TEST_ACCESSED:** false.  
**AUTHORITATIVE_RUN_ID:** `0b697910-e8a2-474b-bc77-bc69ebb8e9c3`.  
**REVIEWED_SOURCE_COMMIT:** `a38bb29664b78cd5cb74a075f210f706878a0a9b`.  
**ADMISSION:** `NOT_ADMITTED` for preferred/baseline/minimum 120/80/24 ladders; `limited_resource_pilot` executed.

A2 lineage preserved. A3 artifacts preserved as an unsuccessful implementation. Prior A4 run `09806343-…` preserved. Prior admission-only `3de109c7-…` is `SUPERSEDED_RESOURCE_MODEL_ONLY`. Historical `docs/PHASE_6_A4_FINAL_REPORT.md` and `docs/PHASE_6_A4_CLOSURE_REPORT.md` are not overwritten.

## Completed work with evidence

- Phases 1–5 preserved under prior identifiers
- Phase 6 historical `bd83cb22-…` and corrected `2a3fb275-…` preserved
- A2 residual histograms/native-basis noise under `evidence/stage6_a2_residual/e437fa3d-…`
- A3 freeze/pilot under `evidence/a3/a5fdb488-…` (scientifically superseded)
- Prior A4 freeze/anchors/native-noise under `evidence/stage6_a4/09806343-…`
- A4 measured non-admission under `evidence/stage6_a4/3de109c7-…` (`SUPERSEDED_RESOURCE_MODEL_ONLY`)
- A4 limited-resource campaign under `evidence/stage6_a4/0b697910-…` (`INCOMPLETE_ENGINEERING_RESOURCE_LIMIT`)

## Next authorised unit

**NONE automatic.** Phase 7 not authorised. Do not open final-test. Not hardware. Do not resume `e85ee977-…`, `41c28597-…`, or `fcbb3e38-…`. Do not treat the 4/4/2 parent limited pilot as the registered 120/80/24 corpus.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/PHASE_6_COMPLETION_REPORT.md`
4. `docs/PHASE_6_A4_IMPLEMENTATION_AND_RESOURCE_AMENDMENT.md`
5. `docs/PHASE_6_A4_CLOSURE_REPORT.md` (historical 3de109c7)
6. `docs/PHASE_6_A4_FINAL_REPORT.md` (historical 09806343)
7. `docs/A3_INVALIDATION_AND_A4_PROTOCOL_AMENDMENT.md`
8. `python -m f1q status` and `python -m f1q doctor`
