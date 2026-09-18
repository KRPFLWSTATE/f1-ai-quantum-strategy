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

No protocol amendments. `frozen: false`.
