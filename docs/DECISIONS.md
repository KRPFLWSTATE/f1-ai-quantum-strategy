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

## Unresolved scientific choices (not decided here)

Simulator adapter vs independent model; action menus; risk weights; classical comparator; C0/C1 depth; C2 admission; test-block sizing; which hardware schedule; historical-data permission. All remain proposed in the dossier.
