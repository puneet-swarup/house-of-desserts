# ADR-0006: ESC/POS for Thermal Printing

## Status

Accepted

## Date

2026-09-21

## Context

The user needs to print customer receipts on a thermal roll printer
(80mm or 58mm). Standard PDF printing is incompatible with thermal printers.
Thermal printers use the ESC/POS byte protocol.

Additionally, a PDF copy is needed for internal records and ITR filing.

## Decision

We will use **python-escpos** to send ESC/POS commands directly to the
thermal printer for customer-facing receipts, and **WeasyPrint** to generate
a PDF invoice for internal records. The printer type (USB, network, file)
is configurable via `.env`.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| PDF → printer (CUPS) | CUPS can drive ESC/POS printers, but adds a system daemon and complexity. |
| Raw socket to printer | No library abstraction. Error-prone. No QR/barcode support. |
| Cloud print API (e.g., HP) | N/A for thermal printers. |

## Consequences

- (+) Direct byte-level control over receipt layout (alignment, bold, barcode, QR).
- (+) `python-escpos` supports USB, Serial, and Network (TCP) printers.
- (+) `PRINTER_TYPE=file` allows testing without a physical printer (saves to a .bin file).
- (−) Printer driver issues are OS-level (mitigation: document per-OS setup in README).
- (−) WeasyPrint requires system libraries (`pango`, `cairo`) — documented in setup.   