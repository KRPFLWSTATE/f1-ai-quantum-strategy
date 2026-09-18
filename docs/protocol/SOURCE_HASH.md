# Source hash — F1_AI_Quantum_Research_Dossier_v3_1.pdf

The original PDF is preserved at `docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf` and at the repository root. It is not modified.

SHA256_PDF: 2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76
SIZE_BYTES: 163479
PAGE_COUNT_REPORTED_IN_PDF: 33
PAGES_EXTRACTED: 33
SHA256_EXTRACTED_TEXT: 75c6d4232617585cf4231d2312a447e434a276dd60360dd8076fb9a9b2c8dd1d
EXTRACTOR: pypdf 6.19.0 (temporary extract environment; not a project runtime dependency)
EXTRACTED_FILE: docs/protocol/dossier_extracted.txt
PDF_METADATA_TITLE: Deadline constrained AI and quantum optimisation for Formula 1 strategy
PDF_METADATA_SUBJECT: Research dossier version 3.1 - corrected proposed protocol, no experimental results
PDF_METADATA_AUTHOR: Kawin Rehan Perera
PDF_METADATA_PRODUCER: ReportLab PDF Library - (opensource)
PDF_METADATA_CREATIONDATE: 2026-09-18T15:20:42+01:00

## Extraction inspection

All 33 pages produced non-empty text (about 2.1k–3.0k characters each) and zero embedded images via pypdf. Page boundaries are marked as `===== PAGE n / 33 =====`.

Formulas recovered as Unicode text, including dossier section 9 `f(x)` / one-hot penalty / `L = (r1 + r2 - 2) / [2(F - 1)]` / `M > B/v_min`, section 11 regret, section 14 `g - q - λu`, section 20 campaign ceiling `min(420, max(0, A - 120))`, and section 22 `1 - (1 - pτ)^S`. Typesetting is flattened; inspect the PDF for original glyphs. Unary coefficients on page 11 appear as `a(c,a)`, which collides with the action index name; treat the PDF as authoritative if this is a typesetting artifact.

Tables (correction log, circuit families, comparators, experiment matrix, hardware envelope, implementation sequence, freeze record) extracted as wrapped paragraphs, not grid cells. Counts used in this repository were checked against that text:

- Splits: 120 / 16 / 24 / 80 blocks plus 40 shift blocks; eight checkpoints each (section 7).
- Hardware primary: 50 jobs, 88 pools, 88,064 shots, 402 s caps; alternative: 38 jobs, 64 pools, 32,768 shots, 414 s (section 20). These are mutually exclusive, not cumulative.

No page was omitted. This hash is the dossier identity. It is not a frozen experimental protocol hash.
