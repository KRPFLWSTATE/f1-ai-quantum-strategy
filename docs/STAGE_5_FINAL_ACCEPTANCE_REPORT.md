# Stage 5 / Phase 5 — Final Acceptance Report (Targeted Repair)

**PHASE_5_ACCEPTANCE:** `PASS_WITH_DOCUMENTED_LIMITATIONS`  
**C1_PREPARATION_EQUIVALENCE:** `PASS`  
**C1_FULL_CIRCUIT_EQUIVALENCE:** `PASS`  
**NEGATIVE_CONTROLS:** `PASS` (7/7 deliberately wrong relative-phase preps rejected)  
**TRAINING_SIMULATOR_UNCHANGED:** `true`  
**MODELS_AND_DONORS_REUSED:** `true` (corrected run `e6b3588b-ab97-48c9-82f4-616785aa3611`)  
**TRAINING_RERUNS:** `0`  
**CAUSAL_MODEL_SCOPE:** `restricted_synthetic_revealed_at_epoch_1`  
**QPU_JOBS:** `0`  
**QPU_EXECUTION_AUTHORISED:** `false`  
**PHASE_6_MECHANISM_PILOT_READY:** `true` (local mechanism / resource estimation only — after review)  
**PHASE_6_OPERATIONAL_PILOT_READY:** `false` (requires causal simulator integration)

This report does **not** overwrite `docs/STAGE_5_REPORT.md` or `docs/STAGE_5_CORRECTED_REPORT.md`.  
Historical runs `6ad68021-f19c-44e7-b166-13ab44dad31b` and `e6b3588b-ab97-48c9-82f4-616785aa3611` are preserved unchanged.

Evidence class: local ideal-circuit verification + documentation honesty repair. Not physically measured. Not a held-out scientific superiority claim. Not actual F1 operational value.

---

## 1. Starting gate and provenance

| Item | Value |
|------|-------|
| Starting / source commit (gate) | `7563c169b2e69123657ff3f6e0b4c9aa970e8363` |
| Corrected Phase 5 run (reused) | `e6b3588b-ab97-48c9-82f4-616785aa3611` |
| Original Phase 5 run (preserved) | `6ad68021-f19c-44e7-b166-13ab44dad31b` |
| Supplemental evidence | `evidence/stage5/final_acceptance_repair/` |
| Docs mirror | `docs/evidence/stage5_final_acceptance/` |
| Packages | PyYAML 6.0.3; numpy 2.5.3; pydantic 2.13.5; qiskit 1.4.6; scipy 1.18.1 |

Reproduction (bounded; no campaign):

```text
.venv/bin/python scripts/stage5_final_acceptance_evidence.py
.venv/bin/python -m pytest tests/stage5/test_phase5_core.py -q
.venv/bin/python -m pytest -q
```

---

## 2. Reproduced C1 defect

**Confirmed:** executable `build_c1_qiskit_circuit()` preparation used an RY+CZ+X+CX+X cascade that does **not** match NumPy `prepare_one_hot_uniform()`.

For block size 2 the defective prep produces:

\[
\frac{|01\rangle - |10\rangle}{\sqrt{2}}
\]

whereas NumPy training initialisation uses all-positive amplitudes:

\[
\frac{|01\rangle + |10\rangle}{\sqrt{2}}
\]

These differ by a **relative** phase, not an irrelevant global phase (state fidelity vs target ≈ 0 for k=2). For k≥3 the defective circuit also produced **incorrect one-hot probabilities** (fidelity ≪ 1).

**Independent-path defect:** `qiskit_statevector_crosscheck_c1()` previously hand-initialised `Statevector(prepare_one_hot_uniform(...))` and called NumPy `apply_c1_mixer`, so it never evolved the executable prep and could not catch the bug.

Evidence: `evidence/stage5/final_acceptance_repair/c1_defect_reproduction.json`.

---

## 3. Repaired preparation and circuit definition

### Preparation (per action block of size k)

`append_one_hot_uniform_prep(qc, idxs)`:

1. `X` on the highest-index qubit in the block.
2. For `i = k-1 … 1`: `CRY(2·arccos(√(1/(i+1))), control=idxs[i], target=idxs[i-1])` then `CX(idxs[i-1], idxs[i])`.

