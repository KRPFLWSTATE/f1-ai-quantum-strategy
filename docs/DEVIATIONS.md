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

No protocol amendments. `frozen: false`.
