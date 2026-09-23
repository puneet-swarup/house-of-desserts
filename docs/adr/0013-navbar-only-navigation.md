# ADR-0013: Navbar-Only Navigation (No Drawer)

## Status

Accepted

## Date

2026-09-22

## Context

The initial design used a daisyUI drawer (sidebar) for navigation.
On mobile, the drawer CSS failed to render correctly after switching
to pre-compiled CSS. Additionally, the navbar already showed all nav
links as emoji icons on mobile, making the sidebar redundant.

## Decision

We will use **navbar-only navigation**. All nav links (Dashboard, Products,
Customers, Orders, Export, Audit) are in the top navbar. On desktop:
icon + text. On mobile: icon only (text hidden via `hidden sm:inline`).
No drawer, no hamburger, no sidebar.

## Consequences

- (+) Simpler HTML (no drawer markup, no checkbox toggle).
- (+) No CSS dependency on daisyUI's drawer component.
- (+) Always-visible navigation. No "where's the menu?" confusion.
- (+) Works identically on mobile and desktop.
- (−) On very small screens (< 360px), 6 icons + logo may be tight
      (mitigated: `overflow-x-auto` on the nav).   