# f1-ai-quantum-strategy

Independent research infrastructure for a **deadline-constrained two-car pit-strategy** study that may later combine a motorsport simulator, classical references, an evaluated learned policy, and quantum candidate generation.

This repository is **not** affiliated with a Formula 1 team. It reports **no experimental results**. Completing software setup, a development preview, or simulator checks does not establish scientific novelty, F1 calibration, or hardware readiness.

## Current scope -- Stage 3

Restricted independent race simulator (`simulator.v1` / interface `3.0.0`), independent mechanism oracles, and engineering validation of the Stage 2 development preview (64 admitted checkpoints). Admission is **not** F1 reconstruction, H1/H2/H3 evidence, or a claim that SC/VSC/tyre physics match real racing.

Scientific protocol status: **DRAFT** (`frozen: false`). Hardware execution: **disabled**. Additional spending: **zero**. Stage 4 is not authorized by this file.

## Supported local environment

- macOS (Apple silicon verified on the author's machine), CPython **3.12** (`requires-python >=3.12,<3.14`)
- Project-local virtualenv; no system Python changes and no administrator install

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
# Reproducible versions:
python -m pip install -r requirements.lock
```

## Checks

```bash
python -m pytest
python -m f1q doctor
python -m f1q status
python -m f1q generator validate
python -m f1q generator plan-splits [--test-blocks 80|88|...|160]
python -m f1q run --plan development_preview
python -m f1q run --plan simulator_check
python -m f1q resume --run-id <id>    # only if a run was interrupted
python -m f1q receipt --run-id <id>
python -m f1q generator audit --run-id <id>
python -m f1q simulator validate
python -m f1q simulator inspect-checkpoint --run-id <id> --episode-id <id>
python -m f1q simulator interface
```

There is no `submit`, hardware, or IBM command. Reserved scientific partitions cannot be materialized. Those modes exit nonzero before any work or network access.

## Evidence locations

- Ledger (mutable, gitignored): `evidence/var/ledger.sqlite`
- Bootstrap artifacts: `evidence/bootstrap/`
- Development preview specs/receipts: `evidence/development/`
- Private simulator-state seeds (gitignored, not solver-visible): `evidence/development/private/`
- Dossier and extraction: `docs/protocol/`
- Stage 1 follow-up: `docs/STAGE_1_FOLLOWUP.md`
- Stage 2 report: `docs/STAGE_2_REPORT.md`
- Stage 3 report: `docs/STAGE_3_REPORT.md`
- Simulator selection / model / validation: `docs/SIMULATOR_SELECTION.md`, `docs/SIMULATOR_MODEL.md`, `docs/SIMULATOR_VALIDATION.md`
- Simulator receipts (engineering): `evidence/simulator/receipts/`
- Private simulator checkpoint state (gitignored, hashed not printed): `evidence/simulator/private/`
- Generator specification: `docs/GENERATOR_SPEC.md`

Development outputs and simulator-check admissions are **not** scientific observations. Do not place them in a results table.

## Next stage

Stage 4 -- action model, objective compiler, QUBO and independent classical references -- awaits its implementation prompt.
