# Stage 3.2 — repair defects reproduced from the simulator source

Project: `f1-ai-quantum-strategy`. This is corrective work within Stage 3. Stage 4 remains blocked. Read this entire prompt, reproduce the findings on the existing source, implement the repairs and return the specified evidence. Do not respond with a plan alone.

## Independent review: what was actually checked

ChatGPT inspected the uploaded Stage 3.1 code bundle and ran targeted diagnostics against its unmodified simulator source. ZIP SHA-256 matched `4133b42762c8ab3077488476373759f35f375592d54dfe981d324b61ed3bda73`. All 60 included files belonging to the 97-file primary snapshot matched their recorded hashes; 37 primary files were absent from this reduced bundle. This verifies the included source bytes, not reconstruction of the entire project.

Review runtime: Python 3.12.14, Pydantic 2.13.5, PyYAML 6.0.3. This differs from the reported pinned development environment. The reviewer called `run_all_mechanism_checks(cfg)` directly and obtained `ok=True`, `failed=[]`. The reviewer did not independently reproduce all 75 pytest tests: pytest was unavailable in that runtime and the bundle omitted many tests/fixtures. Do not misrepresent this as a clean install or full regression verification.

Despite the named mechanism checks passing, the following production defects were reproduced. Preserve these findings and the old reports rather than quietly replacing their conclusions.

### R1 — pit progress jumps forward and then backward

In `engine.py`, `distance()` uses `completed_laps + frozen_frac` while in the pit. `_advance_pit()` increments `completed_laps` at box arrival without resetting/reinterpreting `frozen_frac` consistently.

A hand fixture using the production pit-entry and phase handlers produced:

| Phase | Race time (s) | Reported progress (laps) |
| --- | ---: | ---: |
| transit_in | 900.0 | 10.95 |
| service | 917.0 | 11.95 |
| transit_out | 919.5 | 11.95 |
| on track after exit | 926.3 | 11.02 |

The configured geometry is entry 0.95, box at the next 0.0, exit 0.02. The box should correspond to 11.0, not 11.95. This error can contaminate position, leader selection, checkpoint detection and end-of-race handling. It is not an acceptable numerical tolerance or a harmless visualization issue.

Repair the pit progress representation and phase updates with a documented coordinate convention. Represent or consistently project movement along transit phases; preserve nondecreasing completed distance and correct start/finish crossing exactly once. Separate longitudinal race progress from elapsed pit time, physical path length and crew status where needed. Verify fuel/tyre accounting against the declared pit model without double counting or free unexplained distance.

Add independent phase-by-phase checks for an ordinary stop, a queued stop, a stop across the horizon/finish line and restore during each phase. Use the configured geometry, not hard-coded expectations copied from the transition implementation. A car waiting in its box must not acquire a phantom lap or become the leader through an inconsistent fractional coordinate.

### R2 — reported finish times do not measure individual finishing

`maybe_finish()` stops the entire simulation when the leader finishes and assigns the current race time to every unfinished car. `outcome()` reports these values as individual finish times. In the affected resolution episode, all 20 cars had exactly one shared finish-time value at each resolution.

For the reported problematic high-pit-loss/nonlinear/dense SC episode, independent reruns at h and h/4 produced:

| Quantity | h | h/4 |
| --- | ---: | ---: |
| Shared reported finish time, all 20 cars (s) | 3755.732088315974 | 3755.732084538896 |
| windrow.b rank | 10 | 11 |
| windrow.b progress (laps) | 33.96620816016337 | 33.96416031373225 |
| bluehaven.a rank | 11 | 10 |
| bluehaven.a progress (laps) | 33.964343119672805 | 33.964343028012145 |

Small differences between the two shared timestamps do not establish small individual finish errors or a near-tie between those cars. The current near-tie explanation is unsupported by that metric.

Implement and document an actual finish-line/classification model for the supported synthetic domain. If using leader-triggered completion, distinguish the leader's finish event from each other car's subsequent finish-line crossing and lap deficit. Handle cars in the pits, exact ties, and supported lapping situations explicitly. This is a declared model, not a claim of comprehensive FIA-season compliance.

Alternatively, an instantaneous rank-at-leader-finish quantity can be retained as a separate diagnostic, named honestly, with unknown individual finish times left absent. It cannot silently substitute for race-end ranks and finish-time validation required by the intended evaluator. Do not treat this alternative alone as sufficient to clear Stage 4.

