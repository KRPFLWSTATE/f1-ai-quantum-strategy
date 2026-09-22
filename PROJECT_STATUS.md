# Project status

Updated after **Phase 6 validated resource-limit closure** (run `fc5f0e00-d9e0-4f89-9eea-498461094969`). Chat recollection is not evidence. Do not treat A3 numbers as accepted results. Do not treat the preserved `0b697910` limited diagnostic as Gate E/F or Phase 6 closure.

## Active stage

`active_stage`: **6 closed (`INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED`; Phase 7 not authorised)**.  
**SELECTED_ARCHITECTURE:** A4 checkpoint candidate-generation / downstream-reranking.  
**A3_SCIENTIFIC_RESULT:** `SUPERSEDED_INVALID_IMPLEMENTATION`.  
**PHASE_6_STATUS:** `INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED`.  
**PHASE_6_ENGINEERING:** `INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED`.  
**SELECTED_DESIGN:** `NONE_RESOURCE_LIMIT`.  
**GATE_E_SCIENTIFIC_VALUE:** `UNCLAIMED_RESOURCE_LIMIT` (neither Design F nor Design R admitted; no limited-pilot substitution).  
**GATE_F_LOCAL_PRECISION_AND_RESOURCES:** `FAIL`.  
**OPERATIONAL_DOWNSTREAM_HEADROOM:** `ZERO`.  
**SUPERIORITY_PATH_AVAILABLE:** false.  
**PHASE_7_DESIGN_READY:** false.  
**PHASE_7_BOUNDARY_STUDY_READY:** false.  
**PHASE_7_OPERATIONAL_READY:** false.  
**PHASE_7_SUPERIORITY_READY:** false.  
**QPU_EXECUTION_AUTHORISED:** false. **QPU_JOBS:** 0.  
**FINAL_TEST_ACCESSED:** false.  
**AUTHORITATIVE_RUN_ID:** `fc5f0e00-d9e0-4f89-9eea-498461094969`.  
**START_COMMIT:** `dcfe1cde7f02643d7a2d258d961e7ce2b4e62461`.  
**REVIEWED_SOURCE_COMMIT:** `885f1adffb3b65865dbc752c9b0ca0442eb8fd52`.  
**ADMISSION:** Design F and Design R both `fits=false` after batched production-path probes; no tiny outcome-bearing pilot.

A2 lineage preserved. A3 artifacts preserved as an unsuccessful implementation. Prior A4 run `09806343-…` preserved. Prior admission-only `3de109c7-…` is `SUPERSEDED_RESOURCE_MODEL_ONLY`. Prior limited diagnostic `0b697910-…` is `PRESERVED_LIMITED_DIAGNOSTIC_INVALID_FOR_PHASE6_CLOSURE_OR_GATES`. Historical `docs/PHASE_6_A4_FINAL_REPORT.md`, `docs/PHASE_6_A4_CLOSURE_REPORT.md`, and `docs/PHASE_6_COMPLETION_REPORT.md` are not overwritten.

## Completed work with evidence

- Phases 1–5 preserved under prior identifiers
- Phase 6 historical `bd83cb22-…` and corrected `2a3fb275-…` preserved
- A2 residual histograms/native-basis noise under `evidence/stage6_a2_residual/e437fa3d-…`
- A3 freeze/pilot under `evidence/a3/a5fdb488-…` (scientifically superseded)
- Prior A4 freeze/anchors/native-noise under `evidence/stage6_a4/09806343-…`
- A4 measured non-admission under `evidence/stage6_a4/3de109c7-…` (`SUPERSEDED_RESOURCE_MODEL_ONLY`)
- A4 limited diagnostic under `evidence/stage6_a4/0b697910-…` (`PRESERVED_LIMITED_DIAGNOSTIC_INVALID_FOR_PHASE6_CLOSURE_OR_GATES`)
- Validated resource-limit closure under `evidence/stage6_a4/fc5f0e00-…` (`INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED`)

## Next authorised unit

**NONE automatic.** Phase 7 not authorised. Do not open final-test. Not hardware. Do not resume `e85ee977-…`, `41c28597-…`, `fcbb3e38-…`, `3de109c7-…`, `09806343-…`, or `0b697910-…`. A future Phase 6 retry is not authorised by this closure; the next user decision is manuscript/research-scope disposition or a separately authorised compute envelope.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/PHASE_6_VALIDATED_CLOSURE_REPORT.md`
4. `docs/PHASE_6_0B697910_INVALIDATION.md`
5. `docs/PHASE_6_COMPLETION_REPORT.md` (historical 0b697910)
6. `docs/PHASE_6_A4_CLOSURE_REPORT.md` (historical 3de109c7)
7. `docs/PHASE_6_A4_FINAL_REPORT.md` (historical 09806343)
8. `python -m f1q status` and `python -m f1q doctor`