Product over all blocks yields the same state as `prepare_one_hot_uniform` under **fixed little-endian** indexing (amplitude index bit `i` = qubit `i`), up to one global phase. Relative phases among one-hot basis states are all `+1`.

### Cost and mixer (unchanged scientifically)

- Cost: `PhaseGate(-γ Q_ii)` and `CPhaseGate(-γ Q_ij)` from the actual QUBO.
- Mixer: for each scheduled within-block ring edge, `RXX(β)` then `RYY(β)` ≡ `exp(-i β/2 (XX+YY))`, matching NumPy `_xy_exchange`.

### Cross-check method (repaired)

```text
Statevector.from_instruction(build_c1_qiskit_circuit(...)["circuit"])
```

- No hand-initialised NumPy state on the independent path.
- No `apply_c1_mixer` on the independent path.
- Single declared bit order; no min-over-orderings.

Evidence: `c1_repaired_circuit_definition.json`.

---

## 4. Cross-check results

Tolerances: amplitude `1e-8` (after one global phase); probability `1e-8`; scaled objective expectation `1e-8`.  
Denominator: **9** fixtures (prep-only + p=1 + p=2; block sizes 2, 3, 4; asymmetric nonzero angles).  
Result: **9 / 9 PASS**.

| Label | n | p | block | max\|amp\| diff | ‖⟨·|·⟩‖ | max\|p\| diff | ‖E‖ diff |
|-------|--:|--:|------:|----------------:|--------:|-------------:|---------:|
| prep_size2_n8 | 8 | 0 | 2 | 8.327e-17 | 1.0000000000 | 4.163e-17 | 0 |
| p1_size2_asym | 8 | 1 | 2 | 3.366e-16 | 1.0000000000 | 1.665e-16 | 3.608e-16 |
| p2_size2_asym | 8 | 2 | 2 | 5.215e-16 | 1.0000000000 | 2.914e-16 | 6.384e-16 |
| p1_size2_seed11 | 8 | 1 | 2 | 2.355e-16 | 1.0000000000 | 8.327e-17 | 1.110e-16 |
| prep_size3_n6 | 6 | 0 | 3 | 5.551e-17 | 1.0000000000 | 2.776e-17 | 1.388e-17 |
| p1_size3 | 6 | 1 | 3 | 1.665e-16 | 1.0000000000 | 8.327e-17 | 1.388e-17 |
| p2_size3 | 6 | 2 | 3 | 2.989e-16 | 1.0000000000 | 1.388e-16 | 2.776e-17 |
| p1_size4 | 8 | 1 | 4 | 4.484e-16 | 1.0000000000 | 2.012e-16 | 2.359e-16 |
| p2_size2_n4 | 4 | 2 | 2 | 5.613e-16 | 1.0000000000 | 4.441e-16 | 1.110e-16 |

One-hot preservation: `amp_outside_one_hot_qiskit = 0` on all PASS rows.

Full numeric rows: `c1_crosscheck_results.json`.

### Negative controls

Deliberately wrong relative-phase prep (`Z` on first qubit of each block after correct W prep): **7 / 7 correctly rejected** (amplitude alignment fails / fidelity drops; `expect_reject=true`).

---

## 5. Actual circuit resource tables

Recomputed from **repaired** actual circuits (includes preparation and cost interactions).  
Target basis `rz/sx/x/cx`; **no coupling map**; `routing_used=false`; `swap_routing_overhead_cx=0`.  
Excess CX vs logical 2q count is labelled **`native_basis_decomposition_cx_excess`** (not routing).

12 rows in `actual_circuit_resources.json` (all `actual_circuit=true`, `routing_used=false`, `swap_routing_overhead_cx=0`):

