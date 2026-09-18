# Stage 2 report

Generated from named commands, pytest, and serialized artifacts. Labels: implemented, verified by a named check. The development preview is **not** a scientific result and is **not** 64 validated race checkpoints.

```text
STAGE_1_FOLLOWUP: PASS, with report path docs/STAGE_1_FOLLOWUP.md
FINAL_SOURCE_AND_COMMIT: git HEAD 24346827c11c81717e8161a9a5c9414ea4ba9428 on main (dirty working tree). Preview source snapshot c836750413a4afcecc567707fd94de516500af76fdb3895b97379cd22258475a (git_commit recorded, git_dirty true). Documentation-only files written after that snapshot do not change the primary code hash. Bootstrap snapshot 320dc0f9e7457e31d2a05a7d998b2bedb909447559e04acf1866cb6704aaa583 retained; unrepaired doctor.py bytes were not reconstructable.
STAGE_2_STATUS: COMPLETE
IMPLEMENTED_COMMANDS: python -m f1q doctor | status | run --plan bootstrap | run --plan development_preview | resume --run-id | receipt --run-id | generator validate | generator plan-splits [--test-blocks 80|160] | generator audit --run-id | generator handoff
GENERATOR_AND_SCHEMA_VERSIONS: generator 2.0.0 ; causal schema 2.0.0 ; ledger schema 2 ; package 0.2.0 ; Stage 1 receipt schema 1.0.0 retained
CONFIGURATION_HASH: generator.v1.yaml SHA-256 ffd3f2e5ac5660ef19bb532c099334028aa8e4012340474ad08dacaf774e353c ; project.draft.yaml SHA-256 7387d47c910e08827bd166e0b8166fb9309330e2196c89d8bf7fb83eb3274597 (draft, not a frozen protocol hash)
PARTITION_PLAN_COUNTS: training 120/960 ; tuning 16/128 ; calibration 24/192 ; test floor 80/640 ; main floor 240/1920 ; shift draft 40/320 ; floor including shift 280/2240 ; test maximum 160/1280 ; maximum including shift 360/2880 ; materialized false
DEVELOPMENT_PREVIEW: 8 blocks / 64 specifications / 8 families / 32 SC / 32 VSC (from artifacts)
VALIDATED_RACE_CHECKPOINTS: 0 pending Stage 3
RESERVED_PARTITIONS_MATERIALIZED: none
REJECTIONS_AND_FAILED_ATTEMPTS: schema rejections 0 ; injected interrupt attempts 1 (unit development.preview.fam.01 after fam.00 completed) ; generation retries 0
CHECKS: 60 pytest passed, exit 0 (docs/evidence/stage2/pytest.txt SHA-256 9352925e5e271773731e7ca3a390daf15479f6b144d2d059ca8d677d62821619) ; generator validate exit 0 ; plan-splits 80 and 160 exit 0 ; independent audit ok true ; doctor exit 0 ; live interrupt exit 130 then resume exit 0 ; materialize-training exit 2 ; campaign exit 2
RUN_ID_AND_RECEIPT: 8f292588-a328-4232-b425-c36c610a29f5 ; evidence/development/receipts/8f292588-a328-4232-b425-c36c610a29f5.json ; audit docs/evidence/stage2/preview.audit.json SHA-256 4cb95e61ced33c582e9c549a5cb66f0c9e7c43ab5a05b1b1ec1e219ba842dafc
ASSUMPTIONS_REQUIRING_STAGE_3_OR_PILOT_VALIDATION: green_pit_loss combined transit+service decomposition ; tyre lap-time mapping ; SC/VSC speed profiles and realized duration ; rival policy execution ; race clock at checkpoint ; numeric effective deadlines ; fuel 1.8 kg/lap and 2 kg uncertainty ; compound/set counts ; communication margin 1.0 s ; fictional track archetypes ; shift-panel allocation freeze
SCIENTIFIC_PROTOCOL: DRAFT
RESEARCH_COMPARISON_EXPERIMENTS_EXECUTED: 0
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0
QPU_USAGE_FROM_THIS_STAGE: 0 seconds ; account not queried
PUSH_PERFORMED: false
NEXT_STAGE: 3 — simulator adapter and independent mechanism checks
```

## Named checks

| Risk | Result | Evidence |
| --- | --- | --- |
| Eight families, floor/max split counts, per-block 4 SC / 4 VSC | passed | `tests/test_families_splits.py` ; live `docs/evidence/stage2/plan_splits_floor.json`, `plan_splits_max.json` ; audit `realized` 8/64/32/32 |
| Deterministic payloads across processes and reversed family iteration | passed | `tests/test_development_preview.py` |
| No scientific-split leakage of development IDs | passed | `tests/test_independent_audit.py` ; audit `scientific_split_membership: []` |
| Reserved partitions cannot be materialized | passed | `tests/test_reserved_partitions.py` ; `docs/evidence/stage2/reject_materialize.err` exit 2 |
| Domain-separated streams; fitting seed isolated from episode/evaluation keys | passed | `tests/test_identities_streams.py` |
| Observation excludes private seeds, future duration, future rival decisions; future availability rejected; labeled forecasts permitted | passed | `tests/test_observation_projection.py` |
| Structural validity, exclusions, expired pit not relabeled | passed | `tests/test_structural_validity.py` ; `tests/test_observation_projection.py` |
| Interrupt/resume preserves completed artifacts; source mismatch and corruption block silent reuse | passed | live interrupt/resume of `8f292588-…` ; `tests/test_development_preview.py` ; `tests/test_authorization.py` ; `tests/test_evidence_integrity.py` |
| Independent audit from serialized specs | passed | `python -m f1q generator audit --run-id 8f292588-…` exit 0, `ok: true` |
| Stage 1 regressions after integration | passed | same pytest session, 60 passed |
| Doctor construction failure is a controlled error | passed | `tests/test_doctor_ledger_failure.py` |
| Simulator refuses placeholder results | passed | `tests/test_observation_projection.py::test_simulator_adapter_refuses_placeholder_results` |

## Live preview

Interrupted after `development.preview.fam.00` (exit 130, injected failure 1), then resumed to completed (attempt_count 9, 8/8 units). Artifacts: 64 `*.spec.json` under `evidence/development/artifacts/8f292588-a328-4232-b425-c36c610a29f5/`. Private simulator-state records are under `evidence/development/private/` (gitignored, not solver-visible).

## Documentation after the checked code snapshot

Primary code snapshot for the preview run: `c836750413a4afcecc567707fd94de516500af76fdb3895b97379cd22258475a`. This report, `docs/GENERATOR_SPEC.md`, `PROJECT_STATUS.md`, `AGENTS.md`, and related narrative files were edited after that snapshot. Identity policy v1.1.0: documentation-only edits do not invalidate the primary hash.

No GitHub push. No QPU jobs. Hardware execution remains false.
