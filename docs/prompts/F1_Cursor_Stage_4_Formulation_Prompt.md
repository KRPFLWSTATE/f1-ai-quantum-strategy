# Stage 4 — action model, objective compiler, QUBO, and independent classical references

Project: `f1-ai-quantum-strategy`. Work only in the existing isolated repository. This prompt authorizes Stage 4 local formulation work and one bounded development validation run. Implement the work, execute the checks, create the evidence package, and return the requested report and review bundle. Do not respond with a plan alone.

Stage 3 is closed. Independent review of `STAGE_3_3_REVIEW.zip` verified safe extraction, all 209 manifested members and their hashes, the declared aggregate digest, live equality of the corrected Stage 3.3 scientific payload, exact zero finite-gap movement deltas, and rejection of the historical shared-finish-time shape. The submitted archive SHA-256 was:

```text
71a25e50278e2b3666e066e37f6e325a9e81dfa269766eb2e9669b97ac3bc277
```

The Stage 3.3 report states that local commit `0dbbf0b9afcfbc80e72bfb6f4beee9d8ab59cbbd` is clean and unpushed. Verify the actual repository state yourself. If HEAD or the tree differs, preserve and report the discrepancy; do not reset, overwrite, or hide it.

## Non-negotiable boundaries

- Zero additional spending. Use only local, free/open-source dependencies.
- Keep `hardware_execution_enabled: false`.
- Do not request, inspect, enter, print, store, or test an IBM API key.
- Do not access IBM or any other quantum provider, query balances/backends, implement submission, or submit physical jobs.
- Do not implement QAOA circuits, mixers, angle fitting, parameter banks, learned selectors, dispatch models, AI training, or Stage 5 work.
- Do not materialize or inspect training, tuning, calibration, test, or shift partitions. Use hand fixtures and the already admitted 64-case development preview only.
- Do not scrape F1 data or describe the synthetic restricted model as empirically calibrated Formula One performance.
- Do not run the conditional 1,200-instance scaling panel or a large Monte Carlo campaign.
- Do not push to GitHub, publish, schedule jobs, create GitHub Actions, or modify the closed prior-paper repository.
- Preserve every prior report, run, receipt, correction, and raw artifact. Never reuse a run ID or edit evidence to match an expected conclusion.

This stage establishes Gate C only: direct costs, QUBO/Ising energies, legal decoding, and independent classical references must agree on small cases. It does not establish quantum advantage, circuit novelty, F1 calibration, scientific superiority, or publication results.

## Read and establish state first

Read, in order:

1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `docs/STAGE_3_3_REPORT.md`
4. `docs/STAGE_3_2_REPORT.md`
5. `docs/SIMULATOR_MODEL.md`
6. `docs/SIMULATOR_VALIDATION.md`
7. `docs/STAGE_2_REPORT.md`
8. `docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf`, especially sections 7–10, 14–16, 23–26 and 30
9. Current configuration, schemas, dependency pins, ledger receipts and source snapshot rules

Run `python -m f1q doctor`, `python -m f1q status`, the complete existing test suite, `git status --short`, and the Stage 3.3 diagnostic verification before changing code. Record exact starting HEAD, dirty paths, environment, exits and test count. Never print environment variables or credentials.

Update the project authorization/status files for Stage 4 only after the starting state is captured. Add a bounded `formulation_check` plan and make it the next authorized local unit. Natural-language `do a run` must execute that plan once, save evidence, and stop; it must not begin Stage 5 or open reserved splits.

## 1. Architectural separation

Create clearly separated modules for:

1. legal action generation from a solver-visible `DecisionObservation`;
2. the restricted proxy objective compiler;
3. direct legal-plan scoring;
4. QUBO construction, QUBO-to-Ising conversion, scaling and decoding;
5. exact legal enumeration;
6. an independently implemented integer formulation;
7. classical heuristic candidate generators;
8. a separate simulator evaluator adapter used only for bounded development diagnostics.

