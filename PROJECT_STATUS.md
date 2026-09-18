# Project status

Updated after Stage 1 checks. Chat recollection is not evidence.

## Active stage

Stage 1 complete as software infrastructure. Stage 2 is **not authorised**.

## Completed work with evidence

- Isolated repository `f1-ai-quantum-strategy` on `main`, remote origin connected, **not pushed**
- Dossier v3.1 SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33/33 pages extracted
- CLI `doctor`, `status`, `run --plan bootstrap`, `resume --run-id`, `receipt --run-id`
- Bootstrap setup-fixture run `a0c7a5d7-4387-40f8-82f7-08b7d3593f85` interrupted then resumed; receipt at `evidence/bootstrap/receipts/a0c7a5d7-4387-40f8-82f7-08b7d3593f85.json`
- pytest 24 passed; fresh-venv import passed
- Named checks recorded in `docs/STAGE_1_REPORT.md`

The setup commit `f0dd49ff63dac6d098d0685d92c2f8dae02fbc79` **records** this implementation. It is **not** the source snapshot used by the bootstrap runs (`source_snapshot_hash=320dc0f9e7457e31d2a05a7d998b2bedb909447559e04acf1866cb6704aaa583`, `git_commit=null`, dirty tree).

## Protocol state

- scientific_protocol: DRAFT
- frozen: false
- hardware_execution_enabled: false
- research experiments executed: 0
- physical QPU jobs submitted: 0
- QPU usage from this stage: 0 seconds; account balance not queried

## Blocking findings

None that stop Stage 1. GitHub push is not authorised.

## Next authorised unit

None. Stage 2 (scenario generator and causal checkpoint schema) awaits its implementation prompt.

## Files a future Agent must read first

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/STAGE_1_REPORT.md`
4. `docs/F1_Cursor_Master_Prompt_Stage_1.md` or `docs/prompts/F1_Cursor_Master_Prompt_Stage_1.md`
5. `docs/protocol/SOURCE_HASH.md`
6. `docs/protocol/PROTOCOL_RECORD.md`
7. `docs/DEVIATIONS.md`
8. `python -m f1q status` and `python -m f1q doctor`
