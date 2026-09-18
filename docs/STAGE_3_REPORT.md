# Stage 3 report — race simulator and independent mechanism checks

Evidence from the local ledger and named files. Chat recollection is not evidence. Claims are labeled. Simulator outcomes in this stage are engineering validation, not H1/H2/H3 research comparisons and not proof of actual F1 performance.

```text
STAGE_3_STATUS: COMPLETE
SOURCE_COMMIT_AND_RECOVERABLE_SNAPSHOT: git HEAD 24346827c11c81717e8161a9a5c9414ea4ba9428 dirty=true at the simulator_check run; source snapshot hash 26ed935ce0dbba00963bbe5766c77f1247fed491d2a9cf697f692c1cf5a4e6c1 written to evidence/simulator/snapshots/e2258740-1d08-4427-8305-b149ed504a73.json; clean reconstruction into a temporary directory matched that hash (92 files); documentation hash is separate and does not identify the code snapshot
LEGACY_BOOTSTRAP_PROVENANCE_LIMITATION: preserved. Stage 1 snapshot 320dc0f9… recorded unrepaired doctor.py bytes 96eadf13… that are not in git. That limitation is not relabelled fully reproducible. See docs/STAGE_1_FOLLOWUP.md
SIMULATOR_APPROACH_AND_VERSION: restricted independent model simulator.v1 1.0.0; interface 3.0.0 frozen separately from the scientific protocol; configs/simulator.v1.yaml sha256 b76c59dc65b333eef5793756ec32ab17f7102f418922c5854c515dfaa4c80dd1
UPSTREAM_COMMIT_OR_NOT_USED: TUMFTM/race-simulation inspected at 96ef2c2021982217be008fe458df47c1a72da071 (LGPL-3.0); not imported, not vendored, not executed as adapter. Selection record: docs/SIMULATOR_SELECTION.md
SOURCE_AND_INPUT_PROVENANCE_GATE: PASS. Stage 2 development preview 8f292588-a328-4232-b425-c36c610a29f5 reused unchanged (8 blocks / 64 specs). Hand fixtures labeled. No historical timing, no TUMFTM pars_*.ini, no pretrained VSE
SUPPORTED_DOMAIN_AND_EXCLUSIONS: dry 20-car unit-circle 1D event-driven model; exclusions wet, red flag, sprint, tyre damage, energy deployment, pit-lane closures, refueling, retirements, unsupported race control
CONFIGURATION_AND_DEPENDENCY_HASHES: project.draft.yaml 9362ef90253f95ff427ff85ced4bb8605b2cef1778375e9ae06020b888eaf0c6 (draft, not a frozen protocol hash); requirements.lock fe7a80a5424ff1ff5d9340a4080c7ab5d963ff1c19fafeee56fa85aad70972e0; simulator.v1.yaml b76c59dc65b333eef5793756ec32ab17f7102f418922c5854c515dfaa4c80dd1; simulator.interface.v1.yaml 8d24f561ad53f1889c6554e3cf36bb50556e0a321438a37c2a90691cbda9908a; simulator_check.yaml c2d02d45cefcbd3f59cd228c1818a244496a1a3c53ac4c73aae2f54c9f126718; generator.v1.yaml ffd3f2e5ac5660ef19bb532c099334028aa8e4012340474ad08dacaf774e353c; dossier PDF 2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76; Stage 3 prompt cfd2cef52431f61faa9af8d99673e4cfce7657a9df9fbaa33bdaaf5b10900986; AGENTS.md at run 92af48387c65e920b69c051a36b921b19f1e27588661929cfe0db3c58224f5fb (authorization hashes stored separately from the primary snapshot)
IMPLEMENTED_COMMANDS: python -m f1q doctor | status | run --plan bootstrap | run --plan development_preview | run --plan simulator_check | resume --run-id | receipt --run-id | generator validate | generator plan-splits [--test-blocks multiple-of-8 from 80 through 160] | generator audit | generator handoff | simulator validate | simulator inspect-checkpoint --run-id --episode-id | simulator interface
MECHANISM_CHECKS: all ten PASS; evidence evidence/simulator/artifacts/e2258740-1d08-4427-8305-b149ed504a73/simulator.mechanism_checks/unit.json. free_track pit_identity_error 1.4210854715202004e-14 race_time_error_s 1.9326762412674725e-12 (tol 0.5 s); shared_service max_wait_error_s 0.0 production_wait_error_s 2.2646418074145913e-10; traffic_rejoin PASS (blocked stable, permitted pass, pit-exit geometry); sc_vsc PASS SC gap-sum 0.13885900199110957 -> 0.10505237589240046 laps over 25 s, VSC 0.1386843711807888 unchanged, restart_green true; tyres_fuel PASS; causal_leakage PASS; deadline PASS (timely, exclusive boundary, late, closed, revalidated); resume PASS rank_error 0 time_error_s 0.0 events 212; randomness PASS; classification PASS expected_loss 0.5
DEVELOPMENT_EPISODES_ATTEMPTED: 64 of 64 from preview 8f292588-a328-4232-b425-c36c610a29f5; not overwritten; not promoted to research splits
CHECKPOINTS_ADMITTED_REJECTED_PENDING: admitted 64, rejected 0, pending 0. Admission is simulator.v1 validation of generated development checkpoints, not F1 reconstruction
RESUME_COMPARISONS: 64 uninterrupted vs restored continuations; discrepancies 0; maximum numeric time error 0.0 s; rank error 0. Plus one fresh-process restore in tests/test_simulator_mechanisms.py
DIAGNOSTIC_INTERVENTIONS: 8; failures 0; hash rule sha256(episode_id) min within family, even families SC, odd VSC; not a performance inference
DEADLINE_CHECKS: supported: remaining window = min(decision+nominal, earliest team pit-entry cutoff - 1.0 s margin) - decision; closed iff remaining <= 0; timely iff arrival < effective_end (boundary exclusive). Failed gate: none in the named check. Units/origins aligned on race seconds from race_start
SOURCE_AND_PRIVATE_STATE_RESTORE_CHECK: PASS. reconstructed_hash == source_snapshot_hash 26ed935ce0dbba00963bbe5766c77f1247fed491d2a9cf697f692c1cf5a4e6c1; private package 128 files (64 Stage 2 preview states + 64 Stage 3 checkpoint states) hash ab4d0e23c3f715e9d7ba6eb0d12e74e551a891a9cbec66ebcf6d69e1d0b98dc9; local persistence only, not an offsite backup, does not protect against computer loss
SPLIT_PLANNER_MULTIPLE_OF_EIGHT_CHECK: PASS. TEST_BLOCK_CHOICES = range(80, 161, 8). python -m f1q generator plan-splits --test-blocks 88 exit 0, test_blocks 88, test_checkpoints_planned 704, materialized false. --test-blocks 84 exit 2 AuthorizationError. pytest tests/test_split_planner_multiples.py. No reserved partition materialized
RESERVED_PARTITIONS_MATERIALIZED: none
RESOURCE_USAGE_AND_INCOMPLETE_WORK: max_workers 1 (cap 2); stage3 elapsed 148.916 s of 1800 s cap; incomplete_cap false; RAM 60% ceiling not separately sampled
RUN_IDS_AND_RECEIPT_PATHS: e2258740-1d08-4427-8305-b149ed504a73 ; evidence/simulator/receipts/e2258740-1d08-4427-8305-b149ed504a73.json ; evidence/simulator/receipts/e2258740-1d08-4427-8305-b149ed504a73.md ; preview input 8f292588-a328-4232-b425-c36c610a29f5 unchanged
REGRESSION_CHECKS: pytest 68 passed in 24.43s, exit 0, docs/evidence/stage3/pytest.txt; python -m f1q doctor exit 0, scientific_protocol DRAFT, hardware_execution_enabled false, qpu_account_queried false; inspect-checkpoint after filename-match fix: private_state_bytes_hashed_not_printed equals public private_state_sha256 08f1229bf258f0b367878587f3ee731e56f99d1707212b310f1abdea78b45775 (docs/evidence/stage3/inspect_checkpoint.json)
ASSUMPTIONS_AND_MODEL_LIMITATIONS: 1.8 kg/lap, 2 kg fuel uncertainty, 1.0 s communication margin, 2.5 s stationary service, tyre time_scale 6.0 s, compound offsets 0/0.8/1.6 s, SC 1.45 / VSC 1.40 pace factors, SC queue 1.0 s with catch 0.85, unit-circle geometry, tick-resolution overtaking, instantaneous green restart preserving gaps. Amendments development_spec.fuel.v1 and checkpoint.cutoff.v1 applied at evolution, original Stage 2 bytes preserved. Parameters were not chosen so a preferred strategy wins. Not F1-calibrated. Not TUMFTM-equivalent traffic. Not QPU-ready
SCIENTIFIC_PROTOCOL: DRAFT
RESEARCH_COMPARISON_EXPERIMENTS_EXECUTED: 0
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0
QPU_USAGE_FROM_THIS_STAGE: 0; account not queried
PUSH_PERFORMED: false
NEXT_STAGE: 4 -- action model, objective compiler, QUBO and independent classical references, only under a separate implementation prompt. Stage 3 software gates (mechanism, resume, causal deadline, admitted development checkpoints) passed. Real-world calibration remains NOT RUN and is not claimed
```

