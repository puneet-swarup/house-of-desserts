# ADR-0002: Python + FastAPI as Backend

## Status

Accepted

## Date

2026-09-21

## Context

We need a backend that:
- Is lightweight (runs on a home PC / Raspberry Pi with <512 MB RAM)
- Supports server-rendered HTML with partial updates (HTMX)
- Has first-class async support for printer I/O and file generation
- Is fast to develop (single developer, not a team)
- Has strong typing for maintainability

## Decision

We will use **Python 3.12** with **FastAPI** as the web framework,
**Jinja2** for server-side templating, and **uvicorn** as the ASGI server.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| Spring Boot (Java) | 512 MB+ RAM, 2–5 s startup, annotation-heavy. Overkill for single-user. |
| Quarkus (Java) | Better than Spring, but still JVM overhead. User not comfortable with Java ecosystem tooling. |
| Node.js + Express | Viable, but user has no JS background. Python chosen for ecosystem (escpos, weasyprint). |
| Flask | Synchronous by default, no built-in validation (Pydantic), slower dev loop. |
| Django | Batteries-included but too heavy (ORM, admin, auth) for this scope. |

## Consequences

- (+) ~100 MB RAM at idle. Instant startup.
- (+) Pydantic gives free validation + serialization + OpenAPI docs.
- (+) `python-escpos` and `weasyprint` are mature Python libraries.
- (+) Single-file `main.py` can bootstrap the entire app.
- (−) User is not a Python developer — dependency on AI assistance for code changes.
- (−) GIL limits CPU parallelism (irrelevant here — I/O bound, single user).   