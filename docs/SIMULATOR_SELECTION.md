# Simulator selection (Stage 3)

Labels: **inspected** (upstream bytes/README), **implemented** (this project's restricted model), **verified** only where a named check is cited. Existence of an upstream repository does **not** establish traffic, SC/VSC, or F1 validity.

## Selected approach

**Restricted independent model** `simulator.v1` / interface `3.0.0`, implemented in `src/f1q/simulator/`. No TUMFTM code is imported, vendored, or executed as a runtime adapter. Generated Stage 2 development specifications plus labeled hand-constructed fixtures are the only inputs.

This is the dossier §8 permitted fallback when a pinned full-simulator adapter cannot represent the required checkpoint, sub-lap timing, causal isolation, and generated-input constraints.

## Upstream inspection (not executed as this project's simulator)

Repository: https://github.com/TUMFTM/race-simulation  
Inspected revision: **`96ef2c2021982217be008fe458df47c1a72da071`** (master at clone time 2026-09-19; commit date 2021-09-18, message "Updated readme").  
License: **LGPL-3.0** (`LICENSE` in the inspected tree).  
Declared environment: Python 3.8; pinned `requirements.txt` includes `numpy==1.18.4`, `tensorflow==2.2.0`, `cvxpy==1.1.7`, `tf-agents==0.5.0`. These pins are **not** installable as a drop-in stack on this project's CPython 3.12.13 runtime without a separate unsupported environment.

README (consulted, not a compatibility proof): lap-wise discretisation; full `racesim` plus free-track `racesim_basic`; Virtual Strategy Engineer with `basestrategy`, `realstrategy`, `supervised`, and `reinforcement` options; 2014–2019 parameter files automatically created from a timing database; pretrained RL VSE artifacts.

Inspected capabilities in `racesim/src/race.py` (source reading, **not** an executed check):

| Topic | Inspected declaration | Executed in this project |
| --- | --- | --- |
| State | Lap-indexed arrays `laptimes`, `racetimes`, `positions`, `progress` | no |
| Event ordering | Per-lap loop; FCY then overtaking | no |
| SC | Ghost-car race time plus `min_t_dist_sc`; overtaking forbidden for the whole SC lap | no |
| VSC | FCY lap-time blend; overtaking forbidden if ≥ half the lap is affected | no |
| Pit/service | Inlap/outlap time loss; no shared two-car crew object found in the inspected class slots | no |
| Checkpoint/resume | Pickle of a completed `Race` object for analysis/CI; not a causal mid-race DecisionObservation checkpoint | no |

Input provenance (software licence ≠ data licence): bundled `racesim/input/parameters/pars_*.ini` are historical-race parameterisations. Supervised/RL VSE paths load pickle preprocessors trained on real-world or in-sim decisions. Dossier §6 and the Stage 3 prompt forbid using those as shortcut dependencies.

## Why the adapter was not selected

1. Lap-wise discretisation does not by itself provide pit-entry cutoffs and service arrivals at sub-lap decision times required for the operational deadline gate.
2. Bundled historical configurations and pretrained policies would have to be disabled and replaced; the remaining engine still expects that parameter shape.
3. Installing the 2020-era TensorFlow/NumPy/cvxpy pins would downgrade or fork the project interpreter. A separate compatible environment was judged impractical relative to the restricted model authorised by the dossier.
4. No executed mechanism check of TUMFTM SC bunching versus VSC was performed. Lack of an executed check is **unassessed runtime behaviour**, not proof that the upstream SC model is invalid.

Rejected alternative: wrapping TUMFTM `racesim_basic` only. The README states that the free-track variant cannot validate traffic interactions (dossier §8 agrees).

Independently implementing a restricted model does **not** establish scientific originality. No TUMFTM source was copied. Third-party notices for the inspected (unused) repository remain in `docs/PROVENANCE.md` and `NOTICE`.

## Known limitations of the selected model

Declared in `docs/SIMULATOR_MODEL.md`. Not F1-calibrated. Not a TUMFTM-equivalent traffic model. Not a hardware or QPU path.
