# Action model (Stage 4.2)

Version: **1.2.0** (Stage 4.2 Gate C closure). Evidence class: **development**. Not F1 calibration, not a research replication sample, not a hardware menu freeze. The analytical proxy and the simulator evaluator are separate; neither is race truth.

## Scope

For each solver-visible `DecisionObservation` and declared public physics configuration, construct a deterministic ordered action dictionary `A(c)` for each of the two `selected_car_ids`. A complete research action is a **joint plan covering exactly both cars**.

Action kinds:

- `pit_now` — immediate stop onto an unused, unmounted, compound-consistent physical set
- `delay_laps` — delay exactly 1 or 2 completed laps, then pit onto an explicit set
- `continuation` — execute under downstream policy `compound_obligation.v1@1.2.0`

Each admitted action records: stable `action_id`, car ID, kind, compound/set when applicable, delay, downstream policy ID/version, commitment/expiry semantics, human-readable description, and observable admission facts. Rejected candidates retain a stable exclusion reason.

## Stage 4.2 semantics

- One solver-visible future stop (on-track language unchanged unless a second-stop language is deliberately implemented).
- Same-compound while obligation unmet is rejected at admission.
- Continuation admission is a complete legality proof: unmet obligation without an eligible alternate unused set, insufficient horizon, missed pit entry when an immediate obligation stop is required, malformed in-pit commitment, commitment/inventory conflict, and nonpositive remaining distance are excluded with stable reason codes.
- Cars already in the pit lane admit **continuation only**, and only when a public `committed_pit_service` projects the exact committed compound and set.
- Public observation exposes selected-team in-progress commitments (phase, residual timings, crew occupancy) — not private fuel, rival futures, or sampled regime ends.
- `pit_now` after missed pit entry is **rejected**, not relabelled as next-lap service.

## Equivalence reduction

Policy `kind_delay_compound_age_set.v2`:

- Group by `(kind, delay_laps, compound, set_id, set_age_laps)`
- Different physical set IDs are **not** merged
- Different ages are **not** merged
- Publish member→representative map and degeneracy
- Cost/semantic equivalence is proven independently (unary costs, planned-stop semantics, pair costs vs all opposing retained actions) — not by re-checking the grouping signature alone

## Joint feasibility

Shared-crew double stacking is modelled as a **finite delay cost** from observable service-interval overlap, not an automatic hard prohibition and not an arbitrary adjacent-lap half-service coefficient (that Stage 4 rule is deleted).

## Separation

Action generation accepts only solver-visible observation data and declared public configuration. SpyMapping tests forbid private keys.
