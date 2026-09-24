"""UI tests: Product CRUD, SKU generation."""

from playwright.sync_api import expect


def test_add_product_via_ui(app_page, seeded, live_server):
    app_page.goto(live_server + "/products/new")

    app_page.fill('input[name="name"]', "UI Created Cake")
    app_page.fill('input[name="base_price"]', "450")
    app_page.select_option('select[name="category"]', "Cake")
    app_page.click('button[type="submit"]')

    # Text appears in both the desktop table and the mobile card; either is fine
    expect(app_page.locator("text=UI Created Cake").first).to_be_visible(timeout=8000)


def test_product_sku_autogenerates(app_page, seeded, live_server):
    app_page.goto(live_server + "/products/new")
    app_page.fill('input[name="name"]', "Chocolate Truffle Cake")
    app_page.fill('input[name="measure_value"]', "500")
    app_page.select_option('select[name="measure_unit"]', "g")

    app_page.wait_for_timeout(300)

    sku = app_page.locator('input[name="sku"]').input_value()
    assert "CHOCOLATE" in sku.upper()
    assert "500G" in sku.upper()


def test_seeded_product_visible_in_list(app_page, seeded, live_server):
    app_page.goto(live_server + "/products")
    expect(app_page.locator(f"text={seeded['product_sku']}").first).to_be_visible(timeout=8000)


def test_delete_product_via_ui(app_page, seeded, live_server):
    app_page.goto(live_server + "/products")

    app_page.on("dialog", lambda d: d.accept())

    # Click the first visible Delete button
    app_page.locator("button:has-text('Delete')").first.click()

    expect(app_page.locator("text=Inactive").first).to_be_visible(timeout=8000)
