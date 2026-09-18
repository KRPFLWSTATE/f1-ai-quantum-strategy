# Stage 1 follow-up

Generated from named commands and retained ledger/snapshot bytes. Labels: implemented, verified by a named check. Chat recollection is not evidence. The original Stage 1 report and bootstrap raw records are preserved.

```text
STAGE_1_FOLLOWUP: PASS
GIT_HEAD: 24346827c11c81717e8161a9a5c9414ea4ba9428 (main, working tree dirty after this follow-up)
REMOTE: origin https://github.com/KRPFLWSTATE/f1-ai-quantum-strategy.git ; git ls-remote origin empty (not pushed)
BOOTSTRAP_SNAPSHOT: 320dc0f9e7457e31d2a05a7d998b2bedb909447559e04acf1866cb6704aaa583
BOOTSTRAP_SNAPSHOT_RECOMPUTED_FROM_MANIFEST: 320dc0f9e7457e31d2a05a7d998b2bedb909447559e04acf1866cb6704aaa583
FOLLOWUP_CODE_SNAPSHOT: aeee2a65ebdabfdad8bbee54d12eae85d8427a689941690246e67067988f2519
HARDWARE_EXECUTION_ENABLED: false
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0
```

## A. Final source identity

Verified against git and retained snapshot files, not assumed from the Stage 1 report.

| Record | Value | Evidence |
| --- | --- | --- |
| Branch | `main` | `docs/evidence/stage1_followup/git_branch.txt` |
| HEAD | `24346827c11c81717e8161a9a5c9414ea4ba9428` | `docs/evidence/stage1_followup/git_head.txt` |
| HEAD message | Record Stage 1 doctor repair and check-evidence notes | `docs/evidence/stage1_followup/git_log.txt` |
| Parent | `f0dd49ff63dac6d098d0685d92c2f8dae02fbc79` Initialize Stage 1 research infrastructure and evidence ledger | same |
| Working tree at inspection start | clean | `docs/evidence/stage1_followup/git_status_porcelain.txt` empty |
| Working tree after this follow-up | dirty (doctor/snapshot repairs, tests, this evidence) | `git status` |
| Remote | `origin` → `https://github.com/KRPFLWSTATE/f1-ai-quantum-strategy.git` | `docs/evidence/stage1_followup/git_remote.txt` |
| Remote contents | empty (`git ls-remote origin` produced no refs) | `docs/evidence/stage1_followup/git_ls_remote.txt` |

Bootstrap run `a0c7a5d7-4387-40f8-82f7-08b7d3593f85` records `source_snapshot_hash=320dc0f9e7457e31d2a05a7d998b2bedb909447559e04acf1866cb6704aaa583`, `git_commit=null`, `git_dirty=true`. The retained manifest at `evidence/bootstrap/snapshots/a0c7a5d7-4387-40f8-82f7-08b7d3593f85.json` recomputes to that same hash from its `files` list (**verified** by `docs/evidence/stage1_followup/source_identity.json`). Git HEAD is **not** that snapshot: the bootstrap ran on an uncommitted tree.

File-level comparison of the retained manifest against the post-repair working tree: 41/42 listed files still match. The only code-identity change is `src/f1q/doctor.py`:

| doctor.py bytes | SHA-256 | Where |
| --- | --- | --- |
| Unrepaired (bootstrap snapshot) | `96eadf13b4c47944e021f2340707a3def608319f96de223dbce4b464836e6bf9` | snapshot manifest only |
| Guarded `ledger = None` | `234c7e4d7fcd7b4bcb8d8a4a0bfbf9e31ebf1c2cca2f80c623e9c96af2d3fca1` | git `f0dd49ff` and `24346827` |
| Guard plus controlled initialization error | `43bdfce43114261e36fc03a34febf43664b494498bf39ac2bdee1f68d7c47bd0` | this follow-up working tree |

The unrepaired `doctor.py` bytes **cannot be reconstructed** from git objects (**verified**: no blob hashes to `96eadf13…`). That is an **evidence omission**, not a rewrite of the bootstrap receipt. The receipt and snapshot manifest are retained. A new identified verification is this follow-up's pytest/doctor/install logs, not a recomputation of run `a0c7a5d7-…`.

Which snapshot contains the `_ledger`/`UnboundLocalError` repair:

- Snapshot `320dc0f9…` does **not** contain the repair (`doctor.py` `96eadf13…`).
- Git commits `f0dd49ff` and `24346827` **do** contain `ledger = None`. Commit `24346827` is documentation-only relative to `f0dd49ff` (`PROJECT_STATUS.md`, `docs/DEVIATIONS.md`, `docs/STAGE_1_REPORT.md`); `src/f1q/doctor.py` is identical in both commits.

Hashing policy (**implemented**, **verified** by `tests/test_source_identity_policy.py`):