The action generator and proxy compiler must accept solver-visible observation data and declared public configuration only. They must not receive `RaceEngine`, `SimulatorState.private`, actual fuel, unrevealed regime duration, future rival actions, evaluator seeds, or any private simulator object. Add adversarial tests that fail on forbidden access.

The objective compiler and simulator evaluator must not be aliases, wrappers around the same scoring function, or two modes of one implementation. The compiler builds a restricted analytical proxy in seconds. The evaluator applies complete plans to cloned simulator checkpoints and reports modelled outcome/classification quantities. Use import boundaries and tests to make this separation auditable.

## 2. Complete two-car action model

For each selected car `c`, construct a deterministic ordered action dictionary `A(c)` from the checkpoint observation. Every action is a complete one-car plan containing:

- a stable action ID and car ID;
- `kind`: `pit_now`, `delay_laps`, or `continuation`;
- for pit actions, explicit compound and physical set ID;
- for delayed actions, delay exactly 1 or 2 completed laps from the checkpoint;
- the frozen downstream policy ID and version used after the immediate/delayed instruction is consumed;
- the action's commitment/expiry semantics;
- a human-readable semantic description;
- the observable facts used to admit it;
- an exclusion/rejection reason when a candidate is not admitted.

The external team decision must be a complete joint plan covering **exactly both** `selected_car_ids`; do not treat a one-car partial dictionary as a complete research action. Keep any simulator support for partial internal updates separate from the Stage 4 joint-plan schema.

Generate candidates for the supported timing choices and every unused, unmounted, compatible physical tyre set that is observable. Remove individually illegal or already expired actions before encoding. Check compound/set consistency, used/mounted status, current pit/finished state, remaining horizon, supported delay, compound obligations, and downstream feasibility. `pit_now` after its entry opportunity is a rejected action, not relabelled as next-lap service.

`continuation` is not an underspecified instruction: its record must identify the frozen downstream policy that handles future obligation feasibility. A same-compound stop may remain legal only if the documented downstream policy can still satisfy the obligation within the supported horizon. Reject plans for which completion cannot be established under the restricted model.

Do not silently merge physical sets. If several unused sets are model-equivalent, retain the full action dictionary or publish a deterministic equivalence reduction with the complete member-to-representative map and degeneracy count. Any reduced small/quantum menu must be chosen by a documented semantic rule independent of objective values and solver outcomes. Report both full and reduced counts and every excluded action. Stage 4 reductions are formulation fixtures, not the later frozen hardware menu.

For the present model, shared-crew double stacking is a finite interaction/delay, not automatically a hard prohibition. Therefore the Cartesian product of individually legal actions should normally be jointly feasible. If a genuine pairwise hard incompatibility exists, either remove it using a documented pre-encoding rule that preserves decision semantics or encode an additional hard constraint with its own zero-feasible proof and penalty bound. Never disguise an illegal pair as merely expensive without declaring that modelling choice.

Cross-check every admitted complete joint plan with the production simulator's public validation interface on development fixtures, but do not make the simulator validator the sole implementation of the enumerator's legality rules. Record disagreements as failures.

## 3. Restricted proxy objective

Use explicit seconds as the primary coefficient unit. For cars 1 and 2 and their legal plans, implement:

```text
f(a,b) = C + u1[a] + u2[b] + v[a,b]
```

where:

- `C` is a reported constant baseline;
- each unary term predicts that car's remaining-time contribution under the restricted compiler model;
- `v[a,b]` contains only additional pair interaction not already included in the unaries, including declared shared-crew waiting and restricted rejoin/traffic interaction.

Document the analytical equations, units, coefficient sources, approximations, and the observable inputs used. Cover tyre-age evolution, declared fuel estimate treatment, pit timing, regime-adjusted pit loss, delayed stops, downstream obligation policy, and pair timing. Do not copy private simulator state or call `continue_to_finish()` while compiling coefficients.

