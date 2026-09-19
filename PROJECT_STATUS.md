# Project status

Updated after Stage 4.1 formulation repair. Chat recollection is not evidence.

## Active stage

Stage 4.1 complete as software/evidence (Gate C revalidation). Stage 4 Gate C PASS claim is **superseded**. Stage 5 is **not authorised** and remains blocked pending independent review and the Gate E/headroom decision.

## Completed work with evidence

- Isolated repository `f1-ai-quantum-strategy` on `main`, remote origin connected, **not pushed**
- Dossier v3.1 SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33/33 pages extracted
- Stages 1–3.3 preserved under prior run identifiers (see earlier status history)
- Stage 4 formulation_check run `e8b87881-74a6-46c7-b48e-6b2496a5d586` **preserved** as historical evidence; Gate C PASS claim superseded by Stage 4.1
- Abandoned Stage 4 attempt `1c5b0748-5406-4933-8e41-4f943f4296c7` preserved as failed
- Stage 4.1 formulation_repair_check run `c4d0a199-9cea-4214-83ab-97964f2bf1ac`: pre-repair erratum, downstream-policy one-stop semantics, public pit-entry geometry, age-aware reduction, derived pair overlap, terminal evaluator legality, uncapped pair cross-check (3361/3361), tie-aware panel, QUBO/Ising revalidation, MILP minimizer-set agreement, simulator 1.0.3 / interface 3.0.1, Stage 3.3 diagnostic rewrite
- Named Stage 4.1 record: `docs/STAGE_4_1_REPORT.md`
- Receipt: `evidence/formulation/receipts/c4d0a199-9cea-4214-83ab-97964f2bf1ac.json`
- Review: `review/STAGE_4_1_REVIEW.zip` plus external `review/STAGE_4_1_REVIEW.manifest.json` and `review/STAGE_4_1_FINAL_VERIFY.json`

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

Real-world calibration was not run. GitHub push is not authorised. Reserved scientific partitions are not materialized. Hardware remains disabled. Protocol remains DRAFT. Gate E: exact legal enumeration still removes all proxy headroom on the admitted 64 development checkpoints — carry forward before any Stage 5 superiority design. Stage 4.1 Gate C software/evidence closure does not establish quantum advantage or F1 calibration.

## Next authorised unit

Independent review of Stage 4.1. Stage 5 blocked pending that review and the Gate E decision. No hardware credentials requested.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/STAGE_4_1_REPORT.md`
4. `docs/STAGE_4_REPORT.md` (historical; Gate C claim superseded)
5. `docs/ACTION_MODEL.md`
6. `docs/OBJECTIVE_COMPILER.md`
7. `docs/QUBO_SPECIFICATION.md`
8. `docs/CLASSICAL_REFERENCES.md`
9. `docs/evidence/stage4_1/pre_repair_reproduction.json`
10. `python -m f1q status` and `python -m f1q doctor`