| family | p | n | blocks | depth | n_2q_cx | prep | cost2q | mixer | decomp_excess | routing |
|--------|--:|--:|--------|------:|-------:|-----:|------:|------:|-------------:|--------:|
| C0 | 1 | 8 | [2] | 19 | 12 | 0 | 6 | 8 | 6 | 0 |
| C0 | 1 | 6 | [3] | 39 | 20 | 0 | 10 | 6 | 10 | 0 |
| C0 | 1 | 8 | [4] | 55 | 42 | 0 | 21 | 8 | 21 | 0 |
| C0 | 2 | 8 | [2] | 31 | 24 | 0 | 12 | 16 | 12 | 0 |
| C0 | 2 | 6 | [3] | 63 | 40 | 0 | 20 | 12 | 20 | 0 |
| C0 | 2 | 8 | [4] | 87 | 84 | 0 | 42 | 16 | 42 | 0 |
| C1 | 1 | 8 | [2] | 48 | 56 | 12 | 6 | 16 | 26 | 0 |
| C1 | 1 | 6 | [3] | 85 | 56 | 10 | 10 | 12 | 26 | 0 |
| C1 | 1 | 8 | [4] | 114 | 92 | 14 | 21 | 16 | 43 | 0 |
| C1 | 2 | 8 | [2] | 80 | 100 | 12 | 12 | 32 | 48 | 0 |
| C1 | 2 | 6 | [3] | 139 | 100 | 10 | 20 | 24 | 48 | 0 |
| C1 | 2 | 8 | [4] | 186 | 166 | 14 | 42 | 32 | 80 | 0 |

Historical corrected-run `circuit_resources.json` retained for provenance but is **superseded for acceptance** by these repaired rows (old prep gate counts / mislabelled routing proxy).

---

## 6. What previous results remain reusable (and why)

| Artifact class | Reused? | Why |
|----------------|:-------:|-----|
| NumPy `prepare_one_hot_uniform` / `apply_c1_mixer` / `simulate_c1` | yes | Function bodies byte-identical vs starting commit (SHA-256 of AST source segments unchanged) |
| Parameter bank fits / donors | yes | Training used NumPy simulator only |
| Learned selector models / tuning | yes | Same NumPy expectations / features |
| Formulation / headroom / splits | yes | Unaffected by Qiskit prep |
| Historical C1 **Qiskit** cross-check rows | no | Method was non-independent; superseded |
| Historical C1 resource rows | superseded | Prep + labelling repaired |

Provenance file: `reused_corrected_run_provenance.json`.  
Training unchanged file: `training_simulator_unchanged.json`.

**No retraining. No parameter-bank rerun. No selector retrain.**

---

## 7. Causal-model assumptions and limitations (honesty)

The existing A2 training generator **ASSUMES** SC/VSC duration is **fully revealed at the second decision epoch** (epoch 1 observables are `dur:<laps>`; epoch 0 is shared `root` only).

This is a **restricted synthetic revealed-duration / commitment-epoch surrogate**.

It does **not**:

- demonstrate event-timed, on-track causal validity;
- substitute for Stage-3 pit-entry deadline validation under the live simulator;
- prove causal correctness at subsequent decisions merely because epoch 0 is `root`;
- demonstrate actual F1 operational value.

`decisions_cannot_see_hidden_duration` / microcase `causal_ok` flags validate **only** this surrogate.  
Instance meta now records `causal_duration_model`, `causal_event_timed_on_track_validated=false`, `causal_pit_entry_deadline_validated=false`.

**Generator code paths that place duration into epoch-1 observables were not silently changed** (would invalidate preserved training evidence).

Evidence: `causal_model_scope.json`.

**Operational Phase 6 race-decision pilot prerequisite:** explicit causal simulator integration.

---

## 8. Variational-reference / fit-history coverage (from saved artifacts)

From corrected run `bank_fit_records.json` (reused, not regenerated):

- `n_fits = 288`
- Every retained fit has `best_params` (fresh variational parameter vectors) and `history_compact` (length 10) with `n_history` (typically 80 evals)
- **Gap disclosed:** full raw per-evaluation optimizer traces are **not** stored — only compact histories + `n_history` / `evals`
- `selector_model_weights.json` as a standalone file is **absent**; weights are inside `selector_model_artifacts.json` (present)

---

## 9. Remaining evidence gaps

