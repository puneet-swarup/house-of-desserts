"""UI tests: Today page dispatch + production."""

from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import expect

from app.config import get_settings


def _today_fulfillment() -> str:
    """
    'Today at 15:00' in the BUSINESS timezone, not the runner's.
    On UTC runners, the naive date is one day behind IST between
    18:30 UTC and midnight UTC — which is why this must be tz-aware.
    """
    tz = ZoneInfo(get_settings().business_timezone)
    return datetime.now(tz).strftime("%Y-%m-%d") + "T15:00"


def _create_today_order(app_page, live_server, seeded):
    app_page.goto(live_server + "/orders/new")
    app_page.select_option("#customer_id", str(seeded["customer_id"]))
    app_page.fill('input[name="fulfillment_date"]', _today_fulfillment())
    app_page.select_option('select[name="product_id"]', str(seeded["product_id"]))
    app_page.fill('input[name="quantity"]', "2")
    app_page.click('button[type="submit"]')
    expect(app_page.locator("h2:has-text('Payments')")).to_be_visible(timeout=10000)


def test_today_page_loads(app_page, seeded, live_server):
    app_page.goto(live_server + "/today")
    expect(app_page.locator("h1:has-text('Today')")).to_be_visible(timeout=8000)


def test_dispatch_shows_today_order(app_page, seeded, live_server):
    _create_today_order(app_page, live_server, seeded)

    app_page.goto(live_server + "/today")
    expect(app_page.locator("h2:has-text('Dispatch')")).to_be_visible()
    expect(app_page.locator(f"text={seeded['customer_name']}").first).to_be_visible(timeout=8000)


def test_production_shows_aggregated_sku(app_page, seeded, live_server):
    _create_today_order(app_page, live_server, seeded)

    app_page.goto(live_server + "/today")
    expect(app_page.locator("h2:has-text('Production')")).to_be_visible()
    expect(app_page.locator(f"text={seeded['product_sku']}").first).to_be_visible(timeout=8000)