Avoid double counting. Do not add a separate degradation, traffic or pit penalty if it is already inside predicted remaining time. Add no arbitrary risk/tail functional. Stage 4's primary risk weight is exactly zero because weights have not been selected on tuning data. A future risk extension must have explicit units and a proven linear/quadratic representation.

Implement a direct scorer that evaluates a complete legal joint plan from the uncentred action-cost table without importing or calling the QUBO builder. It is the primary reference for energy agreement.

Before penalties, centre each car's unary coefficients:

```text
m1 = min_a u1[a]
m2 = min_b u2[b]
u1_centered[a] = u1[a] - m1
u2_centered[b] = u2[b] - m2
C_centered = C + m1 + m2
```

Verify exhaustively on legal plan pairs that centring changes no physical objective value, optimal set, gap, or tie. Restore the constant for every physical-unit report.

## 4. QUBO specification and proof

Use one binary variable `x(c,a)` per retained action and exactly one selected action per car. Publish a stable variable order and reversible variable/action mapping.

Adopt and document one convention throughout, preferably:

```text
E_Q(x) = offset + sum_{i <= j} Q[i,j] x_i x_j
```

with a strictly upper-triangular serialisation plus diagonal, binary `x_i ∈ {0,1}`, and no implicit double counting.

The unpenalised QUBO contains centred unary terms on the diagonal and cross-car pair terms. Add one-hot penalties:

```text
M * (sum_a x(1,a) - 1)^2
M * (sum_b x(2,b) - 1)^2
```

and only genuinely required additional hard penalties.

For every encoded instance record:

- proof that at least one feasible bit string exists;
- `P(x)=0` for every feasible state;
- `P(x) >= v_min > 0` for every infeasible state;
- `B`, the sum of absolute unpenalised nonconstant QUBO coefficients after centring;
- the computed or proven `v_min`;
- the exact penalty rule and a strictly positive numerical margin;
- `M > B / v_min` (strict, not equality);
- post-construction verification that no infeasible state can beat the best feasible energy on exhaustive small cases.

Do not use a magic penalty value. Handle `B=0`, empty menus, one-action menus, ties, negative pair terms, and floating-point tolerances explicitly. Include a deliberately adversarial fixture showing that a weaker, unjustified penalty can fail while the derived penalty passes.

Expand the penalty constant correctly. Store both the decision objective and penalised energy; never compare physical seconds after dropping an offset.

Convert the QUBO independently to an Ising cost Hamiltonian using `x=(1-Z)/2`. Record the Ising constant, `h_i`, `J_ij`, bit/sign convention and variable ordering. Verify QUBO and Ising energies for every bit string on small fixtures.

For future circuit use define, record, and test:

```text
s_Q = max(1, max_i |h_i|, max_{i<j} |J_ij|)
```

in the fixed seconds-based coefficient convention, excluding the constant but including hard penalties. Store the largest nonconstant QUBO coefficient separately. Verify that scaling by `s_Q` and undoing it restores every energy difference and physical decision margin. Do not construct a quantum circuit in this stage.

Decode only states satisfying all hard constraints. Return explicit infeasibility reasons for invalid samples. Define deterministic tie handling and retain the full set of exactly tied or tolerance-tied optimal legal plans; do not pick a favourable optimum silently.

## 5. Independent references

Implement the following without using the QUBO optimiser as their core:

### A. Vectorised legal enumeration

Enumerate the `K1 × K2` legal plan table, not `2^(K1+K2)` invalid bit strings. Use NumPy vectorisation for the operational path. Return the exact proxy minimum, all tied minimisers, gaps, legal action count, table-construction time, scan time, memory estimate, and deterministic result hash.

### B. Independent MILP

Use a free/open-source solver through `scipy.optimize.milp`/HiGHS if a compatible local wheel is available. Add pinned NumPy/SciPy versions compatible with the existing Python/macOS environment and record licences/provenance. Do not introduce a paid solver.

