# Simulator model (restricted independent)

Version `1.0.0`. Interface version `3.0.0`, frozen separately from the scientific protocol. Configuration: `configs/simulator.v1.yaml`. Coefficients are **declared assumptions**, not F1 calibration and not a frozen protocol.

This document is the specification the production engine and the independent oracles must implement. Successful software checks do not establish SC/VSC physical validity, tyre science, or operational F1 performance.

## 1. Units, clock, domain

| Quantity | Unit | Origin |
| --- | --- | --- |
| Race clock \(t\) | s | `race_start` (never a wall/monotonic client clock) |
| Progress \(s_i\) | laps (real) | race start; \(s_i = \ell_i + f_i\) with completed laps \(\ell_i = \lfloor s_i \rfloor\) when on the racing line |
| Mass | kg | — |
| Pace | s/lap | instantaneous free lap time \(T_i\) |

Monotonic client clocks record local CPU/wall durations only. They are never compared to \(t\).

Supported domain: dry weather, 20 fictional cars, 10 two-car teams, no wet/red-flag/sprint/tyre-damage/energy-deployment/pit-lane-closure/refueling/retirement. Unsupported cases are rejected with a code. Initialization is a **fictional pre-checkpoint state**; it is not a reconstructed race start.

Simultaneous events at the same \(t\): apply the configured priority (regime end, box arrival, service complete, pit exit, lap complete, catch/pass, pit entry), then break remaining ties by `car_id` lexicographic order. Elapsed time never decreases. A car does not complete the same integer lap twice.

## 2. Track geometry

Unit-circle single racing line. Pit entry fraction \(e = 0.95\), box at start/finish \(b = 0.0\), pit exit \(x = 0.02\). Pit-lane racing-line equivalent \(\phi = (1-e)+x = 0.07\).

On-track equivalent time of that path at green pace \(T_g\):

\[
T_{\mathrm{sector}} = \phi\, T_g.
\]

## 3. Initialization

Let \(T_g\) be the block `green_lap_s`. Place classified position 1 using that car's sampled pit-entry remaining time: fraction \(f_1 = (e - t_{\mathrm{cut},1}/T_g) \bmod 1\). Subsequent cars are packed by `gap_ahead_s` converted at \(T_g\):

\[
s_{k} = s_{k-1} - \frac{g_k}{T_g} - d_k
\]

where \(d_k\) is `lap_deficit`. Operational cutoff for car \(i\) is the race time of the next pit-entry station at the current free pace. Sampled Stage 2 cutoffs are retained as documentation only (amendment `checkpoint.cutoff.v1`).

Race clock at init is the specification's assumed `init_race_time_s` (completed laps \(\times T_g\)). Stage 3 then **advances** to the requested checkpoint; that assumed value is not relabelled as a physics reconstruction of the whole race.

## 4. Tyres and fuel

Compound offsets \(\delta_c \in \{0.0, 0.8, 1.6\}\) s for soft/medium/hard.

Age penalty, Stage 2 `tyre_wear_per_lap` \(w\), optional curvature \(\kappa\):

\[
\Delta T_{\mathrm{tyre}} =
\begin{cases}
w \cdot 6.0 \cdot a & \text{near-linear}\\
w \cdot 6.0 \cdot a + \kappa \cdot 2.0 \cdot a^2 & \text{nonlinear}
\end{cases}
\]

with tyre age \(a\) in laps (progress-dependent: \(da = ds\) on track, \(da = 0\) in the pit except at a set change which resets age to 0 on the new set).

Fuel: estimated mass \(\hat{m}\) is `fuel_kg`. Private actual \(m\) follows amendment `development_spec.fuel.v1`. Consumption \(\dot m = 1.8\) kg per lap of **on-track** progress. No refueling. Negative inventory is a rejection, not a clamp. Observation reports \(\hat{m}\) and the 2 kg uncertainty, never \(m\).

