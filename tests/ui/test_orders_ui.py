"""UI tests: Order creation + status flow via browser."""


def test_create_order_via_ui(page):
    page.click("a[href='/orders/new']")
    page.wait_for_timeout(500)

    # Select customer via search
    page.fill('#customer-search', "UI Test")
    page.wait_for_timeout(800)
    page.click("#customer-results div:first-child")
    page.wait_for_timeout(300)

    # Verify customer selected
    assert page.locator('#customer-selected-label').is_visible()

    # Select a product (first one in dropdown)
    page.select_option('select[name="product_id"]', index=1)

    # Set quantity
    page.fill('input[name="quantity"]', "2")

    # Set advance
    page.fill('input[name="advance_paid"]', "100")

    # Submit
    page.click('button[type="submit"]')
    page.wait_for_timeout(800)

    # Should be on order detail page
    assert "Items" in page.content()
    assert "Payments" in page.content()


def test_status_transition_via_ui(page):
    # Get current order (should be on detail page from previous test)
    if "CONFIRMED" in page.content():
        # Click "Mark In Progress"
        page.click("button:has-text('Mark In Progress')")
        page.wait_for_timeout(500)

        # Reload to see updated status
        page.reload()
        page.wait_for_timeout(500)
        assert "IN PROGRESS" in page.content()


def test_mobile_fab_visible(page):
    """The floating + button should be visible on mobile viewport."""
    page.set_viewport_size({"width": 375, "height": 667})  # iPhone size
    page.goto("http://localhost:8000")
    page.wait_for_timeout(500)

    fab = page.locator('a[href="/orders/new"].btn-circle')
    assert fab.is_visible()