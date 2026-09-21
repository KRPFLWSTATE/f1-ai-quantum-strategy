# Stage 6 Protocol Freeze Record

**PROTOCOL_STATUS:** `BLOCKED_DRAFT`  
**Frozen before calibration outcomes:** `true`  
**Source commit:** `1c7631e609a12562155ba978cb50790f3ed2b6f7`  
**Dirty patch hash:** `645d4e08e4f9a666f53d32c7fb6c507e1fdc3323c1344723a9763297967dbe5d`  
**Freeze SHA-256:** `27191ba16d91802d54f54ab45b42ff3c7948de2d59089a02d5d070a3d4f09c3c`  
**Pilot config SHA-256:** `3af34f3d84ebc7fddbe91d69971c0fb318c1e4318dbb01c425b8de118f9a63be`

## Admitted scientific scope

`local_A2_circuit_mechanism_and_resource_estimation;restricted_synthetic_revealed_duration_surrogate;no_operational_race_decision;no_H1_superiority;no_QPU`

## Frozen elements

See machine-readable `evidence/stage6/bd83cb22-6a38-4d21-9267-3253f52587d7/protocol_freeze.json` for full artifact hashes.

### Models and donors
- Corrected Phase 5 ridge selector artifacts (all four family-depths)
- Donor bank selected ≤8 donors/family-depth
- Fixed donors = tuning-selected (`argmin_mean_training_normalised_regret`) from corrected run only

### Circuits
- C0, C1; p=1, p=2
- C1 executable prep = repaired final-acceptance definition
- C2: NOT_ADMITTED_BY_PROTOCOL

### Policies
- learned, fixed, nn, seeded random-donor

### Classical comparators and budgets
- Exact legal enumeration (strongest when inside deadline)
- Uniform legal sampling (1024 draws)
- Greedy safe fallback; MILP when timely
- Pool: 1024 shots × 10 seeds

### Objective / legality / ties
- Normalised regret (f−f*)/(f_max−f*)
- One-hot vs complete semantic legality separated
- Improvement tolerance 1e-08; ties are not improvements

### Noisy panel (predeclared)
- Depth: p1
- Noise: depolarizing_1q_1e-3_2q_1e-2
- Max qubits: 10
- Synthetic ≠ IBM

### Endpoints / exclusions / analysis rules
- Mechanism endpoints only for confirmatory use of this pilot
- Operational race-outcome: not eligible
- Final-test / QPU / C2 / retraining excluded
- Blocks = independent units; paired SC/VSC; equal family weight
- Do not expand n after viewing effects
- Calibration ≠ independent final-test evidence

## Unresolved fields (block full FROZEN)

- Causal event-timed observation features for A2 policies
- Runtime allocator integration
- Independent operational evaluator random banks + CRN
- Hardware backend / queue / routing (Phase 8)
- Nonzero headroom domain for H1
- Dated Phase 7 reduced-matrix amendment ID (to be issued before final-test)

## Hardware-specific fields

Deferred to Phase 8. `QPU_EXECUTION_AUTHORISED: false`.