Use independent fixtures with known distinct finishing times and lapped-car outcomes. Verify that no value is filled in as a finish time until the event it purports to measure actually happens.

### R3 — overtaking gives a car free longitudinal distance

Both `fire(catch_or_pass)` and `_apply_green_overtakes()` assign the passing car to `distance(ahead) + clearance`. They do not advance time or consume fuel/tyre age for the resulting progress increment.

A controlled production-handler fixture produced `progress_delta=0.0006507139377429638` laps while `time_delta=0`, `fuel_delta=0`, and `tyre_age_delta=0`.

Replace these spatial jumps with a consistent finite movement/event model. A logical order change at a genuine crossing is distinct from adding physical longitudinal distance. Any tiny numerical boundary snap must be justified and bounded independently of the configured overtaking clearance; it must not conceal a finite maneuver. Preserve event ordering and avoid zero-time event loops.

Check a pass near the finish line and pit entry, multiple nearby cars, a blocked pass, and SC/VSC restrictions. Conservation and geometry checks must use before/after production state, not only the existence of an `overtake` event. Preserve the restricted model scope; no elaborate aerodynamic model is required.

### R4 — common commitment is still arrival-dependent in an uncovered case

`consider_recommendation()` computes `commit_t = max(arrival_t, registered_epoch)` and checks timeliness only against the effective deadline. An arrival after an earlier registered commitment epoch can still be accepted and applied later.

With commitment registered at `t0 + 0.1`, arrivals at `t0 + 0.05` and `t0 + 0.2` both returned timely recommendations, but applied at different times: `1015.8846993435944` and `1015.9846993435945` in the hand fixture. Both arrivals were before the separate effective window end.

Make the registered protocol explicit and enforce it: validate the epoch against the initial time and effective cutoff; a result unavailable by the registered commitment must not move that epoch. It must retain the registered fallback outcome and be recorded as late for that commitment. Keep the chosen exact-boundary convention consistent. Alternatively, prohibit custom epochs and use only the effective window end, with documented interface changes.

Test arrivals before, exactly at and after the registered epoch while still before the effective deadline, plus an epoch outside the allowable window. Test non-finite and negative time inputs instead of clamping malformed values into valid-looking observations. Record the actual fallback application and observation timestamps. Reject before mutation when the protocol specification is invalid.

### R5 — recommendation validation accepts invalid and out-of-scope plans

`validate_plan()` accepted a `pit_now` plan requesting compound `hard` with a `medium` set ID. The mismatch is checked later in `mount()`, after the recommendation has already been accepted. It also accepted a plan for a rival outside `selected_car_ids`.

Validate the full external team recommendation before applying it: selected-car scope, explicit partial/full-plan policy, required fields, compound/set consistency, inventory, delay type/range, current pit/finished state, action expiry and feasible supported continuation. Separate internal rival-policy APIs from the external two-car recommendation API. Do not automatically interpret missing or inconsistent values as a different action.

Make applying a team plan atomic. A failure for the second car or during intent resolution must not leave the first car's policy changed while the receipt claims fallback. Test full state equality before/after rejected recommendations and verify continuation obligations under an accepted plan. Clarify any intended ability to remount a currently fitted/used set; do not accidentally refresh old tyres by resetting their age for free.

### R6 — the resolution gate can pass mismatched events and mislabeled quantities

`_max_matched_error()` records missing/count-mismatched events, but `run_resolution_panel()` does not use those mismatches in `pit_ok`. The overall status also does not enforce the recorded legality flag. An empty matched set can become N/A even when events are present at only one resolution.

Rebuild the gate around explicit required predicates: correspondence/count agreement, defined quantities, numerical errors, legality/commitment stability, and classification behavior. N/A means genuinely absent at every compared resolution for a reason appropriate to the fixture; it is not a substitute for a mismatch. Cover h, h/2 and h/4 consistently.

For any rank reversal, identify the cars, actual ranking keys and pairwise separation at each resolution. Classify a near-tie only from a valid same-run pairwise gap and justified numerical uncertainty. The across-resolution maximum timestamp error is not that gap. Do not widen tie thresholds or sort by ID solely to suppress a discrepancy.

