"""UI tests: Customer CRUD + addresses."""

from playwright.sync_api import expect


def test_add_customer_with_address(app_page, seeded, live_server):
    app_page.goto(live_server + "/customers/new")

    app_page.fill('input[name="name"]', "UI Added Customer")
    app_page.fill('input[name="phone"]', "+91 55555 11111")
    app_page.fill('textarea[name="addr_new_line"]', "42 UI Test Street, Mumbai")

    app_page.click('button[type="submit"]')

    expect(app_page.locator("td:has-text('UI Added Customer')")).to_be_visible(timeout=8000)


def test_customer_detail_shows_address(app_page, seeded, live_server):
    app_page.goto(live_server + f"/customers/{seeded['customer_id']}/edit")

    # New-address row is hidden until + Add Address is clicked
    app_page.click("button:has-text('+ Add Address')")
    app_page.fill('textarea[name="addr_new_line"]', "7 Seeded Lane, Bangalore")
    app_page.click('button[type="submit"]')

    app_page.goto(live_server + f"/customers/{seeded['customer_id']}")
    expect(app_page.locator("text=Seeded Lane")).to_be_visible(timeout=8000)


def test_customer_search_by_name(app_page, seeded, live_server):
    app_page.goto(live_server + "/customers")
    app_page.fill('input[name="q"]', "UI Customer")
    app_page.click('button[type="submit"]')

    expect(app_page.locator(f"td:has-text('{seeded['customer_name']}')")).to_be_visible(timeout=8000)


def test_customer_search_empty_state(app_page, seeded, live_server):
    app_page.goto(live_server + "/customers")
    app_page.fill('input[name="q"]', "zzz-nobody-zzz")
    app_page.click('button[type="submit"]')

    expect(app_page.locator("text=No matches")).to_be_visible(timeout=8000)


def test_customer_form_first_row_is_default(app_page, seeded, live_server):
    app_page.goto(live_server + "/customers/new")

    hidden = app_page.locator('input[name="addr_new_default"]').first
    expect(hidden).to_have_value("1")


def test_customer_delete_flow(app_page, seeded, live_server):
    app_page.goto(live_server + f"/customers/{seeded['customer_id']}")

    app_page.on("dialog", lambda d: d.accept())
    app_page.click('button:has-text("Delete")')

    expect(app_page.locator("h1:has-text('Customers')")).to_be_visible(timeout=8000)