## Commands actually run (this stage)

| Command | Exit |
| --- | --- |
| `python -m f1q doctor` | 0 |
| `python -m f1q generator plan-splits --test-blocks 88` | 0 |
| `python -m f1q generator plan-splits --test-blocks 84` | 2 |
| `python -m pytest --tb=line` | 0 (68 passed in 24.43s; docs/evidence/stage3/pytest.txt) |
| `python -m f1q run --plan simulator_check` | 0 |
| `python -m f1q simulator interface` | 0 |
| `python -m f1q simulator inspect-checkpoint --run-id e2258740-1d08-4427-8305-b149ed504a73 --episode-id f1q.dev.block.v2/fam.green_pit_high.tyre_near_linear.traffic_dense/0000/episode/00/SC` | 0 (private hash matched public record) |
| `python -m f1q status` | 0 |

No `git push`. No IBM/QPU/provider call.

## Findings that required documented amendments (not silent science edits)

1. Stage 2 `fuel_kg = max(5, remaining*1.8+U[-2,2])` undershoots horizon need for many cars. Amendment `docs/amendments/development_spec.fuel.v1.md`: estimate stays public; private actual is estimate+offset; floor to need only inside the uncertainty band; otherwise `IMPOSSIBLE_INITIAL_FUEL`.
2. Stage 2 sampled cutoffs were inconsistent with packed gaps. Amendment `docs/amendments/checkpoint.cutoff.v1.md`: pack by gaps; recompute operational cutoffs from geometry.

## Dossier contradictions recorded, not silently rewritten

None that altered dossier v3.1 PDF bytes. The split planner now accepts every multiple of eight from 80 through 160, matching dossier §§7/18 rather than only the 80|160 CLI endpoints.

## Inspected vs executed

Upstream TUMFTM capabilities were **inspected** in source at the pinned commit. No TUMFTM mechanism check was **executed**. Lack of an executed upstream check is unassessed runtime behaviour, not a proof that TUMFTM SC is invalid.
