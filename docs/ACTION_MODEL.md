# Action model (Stage 4)

## Stage 4.1 semantics

- One solver-visible future stop.
- Same-compound while obligation unmet is rejected at admission.
- Continuation invokes `compound_obligation.v1@1.1.0`.
- Public `pit_entry_frac` drives expiry.



Version: **1.1.0** (Stage 4.1). Evidence class: **development**. Not F1 calibration, not a research replication sample, not a hardware menu freeze.

## Scope

For each solver-visible `DecisionObservation` and declared public physics configuration, construct a deterministic ordered action dictionary `A(c)` for each of the two `selected_car_ids`. A complete research action is a **joint plan covering exactly both cars**.

Action kinds:

- `pit_now` — immediate stop onto an unused, unmounted, compound-consistent physical set
- `delay_laps` — delay exactly 1 or 2 completed laps, then pit onto an explicit set
- `continuation` — stay out under frozen downstream policy `compound_obligation.v1` / `1.0.0`

Each admitted action records: stable `action_id`, car ID, kind, compound/set when applicable, delay, downstream policy ID/version, commitment/expiry semantics, human-readable description, and observable admission facts. Rejected candidates retain an exclusion reason (expired pit entry, already in pit for new pit instructions, horizon, obligation infeasibility, etc.).

`pit_now` after missed pit entry is **rejected**, not relabelled as next-lap service.

Cars already in the pit lane admit **continuation only** (service in progress); new pit/delay instructions are excluded.

## Equivalence reduction

Policy `kind_delay_compound_age_lex_set.v1` (Stage 4 formulation fixture, **not** the later frozen hardware menu):

- Group by `(kind, delay_laps, compound, set_age_laps)`
- Retain the lexicographically smallest `set_id` as representative
- Publish the full member→representative map and degeneracy counts
- Report both full and reduced menu sizes

Reduction is independent of objective values and solver outcomes.

## Joint feasibility

Shared-crew double stacking is modelled as a **finite delay cost**, not an automatic hard prohibition. The Cartesian product of individually legal actions is treated as jointly feasible under the restricted model. No disguised “expensive illegal pair” without an explicit modelling declaration.

## Separation

Action generation accepts only solver-visible observation data and declared public configuration. It must not receive `RaceEngine`, private fuel, unrevealed regime end, future rival actions, or evaluator seeds. Adversarial SpyMapping tests enforce this.

Cross-check admitted joint plans with the production simulator’s public `validate_plan` interface on development fixtures. The enumerator’s legality rules are implemented independently of that validator; disagreements are failures.

## Precedent note

Direct F1–QUBO precedent exists (e.g. Kolstee 2026). Stage 4 makes **no** “first F1 QUBO” claim.
