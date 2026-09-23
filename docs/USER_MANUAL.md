# 🧁 House of Desserts — User Manual

A complete walkthrough of every screen, control, and data relationship.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Dashboard](#2-dashboard)
3. [Products](#3-products)
4. [Customers](#4-customers)
5. [Orders](#5-orders)
6. [Invoices](#6-invoices)
7. [Export](#7-export)
8. [Audit Log](#8-audit-log)
9. [Settings](#9-settings)
10. [Data Relationships](#10-data-relationships)
11. [FAQ & Troubleshooting](#11-faq--troubleshooting)

---

## 1. Getting Started

### First-Time Setup

Before using the app, ensure:

1. **Add your products** — Go to 🎂 Products → "Add Product". Add at least one item (name, SKU, price, GST rate).
2. **Add your customers** — Go to 👥 Customers → "Add Customer". Add the person placing the order.
3. **Create an order** — Go to 📋 Orders → "New Order". Select customer, add items, record advance.

### Navigation

The top navbar contains all sections. On mobile, only icons are shown (tap to navigate). On desktop, icon + text.

| Icon | Section | What it does |
|------|---------|-------------|
| 📊 | Dashboard | Today's stats, recent orders |
| 🎂 | Products | Manage your product catalog |
| 👥 | Customers | Manage customer records + addresses |
| 📋 | Orders | Create, track, and manage orders |
| 📥 | Export | Download CSV/JSON for tax filing |
| 📜 | Audit | View all system changes (read-only) |

The **logo** (top-left) always takes you back to the Dashboard.

On mobile, a floating **"+"** button (bottom-right) takes you directly to "New Order".

---

## 2. Dashboard

**URL:** `/`

### What you see

- **4 stat cards** (top row):
  - **Today's Orders** — count of orders created today
  - **Pending Delivery** — count of orders in "READY" status
  - **Outstanding Balance** — total unpaid amount across all active orders
  - **Total Products** — count of active products in catalog

- **Recent Orders table** (below cards):
  - Shows last 10 orders with: Order #, Customer name, Status badge, Amount, Date
  - Click "View All →" to go to the full Orders page

### Status Badge Colors

| Status | Color | Meaning |
|--------|-------|---------|
| INQUIRY | Grey | Customer asked, not yet confirmed |
| CONFIRMED | Blue | You accepted the order |
| IN_PROGRESS | Yellow | You're baking/preparing |
| READY | Green | Ready for pickup/delivery |
| DELIVERED | Purple | Customer received it |
| PAID | Green | Full payment received |
| CANCELLED | Red | Order was cancelled |

---

## 3. Products

**URL:** `/products`

### Product List

Displays all products as **cards** in a grid. Each card shows:
- Name, SKU (monospace font)
- Category badge, HSN code badge, GST rate badge
- Price (bold, bottom-left)
- Active/Inactive status badge
- **Edit** and **Delete** buttons

### Add Product

Click **"+ Add Product"** (top-right). Fill in:

| Field | Required | Example | Notes |
|-------|----------|---------|-------|
| Name | ✅ | Choco Truffle Cake | Display name |
| SKU | ✅ | CHOC-TRUFFLE-500G | Must be unique. Your internal code. |
| HSN Code | No (default 1905) | 1905 | For GST. Cakes = 1905. |
| Category | No (default Cake) | Cake, Bread, Cookie, Pastry | Grouping label |
| Base Price | ✅ | 500.00 | Price before GST |
| GST Rate | No (default 5%) | 5, 0, 12, 18 | Percentage |
| Prep Time | No (default 4) | 4 | Hours needed to prepare |
| Description | No | Rich chocolate truffle... | Shown on invoices |
| Active | ✅ (checked) | — | Uncheck to hide from orders |

### Edit Product

Click **Edit** on a product card. Same form, pre-filled. Change any field → Save.

### Delete Product

Click **Delete** → confirm. Product is **soft-deleted** (marked inactive). It disappears from the order form dropdown but remains in historical orders.

---

## 4. Customers

**URL:** `/customers`

### Customer List

Table view showing: Name, Phone, Email, Order count, Since date, Actions.
- Soft-deleted customers appear at 40% opacity with a "Deleted" badge.
- Active customers have **Edit** and **Delete** buttons.

### Add Customer

Click **"+ Add Customer"**. Fill in:

**Customer Details section:**

| Field | Required | Notes |
|-------|----------|-------|
| Full Name | ✅ | |
| Phone | ✅ | Must be unique among active customers |
| Email | No | |
| Notes | No | Allergies, preferences, etc. |

**Addresses section:**

You can add **multiple addresses** at once:
- Each row has: **Label** (narrow, e.g., "Home") + **Address line** (wide) + **Def** toggle
- Click **"+ Add Address"** to add more rows
- Only ONE address can be marked "Def" (default). Toggling one ON automatically turns others OFF (instant, in the browser).
- The default address is auto-filled when this customer is selected in an order.

### Edit Customer

Click **Edit** on a customer row. Same form as Add, but:
- Existing addresses are shown as **editable rows** (label + line inputs, pre-filled)
- Each has a **Def toggle** (amber when ON) and a **✕** button (soft-deletes that address)
- You can still add new addresses below the existing ones
- Clicking the **Def toggle** on an existing address immediately makes it the default (AJAX, page reloads)

### Customer Detail (Read-Only)

Click a customer's **name** in the list. Shows:
- Customer details (disabled inputs, same layout as edit form)
- Addresses (read-only, with disabled Def toggles)
- **Order History** table (all past orders with status, amount, balance)
- **Edit** button (top-right) → goes to edit form
- **Delete** button (top-right) → soft-deletes customer + all their addresses

### Search (in Order Form)

When creating an order, the customer field is a **typeahead search**:
- Type 2+ characters → dropdown appears
- Matches by **name** (case-insensitive) or **phone number** (partial match)
- Shows: Name, Phone, address count
- Click a result → customer is selected, their addresses populate the delivery field

---

## 5. Orders

**URL:** `/orders`

### Order List

Cards showing: Order #, Customer, Date, Status badge, Amount, Balance (if any).

**Filter tabs** (top): All | Confirmed | In Progress | Ready | Delivered

**Quick actions** (on each card):
- **"→ Mark [Next Status]"** button — advances the order one step
- **"Cancel"** button — cancels the order (with confirmation)

### Order Lifecycle
```
INQUIRY → CONFIRMED → IN_PROGRESS → READY → DELIVERED → PAID
↘ CANCELLED (from any state before DELIVERED)
```

- You **cannot** skip states (e.g., can't go CONFIRMED → READY directly)
- **PAID** is set automatically when balance reaches 0
- **CANCELLED** is a terminal state (can't un-cancel)

### New Order

Click **"+ New Order"** (or the mobile FAB "+").

**Step 1: Customer & Delivery**

| Field | How it works |
|-------|-------------|
| Customer | Type to search. Click a result to select. |
| Delivery Type | "Pickup" (default) or "Delivery" |
| Order Date | Pre-filled with today. Editable. |
| Delivery Date | Optional. When should it be delivered/ready? |
| Delivery Address | **Disabled** if Pickup. **Enabled** if Delivery. Shows a dropdown of saved addresses (if customer has any). Default address auto-fills. You can type a custom address. |
| Notes | Free text (cake message, instructions) |

**Step 2: Items**

- Click **"+ Add Item"** to add rows
- Each row: Product dropdown (shows name + price) + Quantity + ✕ (remove row)
- You can add as many items as needed
- One row is shown by default

**Step 3: Advance Payment**

| Field | Notes |
|-------|-------|
| Amount Received | How much advance the customer paid (0 if none) |
| Method | UPI / Cash / Bank Transfer |

**Submit:** Click **"Create Order"**. You're redirected to the order detail page.

### Order Detail

**URL:** `/orders/{id}`

Shows:
- **Header:** Order #, Customer, Date, Status badge
- **Status actions:** "Mark [Next Status]" + "Cancel" buttons
- **Invoice actions:** "View Invoice" + "Print Receipt" buttons
- **Items table:** Product, SKU, Qty, Unit Price, Total, Notes
- **Payments section:** All payments recorded + "Record Payment" form (if balance > 0)
- **Delivery info:** Address + date (if delivery type)

**Recording a Payment:**
- Amount (pre-filled with remaining balance)
- Method (UPI/Cash/Bank)
- Reference (optional — UPI transaction ID, etc.)
- Click "Record" → balance updates. If balance = 0, status auto-changes to PAID.

### Editing Orders

**Not yet implemented** (Phase 2). Once an order is created, it's locked. If you need to change something:
- For INQUIRY/CONFIRMED: Cancel and recreate
- For later states: Contact the customer, note it in the order notes

---

## 6. Invoices

### Viewing an Invoice

From the order detail page, click **"View Invoice"**.

Shows a styled on-screen preview:
- **Header:** Your business name, address, FSSAI, GSTIN (if set)
- **Bill To:** Customer name, phone, email, default address
- **Deliver To** (or **Pickup**): Delivery address + date
- **Items table:** #, Item, HSN, Qty, Rate, GST, Amount
- **Totals:** Subtotal, CGST + SGST (if registered), Total, Paid, Balance

**Actions:**
- **"Download PDF"** → browser downloads the invoice as a PDF file
- **"Print Receipt"** → sends to thermal printer (or saves to file if `PRINTER_TYPE=file`)

### GST Display Rules

| Your GSTIN in .env | What the invoice shows |
|-------------------|----------------------|
| Blank (not registered) | No GST lines. Just Subtotal + Total. |
| Filled in (registered) | CGST @ X% + SGST @ X% (split 50/50 of the product's GST rate) |

### PDF File Location

Generated PDFs are saved to `data/invoices/` with the invoice number as filename (e.g., `HOD-2026-0001.pdf`).

### Thermal Receipt

Printed on 80mm (or 58mm) roll paper. Shows:
- Business name, address, phone, FSSAI
- Invoice number, date, customer, delivery info
- Itemized list with quantities and amounts
- Subtotal, GST (if registered), Total, Paid, Balance
- "Thank you" footer

---

## 7. Export

**URL:** `/export`

### How to Use

1. Pick a **From Date** and **To Date** (date pickers)
2. Click one of the three download buttons:

| Button | What you get | Use case |
|--------|-------------|----------|
| **Orders CSV** | One row per order: number, date, customer, phone, status, delivery type, totals, items | Monthly review, ITR |
| **Payments CSV** | One row per payment: order #, customer, date, amount, method, reference | Bank reconciliation |
| **Summary JSON** | Aggregated stats: total orders, revenue, GST collected, outstanding, top products | Quick overview for CA |

### CSV Format

Opens directly in Excel. Columns are comma-separated. Use for:
- Filing ITR (income = sum of "Total Amount" column)
- Showing your CA the monthly business activity
- Tracking which products sell most

---

## 8. Audit Log

**URL:** `/audit`

### What it shows

A chronological table of **every significant action**:

| Column | Meaning |
|--------|---------|
| Time | When it happened |
| Entity | What was changed (e.g., "Order#3", "Customer#1") |
| Action | CREATE / UPDATE / DELETE / STATUS_CHANGE / PAYMENT |
| Details | JSON of old/new values |

### Filter Tabs

All | Orders | Payments | Customers | Products

### What gets logged

| Action | Logged as |
|--------|-----------|
| Create a product | Product#1 CREATE |
| Edit a product | Product#1 UPDATE |
| Delete a product | Product#1 DELETE |
| Create a customer | Customer#1 CREATE |
| Edit a customer | Customer#1 UPDATE |
| Delete a customer | Customer#1 DELETE |
| Create an order | Order#1 CREATE |
| Change order status | Order#1 STATUS_CHANGE |
| Record a payment | Payment#1 PAYMENT |
| Delete an address | Address#1 DELETE |

### Purpose

- **Financial transparency:** Prove what was sold, when, and for how much
- **Dispute resolution:** "Did I change that price?" → Check the log
- **CA audit:** Show a complete trail of all transactions

---

## 9. Settings

**URL:** `/settings`

### What it shows

Read-only display of all business configuration:
- Business name, tagline, phone, email, address
- FSSAI number, GSTIN
- Printer type and paper width
- Invoice prefix and start number

### How to Change

Edit the `.env` file in the project root. Restart the server.

Example `.env`:
```env
APP_NAME=House of Desserts
FSSAI_NUMBER=10012345678901
GSTIN=
PHONE=+91 98765 43210   
```

## 10. Data Relationships
```mermaid
┌──────────────┐       ┌──────────────┐
│  CUSTOMERS   │       │  ADDRESSES   │
│──────────────│       │──────────────│
│ id (PK)      │──1:N──│ id (PK)      │
│ name         │       │ customer_id  │──FK→ customers.id
│ phone (UQ)   │       │ label        │
│ email        │       │ line         │
│ notes        │       │ is_default   │
│ is_active    │       │ is_active    │
└──────┬───────┘       └──────────────┘
       │
       │ 1:N
       ▼
┌──────────────┐       ┌──────────────┐
│    ORDERS    │       │ ORDER_ITEMS  │
│──────────────│       │──────────────│
│ id (PK)      │──1:N──│ id (PK)      │
│ order_number │       │ order_id     │──FK→ orders.id
│ customer_id  │──FK───│ product_id   │──FK→ products.id
│ status       │       │ quantity     │
│ order_date   │       │ unit_price   │
│ delivery_type│       │ gst_amount   │
│ delivery_date│       │ line_total   │
│ delivery_addr│       │ customization│
│ total_amount │       └──────────────┘
│ advance_paid │
│ balance_due  │       ┌──────────────┐
│ is_active    │──1:N──│  PAYMENTS    │
└──────────────┘       │──────────────│
                       │ id (PK)      │
                       │ order_id     │──FK→ orders.id
                       │ amount       │
                       │ method       │
                       │ reference    │
                       │ received_at  │
                       └──────────────┘

┌──────────────┐       ┌──────────────┐
│  PRODUCTS    │       │  INVOICES    │
│──────────────│       │──────────────│
│ id (PK)      │       │ id (PK)      │
│ sku (UQ)     │       │ order_id     │──FK→ orders.id (1:1)
│ hsn_code     │       │ invoice_number│
│ name         │       │ invoice_date │
│ category     │       │ status       │
│ base_price   │       │ pdf_path     │
│ gst_rate     │       └──────────────┘
│ prep_time    │
│ is_active    │       ┌──────────────┐
└──────────────┘       │  AUDIT_LOG   │
                       │──────────────│
                       │ id (PK)      │
                       │ entity_type  │
                       │ entity_id    │
                       │ action       │
                       │ old_value    │
                       │ new_value    │
                       │ changed_at   │
                       └──────────────┘   
```
### Key Relationships
| From | To | Type | Meaning |
|------|-----|------|---------|
| Customer | Address | 1:N | One customer has many addresses |
| Customer | Order | 1:N | One customer places many orders |
| Order | OrderItem | 1:N | One order has many line items |
| OrderItem | Product | N:1 | Each line item references one product |
| Order | Payment | 1:N | One order can have multiple payments |
| Order | Invoice | 1:1 | One order has at most one invoice |
| Product | OrderItem | 1:N | One product appears in many order items |

### Soft Delete Behavior
| Entity | What happens on delete |
|--------|----------------------|
| Customer | `is_active=False`. All their addresses also `is_active=False`. Orders remain intact. |
| Product | `is_active=False`. Disappears from order form. Historical orders still show the product name. |
| Address | `is_active=False`. Disappears from dropdowns. Order's `delivery_address` text is unaffected. |
| Order | **Never deleted.** Only status changes to CANCELLED. |
| Payment | **Never deleted.** Immutable financial record. |
| Invoice | **Never deleted.** Immutable financial record. |

## 11. FAQ & Troubleshooting
#### "Why can't I select a customer in the order form?"
You need at least 2 characters in the search box. Also, the customer must be active (not deleted).

#### "Why is the delivery address field greyed out?"
You selected "Pickup" as the delivery type. Switch to "Delivery" to enable it.

#### "Why doesn't the customer's address auto-fill?"
The customer must have at least one active address saved. Go to their Edit page → add an address → mark it as Default.

#### "I deleted a customer but their orders still show their name."
Correct behavior. Orders store the customer's name at the time of order. Soft-deleting the customer doesn't modify historical orders.

#### "The PDF shows 'Rs.' instead of '₹'."
The Noto Sans font file isn't in app/static/fonts/. Either download it (see SETUP.md) or accept "Rs." as the display.

#### "How do I change my business name?"
Edit APP_NAME in the .env file → restart the server.

#### "How do I backdate an order?"
When creating a new order, change the "Order Date" field to the earlier date.

#### "Can I undo a status change?"
Not directly. The audit log records the change. If you need to revert, you'd need to manually update the DB or add a "revert" feature.

#### "The thermal printer isn't printing."
Check: 
- (1) PRINTER_TYPE in .env matches your setup, 
- (2) printer is connected and on, (3) for file type, check data/receipt_preview.bin was created.