Fuel time:

\[
\Delta T_{\mathrm{fuel}} = 0.03\, m.
\]

Free lap time (green):

\[
T_i^{\mathrm{free}} = T_g + \delta_{c_i} + \Delta T_{\mathrm{tyre}} + \Delta T_{\mathrm{fuel}}.
\]

On a green unconstrained flying segment of length \(D\) laps, write \(T(s)=A+Bs+Cs^2\) from that map at the segment start. The independent free-track oracle and the production green-free integrator use

\[
t(D)=AD+\tfrac12 B D^2+\tfrac13 C D^3
\]

and invert \(D(t)\) by Newton. Under SC/VSC caps or traffic-limited speed, motion uses the capped speed over the current step.

Impossible `fuel_kg < 0` or an empty mounted set is rejected. Tyre-set identity, used-compound history, and inventory are maintained. Legal no-damage baseline: compounds `{soft, medium, hard}` only; tyre damage is excluded.

## 5. Pit loss decomposition

Stage 2 `green_pit_loss_s` \(P\) **includes** transit and stationary service versus a green flying lap. Let \(T_{\mathrm{svc}} = 2.5\) s (declared). Transit

\[
T_{\mathrm{transit}} = P + T_{\mathrm{sector}} - T_{\mathrm{svc}}, \quad
T_{\mathrm{in}} = T_{\mathrm{transit}}\frac{1-e}{\phi}, \quad
T_{\mathrm{out}} = T_{\mathrm{transit}}\frac{x}{\phi}.
\]

Identity (must hold exactly):

\[
T_{\mathrm{in}} + T_{\mathrm{svc}} + T_{\mathrm{out}} - T_{\mathrm{sector}} = P.
\]

A neutralization changes \(T_{\mathrm{sector}}\) comparison because the on-track path is slower. The model **does not** subtract an extra SC bonus from \(T_{\mathrm{svc}}\). Queue wait \(W\) is additional and is not part of \(P\).

Shared crew (one per `team_id`): for arrivals \(A_1, A_2\) and services \(S_1, S_2\),

\[
U_1 = \max(A_1, C_0),\quad F_1 = U_1 + S_1,\quad
U_2 = \max(A_2, F_1),\quad F_2 = U_2 + S_2
\]

with \(C_0\) the crew-free time (initially \(-\infty\) / available). Ties at equal \(A\) use `car_id`. Double stacking is this wait, not a prohibition, unless a fixture sets `stacking_policy: forbidden` (then the second arrival is rejected).

Rejoin: the car is inserted at exit fraction on the subsequent lap. It must respect the following gap; it does not teleport through occupancy.

## 6. Traffic and overtaking

Minimum following gap \(g_{\min} = 0.12\) s (distance \(g_{\min}/T_i\) laps). If a faster car is blocked and its free-pace advantage is \(< 0.40\) s/lap, its speed is capped to hold \(g_{\min}\). A pass is permitted only in `GREEN` when the advantage is at least \(0.40\) s/lap and the gap is within \(0.18\) s; after the pass a \(0.05\) s clearance is applied. No pass from a serialization or tie-break alone. SC/VSC: overtaking is not permitted.

Overtaking is resolved at integrator tick resolution (green \(dt_{\max}=1.0\) s, regime \(dt_{\max}=0.25\) s), not as a continuous intercept event. That is an intended restriction of the 1D model, not a claim of F1 overtaking fidelity. Supported overtaking: single-file 1D, one racing line, green only. Not supported: DRS zones, multi-corner geometry, wet, opposite-direction.

## 7. SC, VSC, restart

SC pace \(T_{\mathrm{SC}} = 1.45\, T_g\). VSC cap \(T_{\mathrm{VSC}} = 1.40\, T_g\).

