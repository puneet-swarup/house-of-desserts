"""UI tests: Order creation, status flow, fulfillment requirement."""

from playwright.sync_api import expect


def _create_order(app_page, live_server, seeded, *, advance="0"):
    app_page.goto(live_server + "/orders/new")

    app_page.select_option("#customer_id", str(seeded["customer_id"]))
    app_page.fill('input[name="fulfillment_date"]', seeded["fulfillment"])
    app_page.select_option('select[name="product_id"]', str(seeded["product_id"]))
    app_page.fill('input[name="quantity"]', "2")
    app_page.fill('input[name="advance_paid"]', advance)

    app_page.click('button[type="submit"]')
    # Order detail page shows the "Payments" heading
    expect(app_page.locator("h2:has-text('Payments')")).to_be_visible(timeout=10000)


def test_create_order_via_ui(app_page, seeded, live_server):
    _create_order(app_page, live_server, seeded)
    expect(app_page.locator(f"text={seeded['product_name']}").first).to_be_visible()


def test_status_transition_via_ui(app_page, seeded, live_server):
    """Order CONFIRMED → IN_PROGRESS via the 'Mark In Progress' button."""
    _create_order(app_page, live_server, seeded)

    # We're now on the order detail page in CONFIRMED status.
    # The explicit action button should be present.
    expect(app_page.locator("button:has-text('Mark IN PROGRESS')")).to_be_visible(timeout=5000)

    app_page.click("button:has-text('Mark IN PROGRESS')")
    app_page.wait_for_timeout(1000)

    # After reload, status badge should say IN PROGRESS
    expect(app_page.locator("span.badge:has-text('IN PROGRESS')")).to_be_visible(timeout=8000)

    # And the next action button should now say READY
    expect(app_page.locator("button:has-text('Mark READY')")).to_be_visible(timeout=5000)


def test_mobile_fab_visible(app_page, seeded, live_server):
    app_page.set_viewport_size({"width": 375, "height": 667})
    app_page.goto(live_server + "/")

    fab = app_page.locator('a[href="/orders/new"].btn-circle')
    expect(fab).to_be_visible(timeout=8000)


def test_fulfillment_date_is_required(app_page, seeded, live_server):
    app_page.goto(live_server + "/orders/new")
    app_page.select_option("#customer_id", str(seeded["customer_id"]))
    app_page.select_option('select[name="product_id"]', str(seeded["product_id"]))

    app_page.fill('input[name="fulfillment_date"]', "")
    app_page.click('button[type="submit"]')

    assert "/orders/new" in app_page.url


def test_order_search_via_ui(app_page, seeded, live_server):
    # Create an order for the seeded customer
    _create_order(app_page, live_server, seeded)

    app_page.goto(live_server + "/orders")
    app_page.fill('input[name="q"]', seeded["customer_name"])
    app_page.click('button:has-text("Search")')

    expect(app_page.locator(f"text={seeded['customer_name']}").first).to_be_visible(timeout=8000)
