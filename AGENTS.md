# Project instructions (always load)

Active stage: **6 — Phase 6 corrected closure (audit/correction complete; Phase 7 not authorised)**. Architecture **A2** selected at Stage 5A. Phase 5 final acceptance: `PASS_WITH_DOCUMENTED_LIMITATIONS` (commit `1c7631e…`; corrected run `e6b3588b-…`). Phase 6 historical run `bd83cb22-…` **preserved but superseded** for shot/noise/capacity/sizing/Gate E claims by corrected run `2a3fb275-6c37-4bbc-bdb4-addede80b5c3`: shot accounting corrected (1024 draws); gate-channel noisy panel replaces withdrawn jitter panel; `DEVELOPMENT_HEADROOM: ZERO`; `GATE_E: FAIL_FOR_INTENDED_CONTRIBUTION`; `PROTOCOL_STATUS: MECHANISM_SCOPE_DRAFT_V2_NOT_FINAL_TEST_AUTHORISED`; `CAUSAL_OPERATIONAL_READINESS: false`; `PHASE_7_MECHANISM_READY: false`. Authoritative reports: `docs/PHASES_1_TO_6_ACCEPTANCE_REPORT.md`, `docs/STAGE_6_CORRECTED_REPORT.md`. After a valid bounded Stage 4 closure: `STAGE_4_ENGINEERING: CLOSED_WITH_DOCUMENTED_LIMITATIONS`. Legacy exhaustive Gate C remains `LEGACY_EXHAUSTIVE_GATE: PARTIAL` with `LEGACY_GATE_ACTION: ARCHIVED_DO_NOT_RESUME` (e85ee977 40/64; 41c28597 21 archived files — see `docs/STAGE_4_CLOSURE_ERRATUM.md`). Stage 4.1 is not independently accepted. Stage 4 evidence is **frozen** — do not resume `e85ee977` / `41c28597` or invoke `formulation_gate_c_closure_check`. `QPU_EXECUTION_AUTHORISED: false`. Development headroom on checked A2 instances: **ZERO** (superiority path disabled). Next authorised stage: **NONE automatic — Phase 7 only after explicit prompt**.

## Authority

- Scientific design: `docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf` (v3.1, 18 September 2026), preserved unchanged.
- This conversation's user instructions govern authorization. Stage prompts are filed at `docs/prompts/`.
- `PROJECT_STATUS.md` plus the local ledger are the source of completion state. Chat recollection is not authorization or evidence.
- Legacy count erratum: `docs/STAGE_4_CLOSURE_ERRATUM.md`.
- Phase 5 contract lineage: `docs/STAGE_5A_EXPERIMENT_CONTRACT.md`.
- Phase 6 freeze / novelty: `docs/STAGE_6_PROTOCOL_FREEZE_V2.md`, `docs/STAGE_6_NOVELTY_COMPARISON.md` (v1 freeze/report preserved historically).

## Project boundary

Permitted root: the directory containing `configs/project.draft.yaml` (intended name `f1-ai-quantum-strategy`). Resolve symlinks before writes. Do not modify the closed previous research project or unrelated repositories.

## Evidence rules

Label claims as: proposed, implemented, verified by a named check, simulated, physically measured, unsupported. A test fixture is not an experimental observation. Successful setup, a development preview, simulator checks, Gate C formulation agreement, Phase 5 local ideal simulations, and Phase 6 mechanism pilots do not establish scientific novelty, F1 calibration, quantum advantage, or hardware readiness.

**Validation amendment:** engineering acceptance no longer requires simulating every physical-set Cartesian pair. Required instead: 64-episode analytical coverage, real JSON plan round-trips on every admitted pair, QUBO/Ising identities + algebraic penalty bounds, exactly one lex-first tied-optimum terminal witness per episode, and ≤12 committed hand/regression cases. Do not report the old `GATE_C_FORMULATION: PASS` without explaining the changed scope; use `STAGE_4_ENGINEERING` / `LEGACY_EXHAUSTIVE_GATE`.

## Limits in force

- Zero additional spending. Never fall through to a paid account or paid service.
- No QPU default: `hardware_execution_enabled` is false. Do not submit jobs, inspect IBM balances, or implement a provider submission path unless a later stage prompt authorizes it.
- No scheduled tasks, GitHub Actions, autonomous campaigns, automatic resume/packager/closeout watchers, or automatic publishing.
- Do not scrape timing data. Do not train research models on sealed held-out partitions. Do not open held-out test outcomes.
- Do not materialize reserved **final-test** or **shift** partitions. Phase 6 may register an isolated `phase6.calib.*` calibration cohort (implemented); do not treat it as final-test evidence.
- Do not invoke `formulation_gate_c_closure_check`. Use `python -m f1q.formulation.stage4_closure` for the bounded Stage 4 gate only if re-verification is separately authorised.
- Do not resume `e85ee977-…` or `41c28597-…`.
- Do not alter frozen Phase 5 evidence under `evidence/stage5/<run_id>/` after publication.
- Do not alter historical Phase 6 evidence under `evidence/stage6/bd83cb22-…/` (superseded by `evidence/stage6_corrected/`).
- Do not begin Phase 7 automatically; feasibility ≠ permission.

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
python -m f1q run --plan phase6
python -m f1q.stage5
python -m f1q.stage6
python -m f1q.stage6.corrected_run
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

- **do a run** -- execute the next authorized unit in the recorded plan once. It must not expand into the reserved corpus or start Stage 7/hardware unless authorised.
- **resume** -- recover the identified incomplete run. If several exist, list IDs; do not guess. Never suggest resume for archived legacy Gate C runs.
- **show status** -- read the ledger and integrity checks.
- **push to GitHub** -- separate publication instruction only (authorised when the current user prompt requests it).

## Run / resume semantics

A `run` is an execution container, not automatically one scientific observation. Interrupted attempts are retained. Checksums are verified before skipping completed work; weak `record_hash` must not authenticate evaluator events — automatic matrix resume is fail-closed. Corrupted evidence is not recomputed under the original identifier.

Preserved Stage 4 identifiers: `e8b87881-…`, `c4d0a199-…`, `e85ee977-…` (40 archived / 64 PARTIAL), `41c28597-…` (21 archived files; interrupted; no completed receipt). Do not overwrite them.

Preserved Stage 5/6 identifiers: Phase 5 `6ad68021-…` (historical), `e6b3588b-…` (corrected), final_acceptance_repair; Phase 6 historical `bd83cb22-…`; Phase 6 corrected `2a3fb275-…`.

## Simulator versions (current tree)

- `simulator_version`: **1.0.4**
- `interface_version`: **3.1.0**

Package constants, YAML configs, and engine state must agree (`load_simulator_config` fails closed on mismatch). Package version: **0.5.0** (Stage 6 module `0.6.1`).

## GitHub

Creating the private empty remote is a setup step. Pushing commits is a later, separate requested action unless the current user instruction authorises it.
