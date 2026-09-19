# Stage 4 report — action model, objective compiler, QUBO, classical references

Evidence from the local ledger, named artifacts, and pytest. Chat recollection is not evidence. Claims are labeled. Gate C (formulation agreement) is a software/evidence gate. It does **not** establish quantum advantage, F1 calibration, circuit novelty, or publication results.

Direct F1–QUBO precedent exists; Stage 4 makes **no** “first F1 QUBO” claim. The potential contribution remains the later auditable causal, deadline-aware, headroom-aware AI/quantum allocation study—not complexity manufactured from a small one-hot encoding.

Prior runs preserved (identifiers not reused for recomputation): Stage 2 `8f292588-…`, Stage 3 `e2258740-…`, Stage 3.1 `4388ad68-…`, Stage 3.2 `62b1e5ee-…`. Abandoned Stage 4 attempt `1c5b0748-5406-4933-8e41-4f943f4296c7` preserved as failed (empty-menu crash before in-pit continuation fix). Authorised completed Stage 4 run: `e8b87881-74a6-46c7-b48e-6b2496a5d586`.

Starting HEAD discrepancy vs Stage 3.3 report: Stage 3.3 text cited ending commit `0dbbf0b9…`; repository HEAD at Stage 4 start was `6e504f9c…` (clean), which records the Stage 3.3 ending git state. Preserved and reported; not reset.

