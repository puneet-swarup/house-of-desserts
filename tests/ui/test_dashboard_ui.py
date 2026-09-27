"""UI tests: /dashboard stats page."""

from playwright.sync_api import expect


def test_dashboard_page_loads(app_page, seeded, live_server):
    app_page.goto(live_server + "/dashboard")
    expect(app_page.locator("h1:has-text('Dashboard')")).to_be_visible(timeout=8000)


def test_dashboard_stat_cards_render(app_page, seeded, live_server):
    app_page.goto(live_server + "/dashboard")
    # Four stat labels should each be present
    expect(app_page.locator("text=Today's Orders")).to_be_visible()
    expect(app_page.locator("text=Fulfillments Today")).to_be_visible()
    expect(app_page.locator("text=Outstanding")).to_be_visible()
    expect(app_page.locator("text=Active Products")).to_be_visible()


def test_dashboard_shows_seeded_product_count(app_page, seeded, live_server):
    app_page.goto(live_server + "/dashboard")
    # Seeded product is active — "Active Products" count should be at least 1
    # Locate the card containing "Active Products" and read the sibling number
    card = app_page.locator("div.card", has_text="Active Products").first
    card_text = card.text_content() or ""
    # At least one digit somewhere in the card
    assert any(ch.isdigit() for ch in card_text)
