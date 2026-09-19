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

## Stage 3.1 addendum (2026-09-19) — `development_spec.fuel.v1.1`

Generation **rule unchanged**. This addendum documents the joint model that v1 already implemented and removes any reading of it as an unconditioned Uniform / unbiased observation-error model.

### Joint generation

Let \(u\) be the specification `fuel_uncertainty_kg` (declared 2 kg). Let \(\hat{m}\) be public `fuel_kg`. Offset \(\delta\) is a keyed \(\mathrm{Uniform}(-u,u)\) draw (`event_type=fuel_actual_offset`). Provisional actual \(m_0=\hat{m}+\delta\).

Horizon need \(N = L_{\mathrm{init}}\times 1.8\) uses **remaining laps at initialization** times the declared on-track consumption. That quantity is available at init. It is a declared conservative bound, not a private realized future consumption draw.

- If \(m_0 \ge N\): private actual \(m=m_0\).
- If \(m_0 < N\) and \(\hat{m}+u \ge N\): \(m=N\) and `fuel_floor_applied=true` (atom at the minimum sufficient fuel).
- If \(\hat{m}+u < N\): reject `IMPOSSIBLE_INITIAL_FUEL`. No silent clamp outside the band.

Error \(\varepsilon=m-\hat{m}\) is therefore **not** \(\mathrm{Uniform}(-u,u)\) and **not** unbiased whenever the floor can fire. Probability mass at \(N\) equals the Uniform measure of offsets that would undershoot \(N\), provided the band covers \(N\).

This is an **intentionally conditioned fictional corpus** on the supported no-refueling domain. It is not an unconditioned physical fuel population and not empirical calibration.

Stage 3.1 audit of the existing 64 Stage 2 specifications (1280 cars): 644 floors / 644 cars with mass at the need threshold; 0 rejections; error range about \([-1.94, 1.998]\) kg. Private actuals are stored in development evidence only, not in solver observations. Original Stage 2 spec bytes and Stage 3 run `e2258740-…` are not overwritten.
