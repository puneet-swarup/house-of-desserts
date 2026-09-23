# ADR-0004: HTMX + daisyUI for Frontend

## Status

Accepted

## Date

2026-09-21

## Context

Requirements:
- "Good looking" UI — not plain buttons and dropdowns
- Mobile-responsive (accessed from phone browser)
- No JavaScript build step (no Node, no npm, no webpack)
- Partial page updates for order status changes (no full page reload)
- Single developer with no frontend background

## Decision

We will use **HTMX** for interactivity (server-driven DOM updates) and
**daisyUI** (a Tailwind CSS component library) for styling. Both are loaded
via CDN in the base template. No JavaScript is written by us — HTMX handles
all interactivity via HTML attributes.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| React + Vite | Build step, node_modules, JS complexity. 10× the maintenance for 1 user. |
| Plain CSS (no framework) | "Good looking" requires a design system. Hand-rolling is slow and inconsistent. |
| Bootstrap 5 | Dated look. Less customizable. daisyUI is modern and Tailwind-based. |
| Pico CSS | Too minimal. Lacks cards, badges, modals out of the box. |
| Tailwind alone (no daisyUI) | Would need to hand-code every button/card/modal. daisyUI gives those for free. |

## Consequences

- (+) Professional, modern look with zero custom CSS (daisyUI components).
- (+) Fully responsive — daisyUI is mobile-first.
- (+) No JS build step. One `<script>` tag for HTMX, one `<link>` for daisyUI.
- (+) HTMX means order status updates are instant (no page reload).
- (−) CDN dependency (mitigated: download assets locally if internet is unreliable).
- (−) daisyUI classes are verbose in templates (mitigated: use Jinja2 macros for repeated patterns).   