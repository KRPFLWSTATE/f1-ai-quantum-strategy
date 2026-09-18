# Stage 1 report

Generated from named commands and ledger evidence. Labels: implemented, verified by a named check. This is not a scientific result.

```text
STAGE_1_STATUS: COMPLETE
PROJECT_ROOT: /Users/kawinperera/f1-ai-quantum-strategy
DOSSIER_VERSION_AND_SHA256: v3.1 | 2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76
LOCAL_REPO_AND_BRANCH: local git repository on main; no commits at the time of the checks
GITHUB_REPO: https://github.com/KRPFLWSTATE/f1-ai-quantum-strategy (verified private, empty, owner KRPFLWSTATE)
PUSH_PERFORMED: false
PYTHON_AND_ENVIRONMENT: CPython 3.12.13, Darwin 25.5.0 arm64, 10 CPUs, 25769803776 B RAM, project venv .venv; fresh venv .venv-fresh import check passed
DEPENDENCY_LOCK: requirements.lock SHA-256 fe7a80a5424ff1ff5d9340a4080c7ab5d963ff1c19fafeee56fa85aad70972e0
IMPLEMENTED_COMMANDS: python -m f1q doctor | status | run --plan bootstrap | resume --run-id | receipt --run-id
CHECKS: see table below
BOOTSTRAP_RUN_ID: a0c7a5d7-4387-40f8-82f7-08b7d3593f85
RECEIPT_PATH: evidence/bootstrap/receipts/a0c7a5d7-4387-40f8-82f7-08b7d3593f85.json
SOURCE_SNAPSHOT_AND_COMMIT: snapshot 320dc0f9e7457e31d2a05a7d998b2bedb909447559e04acf1866cb6704aaa583 ; git_commit null; git_dirty true (checks ran before the setup commit)
SCIENTIFIC_PROTOCOL: DRAFT
RESEARCH_EXPERIMENTS_EXECUTED: 0
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0
QPU_USAGE_FROM_THIS_STAGE: 0 seconds; account balance not queried
HARDWARE_EXECUTION_ENABLED: false
BLOCKERS_OR_DEVIATIONS: see docs/DEVIATIONS.md; none block Stage 1 completion
NEXT_STAGE: 2 -- scenario generator and causal checkpoint schema
```

Draft configuration hash (not a frozen protocol hash): `b9bd5a15caeb329edc67943e176ce57844637bf6fbd4ba4f89006e4dc1ba3592`.

A second complete setup-fixture run also exists: `77816c72-6248-4ae2-b944-70973975888a`. It is not a scientific observation.

## Checks

| Check | Result | Evidence |
| --- | --- | --- |
| 1 Configuration/schema rejection | passed | `tests/test_schema_rejection.py`; pytest exit 0 (`evidence/bootstrap/checks/pytest_exit.txt`, `docs/evidence/stage1/pytest.txt`) |
| 2 Boundary protection (traversal and symlink escape) | passed | `tests/test_boundary.py`; temporary fixture only |
| 3 Reproducible fixture payloads | passed | `tests/test_reproducible_payload.py` |
| 4 Interruption and resume | passed | pytest `tests/test_interrupt_resume.py`; live injected interrupt then resume of `a0c7a5d7-4387-40f8-82f7-08b7d3593f85` (`docs/evidence/stage1/bootstrap.interrupt.json`, `docs/evidence/stage1/bootstrap.resume.json`). Completed unit preserved; interrupted attempt retained (`injected_failure_count: 1`); remaining units completed on resume (`attempt_count` 2 then 4) |
| 5 Concurrent dispatch | passed | `tests/test_concurrent.py` and `tests/test_concurrent_dispatch.py`; second command exit 2 with `LedgerLocked` |
| 6 Evidence integrity | passed | `tests/test_evidence_integrity.py`, `tests/test_integrity.py`; checksum mismatch reported and not overwritten; receipt counts from events |
| 7 Authorization / no IBM path | passed | `tests/test_authorization.py`; live `--hardware` and `--plan campaign` exit 2 (`evidence/bootstrap/checks/hardware_exit.txt`, `campaign_exit.txt`) with no provider login |
| 8 Install and CLI smoke | passed | fresh venv `.venv-fresh` (`evidence/bootstrap/checks/fresh_env_import.txt`, exit 0); `python -m f1q doctor` exit 0 after ledger present (`evidence/bootstrap/checks/doctor_after_ledger.json`); `status` exit 0; bootstrap; `receipt --run-id` exit 0 |

Doctor once returned exit 1 after the first bootstrap because `_ledger` raised `UnboundLocalError` if `Ledger(...)` failed before assignment. That was repaired and doctor was re-run against the live ledger (exit 0, all six checks `ok`). That failure was a software defect, not a scientific result.

## Dossier extraction

- 33/33 pages extracted to `docs/protocol/dossier_extracted.txt`
- SHA-256 matches the PDF and `configs/project.draft.yaml`
- Formula/table notes: `docs/protocol/SOURCE_HASH.md`
- Original PDF preserved unchanged

## Short file tree (source and tracked evidence)

```text
f1-ai-quantum-strategy/
  AGENTS.md
  PROJECT_STATUS.md
  README.md
  NOTICE
  pyproject.toml
  requirements.lock
  .cursor/rules/00-project.mdc
  configs/project.draft.yaml
  configs/plans/bootstrap.yaml
  configs/fixtures/fictional_checkpoint.json
  configs/schemas/*.schema.json
  src/f1q/          CLI, schemas, ledger, doctor, runner
  tests/
  docs/protocol/    dossier PDF, extract, SOURCE_HASH, PROTOCOL_RECORD (frozen: false)
  docs/STAGE_1_REPORT.md
  evidence/bootstrap/receipts/
  evidence/bootstrap/checks/
```

Mutable SQLite ledger remains gitignored at `evidence/var/`.

## Next smallest user action

None required for Stage 1. Do not push. Stage 2 waits for a separate implementation prompt. A later “push to GitHub” instruction can publish this private repository.
