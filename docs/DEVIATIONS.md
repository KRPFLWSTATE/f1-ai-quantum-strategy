# Deviations and protocol amendments

No invented deviations. Record only genuine discrepancies.

| Date | Item | Kind | Notes |
| --- | --- | --- | --- |
| 2026-09-19 | PDF table extraction | extraction limitation | ReportLab text extraction wraps table cells into paragraphs. Counts above were checked against that text and the page images were not OCR'd separately. The original PDF remains authoritative. |
| 2026-09-19 | Page 11 unary coefficient glyph | possible typesetting/extraction ambiguity | Extracted `f(x) = sum a(c,a)x(c,a) + ...`. If the typeset PDF used a different coefficient symbol, later QUBO work must follow the PDF, not this flattening. Not a protocol amendment. |
| 2026-09-19 | Opened folder name | process | Cursor was opened on `Quantum Computing and Formula 1` rather than `f1-ai-quantum-strategy`. A separate folder was created. No files in the opened folder were rewritten except that they remain the user's originals. |
| 2026-09-19 | Doctor ledger open | software | After the first live bootstrap, `python -m f1q doctor` exited 1 with `UnboundLocalError` in `_ledger` if construction failed before assignment. Guarded with `ledger = None` and re-ran doctor: exit 0, ledger check ok. Not a scientific amendment. |

No protocol amendments. `frozen: false`.
