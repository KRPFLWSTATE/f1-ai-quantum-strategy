# Restricted proxy objective compiler (Stage 4)

Version: **1.0.0**. Primary coefficient unit: **seconds**. Stage 4 risk weight: **exactly 0** (weights have not been selected on tuning data).

## Decomposition

For cars 1 and 2 with legal plans `a` and `b`:

```text
f(a,b) = C + u1[a] + u2[b] + v[a,b]
```

- `C` — reported constant baseline (0 in the current analytical accumulation; race-time baseline lives in the unaries)
- `u1[a]`, `u2[b]` — predicted remaining-time contribution for each car under the restricted analytical model
- `v[a,b]` — **additional** pair interaction only (shared-crew wait / restricted rejoin), not already inside the unaries

## Analytical model (declared public inputs only)

Observable / public inputs:

- compound, tyre age, estimated fuel kg, remaining laps, revealed regime (if any)
- public `green_lap_s`, `green_pit_loss_s`, tyre form/wear/curvature scales, compound offsets, `kg_per_lap`, `time_per_kg_s`, service time, SC/VSC pace factors
- compound obligation count

Lap time (restricted):

```text
T = (green_lap_s + compound_offset + tyre_delta(age) + time_per_kg * fuel_est) * pace_factor(regime)
```

Regime-adjusted pit loss:

```text
pit_loss_eff = green_pit_loss_s / pace_factor(regime)
```

Plans:

- `pit_now` / `delay_k` apply `pit_loss_eff` at the scheduled lap index and reset age on the new compound
- `continuation` may force a downstream obligation stop near the horizon under `compound_obligation.v1`

Pair term `v`:

- same scheduled pit lap → add `service_stationary_s` once (double-stack wait)
- adjacent pit laps → add `0.5 * service_stationary_s`
- otherwise 0

No separate degradation/traffic/pit penalty is added if already inside predicted remaining time. No arbitrary risk/tail functional.

## Centring

```text
m1 = min_a u1[a]
m2 = min_b u2[b]
u1_centered[a] = u1[a] - m1
u2_centered[b] = u2[b] - m2
C_centered = C + m1 + m2
```

Verified exhaustively on legal pairs: centring changes no physical objective, optimum, gap, or tie. Restore the constant for physical-unit reports.

## Direct scorer

`score_joint_direct` evaluates a legal joint plan from the uncentred (or centred) action-cost table **without** importing or calling the QUBO builder. It is the primary reference for energy agreement.

## Separation from the evaluator

The compiler builds an analytical proxy in seconds. The simulator evaluator (`f1q.formulation.evaluator`) applies complete plans to **cloned** checkpoints via `continue_to_finish` and reports modelled ranks / `L`. These are **not** aliases, wrappers, or two modes of one implementation. AST import-boundary checks enforce separation.

The compiler never calls `continue_to_finish` and never reads private simulator state.