Test the checker itself with small fabricated checker-input fixtures: remove one required event, change its count, flip legality, and alter a rank with well-separated finishing times. Each must yield the appropriate non-PASS result. These are tests of validation logic, not fabricated experimental evidence.

## Minimal reproducible examples for R1, R3, R4 and R5

Save this diagnostic locally before changing the original source and record its output. It uses hand-constructed states and direct production handlers to isolate transitions. Convert its underlying invariants into independent regressions; do not merely assert these historical defective numbers in the repaired implementation.

```python
from pathlib import Path
from f1q.simulator.config import load_simulator_config
from f1q.simulator.interface import RaceSimulator
from f1q.simulator.hand_specs import build_hand_spec
from f1q.simulator.engine import distance

cfg, _ = load_simulator_config(Path('.'))

def fresh():
    sim = RaceSimulator(cfg)
    sim.initialize(build_hand_spec(obligation=1))
    return sim

# Pit-entry -> box -> service -> exit.
s = fresh()
e = s.engine
c = next(iter(e.state['cars'].values()))
cid = c['car_id']
c.update(completed_laps=10, frac=.95, pit_this_lap=True,
         pending_compound='medium', pending_set_id=cid+'.set.medium.0')
e.fire([('pit_entry', cid, {})])
trace = [(c['pit_phase'], e.state['t'], distance(c))]
while c['in_pit']:
    e.state['t'] = c['pit_phase_end']
    e._advance_pit(c)
    trace.append((c['pit_phase'], e.state['t'], distance(c)))
print('pit_trace', trace)

# Overtaking handler: progress change without elapsed time.
s = fresh()
e = s.engine
ids = list(e.state['cars'])
a, b = e.state['cars'][ids[0]], e.state['cars'][ids[1]]
a.update(completed_laps=10, frac=.5, tyre_age_laps=20.)
b.update(completed_laps=10, frac=.4999, tyre_age_laps=0.)
old = (distance(b), b['fuel_actual'], b['tyre_age_laps'], e.state['t'])
e.fire([('catch_or_pass', ids[1], {'ahead': ids[0]})])
new = (distance(b), b['fuel_actual'], b['tyre_age_laps'], e.state['t'])
print('pass_deltas', [v-u for u, v in zip(old, new)])

# Validation incorrectly accepts these before repair.
s = fresh()
ids = list(s.engine.state['cars'])
print('mismatched_set', s.validate_plan({ids[0]: {
    'kind': 'pit_now', 'compound': 'hard',
    'set_id': ids[0]+'.set.medium.0'}}))
print('rival_control', s.validate_plan({ids[3]: {'kind': 'continuation'}}))

# A result arriving after the registered epoch must not move commitment.
s.advance_to_checkpoint()
t0 = s.engine.state['t']
for delay in (.05, .2):
    a = s.clone()
    rec = a.consider_recommendation(
        {ids[0]: {'kind': 'continuation'}},
        arrival_delay_s=delay, commitment_epoch_race_s=t0+.1)
    print('commitment', delay, rec['timely'], rec['selected_plan'],
          rec['registered_commitment_epoch_race_s'], rec['commitment_race_s'])
```

For R2, reuse the existing hash-selected panel's episode `fam.green_pit_high.tyre_nonlinear.traffic_dense/0002/episode/03/SC` and compare raw terminal states at h and h/4. The original source can recreate the numeric table above with `RaceSimulator(_cfg_scaled(cfg, denominator))`, initialization, checkpoint advancement and `continue_to_finish()`. Save actual states and ranking keys, not only a summary saying PARTIAL.

## Execution and evidence requirements

