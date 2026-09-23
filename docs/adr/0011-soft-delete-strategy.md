# ADR-0011: Soft Delete for All Entities

## Status

Accepted

## Date

2026-09-22

## Context

Orders reference customers and products by ID. If a customer or product
is hard-deleted, historical orders lose their referent. Financial records
must be reconstructable at any point in time. Additionally, accidental
deletes are irreversible with hard delete.

## Decision

All user-facing entities use **soft delete** via an `is_active` boolean
column (default `True`). "Delete" sets `is_active = False`. Soft-deleted
records are:
- Hidden from lists, search, and dropdowns
- Still queryable (for audit/reconstruction)
- Never physically removed from the database

Entities with soft delete: `customers`, `products`, `addresses`.
`orders`, `payments`, `invoices`, `audit_log` are never deleted (immutable).

Cascade rule: Deleting a customer soft-deletes all their addresses.

## Consequences

- (+) Financial records always reconstructable.
- (+) Accidental deletes are recoverable (flip `is_active` back to True).
- (+) Audit trail remains intact.
- (−) Must remember to filter `is_active == True` in all queries.
- (−) Table grows over time (mitigated: negligible at home bakery scale).
- (−) "Deleted" customers still occupy their phone number (uniqueness check
      must include `is_active == True`).