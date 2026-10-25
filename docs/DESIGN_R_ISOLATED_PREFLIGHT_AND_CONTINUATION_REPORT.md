# Design R isolated preflight and continuation

**Status:** `not_admitted_tests`. Design R was not admitted. Design F was not launched. The registered corpus was not opened. Phase 7 was not started.

This is an engineering closure. It is not a scientific result on the registered parents.

## Run identity

| Item | Value |
| --- | --- |
| Branch | `design-r-isolated-preflight` |
| Method commit | `e78c65d4b67f4d722e12135af965895571cdf864` |
| Registry commit | `d332d6ee1056de6ee33e1cfa38cc5ded2173228d` |
| Base | `e8aa409b691db248c6ac0cdc14c523057da38ca9` (`origin/phase6-design-r-six-hour`) |
| `origin/main` at fetch | `53ce10d187c2140511c7419863b5447119496a77` |
| Measurement run | `ee3945ba-ee39-48e5-a81b-85b981806f2a` |
| Aborted before checks | `9a32a40a-1790-4f5b-a955-ce093b44cddc` |
| Amendment | `design_r_isolated_preflight_20261025` |
| Amendment file SHA-256 | `8bc519534572eb3faf8eade2ca9d46d8c35cda7ac257c142ddc0b683bb1a602a` |
| Decision SHA-256 | `d4a45777dfc3e2e9fe85505406e10789a82c94b9ee2413133832ea179a71a7bb` |
| Decision path | `evidence/stage6_a4/ee3945ba-ee39-48e5-a81b-85b981806f2a/ADMISSION_DECISION.json` |
| Kernel `compiled-event-loop-2` SHA-256 | `a763fe1bc041f77a4ed7f06978eaf2dfd48a468205d8b675988224afd8a7818f` (unchanged) |

The publication commit that adds this report is not written inside the report.

## Six-parent exposure ledger

The intended campaign `ed37296f-55c5-44e5-8ffd-77410d4789de` has `REGISTERED_SCIENTIFIC_PARENTS_EXECUTED=0`. Six distinct registered parent ids were nevertheless exposed by tests. Those files were not deleted.

Exposed parents, from `configs/design_r_exposed_identities.json` (SHA-256 `5c59128e7c8d1958f65fcc1e09f03f4ac28d78f286cb517471fb269d6036a984`):

- `a4.v2.train.fam.green_pit_high.tyre_near_linear.traffic_dense.0000`
- `a4.v2.train.fam.green_pit_high.tyre_near_linear.traffic_dense.0001`
- `a4.v2.tune.fam.green_pit_high.tyre_near_linear.traffic_dense.0000`
- `a4.v2.tune.fam.green_pit_high.tyre_near_linear.traffic_dense.0001`
- `a4.v2.calib.fam.green_pit_high.tyre_near_linear.traffic_dense.0000`
- `a4.v2.calib.fam.green_pit_high.tyre_near_linear.traffic_dense.0001`

Preserved miniature runs: `cdd21ec6-9d95-48a5-806b-64fd7e296434` and `eeb03bdd-4fdf-4e1e-baf6-590b54c11d4a`. World chunks remain under `evidence/stage6_a4/engineering_byproducts/worlds`. Status: `RETIRED_TO_DEVELOPMENT_HISTORY_NOT_SCIENTIFIC`. Those losses are not Design R results.

## Fresh split

Namespace `a4.v3.iso`. Salt `a4.partitions.v3.isolated.20261025.9a32a40a`. Counts 120 / 80 / 24. Registry content SHA-256 `e696571cbaa12d904b442aaa837c0db2a9122a3772558e5efe9f0a325d582da6`. File SHA-256 `88146c355e70d0b9b32c5504b6c6c3a0ad52449b03bbd8752d51718be30dee05`. Historical `src/f1q/a4/partitions.py` was not edited. The seal audit on the real tree found no outcome files for the new ids (`new_split_outcome_files` empty; `seal` gate true). Final-test and shift outcomes were not materialised.

Observed scientific denominators for this run: train 0 / 120, tune 0 / 80, calibration 0 / 24.

## Test isolation

Engineering preparation now rejects a protected parent before `RaceSimulator` is constructed. `miniature=true` does not bypass that check. Child processes receive `F1Q_PROJECT_ROOT` and refuse a parent-directory walk when `F1Q_REQUIRE_EXPLICIT_ROOT=1`. Report writers refuse the three historical paths that pytest previously overwrote.

The authoritative suite for `ee3945ba` ran in an isolated copy that omitted the two miniature runs and the world-chunk directory. Protected-byte snapshot before and after matched. The read-only seal audit passed before and after.

Pytest exit code: **1**. The only failure was `tests/a4/test_a4_completion_contract.py::test_e2e_miniature_campaign`: `git rev-parse HEAD` returned exit 128 because that isolated tree is not a git checkout. The suite was not deselected to hide this. Progress line: one failure, two skips.

Because pytest exited 1, the admission did **not** continue to parity, rate probes, storage measurement, or the corpus.

## Storage, CPU, and wall

Not produced. The historical formula `n_units * 2_000_000 + evaluation_worlds * 200` remains the recorded failure mode of `ed37296f` (175,246,046,400 bytes). This attempt did not replace it with a measured byte count, because measurement is after a passing suite.

CPU, wall, RSS, and disk projections for `ee3945ba`: **not measured**. No independent projection was run.

## Admission decision

`admitted=false`. `selected_design=NONE_RESOURCE_LIMIT`. `status=not_admitted_tests`. Gates recorded: `tests=false`, `snapshot=true`, `seal=true`. Literal parity was not re-run and was not reused as a pass for this attempt. Resource caps were not evaluated.

`9a32a40a` is a separate abort, preserved: `AttributeError: module 'shutil' has no attribute 'mkdtemp'`. That call also executed no parents. Decision SHA-256 `a8a52fda65d0cf567ed081d16470b27114081975864b874b6e79e06de9822f0f`.

## Scientific gates

| Item | Result |
| --- | --- |
| Paired estimate | NA — calibration was not run |
| Finite-sample q | NA |
| Gate E | `UNCLAIMED` — no admitted execution |
| Gate F | `FAIL` — no measured campaign and the suite stopped |
| `PROXY_HEADROOM` | `ZERO` (carried; not a new downstream result) |
| `PHASE_7_DESIGN_READY` | false |
| `PHASE_7_AUTHORISED` | false |
| `FINAL_TEST_ACCESSED` | false |
| `QPU_JOBS` | 0 |
| Design F | not launched |
| Design R | not admitted |
| Registered parents executed | 0 |

## Historical integrity

Unchanged relative to `e8aa409`: `docs/PHASE_6_COMPLETION_REPORT.md`, `docs/PHASE_6_VALIDATED_CLOSURE_REPORT.md`, `docs/evidence/stage4_2/stage3_3_regression_diagnostic.json`, and `docs/PHASE_6_DESIGN_R_AMENDED_CLOSURE_REPORT.md`. Kernel file hash matches the Route 1 receipt. Frozen evidence trees for `ed37296f`, the two miniatures, `fc5f0e00`, `0b697910`, `3de109c7`, and `09806343` were not overwritten.

## What was not produced

No campaign wall or CPU measurement. No 8-worker efficiency for this attempt. No paired block estimate. No q. No Gate E pass. No continuation into train, tune, calibration, or analysis. No Phase 7.
