# Simulator validation (Stage 3)

Labels: **PASS / FAIL / PARTIAL / NOT RUN**. Successful software checks do not establish F1 calibration, SC/VSC physical validity, tyre science, or quantum readiness. A test fixture is not an experimental observation.

Run: `e2258740-1d08-4427-8305-b149ed504a73` (`python -m f1q run --plan simulator_check`, exit 0, elapsed 148.916 s). Workers: 1 (under the Stage 3 cap of 2). RAM ceiling was not separately metered; elapsed time was under the 1800 s engineering cap. Incomplete work: none.

Supported domain: dry 20-car unit-circle 1D model `simulator.v1` / interface `3.0.0`. Exclusions: wet, red flag, sprint, tyre damage, energy deployment, pit-lane closures, refueling, retirements, unsupported race control.

## Gates

| Gate | Status | Evidence | Domain |
| --- | --- | --- | --- |
| Source / input provenance | PASS | TUMFTM inspected at `96ef2c2021982217be008fe458df47c1a72da071` and **not used**. Inputs are Stage 2 development specs `8f292588-a328-4232-b425-c36c610a29f5` plus labeled hand fixtures. Source snapshot reconstructed: hash `26ed935ce0dbba00963bbe5766c77f1247fed491d2a9cf697f692c1cf5a4e6c1` matched. Private replay package 128 files, hash `ab4d0e23c3f715e9d7ba6eb0d12e74e551a891a9cbec66ebcf6d69e1d0b98dc9`. | Generated fictional development inputs only |
| Structural schema | PASS | Stage 2 specs parse after accepting the stored `substantive_fingerprint`. `python -m f1q generator validate` remains the Stage 2 config check. 68 pytest passed (`docs/evidence/stage3/pytest.txt`). | Schema, not physics |
| Individual mechanism checks | PASS | `evidence/simulator/artifacts/e2258740-1d08-4427-8305-b149ed504a73/simulator.mechanism_checks/unit.json`. All 10 named checks `ok: true`. | Restricted model; see maximum errors below |
| Checkpoint / resume | PASS | 64/64 development episodes admitted; resume max time error 0.0 s; ranks identical. Fresh-process restore: `tests/test_simulator_mechanisms.py::test_resume_equivalence_in_fresh_process`. | Same model and keys |
| Causal decision / deadline | PASS | `causal_leakage` and `deadline` in the mechanism unit. Boundary arrival is exclusive (`arrival < effective_end`). Scenario latency is 1:1 onto the race clock; not an IBM queue measurement. | Research settings 1.0 s margin, 30 s primary budget |
| Admitted development checkpoints | PASS | 64 attempted, 64 admitted, 0 rejected, 0 pending. Preview specs were not overwritten. Not a scientific split. | Engineering validation only |
| Real-world calibration | NOT RUN | No F1 timing, no parameter fit, no team operational trial. | Outside Stage 3 |

## Mechanism maximum errors (independent oracles)

| Check | Pass | Maximum error / observation | Path |
| --- | --- | --- | --- |
| free_track | PASS | pit identity \(1.42\times10^{-14}\) s (tol \(10^{-9}\)); race time \(1.93\times10^{-12}\) s (tol 0.5 s) | mechanism unit.json |
| shared_service | PASS | analytical wait error 0; production wait \(2.26\times10^{-10}\) s | same |
| traffic_rejoin | PASS | blocked leader stable; min gap 0.001319 laps; permitted pass true; pit-exit geometry true | same |
| sc_vsc | PASS | SC pack-gap sum 0.13886 → 0.10505 laps over 25 s; VSC 0.13868 → 0.13868 (unchanged); restart GREEN | same |
| tyres_fuel_obligations | PASS | nonnegative inventory; impossible set rejected | same |
| causal_leakage | PASS | no private tokens in observation; duration status unknown before end | same |
| deadline | PASS | timely / exclusive boundary / late / closed / revalidation | same |
| resume | PASS | rank error 0; time error 0; 212 events; pending phase at snapshot | same |
| randomness | PASS | fuel offsets and regime duration stable across action branches; clone isolation | same |
| classification | PASS | ranks and \((r_1+r_2-2)/(2(F-1))\) match; retirement rejected | same |

## Diagnostic interventions

Eight hash-selected episodes (min `sha256(episode_id)` per family; even families SC, odd VSC). Alternative `pit_now` onto an unused obligation set. Count 8, failures 0. **Not a powered comparison and not evidence of strategy improvement.**

## Intended simplifications

Unit-circle geometry; tick-resolution overtaking; instantaneous green restart that preserves gaps; SC catch-up factor 0.85 toward a 1.0 s queue gap; VSC cap without that bunching rule; one-shot hand plans; fuel and cutoff development-spec amendments; no wet/red-flag/retirement. Restricted models can be scientifically useful; this domain is documented before any later freeze and is **not** adequate as a claim of actual F1 operational validity.
