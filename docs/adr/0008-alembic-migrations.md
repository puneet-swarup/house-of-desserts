
# ADR-0008: Alembic for Schema Migrations

## Status

Accepted

## Date

2026-09-21

## Context

The schema will evolve (new columns, new tables, index changes).
We need a reproducible, versioned way to apply schema changes to the
SQLite database without manual SQL.

## Decision

We will use **Alembic** (the official SQLAlchemy migration tool) with
autogenerate support. Migrations are stored in `alembic/versions/` and
applied via `alembic upgrade head`.

## Consequences

- (+) Reproducible schema changes. `alembic upgrade head` on a fresh DB creates the full schema.
- (+) Autogenerate detects model changes and drafts migrations.
- (+) Migration history is in git — full audit trail of schema evolution.
- (−) Slight learning curve (one command: `alembic revision --autogenerate -m "msg"`).   