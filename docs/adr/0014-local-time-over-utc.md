# ADR-0014: Local Time (IST) Over UTC

## Status

Accepted

## Date

2026-09-22

## Context

The app runs on a single machine in India (IST, UTC+5:30). All users
are the same person. Using `datetime.utcnow` stored timestamps 5h30m
behind what the user sees on their wall clock, causing confusion
("why does my order say 9:00 AM when it's 2:30 PM?").

## Decision

All timestamps use `datetime.now()` (local time). The machine's system
clock is in IST, so stored times match what the user expects.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| `datetime.utcnow` | 5h30m offset from user's perception. Confusing. |
| `datetime.now(timezone.utc)` + display conversion | Adds complexity for zero benefit at single-user scale. |
| Store as integer timestamp | Less readable in DB inspection. No benefit. |

## Consequences

- (+) Timestamps match the user's wall clock. No mental conversion needed.
- (+) Simpler code (no timezone conversion anywhere).
- (−) If the machine's clock/timezone changes, new records will be inconsistent
      with old ones (mitigated: unlikely for a home server).
- (−) Not portable to a multi-timezone deployment (irrelevant for this use case).   