# Generator specification (Stage 2)

Version `2.0.0`. Configuration file: `configs/generator.v1.yaml`. This is a **declared development generator**, not a calibrated Formula 1 model and not a frozen scientific protocol.

Labels: **implemented** (code), **verified** only where a named check is cited. Scenario specifications **await Stage 3 simulator validation**. They are not race trajectories.

## Hierarchy

family → independent parameter block → eight episode specifications → checkpoint request.

Each block shares its sampled block parameters. Four episodes request an SC checkpoint and four request VSC. This is a balanced conditional design, not an estimator of natural safety-car incidence. Distinct IDs do not establish statistical independence; the **block** is the inferential unit.

## Eight families

Cartesian product of:

| Factor | Levels |
| --- | --- |
| Green pit loss | low Uniform(18.0, 21.5) s; high Uniform(24.5, 28.0) s |
| Tyre degradation | near-linear; nonlinear |
| Traffic | sparse mean gap Uniform(1.2, 3.5) s; dense Uniform(0.15, 0.90) s |

Identifiers: `fam.green_pit_{low|high}.tyre_{near_linear|nonlinear}.traffic_{sparse|dense}`.

## Pit loss

`green_pit_loss_s` is the total time loss versus a green flying lap **including pit-lane transit and stationary service**. Stage 3 must not add a second service term unless it first decomposes the quantity. Decomposition is a pending Stage 3 interface.

## Domain (dossier §5–7 assumptions)

- 20 fictional cars, 10 two-car teams, dry weather only.
- Remaining laps at the requested checkpoint: 12–45.
- Green lap 75–110 s; green pit loss 18–28 s.
- Exclusions: wet transitions, red flags, sprint-specific rules, tyre damage, detailed energy deployment. Unsupported cases receive an explicit rejection code.
- Double stacking is a delay cost, not a prohibition. Compound obligations are model configuration, not invented FIA rules.

## Provisional quantities (not F1 calibration)

Documented in `configs/generator.v1.yaml` `provisional_quantities` and `pending_stage3_interfaces`. Includes compounds/sets, 1.8 kg/lap fuel scale with 2 kg uncertainty, 1.0 s communication margin (dossier §15 research setting), checkpoint offset 1–3 green laps, fictional track archetypes. Tyre wear coefficients are scales only; the lap-time map is Stage 3.

## Split registry (planned counts only)

| Partition | Blocks | Checkpoints planned | Per family |
| --- | ---: | ---: | ---: |
| Training | 120 | 960 | 15 |
| Tuning | 16 | 128 | 2 |
| Calibration | 24 | 192 | 3 |
| Primary test floor | 80 | 640 | 10 |
| Primary test maximum | 160 | 1280 | 20 |
| Shift panel (draft) | 40 | 320 | 5 draft |

Floor main total 240 blocks / 1,920 checkpoints; with shift 280 / 2,240. At test maximum including shift: 360 / 2,880. **Materialization of these partitions is gated and unavailable in Stage 2.**

Shift allocation is a **draft** schema of predeclared shifts, not a finalized distribution-shift study. Freeze before use.

## Development preview

Namespace `development`, in none of the scientific partitions. Eight blocks (one per family), eight episode specifications each: 64 specifications, 32 SC and 32 VSC requests. Engineering development data. `awaiting_simulator_validation: true`. Validated race checkpoints: 0.

## Identities and streams

Scheme `f1q.id.v2` / `f1q.stream.v1`. HMAC-SHA256 domain separation over canonical JSON. **Not** Python `hash()`, not a process-global RNG, not row order. Not cryptographic protection against a holder of the repository.

Domains: `block_params`, `episode`, `fitting`, `online_scoring`, `evaluation`. Evaluation keys include driver, lap, event type, and replication so changed action paths do not desynchronize unrelated draws. Changing a fitting seed does not change generated episode assumptions or evaluator-bank keys.

## Causal types

1. `ScenarioSpec` — initialization and checkpoint request.
2. `SimulatorState` — complete physical/RNG state; never solver-visible. Retained under `evidence/development/private/` (gitignored).
3. `DecisionObservation` — allowlist projection at the decision time. Unknown values require a reason. Forecasts need issuance time. Realized future regime duration is excluded.
4. `CheckpointEnvelope` — identity, `validation_status`, observation/state references, solver vs evaluator access.

A request to condition on SC/VSC may be in the generator. The observation includes that regime only when causally revealed. Stage 2 preview envelopes are `awaiting_simulator`.

## Stage 3 handoff

Initialize state from the spec; advance to the prescribed `completed_laps`; reveal the requested regime; project the observation; preserve resume state; validate. Unimplemented simulator execution raises `SimulatorNotImplementedError` and does not return placeholder results. Structural validity is not physical reachability.

## Clocks and deadlines

Race clock origin `race_start`, unit seconds. Monotonic client clocks are separate. Nominal budgets 5/10/30/60/120 s (30 s primary) are research settings, distinct from effective cutoffs. Effective deadline is the earlier of the nominal budget and the earliest two-car pit-entry cutoff minus the communication margin. Expired `pit_now` is recorded as `PIT_WINDOW_CLOSED` and is not relabeled as next lap.

## CLI

```text
python -m f1q generator validate
python -m f1q generator plan-splits [--test-blocks 80|88|...|160]
python -m f1q generator audit --run-id <id>
python -m f1q run --plan development_preview
python -m f1q resume --run-id <id>
python -m f1q receipt --run-id <id>
```

`run` executes one authorized plan once. It does not expand into the reserved corpus.

## Retry

Max three attempts per episode. Rejected cases are retained with distinct attempt IDs. They are not replaced invisibly. The authorized development preview produced zero schema rejections.
