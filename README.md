# f1-ai-quantum-strategy

Independent research infrastructure for a **deadline-constrained two-car pit-strategy** study that may later combine a motorsport simulator, classical references, an evaluated learned policy, and quantum candidate generation.

This repository is **not** affiliated with a Formula 1 team. It reports **no experimental results**. Completing software setup, a development preview, or simulator checks does not establish scientific novelty, F1 calibration, or hardware readiness.

## Current scope -- Phase 5 complete (local)

Restricted independent race simulator (`simulator.v1` **1.0.4** / interface **3.1.0**), Stage 3.x validation/repair/evidence correction, Stage 4 local formulation closed with documented limitations, and **Phase 5** A2 scenario-contingent strategy-policy pipeline (classical references, C0/C1 ideal circuits, parameter bank, learned donor selector). Engineering status: see `docs/STAGE_5_REPORT.md`. Legacy exhaustive Gate C remains `PARTIAL` / `ARCHIVED_DO_NOT_RESUME` (see `docs/STAGE_4_CLOSURE_ERRATUM.md`). This does **not** establish quantum advantage, F1 calibration, held-out H1/H2/H3 evidence, or hardware readiness. Stage 4 Gate E: `PROXY_HEADROOM: ZERO`. Phase 5 development headroom: `ZERO` (superiority path disabled).

Scientific protocol status: **DRAFT** (`frozen: false`). Hardware execution: **disabled**. Additional spending: **zero**. `QPU_EXECUTION_AUTHORISED: false`. `NOVELTY_STATUS: PROPOSED_NOT_LITERATURE_VERIFIED`.

## Supported local environment

- macOS (Apple silicon verified on the author's machine), CPython **3.12** (`requires-python >=3.12,<3.14`)
- Project-local virtualenv; no system Python changes and no administrator install
- Optional local Qiskit for ideal circuit simulation only (no IBM Runtime / provider path)

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
python -m f1q run --plan formulation_check
python -m f1q run --plan phase5
python -m f1q.stage5
python -m f1q resume --run-id <id>    # only if a run was interrupted; never legacy Gate C
python -m f1q receipt --run-id <id>
python -m f1q generator audit --run-id <id>
python -m f1q simulator validate
python -m f1q simulator inspect-checkpoint --run-id <id> --episode-id <id>
python -m f1q simulator interface
python -m f1q simulator diagnostic-stage3-3 [--write|--verify]
```

There is no `submit`, hardware, or IBM command. Reserved scientific partitions cannot be materialized. Those modes exit nonzero before any work or network access.

## Evidence locations

- Ledger (mutable, gitignored): `evidence/var/ledger.sqlite`
- Bootstrap artifacts: `evidence/bootstrap/`
- Development preview specs/receipts: `evidence/development/`
- Formulation Stage 4 artifacts/receipts: `evidence/formulation/`
- Phase 5 evidence: `evidence/stage5/`, summaries `docs/evidence/stage5/`
- Phase 5 report: `docs/STAGE_5_REPORT.md`
- Private simulator-state seeds (gitignored, not solver-visible): `evidence/development/private/`
- Dossier and extraction: `docs/protocol/`
- Stage 1–4 reports under `docs/`
- Stage 5A architecture/contract: `docs/STAGE_5A_ARCHITECTURE_REPORT.md`, `docs/STAGE_5A_EXPERIMENT_CONTRACT.md`

Development outputs, simulator-check admissions, and Phase 5 tuning results are **not** held-out scientific observations. Do not place them in a results table as quantum advantage.

## Next stage

**Stage 6 — local pilot + resource/precision estimation**, only after user review and an explicit Stage 6 prompt. Not hardware. Superiority pilot is not ready while Phase 5 development headroom is zero.