Build the MILP separately from the QUBO builder. Use binary `x_a`, `y_b`, and product variables `z_ab` with:

```text
sum_a x_a = 1
sum_b y_b = 1
z_ab <= x_a
z_ab <= y_b
z_ab >= x_a + y_b - 1
```

and the uncentred physical objective. Record status, bound, termination gap, solve time, selected plans and all solver tolerances. Compare value and the set of valid minimisers against legal enumeration. If coefficient scaling/rounding is required, quantify its maximum error and any induced ties.

If a compatible free solver cannot be installed, mark the independent-integer requirement blocked; do not relabel enumeration or QUBO brute force as an independent MILP.

### C. Restricted DP/analytical reference

For fixtures with zero pair interaction, solve each car independently and combine its minima. Prove the assumption under which this is exact and compare with enumeration. Do not claim this DP/analytical decomposition is exact when pair interactions are nonzero.

### D. Practical classical candidates

Implement deterministic greedy construction plus one-car-at-a-time local improvement, uniform legal sampling, and a seeded simulated-annealing or equivalent local stochastic search over legal joint plans. All must always retain a legal incumbent, expose evaluation/sample budgets, record seeds, and use the same direct proxy scorer. These are development implementations for later fair comparison, not Stage 4 performance claims.

Measure preprocessing and online work separately. Record threads, warm starts, cache policy, machine information and actual wall time. If exact enumeration completes within an operational deadline, label it an operational classical competitor rather than hiding it as an offline reference.

## 6. Headroom and evaluator diagnostics

For every development instance report at least:

```text
heuristic_proxy_headroom = f(greedy_incumbent) - f(exact_proxy_optimum)
exact_reference_headroom = 0
```

Also report tolerance, ties, exact scan time and whether compilation plus exact scan fits each nominal 5/10/30/60/120-second budget. This is development evidence for the later Gate E decision. It is not a quantum-performance result.

Create a small, deterministic, explicitly development-only evaluator panel spanning all eight existing factor families and both SC/VSC where available. Keep it bounded: use a predeclared hash/semantic selection and only enough joint plans to verify architectural separation and expose possible proxy/evaluator ranking disagreement. At minimum include the exact proxy optimum, greedy incumbent, and deterministic comparison plans; evaluate all legal pairs only when the declared cap permits it. Record selection before evaluator outcomes.

For evaluated plans, use simulator clones and report the restricted model's leader-finish classification, selected-team ranks, normalised team-rank loss

```text
L = (r1 + r2 - 2) / (2 * (F - 1))
```

and legality. Call this a **modelled development diagnostic**, not race truth. Report proxy/evaluator rank correlation or disagreement descriptively and identify ties. Do not tune compiler weights from this panel and do not select favourable cases after seeing outcomes.

If exact enumeration eliminates proxy headroom across the admitted development domain, report it plainly. Do not manufacture difficulty by enumerating invalid bit strings, weakening classical code, or expanding the formulation without scientific justification. Gate C may still pass while Gate E becomes a serious later limitation.

## 7. Instance and evidence schema

Add versioned schemas/configuration for the action model, formulation and Stage 4 run. Every machine-readable instance record must include:

- source development checkpoint/spec ID and hash;
- solver-visible observation hash and simulator/interface versions;
- selected cars and complete ordered action dictionaries;
- excluded candidates and reasons;
- full/reduced menu policy and counts;
- coefficient units, compiler version and assumptions;
- uncentred and centred constants/unaries/pair table;
- variable/action mapping and QUBO convention;
- hard constraints, `B`, `v_min`, margin, `M`, proof checks and `s_Q`;
- exact legal optimum, ties and action gap;
- MILP/DP/reference results and tolerances;
- compiler, table, scan and solver timing;
- evidence class `development` and explicit flags that it is not experimental, calibrated-F1, noisy-simulation, or physical-QPU evidence.

