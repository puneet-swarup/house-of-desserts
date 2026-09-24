"""UI tests: WhatsApp message modal."""

from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import expect

from app.config import get_settings


def _today_fulfillment() -> str:
    tz = ZoneInfo(get_settings().business_timezone)
    return datetime.now(tz).strftime("%Y-%m-%d") + "T15:00"


def _create_order(app_page, live_server, seeded):
    app_page.goto(live_server + "/orders/new")
    app_page.select_option("#customer_id", str(seeded["customer_id"]))
    app_page.fill('input[name="fulfillment_date"]', _today_fulfillment())
    app_page.select_option('select[name="product_id"]', str(seeded["product_id"]))
    app_page.fill('input[name="quantity"]', "1")
    app_page.click('button[type="submit"]')
    expect(app_page.locator("h2:has-text('Payments')")).to_be_visible(timeout=10000)


def test_message_button_opens_modal(app_page, seeded, live_server):
    _create_order(app_page, live_server, seeded)

    app_page.click('button:has-text("Message Customer")')
    expect(app_page.locator("dialog#wa-modal")).to_be_visible(timeout=5000)
    expect(app_page.locator("#wa-text")).not_to_have_value("")


def test_message_modal_preview_updates(app_page, seeded, live_server):
    _create_order(app_page, live_server, seeded)

    app_page.click('button:has-text("Message Customer")')
    expect(app_page.locator("#wa-text")).to_be_visible()

    # Change the trigger and expect the text to change
    first = app_page.locator("#wa-text").input_value()
    app_page.select_option("#wa-trigger", "ready")
    app_page.wait_for_timeout(200)
    second = app_page.locator("#wa-text").input_value()
    assert first != second


def test_message_button_available_on_list(app_page, seeded, live_server):
    """After creating an order, the list page has a 💬 Message button."""
    _create_order(app_page, live_server, seeded)

    app_page.goto(live_server + "/orders")
    expect(app_page.locator('button:has-text("💬 Message")').first).to_be_visible(timeout=8000)

    # Clicking it opens the modal
    app_page.locator('button:has-text("💬 Message")').first.click()
    expect(app_page.locator("dialog#wa-modal")).to_be_visible(timeout=5000)
    expect(app_page.locator("#wa-text")).not_to_have_value("")


def test_message_modal_prefers_ready_after_status_change(app_page, seeded, live_server):
    """After marking READY, the 💬 button opens with 'Order is ready' preselected."""
    _create_order(app_page, live_server, seeded)

    app_page.goto(live_server + "/orders")

    # Walk the workflow: CONFIRMED -> IN_PROGRESS -> READY.
    # Click whichever "Mark X" button is current — two steps.
    for _ in range(2):
        btn = app_page.locator('button:has-text("Mark ")').first
        btn.click()
        app_page.wait_for_timeout(900)

    # Now click 💬
    app_page.locator('button:has-text("💬 Message")').first.click()
    expect(app_page.locator("dialog#wa-modal")).to_be_visible(timeout=5000)

    trigger_value = app_page.locator("#wa-trigger").input_value()
    assert trigger_value == "ready"
