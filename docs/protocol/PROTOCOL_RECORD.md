# Protocol record

frozen: false

This is a draft protocol record. Completing Stage 1 bootstrap does not freeze the scientific protocol.

| Field (dossier §30) | Required freeze evidence | Present value |
| --- | --- | --- |
| Scope and rights | Core generated domain; any permitted historical extension and licence | generated-only (proposed); historical track unselected |
| Simulator | Code hash, checkpoint semantics, mechanism tests, distributions | `simulator.v1` / interface `3.0.0`; snapshot `26ed935ce0dbba00963bbe5766c77f1247fed491d2a9cf697f692c1cf5a4e6c1`; mechanism unit on run `e2258740-1d08-4427-8305-b149ed504a73`; distributions remain unfrozen |
| Corpus | Families, splits, counts, seeds | eight families implemented; splits stored as planned counts; development preview generated; scientific partitions not materialized |
| Objective | Units, risk, legality, penalty, normalisation, ties | specified in dossier §9; not implemented |
| Algorithms | Classical comparator, features, donors, circuits, depths, budgets | unselected |
| Statistics | Headroom gate, estimand, policy seeds, effect margin, sizing, resampling | proposed; not frozen |
| Simulation | Random-stream design, production replication count, final-bank isolation | stream domains implemented; production replication unselected |
| Deadlines | Clock origin, cutoffs, effective budgets, state advance, fallback | implemented in `simulator.v1` with research settings; not frozen |
| Hardware | Verified free access, balance, reservation ledger, frozen matrix | unverified; hardware disabled |
| Execution | Authorised run scope, resume rules, protected paths, evidence schema | Stage 3 simulator_check plus retained Stage 2 preview and Stage 1 bootstrap; hardware disabled |
| Claims | Prior-art comparison, intended claims, unsupported claims, limitations | see `docs/CLAIMS.md` |

Draft configuration fingerprint is recorded by `python -m f1q doctor` as `config_hash_draft`. That hash is **not** a frozen protocol hash.

Suggested dossier states not yet used: DRAFT (current), LOCAL_READY, LOCAL_COMPLETE, PROTOCOL_FROZEN, HARDWARE_READY, RUNNING, RECONCILE_REQUIRED, COMPLETE.
