# Project instructions (always load)

Active stage: **4 Closure — bounded engineering closure (`STAGE_4_ENGINEERING: CLOSED_WITH_DOCUMENTED_LIMITATIONS`)**. The former Stage 4.2 exhaustive all-pair terminal Cartesian development matrix is **withdrawn** as an engineering gate and remains **LEGACY_EXHAUSTIVE_GATE: PARTIAL** at saved coverage (`e85ee977` 40/64; `41c28597` 14/64 interrupted). Stage 4.1 is not independently accepted. Stage 5 may begin only as an architecture decision addressing zero proxy headroom; QAOA / learned selectors / hardware paths are **not** authorised to execute.

## Authority

- Scientific design: `docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf` (v3.1, 18 September 2026), preserved unchanged.
- This conversation's user instructions govern authorization. Stage prompts are filed at `docs/prompts/`. Stage 4 Final Closure authorization: operator-provided `F1_Stage_4_Final_Closure.md`.
- `PROJECT_STATUS.md` plus the local ledger are the source of completion state. Chat recollection is not authorization or evidence.

## Project boundary

Permitted root: the directory containing `configs/project.draft.yaml` (intended name `f1-ai-quantum-strategy`). Resolve symlinks before writes. Do not modify the closed previous research project or unrelated repositories.

## Evidence rules

Label claims as: proposed, implemented, verified by a named check, simulated, physically measured, unsupported. A test fixture is not an experimental observation. Successful setup, a development preview, simulator checks, and Gate C formulation agreement do not establish scientific novelty, F1 calibration, quantum advantage, or hardware readiness.

**Validation amendment (Stage 4 Final Closure):** engineering acceptance no longer requires simulating every physical-set Cartesian pair. Required instead: 64-episode analytical coverage, QUBO/Ising identities + algebraic penalty bounds, exactly one lex-first tied-optimum terminal witness per episode, and ≤12 committed hand/regression cases. Do not report the old `GATE_C_FORMULATION: PASS` without explaining the changed scope; use `STAGE_4_ENGINEERING` / `LEGACY_EXHAUSTIVE_GATE`.

## Limits in force

- Zero additional spending. Never fall through to a paid account or paid service.
- No QPU default: `hardware_execution_enabled` is false. Do not submit jobs, inspect IBM balances, or implement a provider submission path unless a later stage prompt authorizes it.
- No scheduled tasks, GitHub Actions, autonomous campaigns, automatic resume/packager/closeout watchers, or automatic publishing.
- Do not scrape timing data. Do not train research models. Do not open held-out test outcomes.
- Do not materialize training, tuning, calibration, test, or shift partitions.
- Do not implement Stage 5 QAOA circuits, mixers, angle banks, learned selectors, or dispatch models unless a later prompt authorizes it.
- Do not invoke `formulation_gate_c_closure_check` (launches the withdrawn exhaustive matrix). Use `python -m f1q.formulation.stage4_closure` for the bounded gate.

## Commands

```text
python -m f1q doctor
python -m f1q status
python -m f1q run --plan bootstrap
python -m f1q run --plan development_preview
python -m f1q run --plan simulator_check
python -m f1q run --plan simulator_followup
python -m f1q run --plan simulator_repair
python -m f1q run --plan formulation_check
python -m f1q run --plan formulation_repair_check
python -m f1q.formulation.stage4_closure
python -m f1q resume --run-id <id>
python -m f1q receipt --run-id <id>
python -m f1q generator validate
python -m f1q generator plan-splits [--test-blocks 80|88|...|160]
python -m f1q generator audit --run-id <id>
python -m f1q simulator validate
python -m f1q simulator inspect-checkpoint --run-id <id> --episode-id <id>
python -m f1q simulator interface
python -m f1q simulator diagnostic-stage3-3 [--write|--verify|--verify-historical]
```

Natural language later:

- **do a run** -- execute the next authorized unit in the recorded plan once. It must not expand into the reserved corpus or start Stage 5 hardware/QAOA unless authorised.
- **resume** -- recover the identified incomplete run. If several exist, list IDs; do not guess. Matrix resume is fail-closed on weak `record_hash`.
- **show status** -- read the ledger and integrity checks.
- **push to GitHub** -- separate publication instruction only.

## Run / resume semantics

A `run` is an execution container, not automatically one scientific observation. Setup fixtures, development previews, simulator checks, and formulation checks are none of training/tuning/calibration/test/shift. Interrupted attempts are retained. Checksums are verified before skipping completed work; weak `record_hash` (math fields only) must not authenticate evaluator events — automatic matrix resume is fail-closed. Corrupted evidence is not recomputed under the original identifier.

Preserved Stage 4 identifiers: `e8b87881-…`, `c4d0a199-…`, `e85ee977-…` (40/64 PARTIAL), `41c28597-…` (14/64 interrupted). Do not overwrite them.

## GitHub

Creating the private empty remote is a setup step. Pushing commits is a later, separate requested action.