1. Work in the existing isolated repository. Inspect actual HEAD/dirty state and preserve recoverable source/configuration snapshots before and after changes. Keep all original Stage 2/3/3.1 evidence. Do not overwrite old run identifiers or amend earlier results to look successful.
2. Reproduce the source-level defects on the pinned development environment. If any differ from this review, explain with state/trace evidence rather than dismissing the report because dependency patch versions differ.
3. Repair the foundational state/finish/movement logic first, then validate recommendation and deadline behavior, then repair the checker. Record implementation decisions and any necessary domain or schema changes. No simulator rewrite for its own sake.
4. Keep the documented conditioned fuel model as an explicit provisional assumption unless a repair needs a coherent adjustment. It is not necessary to redesign an already disclosed distribution merely to manufacture another task. Any changed model assumption must be versioned and applied consistently to generated inputs, observations and evaluator state.
5. Rerun the named mechanism checks and affected shared regressions. Confirm the newly added independent regressions fail on the preserved defective version and pass on the repair, where practical in a separate temporary copy. No artificial success threshold or minimum test count.
6. Because the repairs affect trajectories and classification, rerun the full existing 64-development-episode checkpoint/continuation/resume matrix and eight fixed diagnostic interventions under a NEW run. Preserve original specs and amendments; list rejections instead of replacing unfavorable cases. Compare full state/event signatures as well as terminal results for replay.
7. Rerun the same eight-case h/h2/h4 refinement panel with meaningful finish/position/event quantities and corrected gate logic. If a genuine near-tie remains, preserve and quantify it. Do not spend endlessly chasing roundoff; assess whether its uncertainty can change the research endpoint. An unresolved material modeling or numerical defect leaves Stage 3 PARTIAL/BLOCKED.
8. Keep one worker initially, the 60% RAM ceiling with measured scope, and a 30-minute cumulative simulator-execution cap for this repair validation. No large Monte Carlo banks, reserved scientific partition materialization, research model fitting or quantum execution. Preserve incomplete work if capped; do not silently skip failing cases to finish.
9. Explicitly supersede affected Stage 3/3.1 validity claims. Distinguish corrected software mechanics from still-unperformed real-world calibration. Unmaterialized test data and disabled hardware are expected at this stage, not defects or prerequisites to open those gates early.

## Deliverables and stop point

Save `docs/STAGE_3_2_REPORT.md`, updated model/validation descriptions with a change record, direct reproducer outputs, regression and resolution evidence, new 64-case/intervention receipts, source/configuration manifests and known limitations.

Create `review/STAGE_3_2_REVIEW.zip` with current relevant source, tests, fixtures, configurations, dependencies, reports and machine-readable diagnostic results. Include a checksum manifest INSIDE the ZIP covering every other member; the archive's own SHA-256 belongs outside it. The previous sidecar bundle manifest was not inside the uploaded ZIP. Supply missing fixtures/schema files required by the documented targeted test command, and `README.md` if package installation depends on it. Clearly state any remaining omitted inputs rather than claiming a standalone reproduction.

Exclude credentials, `.git`, environments/caches, unrelated work and reserved research data. Use fictional development inputs as needed. Verify the assembled bundle by extracting it into a clean temporary folder and running its documented targeted checks. A mutable production ledger need not be shipped; targeted checks should use an isolated temporary one or avoid it. Never print secrets when checking the selected contents. Local packaging only; no automatic push/upload.

Return:

```text
STAGE_3_2_STATUS: COMPLETE | PARTIAL | BLOCKED
SOURCE_COMMIT_AND_RECOVERABLE_SNAPSHOT:
R1_PIT_GEOMETRY: reproduced, fixed, independent evidence
R2_FINISH_AND_CLASSIFICATION: reproduced, model definition, independent evidence
R3_MOVEMENT_CONSERVATION: reproduced, fixed, independent evidence
R4_COMMON_COMMITMENT: reproduced, fixed, boundary evidence
R5_PLAN_VALIDATION_AND_ATOMICITY: reproduced, fixed, rejection evidence
R6_RESOLUTION_GATE: injected-checker failures detected and actual panel outcome
NEW_64_CASE_MATRIX: admitted/rejected/incomplete and replay discrepancies
EIGHT_INTERVENTIONS:
REFINEMENT_RESULTS_AND_GENUINE_AMBIGUITIES:
REGRESSIONS_AND_REPAIR_FAILURES:
SUPERSEDED_CLAIMS_AND_PRESERVED_RUNS:
RESOURCE_USAGE:
REVIEW_BUNDLE_PATH_AND_CLEAN_EXTRACT_CHECK:
SCIENTIFIC_PROTOCOL: DRAFT
RESERVED_PARTITIONS_MATERIALIZED: none expected
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0 expected
PUSH_PERFORMED: false expected
STAGE_4_PREREQUISITES: PASS | PARTIAL | FAIL with reasons
```

Use actual evidence, not expected defaults. Stop after reporting. Do not begin Stage 4 or ask for IBM credentials. The user will return the report and bundle for review.
