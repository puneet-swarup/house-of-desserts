"""UI tests: customer detail — stat cards."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from playwright.sync_api import expect

from app.config import get_settings


def _create_order_for(app_page, live_server, seeded):
    tz = ZoneInfo(get_settings().business_timezone)
    dt = (datetime.now(tz) + timedelta(days=1)).strftime("%Y-%m-%dT12:00")

    app_page.goto(live_server + "/orders/new")
    app_page.select_option("#customer_id", str(seeded["customer_id"]))
    app_page.fill('input[name="fulfillment_date"]', dt)
    app_page.select_option('select[name="product_id"]', str(seeded["product_id"]))
    app_page.fill('input[name="quantity"]', "1")
    app_page.click('button[type="submit"]')
    expect(app_page.locator("h2:has-text('Payments')")).to_be_visible(timeout=10000)


def test_customer_detail_shows_stat_cards(app_page, seeded, live_server):
    app_page.goto(live_server + f"/customers/{seeded['customer_id']}")

    expect(app_page.locator("text=Lifetime value")).to_be_visible(timeout=8000)
    expect(app_page.locator("text=Orders").first).to_be_visible()
    expect(app_page.locator("text=Outstanding")).to_be_visible()
    expect(app_page.locator("text=Avg order")).to_be_visible()


def test_customer_stats_update_after_order(app_page, seeded, live_server):
    # Create an order for this customer
    _create_order_for(app_page, live_server, seeded)

    # Visit customer detail
    app_page.goto(live_server + f"/customers/{seeded['customer_id']}")
    expect(app_page.locator("text=Lifetime value")).to_be_visible(timeout=8000)

    # The Orders card should show a count of at least 1
    # Find the card containing "Orders", read its digit text
    card = app_page.locator("div.card", has_text="Orders").first
    text = card.text_content() or ""
    digits = [int(c) for c in text if c.isdigit()]
    assert any(d >= 1 for d in digits), f"Orders count didn't update: {text}"
