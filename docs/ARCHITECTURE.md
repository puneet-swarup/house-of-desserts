# Architecture — Invariants

This file lists the design decisions that must not be broken. Each one
exists because breaking it produces a specific failure. When you're about
to change something and it looks like it violates one of these, stop and
figure out why.

## Money

**Money is `Decimal`, never `Float`.**

Columns are `Numeric(precision, 2)`. All arithmetic goes through
`app.utils.money`. Never use `float` in money paths — the drift compounds
across line items and GST splits, and a tax filing will find it.

Rounding policy: per-line, half-up. This is documented in `money.py`.
Once written, a value never changes; snapshots win over recomputation.

## Invoices

**An invoice is an immutable snapshot of an order at the moment of issue.**

The Invoice row carries its own copy of business identity, billed-to name
and address, order number and date, delivery details, line items (as JSON),
and every total. Editing the order afterwards does NOT change the invoice.
Historical tax documents must not change.

Corollary: never read `order.*` or `customer.*` from a PDF or preview
renderer. Read `invoice.*`.

## Numbering

**Order and invoice numbers come from a sequence table.**

`NumberSequence` holds a monotonic counter per prefix (e.g. `HOD-2026-ORDER`).
Never compute the next number as `count(*) + 1` — that has a race condition
and produces duplicates under concurrency, and gaps under delete.

Invoice numbers must be gapless. Never reuse a number, even on cancel.

## Audit

**Audit entries commit in the same transaction as the mutation they describe.**

`audit_service.log_action` adds a row to the session but does NOT commit.
The caller commits once, at the end, covering both the mutation and the audit.
If the audit write fails, the whole transaction rolls back — no orphaned
financial changes.

## Foreign keys

**`PRAGMA foreign_keys=ON` is set on every SQLite connection.**

SQLite has FK enforcement off by default. Without this, cascade deletes are
decorative and you can insert orphaned rows. The PRAGMA is set in
`database.py` via a `connect` event listener.

WAL and `busy_timeout=5000` accompany it, so concurrent writes don't
immediately fail with "database is locked".

## Inventory

**Stock is a ledger, not a stored balance.**

`Ingredient.current_stock` does not exist. On-hand is `SUM(delta)` over
`StockMovement` rows for that ingredient. This can't drift; a stored
balance can.

Every change — purchase, consumption, wastage, return, adjustment — is a
new row. Never update an old movement. To correct a mistake, add a new
movement that nets the error to zero.

**Cost snapshots on every movement.** `unit_cost_at_time` and
`total_cost_at_time` capture the ingredient's cost at the moment of the
movement. Purchases update the ingredient's weighted-average cost for
*future* movements. Past movements keep their original cost forever.
Historical COGS never changes.

`total_cost_at_time` is always a magnitude (positive), regardless of the
sign of `delta`. Direction lives in `delta`; cost is a positive number.

## Recipes and units

**Recipe quantities are always stored in the ingredient's own unit.**

If the user enters "500 g" for an ingredient stored in kg, the service
converts to "0.5 kg" before saving. Storage is unambiguous; display
reflects what the ingredient is measured in.

**Unit conversion is only allowed within a group.**

- Mass: g ↔ kg (base: g)
- Volume: ml ↔ l (base: ml)
- Count: `pcs`, `packets` — each its own group, no implicit conversion

There is no "1 packet = 6 pcs" rule. That's a product-specific fact, not
a unit fact. If you ever need it, add a `dozen` unit or a pack-conversion
table; don't hack it into `units.py`.

## Timezone

**Storage is naive UTC. Display is business-timezone.**

`app.utils.time.utcnow()` returns a naive datetime in UTC. Columns are
`DateTime` without timezone. Conversions to and from the business timezone
happen at the display and query boundaries.

For columns that are stored as naive-local (like `fulfillment_date`, which
reflects the customer's typed intent), compare against `now(tz).date()`,
not against UTC bounds.

## Fulfillment vs payment

**Two independent state machines.**

`Order.status` tracks fulfillment: INQUIRY → CONFIRMED → IN_PROGRESS →
READY → DELIVERED → PAID (or CANCELLED).

Payment is tracked by two numbers (`advance_paid`, `balance_due`) and a
computed `payment_state` property (`paid` / `partial` / `unpaid`).

Recording a payment never changes fulfillment status. Moving fulfillment
forward never changes payment state. Both are shown as separate badges
wherever an order appears.

## Auto-deduction on production start

**Entering IN_PROGRESS deducts ingredients per recipe.**

Not on order creation (nothing is committed yet) and not on READY
(too late — the ingredients are gone the moment baking starts).

Stock is allowed to go negative. The UI shows a shortage warning before
the user starts production, but does not block. A home bakery knows its
kitchen better than the app.

## Cancel semantics

| From status | Behavior |
|---|---|
| INQUIRY / CONFIRMED | No consumption happened. Clean cancel. |
| IN_PROGRESS | User chooses: **return stock** (creates RETURN movements per consumption) or **waste** (consumption stands). |
| READY | Cancel allowed, but no salvage option. The food was already made; consumption costs stand as a loss. |
| DELIVERED | Not cancellable. A refund or refused delivery is a different concept. |

Every cancel is audited with the `salvage` flag recorded in the audit entry.

## COGS

**Per-order COGS = sum of `total_cost_at_time` on CONSUMPTION movements
referencing that order, minus the same for RETURN movements.**

`total_cost_at_time` is captured at the moment of the movement. It never
changes if ingredient prices move later. `order_cogs()` is the single
function that computes this; reports and the order detail page both use it.

## Soft delete

**Entities use soft delete with a partial unique index.**

`Customer.is_active`, `Product.is_active`, `Ingredient.is_active`. The
unique constraints on phone/SKU/name are partial — only active rows must
be unique. This lets you delete and recreate without collisions.

## Cache and static assets

**`NoCacheMiddleware` sets no-store on HTML responses.**

Dynamic pages never get cached by the browser, so data changes appear
immediately. Static assets under `/static` keep the browser cache.

In dev, this is extended to all responses via `DEBUG=true`.

## CSS

**`app/static/css/app.css` is compiled, not hand-written.**

Source is `app/static/css/input.css` (Tailwind v4 + daisyUI 5). Build with
`.\build-css.ps1`. Any template change that introduces a new utility class
requires a rebuild before it takes effect.

Never write inline `style=""` for layout. If a class isn't compiled, the
fix is to rebuild, not to inline.

Template edits + `build-css.ps1` + commit are always one operation.