Numeric summaries must be generated from raw records, never typed into the report as an independent source. Hash all action dictionaries, coefficient records and derived summaries. Failed instances and solver attempts remain in the denominator with failure codes.

## 8. Required tests

Add focused tests covering at least:

1. deterministic action IDs/order and round-trip serialisation;
2. complete two-car joint plans and rejection of partial/rival plans;
3. no private/future-state access by action generation or compilation;
4. individual legality, expiry, tyre-set consistency, obligations and downstream feasibility;
5. equivalence reduction maps and no silent loss/duplication;
6. cross-check of admitted joint plans with simulator validation;
7. direct objective decomposition and unit consistency;
8. no unary/pair double counting on hand-calculable fixtures;
9. centring preserves every legal objective, optimum, tie and gap;
10. exact QUBO energy equals the direct penalised expression for every bit string on small fixtures;
11. feasible-zero, positive-infeasible `v_min`, strict penalty bound and adversarial weak-penalty failure;
12. QUBO-to-Ising energy equality and reversible bit/action mapping;
13. `s_Q` scaling/restoration and constant handling;
14. exact enumeration value/ties versus independent MILP;
15. zero-interaction DP/analytical result versus enumeration;
16. greedy/local, uniform and annealing legality, determinism under seed, and budget accounting;
17. coefficient/record hash stability and schema rejection of malformed/nonfinite values;
18. compiler/evaluator implementation separation;
19. deterministic evaluator-panel selection made without outcome access;
20. interrupted Stage 4 run persistence and checksum-verified resume without recomputing completed units.

Use hand-derived tiny cases with known answers, including one action per car, asymmetric menu sizes, exact ties, negative interaction, strong double-stack interaction, and an illegal/expired action. Avoid tests that merely invoke the same helper on both sides of an equality.

## 9. Bounded Stage 4 run

Add and execute one new plan, `formulation_check`, under a new run ID. Suggested reviewable units are:

1. `formulation.action_model`
2. `formulation.compiler_direct_costs`
3. `formulation.qubo_ising_gate`
4. `formulation.independent_references`
5. `formulation.development_matrix`
6. `formulation.evaluator_separation_panel`
7. `formulation.source_restore`

Use the 64 already admitted development checkpoints for coverage. Do not call these 64 research replications or a powered sample. Keep the evaluator panel bounded as above. Start with one worker; use at most two only after measuring memory. Enforce the existing 60% RAM ceiling and a 30-minute cumulative Stage 4 execution cap. Preserve partial work and issue a resumable receipt if capped; never drop slow/failing cases or replace them with favourable ones.

The run must record planned/completed/failed units, source and configuration hashes, raw evidence paths, timings, failures, RAM/worker settings, QPU usage `0`, and the next permitted unit. `do a run` must later mean exactly one next authorized local plan, not an autonomous campaign.

## 10. Acceptance gate

Gate C passes only if:

- action dictionaries are deterministic, complete, legal and solver-visible only;
- full/reduced action counts and exclusions are reported;
- direct legal costs and centred costs agree exactly within a declared tolerance;
- QUBO and Ising energies agree with the independent direct expression on exhaustive small cases;
- every feasible state has zero hard penalty, every infeasible state has at least `v_min`, a feasible state exists, and `M > B/v_min` with positive margin;
- decoding and ties are correct;
- vectorised legal enumeration, independent MILP and the zero-interaction analytical/DP reference agree where each applies;
- compiler costs and exact-reference costs/timings are reported honestly;
- all existing and new tests, doctor, status and Stage 3.3 verification pass;
- the Stage 4 run and clean-extract review checks complete without hidden exclusions;
- no reserved split, learned model, circuit, provider, QPU, push or spending occurs.

Failure of Gate C blocks Stage 5. Zero optimisation headroom does not falsify the formulation but must be carried forward as a Gate E warning. Do not convert a no-headroom result into a claim of quantum promise.

## 11. Documentation, commit and review package

Create:

