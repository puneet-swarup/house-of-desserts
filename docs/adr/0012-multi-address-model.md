# ADR-0012: Multi-Address per Customer

## Status

Accepted

## Date

2026-09-22

## Context

A customer may have multiple addresses (Home, Office, "Mom's House").
The delivery address for an order may differ from the customer's default.
A single `address` text column on `customers` is insufficient.

## Decision

We will use a separate `addresses` table with a one-to-many relationship
to `customers`. Each address has:
- `label` (e.g., "Home", "Office")
- `line` (full address text)
- `is_default` (exactly one per customer at a time)
- `is_active` (soft delete)

The `orders.delivery_address` field stores the **specific address for that
order** (may be the default, a different saved address, or a one-off address).

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| Single `address` column on customers | Can't have multiple. Can't label. Can't set default. |
| JSON field on customers | Can't query, can't enforce "one default", harder to validate. |
| Separate `delivery_addresses` table per order | Over-normalized. Addresses are customer attributes, not order attributes. |

## Consequences

- (+) Customer can save 5 addresses, pick any one per order.
- (+) Default address auto-populates the order form.
- (+) Soft-deleted addresses don't appear in dropdowns but remain in history.
- (−) Slightly more complex form (add/edit/delete addresses inline).
- (−) Must enforce "exactly one default" in both UI (JS) and backend.   