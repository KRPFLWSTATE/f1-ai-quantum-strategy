# Deviations and protocol amendments

No invented deviations. Record only genuine discrepancies.

| Date | Item | Kind | Notes |
| --- | --- | --- | --- |
| 2026-09-19 | PDF table extraction | extraction limitation | ReportLab text extraction wraps table cells into paragraphs. Counts above were checked against that text and the page images were not OCR'd separately. The original PDF remains authoritative. |
| 2026-09-19 | Page 11 unary coefficient glyph | possible typesetting/extraction ambiguity | Extracted `f(x) = sum a(c,a)x(c,a) + ...`. If the typeset PDF used a different coefficient symbol, later QUBO work must follow the PDF, not this flattening. Not a protocol amendment. |
| 2026-09-19 | Opened folder name | process | Cursor was opened on `Quantum Computing and Formula 1` rather than `f1-ai-quantum-strategy`. A separate folder was created. No files in the opened folder were rewritten except that they remain the user's originals. |
| 2026-09-19 | Doctor ledger open | software | After the first live bootstrap, `python -m f1q doctor` exited 1 with `UnboundLocalError` in `_ledger` if construction failed before assignment. Guarded with `ledger = None` and later a controlled failed check. Not a scientific amendment. |
| 2026-09-19 | Bootstrap doctor.py bytes | evidence omission | Snapshot `320dc0f9…` records unrepaired `doctor.py` `96eadf13…`. Those bytes are not in git. Receipt retained; not rewritten. Follow-up verification is `docs/STAGE_1_FOLLOWUP.md`. |
| 2026-09-19 | Green pit loss composition | modelling clarification | Dossier states 18–28 s green pit loss without splitting transit versus service. Stage 2 treats the sampled value as combined transit+service. Stage 3 decomposes \(T_{\mathrm{in}}+T_{\mathrm{svc}}+T_{\mathrm{out}}-T_{\mathrm{sector}}=P\) without adding service twice. |
| 2026-09-19 | Fuel initialisation vs horizon need | development-spec amendment | `docs/amendments/development_spec.fuel.v1.md`. Original Stage 2 spec bytes unchanged. |
| 2026-09-19 | Cutoff vs gap packing | development-spec amendment | `docs/amendments/checkpoint.cutoff.v1.md`. Original Stage 2 spec bytes unchanged. |
| 2026-09-19 | Split-planner CLI endpoints | software | Advertised `--test-blocks 80\|160` under-specified the dossier range. Planner now accepts every multiple of eight from 80 through 160. Not a scientific amendment. |

| 2026-09-19 | Fuel floor as Uniform/unbiased | documentation / modelling | `development_spec.fuel.v1.1` records the existing conditioned atom-at-need rule. Generation not changed. |
| 2026-09-19 | 0.5 s free-track tolerance | software acceptance | Unjustified for the analytic oracle; replaced by \(10^{-6}\) s FP/Newton bound. |
| 2026-09-19 | Commit-on-arrival vs common epoch | software | Production default commitment epoch is the registered/effective end so early arrival cannot pit earlier. |
| 2026-09-19 | Missed pit-now as next lap | software | Expired/rejected; not relabelled. |
| 2026-09-19 | TUM pin wording | report | Selection text no longer infers that all modern adapters are impossible. |
| 2026-09-19 | Resolution rank flip | limitation | One development episode flipped rank under h/h2/h4 with finish error \(\sim 5\times 10^{-7}\) s. Gate PARTIAL. |
| 2026-09-20 | Phase 5 development headroom zero | measured limitation | On A2 circuit_unit/tiny development instances, exact enumeration finishes inside the operational deadline; `DEVELOPMENT_HEADROOM: ZERO`; `SUPERIORITY_PATH_AVAILABLE: false`. Weak fallback gaps are not superiority headroom. |
| 2026-09-20 | C2 not admitted | protocol decision | Shared crew overlap is a finite cost; C1 one-hot XY sufficient. `C2_STATUS: NOT_ADMITTED_BY_PROTOCOL`. |
| 2026-09-20 | Phase 5 novelty | standing rule | `NOVELTY_STATUS: PROPOSED_NOT_LITERATURE_VERIFIED`; C0/C1/QAOA not claimed novel. |
| 2026-09-21 | Phase 6 calibration cohort namespace | protocol realisation | Reserved generator calibration partition was unmaterialized; Phase 6 registered isolated `phase6.calib.*` blocks (24/48) with no final-test access. Not a silent redesign of Phase 5 training. |
| 2026-09-21 | Phase 6 zero headroom on calibration | measured limitation | All 48 completed cases: exact enumeration inside deadline; mean/max strict-improve vs exact = 0; superiority path unavailable. |
| 2026-09-21 | Phase 6 protocol BLOCKED_DRAFT | freeze limitation | Mechanism freeze recorded; full scientific FROZEN blocked pending causal operational fields + Phase 7 amendment before final-test; hardware deferred to Phase 8. |
| 2026-09-21 | Noisy zero-noise jitter | implementation defect fix | Initial synthetic noisy panel used 1e-6 jitter at p1=p2=0 (30/32 zn). Fixed to exact identity; noisy panel regenerated only; mechanism pilot unchanged. |
| 2026-09-21 | Full dossier Phase 7 vs 24h ceiling | resource limitation | Extrapolated full dossier matrix exceeds provisional 24 CPU-h ceiling; reduced mechanism matrix (~1.76 CPU-h) proposed with dated amendment required before final-test. |
| 2026-09-21 | Phase 6 Hilbert shot cap | critical defect (corrected) | `pool_sample_metrics` used `min(pool_size, 2**n)`; 8q pools labelled 1024 drew 256. Corrected run `2a3fb275-…`; historical `bd83cb22-…` preserved. |
| 2026-09-21 | Phase 6 noise panel class | critical defect (withdrawn) | Historical panel was probability mix + jitter, not gate channels. Withdrawn as gate-noise evidence; replaced by DensityMatrix 1q/2q depolarizing sensitivity model. |
| 2026-09-21 | Phase 6 capacity hard-codes | high defect (corrected) | Unsupported 25.46h constants withdrawn; measurement-backed arithmetic; 80 blocks ≠ 80 cases. |
| 2026-09-21 | Phase 6 sizing placeholder | high defect (corrected) | Stratified bootstrap now executed; zero-variance does not power superiority. |
| 2026-09-21 | Gate E / Phase 7 ready | scientific correction | Prior `PASS_FOR_DEFINED_SCOPE` and `PHASE_7_MECHANISM_READY=true` withdrawn; Gate E `FAIL_FOR_INTENDED_CONTRIBUTION`; mechanism ready false. |

No protocol amendments that reopen final-test. Protocol status: `MECHANISM_SCOPE_DRAFT_V2_NOT_FINAL_TEST_AUTHORISED`.