1. Compact (not full) variational fit histories — disclosed above.
2. Causal model remains a synthetic commitment-epoch surrogate — not live simulator causal proof.
3. No QPU / no hardware; development headroom remains ZERO on checked instances (unchanged scientific finding).
4. Historical corrected-run circuit resource JSON not rewritten (frozen); acceptance uses supplemental repaired resources.

None of these gaps reopen the C1 executable-circuit defect after this repair.

---

## 10. Phase 5 acceptance status

**PASS_WITH_DOCUMENTED_LIMITATIONS**

- C1 executable prep ≡ NumPy training init (relative phases): **PASS**
- Full actual-circuit Statevector equivalence (p=1, p=2): **PASS**
- Negative controls: **PASS**
- Resources from repaired actual circuits with honest decomposition labelling: **PASS**
- Training / donors / selectors reusable without campaign: **PASS**
- Causal scope: **documented restriction** (not silently claimed as on-track causal proof)

---

## 11. Phase 6 readiness (split)

| Track | Ready? | Notes |
|-------|:------:|-------|
| Mechanism / resource estimation pilot (local) | **yes** (after independent review; still no QPU) | C1 circuits now independently cross-checked |
| Operational race-decision pilot | **no** | Requires causal simulator integration; surrogate ≠ F1 value |

Do **not** begin Phase 6 in this repair.

---

## 11b. Test execution (this repair)

| Suite | Status | Elapsed |
|-------|--------|--------:|
| `tests/stage5/test_phase5_core.py` | PASS 20/20 | 49.3 s |
| Full suite excluding `tests/formulation` | PASS | 83.0 s |
| `tests/formulation/test_gate_c.py` | PASS | 211.0 s |
| `tests/formulation/test_stage4_1_repair.py` | PASS | 228.1 s |
| `tests/formulation/test_stage4_2_repair.py` | PASS | 5.3 s |
| `tests/formulation/test_stage4_closure.py` | PASS | 7.8 s |
| Monolithic `pytest -q` | TIMEOUT at 290 s (budget) | — |

**FULL_TESTS:** `PASS_VIA_SPLIT` — every collected test file passed under ≤300 s per command; the single monolithic invocation exceeds the hard 300 s command limit (disclosed, not hidden).

## 12. Evidence index

| File | Role |
|------|------|
| `evidence/stage5/final_acceptance_repair/c1_defect_reproduction.json` | Defect reproduction |
| `evidence/stage5/final_acceptance_repair/c1_repaired_circuit_definition.json` | Repaired definitions |
| `evidence/stage5/final_acceptance_repair/c1_crosscheck_results.json` | Cross-checks + negatives |
| `evidence/stage5/final_acceptance_repair/actual_circuit_resources.json` | Resource tables |
| `evidence/stage5/final_acceptance_repair/training_simulator_unchanged.json` | NumPy path hashes |
| `evidence/stage5/final_acceptance_repair/reused_corrected_run_provenance.json` | Donor/model reuse |
| `evidence/stage5/final_acceptance_repair/causal_model_scope.json` | Causal honesty |
| `evidence/stage5/final_acceptance_repair/run_receipt.json` | Receipt |
| `docs/STAGE_5_FINAL_ACCEPTANCE_REPORT.md` | This report |
| `docs/evidence/stage5_final_acceptance/STAGE_5_FINAL_ACCEPTANCE_MANIFEST.json` | Acyclic manifest |
| `docs/evidence/stage5_final_acceptance/STAGE_5_FINAL_ACCEPTANCE_FINAL_VERIFY.json` | Final verifier |

Acyclic rule: raw evidence + report → manifest → final verifier. No self-file hash inside the hashed payload of the verifier’s own file before write. Every committed digest independently reopened and checked.

---

## 13. Code touch summary (surgical)

- `src/f1q/stage5/circuits_c1.py` — repaired W-prep; negative-control helper
- `src/f1q/stage5/ideal_sim.py` — genuine C1 Statevector cross-check; resource labelling
- `src/f1q/stage5/model.py` — causal-scope documentation + meta flags (no generator timing change)
- `tests/stage5/test_phase5_core.py` — focused acceptance tests
- `scripts/stage5_final_acceptance_evidence.py` — bounded evidence packager

Phase 4 sources/evidence: untouched. Historical Phase 5 evidence directories: untouched.
