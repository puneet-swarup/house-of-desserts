# ADR-0007: Environment-Based Configuration

## Status

Accepted

## Date

2026-09-21

## Context

Business details (name, FSSAI, GSTIN, phone, address) and technical
settings (DB path, printer config) must be:
- Configurable without code changes
- Not committed to version control (contain business info)
- Easy to change (e.g., business rebrand, new GSTIN)
- The app name itself should be configurable (not hardcoded)

## Decision

All configuration is loaded from environment variables via a `.env` file
at the project root, parsed by **pydantic-settings**. The `.env` file is
gitignored; `.env.example` is committed as a template. The app name, FSSAI
number, GSTIN, phone, address, and printer settings are all env-driven.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| Hardcoded in `config.py` | Requires code change + redeploy for any business detail change. |
| Database-stored settings | Chicken-and-egg: need DB to read settings that configure DB. |
| YAML/TOML config file | Works, but `.env` is the de facto standard and integrates with 12-factor. |

## Consequences

- (+) Change business name → edit one line in `.env` → restart. Done.
- (+) No secrets in code. `.env` is gitignored.
- (+) Same codebase works for dev (mock printer) and prod (real printer).
- (−) Must remember to restart server after `.env` changes (mitigation: `--reload` in dev).   