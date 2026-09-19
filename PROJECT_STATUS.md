# Project status

Updated after Stage 3.3. Chat recollection is not evidence.

## Active stage

Stage 3.3 complete as software/evidence correction. Stage 4 is **not authorised**.

## Completed work with evidence

- Isolated repository `f1-ai-quantum-strategy` on `main`, remote origin connected, **not pushed**
- Dossier v3.1 SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33/33 pages extracted
- Stage 1 follow-up: `docs/STAGE_1_FOLLOWUP.md` (PASS); unrepaired bootstrap `doctor.py` bytes limitation preserved
- Stage 2 development-preview run `8f292588-a328-4232-b425-c36c610a29f5`: 8 blocks, 64 specifications, original files not overwritten
- Stage 3 simulator-check run `e2258740-1d08-4427-8305-b149ed504a73`: preserved; not recomputed under that identifier
- Stage 3.1 simulator-followup run `4388ad68-6bd3-4a43-9099-32e52f56eb28`: preserved; PARTIAL resolution claim superseded by 3.2
- Stage 3.2 simulator-repair run `62b1e5ee-3f13-44be-98e0-8af018eb286b`: R1–R6 repairs; 64-episode matrix; interventions; resolution panel PASS; production simulator.v1 **1.0.2**
- Stage 3.3 evidence correction: stale `docs/evidence/stage3_2/post_repair_diagnostic.json` preserved with erratum; live-generated `docs/evidence/stage3_3/post_repair_diagnostic.corrected.json`; R2 regression hardened; no production behavior change; no new simulator_repair run
- Named Stage 3.3 record: `docs/STAGE_3_3_REPORT.md`
- Receipt (Stage 3.2, preserved): `evidence/simulator/receipts/62b1e5ee-3f13-44be-98e0-8af018eb286b.json`

## Protocol state

- scientific_protocol: DRAFT
- frozen: false
- hardware_execution_enabled: false
- research comparison experiments executed: 0
- physical QPU jobs submitted: 0
- QPU usage from this stage: 0 seconds; account balance not queried

## Explicit later-stage limitations (not Stage 3.3 failures)

Real-world calibration was not run. GitHub push is not authorised. Reserved scientific partitions are not materialized. Hardware remains disabled. Protocol remains DRAFT. Stage 4 awaits its implementation prompt.

## Next authorised unit

None. Stage 4 (action model, QUBO, independent classical references) awaits its implementation prompt.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/STAGE_3_3_REPORT.md`
4. `docs/STAGE_3_2_REPORT.md`
5. `docs/STAGE_3_1_REPORT.md`
6. `docs/STAGE_3_REPORT.md`
7. `docs/SIMULATOR_VALIDATION.md`
8. `docs/SIMULATOR_SELECTION.md`
9. `docs/SIMULATOR_MODEL.md`
10. `docs/STAGE_2_REPORT.md`
11. `docs/protocol/SOURCE_HASH.md`
12. `python -m f1q status` and `python -m f1q doctor`