- `docs/ACTION_MODEL.md`
- `docs/OBJECTIVE_COMPILER.md`
- `docs/QUBO_SPECIFICATION.md`
- `docs/CLASSICAL_REFERENCES.md`
- `docs/STAGE_4_REPORT.md`
- machine-readable raw/summary evidence under a new Stage 4 run ID
- updated `README.md`, `PROJECT_STATUS.md`, `AGENTS.md`, configuration, schemas and CLI documentation

State explicitly that direct F1-QUBO precedent exists and Stage 4 makes no “first F1 QUBO” or quantum-advantage claim. The potential contribution remains the later auditable causal, deadline-aware, headroom-aware AI/quantum allocation study—not complexity manufactured from a small one-hot encoding.

After all checks pass, create one local Stage 4 commit if it can include only authorized project changes. Never include credentials, environments, caches, mutable ledger state, protected data or unrelated changes. Do not push.

Create `review/STAGE_4_REVIEW.zip` with relevant current source, tests, schemas, configs, dependency locks, documentation, Stage 3.3 closure evidence, Stage 4 raw/summary evidence and receipts. Include `MANIFEST.sha256.json` inside the ZIP covering every other member by path, bytes and SHA-256, and document the aggregate algorithm. Store the ZIP's own SHA-256 in an external sidecar.

Extract the bundle into a new temporary directory, verify all member hashes and aggregate, install/use the documented environment, and run the targeted Gate C checks plus formulation-record verification without the original ledger. Record exact clean-extract commands and results. Omitted inputs must be listed; do not claim standalone reproduction if they are absent.

## Required return and stop point

Return:

```text
STAGE_4_STATUS: COMPLETE | PARTIAL | BLOCKED
STARTING_HEAD_AND_TREE:
ENDING_HEAD_LOCAL_COMMIT_AND_TREE:
ENVIRONMENT_AND_NEW_FREE_DEPENDENCIES:
ACTION_MODEL_VERSION:
FULL_AND_REDUCED_ACTION_COUNTS:
ILLEGAL_OR_EXCLUDED_ACTIONS:
PROXY_OBJECTIVE_UNITS_AND_ASSUMPTIONS:
COMPILER_EVALUATOR_SEPARATION:
QUBO_CONVENTION_AND_VARIABLE_MAPPING:
PENALTY_PROOF: B, v_min, margin, M, feasible-zero/infeasible-positive checks
ISING_MAPPING_AND_SCALE_SQ:
EXHAUSTIVE_SMALL_CASE_ENERGY_AGREEMENT:
EXACT_LEGAL_ENUMERATION:
INDEPENDENT_MILP_AGREEMENT:
RESTRICTED_DP_ANALYTICAL_AGREEMENT:
CLASSICAL_HEURISTIC_CHECKS:
DEVELOPMENT_MATRIX: planned/completed/failed, not a powered comparison
PROXY_HEADROOM_AND_EXACT_RUNTIME_WARNING:
EVALUATOR_SEPARATION_PANEL:
FULL_REGRESSION_RESULT:
FORMULATION_CHECK_RUN_ID_AND_RECEIPT:
RESOURCE_USAGE:
REVIEW_BUNDLE_PATH_SHA256_AND_CLEAN_EXTRACT:
GATE_C_FORMULATION: PASS | PARTIAL | FAIL
GATE_E_HEADROOM_WARNING: none | present, with evidence
SCIENTIFIC_PROTOCOL: DRAFT
RESERVED_PARTITIONS_MATERIALIZED: none
LEARNED_MODELS_TRAINED: 0
QUANTUM_CIRCUITS_EXECUTED: 0
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0
QPU_USAGE_SECONDS: 0
PUSH_PERFORMED: false
STAGE_5_PREREQUISITES: PASS | PARTIAL | FAIL with reasons
```

Then stop. Do not begin Stage 5 and do not ask for an IBM API key. The user will return `docs/STAGE_4_REPORT.md` and `review/STAGE_4_REVIEW.zip` for independent review.
