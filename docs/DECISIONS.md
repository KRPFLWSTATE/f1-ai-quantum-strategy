# Implementation decisions

| Date | Decision | Reason | Status |
| --- | --- | --- | --- |
| 2026-09-19 | Create `/Users/kawinperera/f1-ai-quantum-strategy` as the permitted root instead of initializing Git inside `Quantum Computing and Formula 1` | Master prompt names `f1-ai-quantum-strategy`. The opened folder was not a Git repository and contained only the dossier PDF, this prompt, and `.DS_Store`. Seed files were copied, not moved, so the opened folder remains intact | implemented |
| 2026-09-19 | Use CPython 3.12.13 from Homebrew, `requires-python = ">=3.12,<3.14"` | 3.12 is installed and is the conservative choice for a later Qiskit/SciPy/ML stack. 3.13 and 3.14 exist on the machine but are unused. System Python is not modified | implemented |
| 2026-09-19 | Project-local `.venv`; pip with a fully pinned `requirements.lock` | Stage 1 needs pydantic, PyYAML, pytest. No quantum or numerical stack is installed in order to claim readiness | implemented |
| 2026-09-19 | Pydantic v2 schemas (`extra=forbid`) plus YAML configs | Validation of nested observations without a large framework | implemented |
| 2026-09-19 | SQLite WAL ledger under `evidence/var/` plus exclusive `fcntl` writer lock; raw events/manifests also written as files | Transactional index, durable raw records, real contention check for two `run` commands | implemented |
| 2026-09-19 | Conservative `max_workers: 1` | Host has 10 cores and 24 GiB; Stage 1 launches no stress benchmark | implemented |
| 2026-09-19 | No SPDX license file yet | Dossier defers the project's release license until the release decision; third-party notices still recorded in PROVENANCE | pending |
| 2026-09-19 | Private GitHub repository name `f1-ai-quantum-strategy` under personal account `KRPFLWSTATE`, no push | Authorized Stage 1 remote; publishing remains a separate action | verified: https://github.com/KRPFLWSTATE/f1-ai-quantum-strategy (private, empty) |
| 2026-09-19 | IBM backend, verified quota time, calibrated threshold, model artifact, simulation distribution, protocol hash, completed gate remain null with reasons | Master prompt: never invent those values | implemented |
| 2026-09-19 | Primary source snapshot excludes narrative docs; `documentation_hash` is separate (policy v1.1.0) | Stage 2 prompt: documentation-only edits must not invalidate scientific/code identity | implemented; verified by `tests/test_source_identity_policy.py` |
| 2026-09-19 | Green pit loss is a combined transit+service delta versus a green flying lap | Prevent Stage 3 double counting | implemented in `configs/generator.v1.yaml` |
| 2026-09-19 | Development preview uses a `development` namespace; scientific partitions stay planned-only | Dossier split integrity | implemented; `run --plan materialize-training` rejected |
| 2026-09-19 | Shift panel 5 blocks/family is a draft allocation, unfrozen | Dossier: freeze before use | documented, not materialized |
| 2026-09-19 | Tyre wear stored as form plus scale; lap-time map declared in simulator.v1 | Stage 3 physics coefficients are assumptions, not F1 calibration | implemented; not calibrated |
| 2026-09-19 | Reject TUMFTM adapter; implement restricted independent model `simulator.v1` | Inspected commit `96ef2c2021982217be008fe458df47c1a72da071` is lap-wise, pins Python 3.8/TF 2.2, and bundles historical inputs | implemented; documented in `docs/SIMULATOR_SELECTION.md` |
| 2026-09-19 | Split planner accepts every multiple of eight from 80 through 160 | Dossier §§7/18; CLI previously advertised only 80\|160 | implemented; verified by `tests/test_split_planner_multiples.py` |
| 2026-09-19 | Hand `pit_now` / `delay_laps` are one-shot | Repeating delay plans produced extra pits and broke the free-track oracle | implemented |
| 2026-09-19 | Conservative `max_workers: 2` in Stage 3 | Prompt cap; execution used 1 worker | implemented |

## Unresolved scientific choices (not decided here)

Action menus; risk weights; classical comparator; C0/C1 depth; C2 admission; test-block sizing for the actual study; which hardware schedule; historical-data permission. All remain proposed in the dossier.
