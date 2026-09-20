# Project status

Updated after complete Phase 5 (A2 learning and local circuit pipeline). Chat recollection is not evidence.

## Active stage

`active_stage`: **5**. Stage 5A architecture decision: **`STAGE_5A: PASS`** (selected **A2**). Phase 5 engineering: see `docs/STAGE_5_REPORT.md` / `docs/evidence/stage5/STAGE_5_FINAL_VERIFY.json`. **`PROXY_HEADROOM: ZERO`** remains the Stage 4 finding on single-checkpoint proxies. Phase 5 development headroom on A2 circuit_unit/tiny instances: **`DEVELOPMENT_HEADROOM: ZERO`** (exact finishes inside deadline; superiority path disabled). **`NOVELTY_STATUS: PROPOSED_NOT_LITERATURE_VERIFIED`**. **`QPU_EXECUTION_AUTHORISED: false`**. **`QPU_JOBS: 0`**. **`C2_STATUS: NOT_ADMITTED_BY_PROTOCOL`**.

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
- **Phase 5:** A2 package `src/f1q/stage5/`, frozen run under `evidence/stage5/<run_id>/`, report `docs/STAGE_5_REPORT.md`, verify `docs/evidence/stage5/STAGE_5_FINAL_VERIFY.json`

## Protocol state

- scientific_protocol: DRAFT
- frozen: false
- hardware_execution_enabled: false
- research comparison experiments executed: 0 (Phase 5 results are development/tuning only)
- physical QPU jobs submitted: 0
- QPU usage from this stage: 0 seconds; account balance not queried
- Phase 5 local circuit ideal simulations: executed (not physical)
- learned donor selector: trained on training blocks only (development)

## Explicit limitations

Real-world calibration was not run. Reserved scientific partitions are not materialized. Hardware remains disabled. Protocol remains DRAFT. Exact legal enumeration still removes proxy headroom on development single-checkpoint menus. On A2 circuit_unit/tiny development instances, exact classical enumeration finishes inside the operational deadline, so **development objective headroom is zero** and the superiority path is disabled. Historical exhaustive matrix evidence remains PARTIAL. Novelty is proposed, not literature-verified. No quantum advantage claim. C2 not admitted by protocol.

## Next authorised unit

**Stage 6 — local pilot + resource/precision estimation**, only when an explicit Stage 6 prompt is issued after user review. Not hardware. Prerequisites: Phase 5 evidence reviewed; `QPU_EXECUTION_AUTHORISED` remains false; Stage 4 frozen; zero spend. Superiority pilot is **not** ready while `SUPERIORITY_PATH_AVAILABLE: false`.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/STAGE_5_REPORT.md`
4. `docs/evidence/stage5/STAGE_5_FINAL_VERIFY.json`
5. `docs/STAGE_5A_ARCHITECTURE_REPORT.md`
6. `docs/STAGE_5A_EXPERIMENT_CONTRACT.md`
7. `docs/STAGE_4_CLOSURE_ERRATUM.md`
8. `python -m f1q status` and `python -m f1q doctor`
