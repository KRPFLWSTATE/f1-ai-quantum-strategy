# Stage 4 Closure Erratum — legacy exhaustive matrix counts

**Status:** corrective documentation for Stage 4 Final Closure. Does not reopen Gate C as PASS.

## Filesystem counts (git-tracked `*.record.json`)

Counts are derived from `git ls-files` under each run's `formulation.development_matrix/` directory (see `f1q.formulation.legacy_counts.count_committed_record_json`). Untracked leftovers from unauthorised resumes are excluded.

| Run ID | Archived record files | Planned | Ledger / receipt |
|--------|----------------------:|--------:|------------------|
| `e85ee977-8a35-40c1-b690-02724dea3228` | **40** | 64 | interrupted / PARTIAL |
| `41c28597-0ce0-428f-8230-ba2ca973c5b7` | **21** | 64 | interrupted; **no completed receipt** |

## Why earlier snapshots disagreed for `41c28597`

Asynchronous packaging and a continuing process produced inconsistent published numbers:

| Snapshot | Count reported | Context |
|----------|---------------:|---------|
| Stop snapshot during Final Closure | 14 | Process still writing when packaging began |
| v1 frozen ZIP contents | 18 | ZIP freeze mid-write |
| Interim status text | 20 | Later status rewrite before push |
| Pushed repository at `83f480a` | **21** | Git-tracked files at publication tip |

**Canonical description for `41c28597`:**

> 21 archived record files; interrupted; no completed receipt; excluded from the bounded engineering gate.

## What these runs are not

- Neither legacy run is complete.
- Neither is resumable under current policy (`LEGACY_GATE_ACTION: ARCHIVED_DO_NOT_RESUME`).
- Neither is merged with another run.
- Neither is evidence of 64/64 terminal Cartesian all-pair coverage.

## Engineering gate amendment

The old exhaustive all-pair terminal Cartesian requirement remains **`LEGACY_EXHAUSTIVE_GATE: PARTIAL`** and is **withdrawn** as the Stage 4 engineering acceptance criterion. Bounded closure (`python -m f1q.formulation.stage4_closure`) is the authorised engineering gate.

The historical v1 package (`STAGE_4_CLOSURE_REVIEW.zip` and companions) is **superseded evidence**. Preserve it and Git history; do not overwrite. Use v2 deliverables after this correction.

## Do not

- Invoke `formulation_gate_c_closure_check`.
- Resume `e85ee977-…` or `41c28597-…`.
- Delete or rewrite historical legacy `*.record.json` files.