- Primary snapshot hash (`snapshot["hash"]`) covers `src/**/*.py`, `configs/**/*`, `pyproject.toml`, `requirements.lock`, `tests/**/*.py`, `docs/protocol/SOURCE_HASH.md`.
- Narrative documentation uses `documentation_hash`. Documentation-only edits do not change the primary hash.
- Policy version `1.1.0` is recorded on new snapshots. Git HEAD is a separate field and does not identify a dirty tree.

## B. Checks after the repair

Original live records (preserved, not restated as a new audit of `320dc0f9…`):

| Check | Original result | Path |
| --- | --- | --- |
| pytest | exit 0, 24 tests | `docs/evidence/stage1/pytest.txt`, `evidence/bootstrap/checks/pytest_exit.txt` |
| doctor before ledger? / after first bootstrap | exit 1 | `docs/evidence/stage1/doctor.txt`, `evidence/bootstrap/checks/doctor_exit.txt` |
| doctor after repair against live ledger | exit 0 | `evidence/bootstrap/checks/doctor_after_ledger.json` (exit 0) |
| interrupt/resume | injected interrupt then resume of `a0c7a5d7-…` | `docs/evidence/stage1/bootstrap.interrupt.json`, `bootstrap.resume.json` |
| concurrent dispatch | second command `LedgerLocked` | `tests/test_concurrent.py`, `tests/test_concurrent_dispatch.py` |

Those original pytest/doctor JSON files record `git_commit: null`. They therefore **do not** identify git `f0dd49ff`/`24346827`. Whether they ran on unrepaired `96eadf13…` or repaired `234c7e4d…` cannot be proven from those logs alone. That is an evidence omission. The live UnboundLocalError (exit 1) is retained as a software-defect record; it is not a scientific result.

Follow-up suite on the identified current source (isolated tmp ledgers in pytest; production ledger untouched by tests):

| Command | Exit | Evidence |
| --- | --- | --- |
| `python -m pytest tests -q` after doctor/snapshot repairs | 0 (30 passed) | `docs/evidence/stage1_followup/pytest_after_repair.txt` SHA-256 `a2a3c4b68aa70416fb312e4aaae8e14c352c367fc692b27c4622eb9644d825cf` |
| `python -m f1q doctor` | 0 | `docs/evidence/stage1_followup/doctor.json` |
| `python -m f1q status` | 0 | `docs/evidence/stage1_followup/status.json` |
| Injected `Ledger.__init__` failure | controlled `ledger initialization failed`, no `UnboundLocalError` | `tests/test_doctor_ledger_failure.py` (**verified**) |
| Injected `Ledger.acquire` `LedgerLocked` | controlled error, no `UnboundLocalError` | same |

Doctor now returns a failed check with `error_type` when ledger initialization raises, instead of an unassigned-variable crash (**implemented** in `src/f1q/doctor.py`).

## C. Installation outside the source directory

Original `evidence/bootstrap/checks/fresh_env_import.txt` records `import_ok` from `.venv-fresh`. That is **not** evidence of a non-editable install or of CLI execution from a directory outside the tree with `PYTHONPATH` unset. Evidence omission, not an install defect.

Follow-up (**verified**):

1. Clean venv, `pip install -r requirements.lock`, `pip install .` (not editable).
2. `cwd` `/private/tmp/f1q-followup-wheeloutside-KWwtrB`, `PYTHONPATH` unset, `PYTHONNOUSERSITE=1`.
3. Interpreter `/private/tmp/f1q-followup-wheelvenv-Dcs3Jv/venv/bin/python` (CPython 3.12.13).
4. Installed package `/private/tmp/f1q-followup-wheelvenv-Dcs3Jv/venv/lib/python3.12/site-packages/f1q/__init__.py` (`installed_inside_venv: true`).
5. `python -m f1q --project-root /Users/kawinperera/f1-ai-quantum-strategy doctor` exit 0.

Paths: `docs/evidence/stage1_followup/fresh_wheel_import.json` (SHA-256 `a53c6d7eccb62e9d14eb4dafa1fe474a0d9482670179679fc454ec14730c881d`), `fresh_wheel_doctor.json` (SHA-256 `36d7290a652e35da8d5f09ee2d543de4427eb092ea668d62258f6d5042410db6`), `fresh_wheel_doctor_exit.txt` = 0. An additional editable-install check is recorded in `fresh_outside_import.json`; the non-editable wheel/venv install is the install-identity evidence.

## Remaining limits

- Unrepaired `doctor.py` bytes from snapshot `320dc0f9…` are not in git. Do not rewrite the bootstrap receipt.
- Scientific protocol remains DRAFT. Hardware remains disabled. Account balance was not queried.
- Missing local Git author identity is not treated as a scientific blocker; source snapshots and git commits are recorded.
- No unresolved ledger, authorization, or isolation defect that blocks Stage 2.

## Next

Stage 2 implementation is authorized by `docs/prompts/F1_Cursor_Stage_2_Prompt.md`.
