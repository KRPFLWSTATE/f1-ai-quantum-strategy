# Project status

Updated after Stage 3. Chat recollection is not evidence.

## Active stage

Stage 3 complete as software (restricted independent simulator, independent mechanism checks, 64-episode development validation). Stage 4 is **not authorised**.

## Completed work with evidence

- Isolated repository `f1-ai-quantum-strategy` on `main`, remote origin connected, **not pushed**
- Dossier v3.1 SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33/33 pages extracted
- Stage 1 follow-up: `docs/STAGE_1_FOLLOWUP.md` (PASS); unrepaired bootstrap `doctor.py` bytes limitation preserved
- Stage 2 development-preview run `8f292588-a328-4232-b425-c36c610a29f5`: 8 blocks, 64 specifications, original files not overwritten
- Stage 3 simulator-check run `e2258740-1d08-4427-8305-b149ed504a73`: 10/10 mechanism checks, 64/64 checkpoints admitted, 8/8 diagnostic interventions, source snapshot reconstructed
- Receipt: `evidence/simulator/receipts/e2258740-1d08-4427-8305-b149ed504a73.json`
- pytest 68 passed (`docs/evidence/stage3/pytest.txt`)
- Named Stage 3 record: `docs/STAGE_3_REPORT.md`, `docs/SIMULATOR_VALIDATION.md`

The Stage 3 source snapshot is `26ed935ce0dbba00963bbe5766c77f1247fed491d2a9cf697f692c1cf5a4e6c1` at git `24346827c11c81717e8161a9a5c9414ea4ba9428` with a dirty tree at run time. Git HEAD alone does not identify a dirty tree.

## Protocol state

- scientific_protocol: DRAFT
- frozen: false
- hardware_execution_enabled: false
- research comparison experiments executed: 0
- physical QPU jobs submitted: 0
- QPU usage from this stage: 0 seconds; account balance not queried

## Blocking findings

None that stop Stage 3 software gates. Real-world calibration was not run. GitHub push is not authorised. Reserved scientific partitions are not materialized. Stage 4 awaits its implementation prompt.

## Next authorised unit

None. Stage 4 (action model, QUBO, independent classical references) awaits its implementation prompt.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/STAGE_3_REPORT.md`
4. `docs/SIMULATOR_VALIDATION.md`
5. `docs/SIMULATOR_SELECTION.md`
6. `docs/SIMULATOR_MODEL.md`
7. `docs/STAGE_2_REPORT.md`
8. `docs/protocol/SOURCE_HASH.md`
9. `python -m f1q status` and `python -m f1q doctor`
