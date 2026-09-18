# Project instructions (always load)

Active stage: **1 -- isolation, environment, schemas, ledger, bootstrap checks**. Later stages are pending and are not authorized by this file.

## Authority

- Scientific design: `docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf` (v3.1, 18 September 2026), preserved unchanged.
- This conversation's user instructions govern authorization. The Stage 1 master prompt is filed at `docs/prompts/F1_Cursor_Master_Prompt_Stage_1.md`.
- `PROJECT_STATUS.md` plus the local ledger are the source of completion state. Chat recollection is not authorization or evidence.

## Project boundary

Permitted root: the directory containing `configs/project.draft.yaml` (intended name `f1-ai-quantum-strategy`). Resolve symlinks before writes. Do not modify the closed previous research project or unrelated repositories.

## Evidence rules

Label claims as: proposed, implemented, verified by a named check, simulated, physically measured, unsupported. A test fixture is not an experimental observation. Successful setup does not establish scientific novelty, simulator validity, or hardware readiness.

## Limits in force

- Zero additional spending. Never fall through to a paid account or paid service.
- No QPU default: `hardware_execution_enabled` is false. Do not submit jobs, inspect IBM balances, or implement a provider submission path in Stage 1.
- No scheduled tasks, GitHub Actions, autonomous campaigns, or automatic publishing.
- Do not scrape timing data. Do not train research models. Do not open held-out test outcomes.

## Commands

```text
python -m f1q doctor
python -m f1q status
python -m f1q run --plan bootstrap
python -m f1q resume --run-id <id>
python -m f1q receipt --run-id <id>
```

Natural language later:

- **do a run** -- execute the next authorized unit in the recorded plan once. During setup this cannot manufacture a scientific plan or start Stage 2+.
- **resume** -- recover the identified incomplete run. If several exist, list IDs; do not guess.
- **show status** -- read the ledger and integrity checks.
- **push to GitHub** -- separate publication instruction only. Inspect the scoped diff, exclude secrets/restricted inputs, verify remote ownership, and push this project only. It does not authorize runs, public visibility, or history rewrites.

## Run / resume semantics

A `run` is an execution container, not automatically one scientific observation. Setup fixtures are none of training/tuning/calibration/test/shift. Interrupted attempts are retained. Checksums are verified before skipping completed work. Corrupted evidence is not recomputed under the original identifier.

## GitHub

Creating the private empty remote is a setup step. Pushing commits is a later, separate requested action.
