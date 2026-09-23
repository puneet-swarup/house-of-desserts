# ADR-0010: Pre-compiled CSS (Tailwind Standalone CLI)

## Status

Accepted

## Date

2026-09-22

## Context

The Tailwind Play CDN (`cdn.tailwindcss.com`) compiles CSS in the browser
on every page load (~300 KB JS download + 3–10 s compilation time on mobile).
This made the app unusably slow on mobile data (India networks).
Additionally, CDN dependency means the app breaks without internet.

## Decision

We will use the **Tailwind Standalone CLI** (single binary, no Node.js)
to pre-compile CSS at build time. The output is a single `app.css` file
(~15–30 KB) served as a static asset. daisyUI is included as a plugin.
HTMX is also self-hosted. **Zero external CDN dependencies.**

## Build Process

```bash
cd app/static/css
tailwindcss.exe -i input.css -o app.css --minify   
```

During development, use --watch mode for auto-rebuild on template changes.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| Tailwind Play CDN | 3–10 s load time on mobile. CDN dependency. FOUC. |
| Tailwind v4 browser runtime | ~1 MB JS, still compiles in browser, less stable. |
| Hand-written CSS | No utility classes, slower development, inconsistent spacing. |
| Node.js + PostCSS build | Requires Node.js install. Overkill for a single-developer project. |

## Consequences
- (+) ~500 ms to styled render (was 4–10 s). No FOUC.
- (+) Zero CDN dependency. Works fully offline over Tailscale.
- (+) Single ~20 KB CSS file. Fast on any connection.
- (−) Must rebuild CSS after adding new Tailwind classes in templates.
- (−) tailwindcss.exe binary (~30 MB) in the project (gitignored).