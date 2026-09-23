# ADR-0001: Record Architecture Decisions

## Status

Accepted

## Date

2026-09-21

## Context

This project will evolve over time. Decisions made today (tech stack,
data model, deployment strategy) need to be documented so that future
changes are informed by the original rationale. Without records,
decisions get re-litigated or accidentally reversed.

## Decision

We will record significant architectural decisions as ADRs in `docs/adr/`.
Each ADR follows the Nygard format: Status, Context, Decision, Consequences.
ADRs are numbered sequentially, never deleted, and superseded (not edited)
when a decision changes.

## Consequences

- (+) Rationale is preserved; new contributors (or future-me) can understand why.
- (+) Prevents accidental re-litigation of settled decisions.
- (−) Small overhead per decision (~10 min to write).
- (~) ADRs are only as good as the discipline to write them at decision time.   