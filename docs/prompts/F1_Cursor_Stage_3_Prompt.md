# Cursor Stage 3 — race simulator and independent mechanism checks

Project: `f1-ai-quantum-strategy`. Scientific reference: `F1_AI_Quantum_Research_Dossier_v3_1.pdf`. Execute this prompt through its stop point, resolving ordinary engineering choices yourself. Return an evidence-based report, not merely a plan.

## 1. Authorized scope and starting evidence

Read `AGENTS.md`, `PROJECT_STATUS.md`, the Stage 1 follow-up, `docs/STAGE_2_REPORT.md`, generator specification, provenance/decisions/deviations, current schemas and dossier sections 5–9, 15, 19 and 23–26. Inspect the actual code and manifests before editing.

The supplied Stage 2 report identifies:

- Reported HEAD `24346827c11c81717e8161a9a5c9414ea4ba9428`, with a dirty tree.
- Preview source snapshot `c836750413a4afcecc567707fd94de516500af76fdb3895b97379cd22258475a`.
- Development preview run `8f292588-a328-4232-b425-c36c610a29f5`: eight blocks, 64 episode specifications, eight families, 32 SC and 32 VSC; no validated race checkpoints.
- Sixty passing tests, with the reserved scientific partitions still unmaterialized.
- An early bootstrap snapshot whose unrepaired `doctor.py` bytes could not be reconstructed. Preserve this disclosed limitation; do not relabel it fully reproducible.

Authorize local simulator selection, necessary free dependencies, implementation, independent mechanism checks, and bounded validation using these development inputs plus explicitly labeled hand-constructed fixtures. Local commits using the existing identity are allowed. No GitHub push, provider login, QPU submission, model training, QUBO/circuit implementation, full study, protected timing-data download, cloud deployment, billing or article drafting. Do not alter the closed research project.

Keep the scientific protocol DRAFT. Simulator-generated outcomes in this stage are engineering validation evidence, not H1/H2/H3 research comparisons or proof of actual F1 performance.

## 2. Preserve current work and make evidence recoverable

Inspect the working tree; do not reset or discard it. Determine which current files correspond to the checked Stage 2 source and which changed afterward. A dirty tree is acceptable when its exact relevant bytes are preserved and identified.

Verify the existing preview's artifact checksums and receipt counts. Check that private scenario inputs needed for replay actually exist and are indexed, not merely mentioned as gitignored. Do not dump private simulation draws or account information into solver inputs or chat logs.

For each new run, retain a recoverable source/configuration snapshot, dependency lock, content manifest and hashes. A hash without the source bytes is insufficient. Include generator/simulator configurations, scientific constants and any executable templates in the numerical source identity. Record the versions/hashes of authorization and project instructions separately; calling `AGENTS.md` documentation must not allow a change in execution permission to go unrecorded.

Demonstrate one clean reconstruction of the Stage 3 source/configuration package into a temporary directory and verify its hashes. Private simulation state and RNG replay material must also have a durable local recovery package with a manifest. This is authorized local persistence; no external backup service or paid storage is assumed. Do not claim that a local copy protects against loss of the computer.

Inspect the split planner's advertised `[--test-blocks 80|160]` behavior. The dossier allows every multiple of eight from 80 through 160 before test exposure, not only the endpoints. If only endpoints are accepted, correct the planner and check a value such as 88 along with invalid values, without materializing any reserved partition. If it already supports the full range, record that fact without an unnecessary rewrite.

Fix only concrete shared-infrastructure defects found here. Preserve all earlier raw records and identify any replacements as new attempts or versions.

## 3. Select and document the simulator implementation

Assess the dossier's preferred starting point, the full simulator in the official repository:

https://github.com/TUMFTM/race-simulation

Inspect and record a specific commit, license/notices, dependencies, state representation, event ordering, SC/VSC implementation, pit/service logic and possible checkpoint/resume hooks. Separate an inspected capability from an executed check. Its README describes a lap-wise simulator and an older Python development environment; neither proves that the required sub-lap decision timing will work in this project.

Use generated inputs. Do not use bundled historical race configurations, timing-derived trained policies or prerecorded actual strategies as shortcut dependencies. Check required input provenance separately from the software license. Disable any feature that implicitly loads those assets. Preserve applicable third-party notices for reused code.

Prefer a pinned adapter if it can represent the required mechanisms, isolate state/RNG and support causal checkpoints on the current supported environment. Make targeted compatibility changes or use a separate compatible environment if practical; do not downgrade the whole project to an unsupported interpreter or install every upstream training dependency blindly.

If the adapter fails concrete requirements or is impractical under the local constraints, document the inspected evidence and implement the dossier's permitted restricted independent model. If upstream inspection is unavailable, call it unassessed, not proven incompatible. An independently implemented model must identify its assumptions and any reused code honestly; lack of an upstream dependency does not establish scientific originality.

