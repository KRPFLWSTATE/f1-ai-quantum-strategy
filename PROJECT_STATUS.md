# Project status

Updated after **Phase 6 local mechanism / precision / Gate E** (run `bd83cb22-6a38-4d21-9267-3253f52587d7`). Chat recollection is not evidence.

## Active stage

`active_stage`: **6**.  
**PHASE_6_ENGINEERING:** `PASS_WITH_DOCUMENTED_LIMITATIONS` — see `docs/STAGE_6_REPORT.md`.  
**GATE_E_SCIENTIFIC_VALUE:** `PASS_FOR_DEFINED_SCOPE` (mechanism/resource question only).  
**GATE_F_LOCAL_PRECISION_AND_RESOURCES:** `PASS_WITH_LIMITATIONS` (reduced Phase 7 matrix fits 24h ceiling; full dossier matrix does not).  
**PROTOCOL_STATUS:** `BLOCKED_DRAFT` (mechanism freeze recorded; operational/superiority/hardware fields unresolved).  
**CAUSAL_OPERATIONAL_READINESS:** `false`.  
**DEVELOPMENT_HEADROOM:** `ZERO` on completed calibration cases (exact incumbent).  
**SUPERIORITY_PATH_AVAILABLE:** `false`.  
**PHASE_7_MECHANISM_READY:** `true` (after dated amendment + review; not auto-started).  
**PHASE_7_OPERATIONAL_READY:** `false`.  
**PHASE_7_SUPERIORITY_READY:** `false`.  
**QPU_EXECUTION_AUTHORISED:** `false`. **QPU_JOBS:** `0`.

Phase 5 remains closed historical: **PHASE_5_ACCEPTANCE** `PASS_WITH_DOCUMENTED_LIMITATIONS`; corrected run `e6b3588b-…` reused; final-acceptance commit `1c7631e…`. Stage 4 engineering closed with documented limitations; legacy exhaustive Gate C archived do-not-resume.

## Completed work with evidence

- Phases 1–5 preserved under prior identifiers (see prior status revisions)
- **Phase 6:** run `bd83cb22-6a38-4d21-9267-3253f52587d7`, report `docs/STAGE_6_REPORT.md`, protocol `docs/STAGE_6_PROTOCOL_FREEZE.md`, novelty `docs/STAGE_6_NOVELTY_COMPARISON.md`, evidence `evidence/stage6/bd83cb22-…/` + `docs/evidence/stage6/`
- Calibration cohort: 24 blocks / 48 SC+VSC cases completed; final-test not accessed
- Noisy synthetic panel completed (exact zero-noise control after jitter repair)

## Protocol state

- scientific_protocol: BLOCKED_DRAFT (full freeze blocked)
- mechanism pilot freeze record: present under Stage 6 evidence
- hardware_execution_enabled: false
- research comparison experiments on held-out final-test: 0
- physical QPU jobs: 0

## Explicit limitations

Operational causal simulator integration for A2 policies is not established (restricted synthetic revealed-at-epoch-1 surrogate remains). Exact classical enumeration removes proxy headroom on the checked calibration domain. Full dossier Phase 7 counts exceed the provisional 24 CPU-hour ceiling; reduced matrix proposed with amendment required before final-test. Novelty is scoped Gate E pass only — not absolute novelty or F1 value. C2 not admitted. No quantum advantage claim.

## Next authorised unit

**NONE automatic.** Phase 7 mechanism campaign only after explicit prompt + dated reduced-matrix amendment + independent review. Operational/superiority Phase 7 not ready. Not hardware.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/STAGE_6_REPORT.md`
4. `docs/STAGE_6_PROTOCOL_FREEZE.md`
5. `docs/STAGE_6_NOVELTY_COMPARISON.md`
6. `docs/evidence/stage6/STAGE_6_FINAL_VERIFY.json`
7. `docs/STAGE_5_FINAL_ACCEPTANCE_REPORT.md`
8. `docs/STAGE_5_CORRECTED_REPORT.md`
9. `docs/STAGE_4_CLOSURE_ERRATUM.md`
10. `python -m f1q status` and `python -m f1q doctor`
