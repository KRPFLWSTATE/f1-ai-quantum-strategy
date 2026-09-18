# Protocol record

frozen: false

This is a draft protocol record. Completing Stage 1 bootstrap does not freeze the scientific protocol.

| Field (dossier §30) | Required freeze evidence | Present value |
| --- | --- | --- |
| Scope and rights | Core generated domain; any permitted historical extension and licence | generated-only (proposed); historical track unselected |
| Simulator | Code hash, checkpoint semantics, mechanism tests, distributions | null -- Stage 3 |
| Corpus | Families, splits, counts, seeds | proposed in dossier §7; not generated |
| Objective | Units, risk, legality, penalty, normalisation, ties | specified in dossier §9; not implemented |
| Algorithms | Classical comparator, features, donors, circuits, depths, budgets | unselected |
| Statistics | Headroom gate, estimand, policy seeds, effect margin, sizing, resampling | proposed; not frozen |
| Simulation | Random-stream design, production replication count, final-bank isolation | unselected |
| Deadlines | Clock origin, cutoffs, effective budgets, state advance, fallback | proposed research settings |
| Hardware | Verified free access, balance, reservation ledger, frozen matrix | unverified; hardware disabled |
| Execution | Authorised run scope, resume rules, protected paths, evidence schema | Stage 1 software-check plan only |
| Claims | Prior-art comparison, intended claims, unsupported claims, limitations | see `docs/CLAIMS.md` |

Draft configuration fingerprint is recorded by `python -m f1q doctor` as `config_hash_draft`. That hash is **not** a frozen protocol hash.

Suggested dossier states not yet used: DRAFT (current), LOCAL_READY, LOCAL_COMPLETE, PROTOCOL_FROZEN, HARDWARE_READY, RUNNING, RECONCILE_REQUIRED, COMPLETE.
