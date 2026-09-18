# Development-spec amendment: fuel.v1

Status: **declared Stage 3 modelling amendment**. Original Stage 2 specifications are preserved unchanged. This amendment applies only when those specs are evolved by `simulator.v1`.

## Finding

Stage 2 sampled `fuel_kg = max(5, remaining_laps_at_init * 1.8 + Uniform(-2, 2))`. About half of cars are therefore below `remaining_laps_at_init * 1.8`. Treating `fuel_kg` as private actual mass and consuming 1.8 kg/lap would exhaust inventory before the horizon. Silently raising consumption-adjusted mass would hide the modelling error. Rejecting every such car would reject essentially the entire 64-episode preview.

## Amendment (not a silent clamp outside the uncertainty band)

- `fuel_kg` on the specification remains the **estimated** onboard mass (solver-visible).
- Private actual mass is `estimate + offset` with `offset ~ Uniform(-u, u)` keyed by the evaluation stream (`event_type=fuel_actual_offset`).
- If that draw is still below `remaining_init * 1.8`, and `estimate + u` covers the horizon, actual mass is set to the horizon requirement. That uses only mass that the documented 2 kg uncertainty band already allowed. The floor is recorded on the private state (`fuel_floor_applied`).
- If even `estimate + u` cannot cover the horizon, initialize **rejects** with `IMPOSSIBLE_INITIAL_FUEL`. No clamp.

Original specs are not rewritten. Simulator runs that apply this rule record `amendment_ids: ["development_spec.fuel.v1"]` on new artifacts.