Save `docs/SIMULATOR_SELECTION.md` with the selected approach, source/commit, input provenance, dependency decision, rejected alternatives and known limitations. No option may claim traffic or SC validity merely because an upstream repository exists.

## 4. Explicit time, state and race mechanics

Write a compact mathematical/event specification in `docs/SIMULATOR_MODEL.md` before completing the production implementation. Define units, state variables, ordering, model equations and assumptions. Do not calibrate parameters by making a preferred strategy win.

Choose a deterministic event or time-step scheme capable of representing pit-entry cutoffs and service arrivals. A lap-only implementation is acceptable only if its timing refinement actually supports these events. If it cannot, declare a static checkpoint limitation and leave the operational deadline gate failed; do not silently simulate “pit now” on a later lap.

The following mechanisms are required within the explicitly supported domain:

### Clock, progress and initialization

Maintain consistent race clock, car progress, completed laps, ordering and remaining horizon. Define simultaneous-event tie rules. State must advance without negative elapsed time, duplicate lap completion or inconsistent positions. Use meaningful initialization from a declared fictional pre-checkpoint state, then advance to the requested checkpoint; do not label a synthetic mid-race initialization as a reconstructed race start.

Resolve the Stage 2 pending checkpoint clock, cutoffs and communication margin. Values such as 1.0-second communication margin, 1.8 kg/lap fuel consumption and 2 kg uncertainty remain explicit assumptions until investigated; schema acceptance does not validate them.

### Tyres and fuel

Specify lap/progress-dependent tyre-age and fuel updates, compound effects and near-linear/nonlinear degradation. State the mapping from abstract Stage 2 degradation parameters to time or speed. Maintain tyre-set identity, inventory and used-compound history, with a legal no-damage baseline. Separate estimated fuel in observations from any private actual fuel used by the simulator. Reject impossible initial fuel rather than silently clamping away a modeling error; no refueling is included in the core.

### Pit lane and shared crew

Separate pit transit, service duration, queue/wait time and the time the corresponding on-track route would have taken. Explain exactly how Stage 2 green pit loss is decomposed so that service or lost time is not counted twice. A neutralization changes the on-track comparison; do not deduct an arbitrary duplicate SC bonus.

Represent the crew as a shared service resource. A second team car arriving while the first is served must wait. Apply the configured crew relationships to the fictional field consistently. Double stacking has a finite modeled delay unless an explicitly configured policy forbids it. Rejoining the track must respect its ordering and traffic rules.

### Traffic and rivals

Implement a declared following/overtaking model whose behavior is testable in sparse and dense conditions. Avoid teleportation, negative gaps or arbitrary position swaps. Document simplified track geometry and which overtaking situations are supported.

Use a deterministic or seeded baseline continuation policy for the team and rivals, operating only on their allowed observations. It is a development policy, not the later tuned strongest classical comparator. It must remain feasible to race end under supported obligations. Include a simple non-reactive policy and an observable-state response interface so later sensitivity policies can be added without exposing private future state. No learned model or exhaustive strategy search is required now.

### SC, VSC and restart

Implement SC pace control with finite, causal bunching under a specified model. Do not instantaneously collapse every gap or use only a common lap-time multiplier. Vehicles must move consistently with the clock and progress.

Implement VSC pace control without deliberately imposing SC-style queue compression. Do not require every time gap to remain exactly constant under all car dynamics; the distinction is the mechanism, not an incorrect universal gap invariant.

Represent regime onset, information revelation, duration uncertainty and return to green. Future realized release time must remain private until revealed. All policy observations and commands must respect the event order. Unsupported pit-lane closures or special race-control procedures must be rejected or explicitly excluded, not guessed.

### Obligations and classification

Make the synthetic dry-race compound obligations configurable and keep a feasible continuation. Model rules are not a claim of exhaustive compliance with an actual FIA season. Implement a consistent finish/classification and tie rule, with an explicit treatment of lapped cars and retirement. If retirement events or certain lapping situations are excluded from the restricted model, reject them and state the narrowed domain; do not silently rank unsupported cases.

For completed supported cases, compute both individual ranks and the dossier's normalized team-rank loss `(r1 + r2 - 2) / (2 * (F - 1))`. Preserve ranks and field size for independent checking. This reports simulator outcomes, not the proxy objective or championship utility. No strategy-performance conclusion follows from the development rollout.

## 5. Causal checkpoint, action and deadline interface

Implement real versions of initialize, advance-to-checkpoint, observe, serialize, restore, advance-to-time, apply/validate-plan and continue-to-finish, using the Stage 2 types where suitable. Freeze their current interface versions, not the overall scientific protocol.

