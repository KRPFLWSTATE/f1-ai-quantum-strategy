# Development-spec amendment: checkpoint.cutoff.v1

Status: **declared Stage 3 modelling amendment**. Original Stage 2 cutoff samples are preserved on the specification.

## Finding

Stage 2 drew `pit_entry_commitment_cutoff_remaining_s` independently of `gap_ahead_s` and track geometry. Those two quantities cannot both be used as physical initial conditions without inconsistency.

## Amendment

- Pack the field from classified order and `gap_ahead_s` converted at the initial green pace, with the leader's on-track fraction taken from **that car's** sampled cutoff so the leader retains a Stage 2-aligned pit-entry time.
- Recompute every car's operational pit-entry cutoff from geometry: remaining time at the current pace to the next pit-entry station.
- Store sampled cutoffs as `sampled_cutoff_remaining_s` (not used for physics). Operational cutoffs are `pit_entry_commitment_cutoff_race_s`.

This is a geometry resolution, not a claim that Stage 2 cutoffs were F1-measured.
