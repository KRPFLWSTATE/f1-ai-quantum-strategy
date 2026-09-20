# Project status

Updated after **Phase 5 targeted final-acceptance repair** (C1 executable prep + causal honesty). Chat recollection is not evidence.

## Active stage

`active_stage`: **5**. Stage 5A architecture decision: **`STAGE_5A: PASS`** (selected **A2**).  
**PHASE_5_ACCEPTANCE:** `PASS_WITH_DOCUMENTED_LIMITATIONS` — see `docs/STAGE_5_FINAL_ACCEPTANCE_REPORT.md` (C1 prep ≡ NumPy; genuine Statevector cross-check; causal model labelled restricted synthetic revealed-duration surrogate).  
**PHASE_5_CORRECTED_ENGINEERING:** `PASS` (run `e6b3588b-ab97-48c9-82f4-616785aa3611`) — training/donors/selectors **reused** (NumPy simulator unchanged; no retraining).  
Historical Phase 5 run `6ad68021-f19c-44e7-b166-13ab44dad31b` is **preserved unchanged** and is **not** corrected-compliant.  
See `docs/STAGE_5_CORRECTED_REPORT.md` / `docs/evidence/stage5_corrected/` and supplemental `docs/evidence/stage5_final_acceptance/`.  
**`PROXY_HEADROOM: ZERO`** remains the Stage 4 finding on single-checkpoint proxies. Phase 5 corrected development headroom on checked A2 instances: **`DEVELOPMENT_HEADROOM: ZERO`** (exact finishes inside deadline; superiority path disabled). **`NOVELTY_STATUS: PROPOSED_NOT_LITERATURE_VERIFIED`**. **`QPU_EXECUTION_AUTHORISED: false`**. **`QPU_JOBS: 0`**. **`C2_STATUS: NOT_ADMITTED_BY_PROTOCOL`**.  
**`CAUSAL_MODEL_SCOPE`:** `restricted_synthetic_revealed_at_epoch_1` — not event-timed on-track / pit-entry deadline validation.

After a valid bounded Stage 4 closure: **`STAGE_4_ENGINEERING: CLOSED_WITH_DOCUMENTED_LIMITATIONS`**. **`LEGACY_EXHAUSTIVE_GATE: PARTIAL`** with **`LEGACY_GATE_ACTION: ARCHIVED_DO_NOT_RESUME`**. Filesystem/git-tracked counts (see `docs/STAGE_4_CLOSURE_ERRATUM.md`): **e85ee977 = 40/64**; **41c28597 = 21 archived record files** (interrupted; no completed receipt; excluded from the bounded gate). Stage 4.1 is **not independently accepted**. Stage 4 evidence remains frozen.

## Completed work with evidence

- Isolated repository `f1-ai-quantum-strategy` on `main`, remote origin `https://github.com/KRPFLWSTATE/f1-ai-quantum-strategy.git`
- Dossier v3.1 SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33/33 pages extracted
- Stages 1–3.3 preserved under prior run identifiers
- Stage 4 formulation_check run `e8b87881-74a6-46c7-b48e-6b2496a5d586` **preserved**
- Stage 4.1 formulation_repair_check run `c4d0a199-9cea-4214-83ab-97964f2bf1ac` **preserved**
- Stage 4.2 run `e85ee977-8a35-40c1-b690-02724dea3228` **preserved PARTIAL 40 archived / 64**
- Interrupted Stage 4.2 continuation `41c28597-0ce0-428f-8230-ba2ca973c5b7` **preserved at 21 archived files**; not completed; no completed receipt; not merged; do not resume
- Stage 4 Final Closure / Correction bounded gate regenerates under `evidence/formulation/artifacts/stage4_closure/`
- Current simulator/interface: **1.0.4 / 3.1.0**
- **Stage 5A:** `docs/STAGE_5A_ARCHITECTURE_REPORT.md`, `docs/STAGE_5A_EXPERIMENT_CONTRACT.md`, `docs/evidence/stage5a/`
- **Phase 5 (historical):** run `6ad68021-…`, report `docs/STAGE_5_REPORT.md` — preserved; superseded for engineering acceptance by correction
- **Phase 5 corrected:** run `e6b3588b-ab97-48c9-82f4-616785aa3611`, report `docs/STAGE_5_CORRECTED_REPORT.md`, verify under `docs/evidence/stage5_corrected/`
- **Phase 5 final acceptance repair:** `docs/STAGE_5_FINAL_ACCEPTANCE_REPORT.md`, evidence `evidence/stage5/final_acceptance_repair/` + `docs/evidence/stage5_final_acceptance/` (C1 prep/cross-check repair; no retraining)

## Protocol state

- scientific_protocol: DRAFT
- frozen: false
- hardware_execution_enabled: false
- research comparison experiments executed: 0 (Phase 5 results are development/tuning only)
- physical QPU jobs submitted: 0
- QPU usage from this stage: 0 seconds; account balance not queried
- Phase 5 local circuit ideal simulations: executed (not physical)
- learned donor selector: trained on **all 144** training blocks; evaluated on **all 80** tuning blocks; all four family-depths (development)

## Explicit limitations

Real-world calibration was not run. Reserved scientific partitions are not materialized. Hardware remains disabled. Protocol remains DRAFT. Exact legal enumeration still removes proxy headroom on development single-checkpoint menus. On checked A2 circuit_unit/tiny development instances, exact classical enumeration finishes inside the operational deadline, so **development objective headroom is zero** and the superiority path is disabled. Historical exhaustive matrix evidence remains PARTIAL. Novelty is proposed, not literature-verified. No quantum advantage claim. C2 not admitted by protocol. Scenario probabilities are **deterministic_synthetic**, not AI-trained. Phase 5 causal duration handling is a **restricted synthetic revealed-at-epoch-1 surrogate** — not event-timed on-track causal validation or live pit-entry deadline proof; it does not demonstrate actual F1 operational value.

## Next authorised unit

**NONE — await independent review.** Stage 6 local mechanism/resource pilot only when an explicit Stage 6 prompt is issued after review. **Operational** race-decision pilot is **not** ready (`PHASE_6_OPERATIONAL_PILOT_READY: false`) until causal simulator integration. Not hardware. Prerequisites: final-acceptance evidence reviewed; `QPU_EXECUTION_AUTHORISED` remains false; Stage 4 frozen; zero spend. Superiority pilot is **not** ready while `SUPERIORITY_PATH_AVAILABLE: false`.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/STAGE_5_FINAL_ACCEPTANCE_REPORT.md`
4. `docs/STAGE_5_CORRECTED_REPORT.md`
5. `docs/evidence/stage5_final_acceptance/STAGE_5_FINAL_ACCEPTANCE_FINAL_VERIFY.json`
6. `docs/evidence/stage5_corrected/STAGE_5_CORRECTED_FINAL_VERIFY.json`
7. `docs/STAGE_5_REPORT.md` (historical only)
8. `docs/STAGE_5A_ARCHITECTURE_REPORT.md`
9. `docs/STAGE_5A_EXPERIMENT_CONTRACT.md`
10. `docs/STAGE_4_CLOSURE_ERRATUM.md`
11. `python -m f1q status` and `python -m f1q doctor`
