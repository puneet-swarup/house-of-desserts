"""UI tests: Nav links, clock, FAB."""

from playwright.sync_api import expect


def test_navbar_links_work(app_page, seeded, live_server):
    for href, heading_text in [
        ("/products", "Products"),
        ("/customers", "Customers"),
        ("/orders", "Orders"),
    ]:
        app_page.goto(live_server + "/")
        app_page.click(f"a[href='{href}']")
        expect(app_page.locator(f"h1:has-text('{heading_text}')")).to_be_visible(timeout=8000)


def test_logo_returns_to_today(app_page, seeded, live_server):
    app_page.goto(live_server + "/products")
    app_page.click("a[href='/today'] img")
    expect(app_page.locator("h1:has-text('Today')")).to_be_visible(timeout=8000)


def test_live_clock_present(app_page, seeded, live_server):
    app_page.goto(live_server + "/")
    expect(app_page.locator("#nav-date")).to_have_count(1)
    expect(app_page.locator("#nav-time")).to_have_count(1)