```text
STAGE_4_STATUS: COMPLETE
STARTING_HEAD_AND_TREE: HEAD 6e504f9c8b9c8517ebfbe542ff1a7d0dc6a8f348 dirty=false; doctor ok; diagnostic-stage3-3 --verify match=true; pytest baseline 88 passed; hardware_execution_enabled false; scientific_protocol DRAFT
ENDING_HEAD_LOCAL_COMMIT_AND_TREE: HEAD 5c949769d96079b1db9aad310a04fcc08c81c29f dirty=false; local commit "Close Stage 4 Gate C formulation with action model, QUBO, and classical references."; not pushed
ENVIRONMENT_AND_NEW_FREE_DEPENDENCIES: CPython 3.12.13 macOS arm64; added numpy==2.5.3 and scipy==1.18.1 (free/open-source; SciPy milp/HiGHS); pins in requirements.lock
ACTION_MODEL_VERSION: 1.0.0
FULL_AND_REDUCED_ACTION_COUNTS: across 64 episodes, per-car full menus min/max 1–22 (sum 1601); reduced menus min/max 1–10 (sum 845); reduction policy kind_delay_compound_lex_set
ILLEGAL_OR_EXCLUDED_ACTIONS: 999 excluded candidates recorded with reasons (expired pit_now, already_in_pit for new pit/delay, horizon, obligation, etc.)
PROXY_OBJECTIVE_UNITS_AND_ASSUMPTIONS: seconds; risk_weight=0; fuel uses estimated kg only; regime pit_loss = green_pit_loss/pace_factor; pair = shared-crew service wait; no private fuel; no continue_to_finish in compiler
COMPILER_EVALUATOR_SEPARATION: verified by AST import-boundary check (sep.ok=true); compiler analytical; evaluator uses RaceSimulator.clone + continue_to_finish
QUBO_CONVENTION_AND_VARIABLE_MAPPING: E_Q=offset+sum_{i<=j} Q_ij x_i x_j; upper+diag serialisation; car1 then car2 action order
PENALTY_PROOF: B, v_min=1, margin=1, M=B/v_min+margin; sample episode00 B≈648.684 M≈649.684; feasible P=0; exhaustive small-n proof_ok=true; adversarial weak M fails
ISING_MAPPING_AND_SCALE_SQ: x=(1-Z)/2; sample s_Q≈1663.693; QUBO↔Ising mismatches=0 on 2^14 strings; scale restoration error ~2e-11
EXHAUSTIVE_SMALL_CASE_ENERGY_AGREEMENT: hand fixtures + sample development instances; feasible energy equals centred direct objective
EXACT_LEGAL_ENUMERATION: NumPy K1×K2 scan; operational competitor; 64/64 completed
INDEPENDENT_MILP_AGREEMENT: scipy.optimize.milp/HiGHS; 64/64 agree with enumeration within tolerance
RESTRICTED_DP_ANALYTICAL_AGREEMENT: exact only when pair≡0; nonzero-pair cases correctly refuse exact claim; zero-pair hand fixtures agree
CLASSICAL_HEURISTIC_CHECKS: greedy+local, uniform, SA — legal incumbents, seed determinism verified by pytest
DEVELOPMENT_MATRIX: planned 64 / completed 64 / failed 0; not a powered comparison
PROXY_HEADROOM_AND_EXACT_RUNTIME_WARNING: heuristic_proxy_headroom=0 on all 64 (gate_e_warning=true); matrix elapsed ≈2.88s; compile+scan within 5s budget on fixtures
EVALUATOR_SEPARATION_PANEL: 8 families; selection_hash before outcomes; rank_agreement 5 agree / 3 disagree (descriptive); modelled diagnostic only
FULL_REGRESSION_RESULT: pytest 109 collected, 108 passed, 1 skipped (optional resume smoke); doctor ok; status readiness stage4-complete-pending-stage5; Stage 3.3 diagnostic verify match=true
FORMULATION_CHECK_RUN_ID_AND_RECEIPT: e8b87881-74a6-46c7-b48e-6b2496a5d586; interrupted after formulation.action_model then resumed; receipt evidence/formulation/receipts/e8b87881-74a6-46c7-b48e-6b2496a5d586.json
RESOURCE_USAGE: max_workers=1; RAM ceiling 60%; Stage 4 cap 1800s; run duration_monotonic_s≈32.70; QPU 0
REVIEW_BUNDLE_PATH_SHA256_AND_CLEAN_EXTRACT: review/STAGE_4_REVIEW.zip sha256 30fbcf9e166c0c767817ea9608020dd66bf51bc9846834f6310d3ad18c5a446b (548 members including inner MANIFEST.sha256.json); sidecar review/STAGE_4_REVIEW.manifest.json; clean extract verified 547 members + aggregate (docs/evidence/stage4/clean_extract_verify.json); targeted formulation pytest exit 0 (20 passed, 1 skipped); formulation-record spotcheck milp_agree=true; omitted ledger/.venv/.git/private seeds as listed in inner manifest; ZIP self-digest authoritative only in sidecar
GATE_C_FORMULATION: PASS
GATE_E_HEADROOM_WARNING: present — exact enumeration removes all proxy headroom on the 64 admitted development checkpoints (mean/max/min headroom 0)
SCIENTIFIC_PROTOCOL: DRAFT
RESERVED_PARTITIONS_MATERIALIZED: none
LEARNED_MODELS_TRAINED: 0
QUANTUM_CIRCUITS_EXECUTED: 0
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0
QPU_USAGE_SECONDS: 0
PUSH_PERFORMED: false
STAGE_5_PREREQUISITES: PARTIAL — Gate C PASS and software/evidence closed; Gate E headroom warning must be carried into Stage 5 design; F1 calibration, reserved partitions, hardware readiness, protocol freeze, and QAOA work remain later limitations / unauthorised
```

## Commands actually run (representative)

| Command | Exit |
| --- | --- |
| `python -m f1q doctor` | 0 |
| `python -m f1q status` | 0 |
| `python -m f1q simulator diagnostic-stage3-3 --verify` | 0 |
| `F1Q_TEST_INTERRUPT_AFTER=formulation.action_model python -m f1q run --plan formulation_check` | 130 (interrupted) |
| `python -m f1q resume --run-id e8b87881-74a6-46c7-b48e-6b2496a5d586` | 0 |
| `python -m pytest` | 0 (108 passed, 1 skipped) |
| clean-extract targeted `pytest tests/formulation/test_gate_c.py` | 0 |

No `git push`. No IBM/QPU/provider call. No Stage 5 QAOA / learned selectors. No reserved-split materialization.

## Documentation

- `docs/ACTION_MODEL.md`
- `docs/OBJECTIVE_COMPILER.md`
- `docs/QUBO_SPECIFICATION.md`
- `docs/CLASSICAL_REFERENCES.md`
- Prompt filed: `docs/prompts/F1_Cursor_Stage_4_Formulation_Prompt.md`

## Closing git note

Local commit `5c949769d96079b1db9aad310a04fcc08c81c29f` records the authorized Stage 4 formulation software and evidence stack. Push was not performed.