A solver receives only DecisionObservation. Private duration draws, actual future rival plans, evaluator random banks and full SimulatorState must stay behind the simulator boundary. Checkpoint persistence must include all state needed for exact continuation: event queue or integrator phase, tie order, pending service, policies, inventories, regime state and random-stream references. A positions-and-lap table alone is not enough.

Support a small hand-specified team-plan interface: pit now, delay by one or two completed laps, or follow the feasible continuation, including selected compound/set where relevant. This is needed to exercise mechanics; the legal-action enumerator, objective compiler and QUBO belong to Stage 4. Do not hide optimization inside the simulator to make validation succeed.

For a given registered menu and checkpoint, calculate the effective decision window from the nominal duration, absolute commitment cutoff(s) and communication margin using explicitly aligned units/origins. Never compare an absolute race time with a duration directly. A nonpositive remaining window is closed.

Advance under the current fallback while a proposed decision delay elapses. At a common commitment epoch revalidate a recommendation against information revealed by then. Record arrival, expiry, legality, commitment, selected plan and fallback reason. An early-arriving recommendation must not get an unregistered earlier commitment advantage in a later comparison. A stale “pit now” command cannot become “pit next lap” without being a different action.

These Stage 3 delay experiments inject scenario latency. Record local measured CPU/wall durations separately; neither is a measured IBM queue/network service level. Do not introduce an actual hardware latency claim.

## 6. Independent checks with known answers

Prepare hand-constructed cases with expected outcomes calculated without calling the production transition routine. Store expected values and derivations before checking the production result. Declare numeric tolerances and reasons; never increase them simply to pass a failure.

Required checks include:

1. **Free-track reference:** deterministic fuel/tyre evolution, lap times, a fixed pit stop and race-end time against an independently coded sum or recurrence. Check the green pit-loss decomposition explicitly.
2. **Shared service oracle:** for two box-arrival times and fixed service lengths, independently compute each service start as the later of its arrival and crew availability, then completion. Verify waiting, both arrival orders, a tie and a no-overlap case. Extra waiting need not imply worse final rank under every traffic model; test the actual service quantity.
3. **Traffic/rejoin:** known orderings for a blocked following case, a permitted pass, and pit exit into a known gap. No overtaking merely from a serialization or tie-break artifact.
4. **SC/VSC distinction:** under a specified controlled setup, show SC convergence toward the configured queue gap over time and VSC pace restriction without that bunching rule; check green restart continuity. Use suitable edge cases and report finite-horizon behavior, not just a favorable plot.
5. **Tyres, fuel and obligations:** no negative physical inventory, correct set changes/history, and rejection of an impossible command; explicit uncertainty handling and race-horizon consistency.
6. **Causal leakage:** observations unchanged when private future draws are changed before their revelation, provided all past/current states match. After a reveal, observations may differ causally. Policies may not inspect the private state object.
7. **Deadline behavior:** timely, exactly-at-boundary, expired, late, closed-pit and changed-state cases; verify effective cutoff arithmetic and fallback legality. Tie semantics at the boundary must be documented.
8. **Resume equivalence:** uninterrupted and restored continuations agree under identical event keys, including a checkpoint during a pending service/regime transition. Compare event sequences, state and terminal outcome, not only ranks. Verify restore in a fresh process.
9. **Randomness:** unrelated event draws remain stable when action paths differ; induced traffic effects may differ. Branches must not mutate the same shared state. Paired rollout reproducibility is required; a full variance-reduction study remains for the pilot.
10. **Classification and outcome arithmetic:** independently calculate ranks and normalized loss from fixture outcomes, including the model's supported tie/lapping/retirement cases or explicit rejections.

Use independent modules for analytical references. Do not implement the future proxy compiler as an alias for this evaluator. Any shared helpers must be mundane utilities, not the core equation being checked.

## 7. Development validation matrix and resource limit

Keep scientific training/tuning/calibration/test/shift partitions unopened. Reuse the Stage 2 preview as input; do not overwrite its original specifications or promote its blocks into research splits.

After mechanism checks pass, attempt all 64 existing episode specifications under one documented feasible baseline policy and one deterministic development world per episode. Advance to the prescribed checkpoint and validate it, then continue to finish. Restore every admitted checkpoint in a fresh process and compare its continuation with the uninterrupted path under identical draws.

Additionally select eight episodes by a declared hash rule covering the eight families, balanced four SC/four VSC where feasible before outcomes are inspected. On each, exercise one clearly specified alternative plan to check that intervention, cloning and continuation work. If no alternative is feasible, record it; do not silently replace the episode with a favorable one. This is a diagnostic intervention check, not a powered comparison or evidence of strategy improvement.

