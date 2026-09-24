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
    _create_order(app_page, live_server, seeded)

    app_page.select_option('select[name="status"]', "IN_PROGRESS")
    app_page.click('button:has-text("Update")')

    expect(app_page.locator("text=IN PROGRESS").first).to_be_visible(timeout=8000)


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
