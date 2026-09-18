# Requirements traceability (draft)

Scientific components listed here remain **unfrozen**. Status values: proposed (dossier), pending (not built), implemented (code exists), verified (named check).

| ID | Constraint | Dossier | Future acceptance check | Status |
| --- | --- | --- | --- | --- |
| T1 | Generated fictional scenarios are the core; 20-car field is a model assumption; historical timing is optional and separately justified; FastF1 MIT is not a data licence | §§5-6, [18][19] | Generator publishes distributions; any historical track records lawful basis | implemented development preview; not calibrated; historical track unselected |
| T2 | Model two-car SC/VSC, tyre/fuel, shared service, rejoin traffic, continuation; double stacking is a delay cost, not a universal prohibition | §5 | Mechanism tests in Stage 3 | verified by named checks on the restricted model; not F1-calibrated |
| T3 | Enumerate legal action combinations; one-hot bits ? legal plans; if incumbent already minimizes the proxy, quantum search cannot improve that objective | §§9-10, 14 | Legal-plan enumeration vs bit-string counts; headroom gate | pending |
| T4 | Scientific-value gate before the full test campaign; impossible superiority comparisons are not rescued by more repetitions | §§10, 18, 26 Gate E | Record headroom before opening test | pending |
| T5 | Fitting, tuning, calibration, test, shift are separate. Base 120/16/24/80 blocks, eight checkpoints, plus 40 shift. Test may rise to 160 under pre-exposure sizing. Setup fixtures belong to none of these splits | §§7, 18 | Split integrity audits | planned counts verified; reserved partitions not materialized; development namespace separate |
| T6 | Runtime AI is an evaluated learned component with fixed, nearest-neighbour and random-donor comparisons. Deterministic orchestration is not learned AI | §§11, 16, 23 | H2 comparisons on held-out data | pending |
| T7 | C0 and C1 are core families; C2 is a conditional local substudy. Include preparation, routing, ancillas; compare full packages. Do not claim QAOA/XY/guarded exchanges as inventions | §§12-13 | Circuit resource records; prior-art attribution | pending |
| T8 | Preserve corrected QUBO feasibility assumptions, sufficient penalty bound, objective centering and normalization. Check direct action costs vs encoded energies. Do not assume arbitrary weighted cost angles have period 2? | §§9, 11 | Independent energy checks on small cases | pending |
| T9 | Effective deadlines include pit-entry expiry, communication margin, causal state advance and commitment-time legality. Local inference/compilation/queue/communication times cannot be omitted from end-to-end claims. Use monotonic clocks for local durations | §§15, 17 | Deadline and latency records | numeric effective deadlines implemented for the restricted model; scenario latency is not an IBM measurement |
| T10 | H1 is conditionally confirmatory; H2/H3 and hardware are exploratory/descriptive. Paired blocks; independent evaluation banks. Do not count shots/seeds/checkpoints as independent races. Avoid naive nested Monte Carlo on the primary block bootstrap | §§4, 18-19 | Analysis code matches protocol | pending |
| T11 | Reported QPU balance 540 s, unverified. Protected reserve 120 s. Campaign ceiling `min(420, max(0, verified_available_seconds - 120))`. Formula is a future cap, not execution permission | §20 | Verify free access before hardware | recorded as unresolved nulls; not queried |
| T12 | Primary hardware schedule 50 jobs / 88 pools / 88,064 shots / 402 s; alternative 38 / 64 / 32,768 / 414 s. Mutually exclusive, not cumulative. Defer dispatch | §§20-21 | Pilot-selected frozen schedule | pending |
| T13 | Future jobs need intent recovery, reservations, usage reconciliation, durable raw evidence. Unknown usage stays reserved; no blind resubmit. Measured zero ? unqueried account | §21 | Hardware preflight | pending; no submission path exists |
| T14 | No absolute novelty, guaranteed quantum advantage, team adoption, F1 performance gain, or publication acceptance. Claims follow evidence. Record AI assistance honestly | §§3, 27 | Claims ledger | documented in `docs/CLAIMS.md` as unsupported |

## Identifier classes (interface only)

Separate identifiers are reserved for: scenario, decision checkpoint, policy repetition, circuit/sample pool, provider job, work unit, attempt. A run is an execution container. Stage 1 implements work unit, attempt, run, artifact and receipt identifiers. Provider job IDs are null with reason.
