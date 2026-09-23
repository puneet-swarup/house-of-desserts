# ADR-0009: fpdf2 for PDF Generation

## Status

Accepted

## Date

2026-09-22

## Context

We need to generate PDF invoices for records and ITR filing.
WeasyPrint (initial choice) requires system libraries (Pango, Cairo, GDK)
that are painful to install on Windows. It also adds ~50 MB of dependencies.
For a simple tabular invoice (header, items table, totals, footer),
a full HTML→PDF engine is overkill.

## Decision

We will use **fpdf2** (pure Python, zero system dependencies) for PDF
generation. The invoice is built programmatically (cell by cell) rather
than rendered from an HTML template.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| WeasyPrint | Requires Pango/Cairo system libs. Painful on Windows. Overkill for tabular output. |
| ReportLab | Heavier API, more verbose for simple layouts. |
| Browser print-to-PDF | Requires a browser, not scriptable from the backend. |

## Consequences

- (+) Zero system dependencies. `pip install fpdf2` and it works on any OS.
- (+) ~2 MB install vs. ~50 MB for WeasyPrint + system libs.
- (+) Fast generation (<50ms per invoice).
- (−) No HTML/CSS flexibility. Complex layouts (multi-column, images) are harder.
- (−) Invoice layout is code, not a template. Visual changes require code edits.   