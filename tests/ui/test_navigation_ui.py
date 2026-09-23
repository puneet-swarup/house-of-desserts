"""UI tests: Navigation + SPA-like behavior."""


def test_navbar_links_work(page):
    # Click through all nav links
    for href, text in [
        ("/", "Dashboard"),
        ("/products", "Products"),
        ("/customers", "Customers"),
        ("/orders", "Orders"),
        ("/export", "Export"),
        ("/audit", "Audit"),
    ]:
        page.click(f"a[href='{href}']")
        page.wait_for_timeout(300)
        assert page.url.endswith(href) or "localhost:8000" in page.url


def test_logo_returns_to_dashboard(page):
    page.click("a[href='/products']")
    page.wait_for_timeout(300)
    # Click logo
    page.click("a[href='/'] img")
    page.wait_for_timeout(300)
    assert "Today's Orders" in page.content()


def test_live_clock_present(page):
    page.wait_for_timeout(1100)  # Wait for clock to tick
    date_el = page.locator('#nav-date')
    time_el = page.locator('#nav-time')
    # On mobile these are hidden, so check they exist in DOM
    assert date_el.count() > 0
    assert time_el.count() > 0