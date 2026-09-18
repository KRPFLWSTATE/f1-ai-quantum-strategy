# Provenance

Software licensing is separate from data rights. Unselected dependencies remain unselected.

| Item | Source | Version / commit when selected | License status | Permitted use in this project |
| --- | --- | --- | --- | --- |
| Dossier PDF v3.1 | Local file supplied by Kawin Rehan Perera | SHA-256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76` | Author's research specification | Design reference; preserved unchanged |
| Stage 1 master prompt | Local file | as copied into `docs/prompts/` | Author's implementation authorization | Stage 1 only |
| CPython | https://www.python.org / Homebrew `python@3.12` | 3.12.13 | PSF | Runtime |
| pydantic | https://pypi.org/project/pydantic/ | pinned in `requirements.lock` | MIT | Schema validation |
| PyYAML | https://pypi.org/project/PyYAML/ | pinned in `requirements.lock` | MIT | Config parsing |
| pytest | https://pypi.org/project/pytest/ | pinned in `requirements.lock` | MIT | Tests |
| setuptools | https://pypi.org/project/setuptools/ | pinned in lock (build) | MIT | Packaging |
| SQLite | Python stdlib | as shipped with 3.12.13 | public domain dedication | Ledger |
| pypdf (extract-only, not a runtime dependency) | PyPI, temporary `/tmp` target | recorded in SOURCE_HASH.md | BSD-3-Clause | One-off PDF text extraction |

## Explicitly unselected (later stages, not installed)

Qiskit, Qiskit Aer, SciPy, NumPy as a forced Stage 1 dependency, scikit-learn or other ML libraries, HiGHS/CBC/other integer solvers, FastF1, TUM race-simulation, F1DP. No commit of those projects is pinned.

## Data rights

No Formula 1 timing feed, FastF1 session files, or other protected race data are present. Core inputs are generated fictional fixtures. An open-source software licence is not a licence for underlying timing records ([19] in the dossier).