**SC bunching (finite, causal):** consecutive cars have target time gap \(G = 1.0\) s at SC pace. The leader runs at \(T_{\mathrm{SC}}\). A follower with gap \(> G\) may run as fast as \(T_{\mathrm{catch}} = 0.85\, T_{\mathrm{SC}}\) (still no overtake) until the gap reaches \(G\), then matches the car ahead. Gaps are **not** collapsed instantaneously and are **not** implemented as a lone common lap-time multiplier.

**VSC:** every car is capped at \(T_{\mathrm{VSC}}\). There is **no** catch-up-to-\(G\) rule. Gaps may drift if free dynamics differ; the distinction is the missing bunching mechanism.

Duration: private draw \(\tau \sim \mathrm{Uniform}(1.8, 3.2)\) laps converted with the regime pace factor, keyed by the evaluation stream. Observation at the checkpoint knows the regime type once revealed and does **not** know \(\tau\). Changing \(\tau\) before revelation must leave `DecisionObservation` unchanged. After the private end time, pace returns to green **immediately** with positions/gaps preserved (no extra compression). Pit-lane closures are excluded.

## 8. Policies

Development baseline (team and rivals): observable-state only. If compound-obligation (two distinct compounds in used history) is unmet, pit at the first legal opportunity after the checkpoint for an unused set of a missing compound; otherwise stay out. Feasible to race end under supported obligations. A **non-reactive** policy ignores rivals. A later response interface may read only `DecisionObservation`. No learned model, no exhaustive search, not the Stage 4 classical comparator.

Hand-specified team plans: `pit_now`, `delay_laps` \(\in \{1,2\}\), or `continuation`, with compound/set when pitting. `delay_laps` is measured from completed laps at apply time. After the car enters the pit the plan is consumed and is not repeated. A stale `pit_now` is never relabelled as next lap.

## 9. Checkpoint, action, deadline

Advance from init until the leader's completed laps equal the request, then reveal the requested regime. `observe` projects `DecisionObservation` only.

Effective window, all in race seconds with origin `race_start`:

\[
t_{\mathrm{nom}} = t_{\mathrm{dec}} + B,\quad
t_{\mathrm{cut}} = \min_i t_{\mathrm{entry},i}^{\mathrm{team}} - m,\quad
t_{\mathrm{eff}} = \min(t_{\mathrm{nom}}, t_{\mathrm{cut}}),\quad
w = t_{\mathrm{eff}} - t_{\mathrm{dec}}.
\]

\(B\) is the nominal budget duration (primary \(30\) s). \(m = 1.0\) s communication margin (dossier §15 research setting). Never compare an absolute time to a duration without conversion. If \(w \le 0\) the window is **closed**. Arrival is timely iff \(t_{\mathrm{arr}} < t_{\mathrm{eff}}\) (boundary excluded). During a proposed delay the race advances under the current fallback. Commitment uses a common epoch; an early recommendation does not obtain an unregistered earlier-commitment advantage. Scenario delay is injected 1:1 onto the race clock for these experiments; recorded CPU/wall times are local only, not IBM queue measurements.

## 10. Classification

Race ends when the leader's progress reaches `race_horizon_laps`. Remaining cars are classified by progress at that \(t\), then finish time, then `car_id`. Lapped cars have lower progress. Retirement is rejected. For team cars with ranks \(r_1, r_2\) and field size \(F\):

\[
L = \frac{r_1 + r_2 - 2}{2(F-1)}.
\]

This is a simulator outcome, not the QUBO proxy and not championship utility.

## 11. Persistence

Serialize: clock, every car (progress, tyres, inventory, pit phase, commitments), crew-free times, regime including private end time, policy tables, event log, stream key references, integrator phase. Restore in a new process must match event sequence, state, and terminal outcome under identical keys. A positions-and-lap table is not sufficient.

## 12. What this model is not

Not a calibrated F1 plant. Not TUMFTM. Not H1/H2/H3 evidence. Not QPU-ready. Parameters were **not** chosen so that a preferred strategy wins.
