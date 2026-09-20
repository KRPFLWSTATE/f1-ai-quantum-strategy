# Project instructions (always load)

Active stage: **5 — Phase 5 complete (await review)**. Architecture **A2** selected at Stage 5A. Phase 5 implements local A2 scenario-tree policy formulation, classical references, C0/C1 ideal circuits, parameter bank, and learned donor selector. See `docs/STAGE_5_REPORT.md`. After a valid bounded Stage 4 closure: `STAGE_4_ENGINEERING: CLOSED_WITH_DOCUMENTED_LIMITATIONS`. Legacy exhaustive Gate C remains `LEGACY_EXHAUSTIVE_GATE: PARTIAL` with `LEGACY_GATE_ACTION: ARCHIVED_DO_NOT_RESUME`. Counts for archived matrix runs must be read from git-tracked `*.record.json` (see `docs/STAGE_4_CLOSURE_ERRATUM.md`): currently **e85ee977 = 40/64**, **41c28597 = 21 archived files** (interrupted; no completed receipt; excluded from the bounded gate). Stage 4.1 is not independently accepted. Stage 4 evidence is **frozen** — do not resume `e85ee977` / `41c28597` or invoke `formulation_gate_c_closure_check`. `QPU_EXECUTION_AUTHORISED: false`. `NOVELTY_STATUS: PROPOSED_NOT_LITERATURE_VERIFIED`. Development headroom on Phase 5 A2 instances: **ZERO** (superiority path disabled). Next stage after review: **Stage 6 local pilot + resource/precision estimation**, NOT hardware.

## Authority

- Scientific design: `docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf` (v3.1, 18 September 2026), preserved unchanged.
- This conversation's user instructions govern authorization. Stage prompts are filed at `docs/prompts/`.
- `PROJECT_STATUS.md` plus the local ledger are the source of completion state. Chat recollection is not authorization or evidence.
- Legacy count erratum: `docs/STAGE_4_CLOSURE_ERRATUM.md`.
- Phase 5 contract lineage: `docs/STAGE_5A_EXPERIMENT_CONTRACT.md`.

## Project boundary

Permitted root: the directory containing `configs/project.draft.yaml` (intended name `f1-ai-quantum-strategy`). Resolve symlinks before writes. Do not modify the closed previous research project or unrelated repositories.

## Evidence rules

Label claims as: proposed, implemented, verified by a named check, simulated, physically measured, unsupported. A test fixture is not an experimental observation. Successful setup, a development preview, simulator checks, Gate C formulation agreement, and Phase 5 local ideal simulations do not establish scientific novelty, F1 calibration, quantum advantage, or hardware readiness.

**Validation amendment:** engineering acceptance no longer requires simulating every physical-set Cartesian pair. Required instead: 64-episode analytical coverage, real JSON plan round-trips on every admitted pair, QUBO/Ising identities + algebraic penalty bounds, exactly one lex-first tied-optimum terminal witness per episode, and ≤12 committed hand/regression cases. Do not report the old `GATE_C_FORMULATION: PASS` without explaining the changed scope; use `STAGE_4_ENGINEERING` / `LEGACY_EXHAUSTIVE_GATE`.

## Limits in force

- Zero additional spending. Never fall through to a paid account or paid service.
- No QPU default: `hardware_execution_enabled` is false. Do not submit jobs, inspect IBM balances, or implement a provider submission path unless a later stage prompt authorizes it.
- No scheduled tasks, GitHub Actions, autonomous campaigns, automatic resume/packager/closeout watchers, or automatic publishing.
- Do not scrape timing data. Do not train research models on sealed held-out partitions. Do not open held-out test outcomes.
- Do not materialize training, tuning, calibration, test, or shift partitions beyond Phase 5's generated training+tuning block IDs (no calib/eval/test materialisation).
- Do not invoke `formulation_gate_c_closure_check`. Use `python -m f1q.formulation.stage4_closure` for the bounded Stage 4 gate only if re-verification is separately authorised.
- Do not resume `e85ee977-…` or `41c28597-…`.
- Do not alter frozen Phase 5 evidence under `evidence/stage5/<run_id>/` after publication.

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
python -m f1q run --plan phase5
python -m f1q.stage5
python -m f1q.formulation.stage4_closure
python -m f1q resume --run-id <id>
python -m f1q receipt --run-id <id>
python -m f1q generator validate
python -m f1q generator plan-splits [--test-blocks 80|88|...|160]
python -m f1q generator audit --run-id <id>
python -m f1q simulator validate
python -m f1q simulator inspect-checkpoint --run-id --episode-id
python -m f1q simulator interface
python -m f1q simulator diagnostic-stage3-3 [--write|--verify|--verify-historical]
```

Natural language later:

- **do a run** -- execute the next authorized unit in the recorded plan once. It must not expand into the reserved corpus or start Stage 6/hardware unless authorised.
- **resume** -- recover the identified incomplete run. If several exist, list IDs; do not guess. Never suggest resume for archived legacy Gate C runs.
- **show status** -- read the ledger and integrity checks.
- **push to GitHub** -- separate publication instruction only.

## Run / resume semantics

A `run` is an execution container, not automatically one scientific observation. Interrupted attempts are retained. Checksums are verified before skipping completed work; weak `record_hash` must not authenticate evaluator events — automatic matrix resume is fail-closed. Corrupted evidence is not recomputed under the original identifier.

Preserved Stage 4 identifiers: `e8b87881-…`, `c4d0a199-…`, `e85ee977-…` (40 archived / 64 PARTIAL), `41c28597-…` (21 archived files; interrupted; no completed receipt). Do not overwrite them.

## Simulator versions (current tree)

- `simulator_version`: **1.0.4**
- `interface_version`: **3.1.0**

Package constants, YAML configs, and engine state must agree (`load_simulator_config` fails closed on mismatch). Package version: **0.5.0**.

## GitHub

Creating the private empty remote is a setup step. Pushing commits is a later, separate requested action unless the current user instruction authorises it.
