# f1-ai-quantum-strategy

Independent research infrastructure for a **deadline-constrained two-car pit-strategy** study that may later combine a motorsport simulator, classical references, an evaluated learned policy, and quantum candidate generation.

This repository is **not** affiliated with a Formula 1 team. It reports **no experimental results**. Completing software setup does not establish scientific novelty, simulator validity, or hardware readiness.

## Current scope -- Stage 1 only

Project isolation, local environment, persistent instructions, schemas, an evidence ledger, and bootstrap software checks. Stages 2-10 (scenario generation, simulator, QUBO, learned policy, campaigns, QPU jobs, publication packaging) are pending and are not authorized here.

Scientific protocol status: **DRAFT** (`frozen: false`). Hardware execution: **disabled**. Additional spending: **zero**.

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
python -m f1q run --plan bootstrap
python -m f1q resume --run-id <id>    # only if a run was interrupted
python -m f1q receipt --run-id <id>
```

There is no `submit`, hardware, or IBM command. Those modes exit nonzero before any work or network access.

## Evidence locations

- Ledger (mutable, gitignored): `evidence/var/ledger.sqlite`
- Bootstrap artifacts, events, snapshots, receipts: `evidence/bootstrap/`
- Dossier and extraction: `docs/protocol/`
- Stage 1 report: `docs/STAGE_1_REPORT.md`

Fixture outputs are **setup evidence**, not scientific observations. Do not place them in a results table.

## Next stage

Stage 2 -- scenario generator and causal checkpoint schema -- awaits its implementation prompt.