Run the boundary fixtures independently of the development matrix. Record every attempt, rejected episode, unsupported condition, failed comparison and incomplete unit. Admission requires actual validation; a table total of 64 must not override failures. If a Stage 2 assumption needs correction, create a versioned development-spec amendment and preserve the original; reruns receive new identities linked to the reason.

Use at most two workers initially and no more than the dossier's 60% RAM ceiling. Bound total simulator execution for this stage to 30 minutes of elapsed run time, excluding coding and dependency installation, and record completed work if that cap is reached. This is a Stage 3 engineering limit, not a benchmark timing result or a promise that the full study fits. Do not launch large Monte Carlo banks or silently reduce validation mechanisms to fit.

Extend the ledger/CLI with a documented simulator-check plan, model validation, checkpoint inspection with public/private separation and resume. Use existing authorization, intent, atomic-write and checksum checks. “Do a run” still executes one recorded authorized unit, not all later stages.

## 8. Gate status, deliverables and stop point

Save `docs/SIMULATOR_SELECTION.md`, `docs/SIMULATOR_MODEL.md`, `docs/SIMULATOR_VALIDATION.md` and `docs/STAGE_3_REPORT.md`, along with current source, configs, dependency lock, raw event traces, private replay packages, public observation records, comparison errors, audits and receipts. Update status, provenance, decisions, deviations and requirements traceability.

Separate:

- source/input provenance gate;
- structural schema checks;
- individual mechanism checks;
- checkpoint/resume checks;
- causal decision/deadline checks;
- admitted development checkpoints;
- real-world calibration, which remains unperformed.

Give each gate PASS, FAIL, PARTIAL or NOT RUN with evidence and an explicit supported domain. “All unit tests pass” is not itself sufficient for the simulator gate. If a core SC/VSC, shared-crew, causal deadline or continuation mechanism fails, mark Stage 3 partial/blocked and identify the precise remaining work. Do not proceed to Stage 4 merely because software can run.

Report intended model simplifications plainly. A restricted model may be scientifically useful, but its scope must remain adequate for the question and its domain must be documented before freezing the study. No gate can establish actual F1 operational validity without appropriate external evidence.

Review the scoped diff, run relevant Stage 1/2 regressions once after integration, and make a local commit if possible. Keep the latest checked code and evidence identifiable even if narrative documentation is edited afterward. No push, publication or QPU usage.

Return this report, using actual values rather than the expected defaults:

```text
STAGE_3_STATUS: COMPLETE | PARTIAL | BLOCKED
SOURCE_COMMIT_AND_RECOVERABLE_SNAPSHOT:
LEGACY_BOOTSTRAP_PROVENANCE_LIMITATION:
SIMULATOR_APPROACH_AND_VERSION:
UPSTREAM_COMMIT_OR_NOT_USED:
SOURCE_AND_INPUT_PROVENANCE_GATE:
SUPPORTED_DOMAIN_AND_EXCLUSIONS:
CONFIGURATION_AND_DEPENDENCY_HASHES:
IMPLEMENTED_COMMANDS:
MECHANISM_CHECKS: each gate, evidence path and maximum error where relevant
DEVELOPMENT_EPISODES_ATTEMPTED:
CHECKPOINTS_ADMITTED_REJECTED_PENDING:
RESUME_COMPARISONS: count, discrepancies, maximum numeric error
DIAGNOSTIC_INTERVENTIONS: count and failures; no performance inference
DEADLINE_CHECKS: supported behavior and any failed gate
SOURCE_AND_PRIVATE_STATE_RESTORE_CHECK:
SPLIT_PLANNER_MULTIPLE_OF_EIGHT_CHECK:
RESERVED_PARTITIONS_MATERIALIZED:
RESOURCE_USAGE_AND_INCOMPLETE_WORK:
RUN_IDS_AND_RECEIPT_PATHS:
REGRESSION_CHECKS:
ASSUMPTIONS_AND_MODEL_LIMITATIONS:
SCIENTIFIC_PROTOCOL: DRAFT
RESEARCH_COMPARISON_EXPERIMENTS_EXECUTED: 0 expected
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0 expected
QPU_USAGE_FROM_THIS_STAGE: 0 expected; account not queried
PUSH_PERFORMED: false expected
NEXT_STAGE: 4 only if the relevant simulator gates pass; otherwise named repair
```

Save the report and include a concise complete version in chat. Stop here. Stage 4 will implement the action model, objective compiler, QUBO and independent classical references under a separate prompt.

## Source note

The upstream [TUMFTM race-simulation README](https://github.com/TUMFTM/race-simulation) was consulted while preparing this prompt. It describes lap-wise simulation, distinguishes full and free-track components, and identifies timing-derived example inputs and pretrained policies. Its declarations guide the selection audit; they do not verify compatibility or checkpoint support for this project. The implementation must pin and inspect the actual revision it uses.
