# Restricted proxy objective compiler (Stage 4.2)

Version: **1.2.0**. Primary coefficient unit: **seconds**. Stage 4 risk weight: **exactly 0**. This is an **analytical proxy**, not the simulator evaluator and not race truth.

Stage 4.2 supersedes Stage 4 / 4.1 Gate C software claims for in-pit residual costing, pair timing, and planned-stop semantics. Numerical coefficients must be regenerated; do not copy Stage 4.1 goldens.

## Decomposition

```text
f(a,b) = C + u1[a] + u2[b] + v[a,b]
```

- `C` — constant baseline (0 in the current analytical accumulation)
- `u1[a]`, `u2[b]` — predicted remaining-time contribution under the restricted analytical model
- `v[a,b]` — additional shared-crew wait from observable service-interval overlap only

## Analytical model (declared public inputs only)

Observable / public inputs:

- compound, tyre age, estimated fuel kg, remaining laps, revealed regime (if any)
- public lap/pit/tyre/fuel constants and SC/VSC pace factors
- public `pit_entry_frac`
- public `committed_pit_service` for selected-team in-pit cars (compound, set, phase, residual phase timings, crew free-at)

Lap time (restricted):

```text
T = (green_lap_s + compound_offset + tyre_delta(age) + time_per_kg * fuel_est) * pace_factor(regime)
```

Regime-adjusted pit loss for on-track scheduled stops:

```text
pit_loss_eff = green_pit_loss_s / pace_factor(regime)
```

Plans:

- `pit_now` / `delay_k` apply `pit_loss_eff` at the scheduled lap index and reset age on the new compound
- on-track `continuation` may schedule an immediate alternate-compound stop when the obligation is unmet
- **in-pit continuation** models the **residual** committed stop from the decision instant: remaining transit/wait/service/exit once, mount the exact committed set/compound, reset age at service completion, and use that compound for subsequent laps. Source of the planned-stop record: `in_progress_commitment`. Elapsed pit time is not double-charged.

## Pair term

```text
wait = max(0, earlier_service_end - later_service_start)
```

using predicted box arrivals and/or public committed service intervals. The pair term is zero with an explicit reason when public timing is insufficient. The deleted Stage 4 adjacent-lap half-service coefficient is not restored.

Unary residuals include a car’s own remaining wait once; the pair term adds shared-crew overlap once.

## Centring

```text
m1 = min_a u1[a]
m2 = min_b u2[b]
u1_centered[a] = u1[a] - m1
u2_centered[b] = u2[b] - m2
C_centered = C + m1 + m2
```

Centring must not change the physical objective ordering beyond declared tolerance.
