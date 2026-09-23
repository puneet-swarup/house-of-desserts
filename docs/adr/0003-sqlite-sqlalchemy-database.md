# ADR-0003: SQLite + SQLAlchemy for Data Layer

## Status

Accepted

## Date

2026-09-21

## Context

Requirements:
- Single user, <10K orders/year
- Zero server processes (no Postgres daemon to manage)
- Data must be portable (no vendor lock-in)
- Must support migration to Postgres later if business grows
- ACID compliance for financial records

## Decision

We will use **SQLite** as the database engine and **SQLAlchemy 2.0** (ORM)
as the data access layer. The `DB_URL` in `.env` controls the backend,
making migration to Postgres a one-line config change.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| PostgreSQL | Requires a running server, more RAM, more ops. Unnecessary at this scale. |
| MySQL/MariaDB | Same as Postgres. Also worse for JSON fields. |
| Raw SQL (no ORM) | No portability guarantee. Schema changes become manual. |
| NoSQL (MongoDB) | Overkill. Relational model fits orders/payments perfectly. |

## Consequences

- (+) Zero-config. Single file. No daemon. `bakery.db` is the entire database.
- (+) SQLite is ACID-compliant — safe for financial records.
- (+) SQLAlchemy ORM means all queries are portable SQL. Migration = change `DB_URL`.
- (+) Full-text search available (FTS5) if needed later.
- (−) Single-writer constraint. Fine for 1 user; would need Postgres for concurrent writes.
- (−) No built-in user management / connection pooling (irrelevant at this scale).   