# Project status

Updated after **Phases 1–6 consolidated audit/correction** (Stage 6 corrected run `2a3fb275-6c37-4bbc-bdb4-addede80b5c3`). Chat recollection is not evidence.

## Active stage

`active_stage`: **6 (corrected closure pending Phase 7 authorisation)**.  
**PHASE_6_ACCEPTANCE:** `CORRECTED_WITH_DOCUMENTED_LIMITATIONS` — see `docs/STAGE_6_CORRECTED_REPORT.md` and `docs/PHASES_1_TO_6_ACCEPTANCE_REPORT.md`.  
**GATE_E_SCIENTIFIC_VALUE:** `FAIL_FOR_INTENDED_CONTRIBUTION` (prior `PASS_FOR_DEFINED_SCOPE` withdrawn).  
**GATE_F_LOCAL_PRECISION_AND_RESOURCES:** `PASS_WITH_LIMITATIONS`.  
**PROTOCOL_STATUS:** `MECHANISM_SCOPE_DRAFT_V2_NOT_FINAL_TEST_AUTHORISED`.  
**SHOT_ACCOUNTING:** `CORRECTED`.  
**NOISE_EVIDENCE_CLASS:** `synthetic_gate_depolarizing_sensitivity_model` (historical jitter panel withdrawn as gate-noise evidence).  
**CAUSAL_OPERATIONAL_READINESS:** `false`.  
**DEVELOPMENT_HEADROOM:** `ZERO`.  
**SUPERIORITY_PATH_AVAILABLE:** `false`.  
**PHASE_7_MECHANISM_READY:** `false`.  
**PHASE_7_OPERATIONAL_READY:** `false`.  
**PHASE_7_SUPERIORITY_READY:** `false`.  
**QPU_EXECUTION_AUTHORISED:** `false`. **QPU_JOBS:** `0`.

Phase 5 remains closed historical: **PHASE_5_ACCEPTANCE** `PASS_WITH_DOCUMENTED_LIMITATIONS`; corrected run `e6b3588b-…`; final-acceptance commit `1c7631e…`. Stage 4 engineering closed with documented limitations; legacy exhaustive Gate C archived do-not-resume.

## Completed work with evidence

- Phases 1–5 preserved under prior identifiers
- **Phase 6 historical (superseded for shot/noise/capacity/sizing/Gate E claims):** `bd83cb22-…` preserved under `evidence/stage6/`
- **Phase 6 corrected:** `2a3fb275-…` under `evidence/stage6_corrected/` + `docs/evidence/stage6_corrected/`
- Calibration cohort re-run with exact 1024-draw pools; final-test not accessed
- Gate-channel noisy sensitivity panel completed (synthetic ≠ IBM)

## Protocol state

- scientific_protocol: MECHANISM_SCOPE_DRAFT_V2_NOT_FINAL_TEST_AUTHORISED
- hardware_execution_enabled: false
- research comparison experiments on held-out final-test: 0
- physical QPU jobs: 0

## Explicit limitations

Operational causal simulator integration for A2 policies is not established. Exact classical enumeration removes proxy headroom on the checked domain. Gate E fails for the intended AI–quantum–F1 contribution. Best-of-pool regret saturated at zero. C2 not admitted. No quantum advantage claim.

## Next authorised unit

**NONE automatic.** Phase 7 not authorised by this correction. Mechanism follow-up only after explicit prompt + dated amendment + review. Operational/superiority Phase 7 not ready. Not hardware.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/PHASES_1_TO_6_ACCEPTANCE_REPORT.md`
4. `docs/STAGE_6_CORRECTED_REPORT.md`
5. `docs/STAGE_6_PROTOCOL_FREEZE_V2.md`
6. `docs/STAGE_6_NOVELTY_COMPARISON.md`
7. `docs/evidence/stage6_corrected/STAGE_6_CORRECTED_FINAL_VERIFY.json`
8. `docs/STAGE_5_FINAL_ACCEPTANCE_REPORT.md`
9. `docs/STAGE_4_CLOSURE_ERRATUM.md`
10. `python -m f1q status` and `python -m f1q doctor`
