# Project status

Updated after Stage 4.2 Gate C semantic closure and packaging repair (PARTIAL matrix). Chat recollection is not evidence.

## Active stage

Stage 4.2 complete as software/evidence with **GATE_C_FORMULATION: PARTIAL** (development matrix 40/64 under the authorised 30-minute cumulative time-cap; remaining episodes preserved for checksum-safe resume). Stage 4.1 is **not independently accepted**. Stage 5 is **not authorised** and remains blocked pending independent review of Stage 4.2 and the Gate E/headroom decision.

## Completed work with evidence

- Isolated repository `f1-ai-quantum-strategy` on `main`, remote origin `https://github.com/KRPFLWSTATE/f1-ai-quantum-strategy.git`
- Dossier v3.1 SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33/33 pages extracted
- Stages 1–3.3 preserved under prior run identifiers
- Stage 4 formulation_check run `e8b87881-74a6-46c7-b48e-6b2496a5d586` **preserved**; Gate C PASS claim superseded
- Abandoned Stage 4 attempt `1c5b0748-5406-4933-8e41-4f943f4296c7` preserved as failed
- Stage 4.1 formulation_repair_check run `c4d0a199-9cea-4214-83ab-97964f2bf1ac` **preserved**; independent-review failure registered via Stage 4.2 erratum
- Abandoned Stage 4.2 attempt `90e50d03-371c-4663-94fb-ad1da84a0bcf` preserved (source fingerprint change)
- Stage 4.2 formulation_gate_c_closure_check run `e85ee977-8a35-40c1-b690-02724dea3228`: F1–F9 repairs, public in-pit commitment schema, evaluator `kind`/`service_complete` semantics, continuation admission, reduction proof, tie-aware panel, QUBO/Ising revalidation, historical Stage 3.3 SHA restored, current diagnostic under `docs/evidence/stage4_2/`, review-package builder/verifier; matrix **40/64 PARTIAL** (7195/7195 pairs validated/round-tripped/terminally executed on completed episodes; 24 episodes incomplete)
- Named Stage 4.2 report: `docs/STAGE_4_2_REPORT.md`
- Reviewed tip commit: `97acf67b4c58816d8f710db7604151f914f3e2f8` (evidence commit `42227710f0f75f1e39649850a62547e95c9d8d6c`)
- Receipt: `evidence/formulation/receipts/e85ee977-8a35-40c1-b690-02724dea3228.json`
- Review ZIP SHA-256 `7aec1f48172cab627bb274451a217b319f07671d47de1732e19b658be31f8aa5` (714162 bytes); sidecar `review/STAGE_4_2_REVIEW.manifest.json`; `review/STAGE_4_2_FINAL_VERIFY.json`

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

Real-world calibration was not run. GitHub publication of this tip was requested. Reserved scientific partitions are not materialized. Hardware remains disabled. Protocol remains DRAFT. Gate E: exact legal enumeration still removes all proxy headroom on completed development checkpoints — carry forward before any Stage 5 superiority design. Stage 4.2 Gate C is PARTIAL because the all-pair terminal-execution matrix did not finish 64/64 under the local time cap. Software repairs for F1–F9 are implemented and regression-tested; incomplete matrix coverage prevents Gate C PASS.

## Next authorised unit

Independent review of Stage 4.2 only. Checksum-safe resume of `e85ee977-…` matrix remainder is blocked until the working tree matches run source snapshot `8dfb911f…` (post-closure commits changed the fingerprint). A new authorised plan/run would be required to regenerate a complete 64/64 matrix under the current tip. Stage 5 blocked. No hardware credentials requested.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/STAGE_4_2_REPORT.md`
4. `docs/STAGE_4_1_REPORT.md` (historical; not independently accepted)
5. `docs/STAGE_4_REPORT.md` (historical; Gate C claim superseded)
6. `docs/ACTION_MODEL.md`
7. `docs/OBJECTIVE_COMPILER.md`
8. `docs/QUBO_SPECIFICATION.md`
9. `docs/CLASSICAL_REFERENCES.md`
10. `docs/evidence/stage4_2/pre_repair_reproduction.json`
11. `python -m f1q status` and `python -m f1q doctor`
