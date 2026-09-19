# Project status

Updated after Stage 4. Chat recollection is not evidence.

## Active stage

Stage 4 complete as software/evidence (Gate C). Stage 5 is **not authorised**.

## Completed work with evidence

- Isolated repository `f1-ai-quantum-strategy` on `main`, remote origin connected, **not pushed**
- Dossier v3.1 SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33/33 pages extracted
- Stage 1 follow-up: `docs/STAGE_1_FOLLOWUP.md` (PASS); unrepaired bootstrap `doctor.py` bytes limitation preserved
- Stage 2 development-preview run `8f292588-a328-4232-b425-c36c610a29f5`: 8 blocks, 64 specifications, original files not overwritten
- Stage 3 simulator-check run `e2258740-1d08-4427-8305-b149ed504a73`: preserved; not recomputed under that identifier
- Stage 3.1 simulator-followup run `4388ad68-6bd3-4a43-9099-32e52f56eb28`: preserved; PARTIAL resolution claim superseded by 3.2
- Stage 3.2 simulator-repair run `62b1e5ee-3f13-44be-98e0-8af018eb286b`: R1–R6 repairs; 64-episode matrix; interventions; resolution panel PASS; production simulator.v1 **1.0.2**
- Stage 3.3 evidence correction: stale diagnostic preserved with erratum; corrected live artifact; R2 regression hardened; no production behavior change
- Stage 4 formulation_check run `e8b87881-74a6-46c7-b48e-6b2496a5d586`: action model, compiler, QUBO/Ising Gate C, MILP/enumeration/DP/heuristics, 64-episode matrix, evaluator panel; interrupted then resumed; Gate C PASS; Gate E headroom warning (zero proxy headroom on all 64)
- Abandoned Stage 4 attempt `1c5b0748-5406-4933-8e41-4f943f4296c7` preserved as failed (pre-fix crash)
- Named Stage 4 record: `docs/STAGE_4_REPORT.md`
- Receipt: `evidence/formulation/receipts/e8b87881-74a6-46c7-b48e-6b2496a5d586.json`

## Protocol state

- scientific_protocol: DRAFT
- frozen: false
- hardware_execution_enabled: false
- research comparison experiments executed: 0
- physical QPU jobs submitted: 0
- QPU usage from this stage: 0 seconds; account balance not queried
- learned models trained: 0
- quantum circuits executed: 0

## Explicit later-stage limitations (not Stage 4 Gate C failures)

Real-world calibration was not run. GitHub push is not authorised. Reserved scientific partitions are not materialized. Hardware remains disabled. Protocol remains DRAFT. Gate E: exact legal enumeration removes all proxy headroom on the admitted 64 development checkpoints — carry forward before any Stage 5 superiority design. Stage 5 awaits its implementation prompt.

## Next authorised unit

None. Stage 5 (QAOA / learned selectors) awaits its implementation prompt.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/STAGE_4_REPORT.md`
4. `docs/ACTION_MODEL.md`
5. `docs/OBJECTIVE_COMPILER.md`
6. `docs/QUBO_SPECIFICATION.md`
7. `docs/CLASSICAL_REFERENCES.md`
8. `docs/STAGE_3_3_REPORT.md`
9. `docs/STAGE_3_2_REPORT.md`
10. `docs/protocol/SOURCE_HASH.md`
11. `python -m f1q status` and `python -m f1q doctor`
