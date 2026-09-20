# Project status

Updated after Stage 4 Final Closure (bounded engineering gate). Chat recollection is not evidence.

## Active stage

Stage 4 engineering closure complete as software/evidence with **`STAGE_4_ENGINEERING: CLOSED_WITH_DOCUMENTED_LIMITATIONS`**. The former Stage 4.2 exhaustive all-pair terminal Cartesian matrix is **`LEGACY_EXHAUSTIVE_GATE: PARTIAL`** (saved coverage only; not renamed corrected). Stage 4.1 is **not independently accepted**. **`STAGE_5_DESIGN_READY: true`** only for the architecture decision that must address **`PROXY_HEADROOM: ZERO`** before any circuit commitment. **`QPU_EXECUTION_AUTHORISED: false`**.

## Completed work with evidence

- Isolated repository `f1-ai-quantum-strategy` on `main`, remote origin `https://github.com/KRPFLWSTATE/f1-ai-quantum-strategy.git`
- Dossier v3.1 SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33/33 pages extracted
- Stages 1–3.3 preserved under prior run identifiers
- Stage 4 formulation_check run `e8b87881-74a6-46c7-b48e-6b2496a5d586` **preserved**
- Stage 4.1 formulation_repair_check run `c4d0a199-9cea-4214-83ab-97964f2bf1ac` **preserved**
- Stage 4.2 run `e85ee977-8a35-40c1-b690-02724dea3228` **preserved PARTIAL 40/64** (7195 historical pairs under old checker)
- Interrupted Stage 4.2 continuation `41c28597-0ce0-428f-8230-ba2ca973c5b7` **preserved at 20/64** (was 14 when first stopped; a leftover unauthorised `resume` briefly continued before Final Closure terminated it); not completed; not merged
- Stage 4 Final Closure bounded gate: 64/64 analytical + 64/64 lex-first terminal witnesses + 12/12 hand cases — `evidence/formulation/artifacts/stage4_closure/`
- Named closure report: `STAGE_4_CLOSURE_REPORT.md` / `docs/STAGE_4_CLOSURE_REPORT.md`
- Review ZIP SHA-256 `4f018415ed13eebd13d2d8439a193ebf80b5a2ef18e2b6c34561909f2f46b3ab` (1748016 bytes); sidecar + `STAGE_4_CLOSURE_FINAL_VERIFY.json` (`ok: true`)
- Defects A–C (exact entry-lap timing / shared semantics; transit_out service_already_completed; unified service-interval pair timing) **fixed now** and regression-tested
- Automatic Stage 4.2 closeout/packager/weak-hash resume paths **disabled / fail-closed**

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

Real-world calibration was not run. Reserved scientific partitions are not materialized. Hardware remains disabled. Protocol remains DRAFT. Exact legal enumeration still removes all proxy headroom on development checkpoints — Stage 5 must not bypass this finding or create artificial difficulty. Historical exhaustive matrix evidence remains PARTIAL and is not proof that the corrected checker passed every Cartesian pair. Supported dry-race action language remains the declared two-compound / one-solver-visible-stop domain.

## Next authorised unit

Stage 5 **architecture decision** only: address zero-headroom / classical enumerability of the small action space before any QAOA, learned selector, provider, or QPU path. Independent review of the Stage 4 closure package. Push to GitHub only on separate instruction. No automatic campaigns.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `STAGE_4_CLOSURE_REPORT.md` / `docs/STAGE_4_CLOSURE_REPORT.md`
4. `docs/STAGE_4_2_REPORT.md` (historical PARTIAL; superseded as engineering gate)
5. `docs/STAGE_4_1_REPORT.md` (historical; not independently accepted)
6. `docs/STAGE_4_REPORT.md` (historical; Gate C claim superseded)
7. `docs/evidence/stage4_closure/coverage_checklist.json`
8. `python -m f1q status` and `python -m f1q doctor`
