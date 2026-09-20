# Project status

Updated after Stage 4 timing-provenance repair and corrected bounded closure (v2 packaging). Chat recollection is not evidence.

## Active stage

`active_stage`: **4**. After a valid bounded closure: **`STAGE_4_ENGINEERING: CLOSED_WITH_DOCUMENTED_LIMITATIONS`**. **`LEGACY_EXHAUSTIVE_GATE: PARTIAL`** with **`LEGACY_GATE_ACTION: ARCHIVED_DO_NOT_RESUME`**. Filesystem/git-tracked counts (see `docs/STAGE_4_CLOSURE_ERRATUM.md`): **e85ee977 = 40/64**; **41c28597 = 21 archived record files** (interrupted; no completed receipt; excluded from the bounded gate). Stage 4.1 is **not independently accepted**. **`PROXY_HEADROOM: ZERO`**. **`STAGE_5_DESIGN_READY: true`** only for the architecture decision addressing zero headroom. **`QPU_EXECUTION_AUTHORISED: false`**.

## Completed work with evidence

- Isolated repository `f1-ai-quantum-strategy` on `main`, remote origin `https://github.com/KRPFLWSTATE/f1-ai-quantum-strategy.git`
- Dossier v3.1 SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33/33 pages extracted
- Stages 1–3.3 preserved under prior run identifiers
- Stage 4 formulation_check run `e8b87881-74a6-46c7-b48e-6b2496a5d586` **preserved**
- Stage 4.1 formulation_repair_check run `c4d0a199-9cea-4214-83ab-97964f2bf1ac` **preserved**
- Stage 4.2 run `e85ee977-8a35-40c1-b690-02724dea3228` **preserved PARTIAL 40 archived / 64**
- Interrupted Stage 4.2 continuation `41c28597-0ce0-428f-8230-ba2ca973c5b7` **preserved at 21 archived files**; not completed; no completed receipt; not merged; do not resume
- Stage 4 Final Closure / Correction bounded gate regenerates under `evidence/formulation/artifacts/stage4_closure/`
- Timing-provenance repair: restored `pit_entry.detail.pit_entry_completed_laps` producer logging (class C) + strict pit_entry↔service_complete pairing; diagnosis `docs/evidence/stage4_closure_correction/timing_failure_diagnosis.json`
- Failed timing attempt preserved at `evidence/formulation/artifacts/stage4_closure_failed_timing_attempt_1/` (not scientific evidence; not canonical)
- Erratum: `docs/STAGE_4_CLOSURE_ERRATUM.md`
- Historical v1 closure ZIP superseded; canonical package is v2 after this correction
- Current simulator/interface: **1.0.4 / 3.1.0** (package constants, YAML, engine agree)

## Protocol state

- scientific_protocol: DRAFT
- frozen: false
- hardware_execution_enabled: false
- research comparison experiments executed: 0
- physical QPU jobs submitted: 0
- QPU usage from this stage: 0 seconds; account balance not queried
- learned models trained: 0
- quantum circuits executed: 0

## Explicit limitations

Real-world calibration was not run. Reserved scientific partitions are not materialized. Hardware remains disabled. Protocol remains DRAFT. Exact legal enumeration still removes all proxy headroom on development checkpoints — Stage 5 must not bypass this finding or create artificial difficulty. Historical exhaustive matrix evidence remains PARTIAL and is not proof of 64/64 terminal Cartesian coverage.

## Next authorised unit

**Stage 5 architecture decision addressing zero proxy headroom.** Keep `active_stage` at 4 until a separate Stage 5 prompt. No automatic campaigns. No resume of archived legacy Gate C runs.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/STAGE_4_CLOSURE_ERRATUM.md`
4. `STAGE_4_CLOSURE_REPORT_v2.md` / `docs/STAGE_4_CLOSURE_REPORT_v2.md` (after correction packaging)
5. `STAGE_4_CLOSURE_REPORT.md` (historical v1; superseded)
6. `docs/STAGE_4_2_REPORT.md` (historical PARTIAL; withdrawn as engineering gate)
7. `python -m f1q status` and `python -m f1q doctor`
