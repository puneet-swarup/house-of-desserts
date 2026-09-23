"""UI tests: Customer CRUD + addresses via browser."""


def test_add_customer_with_address(page):
    page.click("a[href='/customers']")
    page.wait_for_timeout(500)
    page.click("a[href='/customers/new']")
    page.wait_for_timeout(500)

    # Fill customer details
    page.fill('input[name="name"]', "UI Test Customer")
    page.fill('input[name="phone"]', "+91 12345 67890")

    # Fill address (first row)
    page.fill('input[name="addr_new_label"]', "Home")
    page.fill('input[name="addr_new_line"]', "42 UI Test Street, Mumbai")
    # Check default
    page.check'input[name="addr_new_default"]')

    # Submit
    page.click('button[type="submit"]')
    page.wait_for_timeout(500)

    # Verify in list
    assert "UI Test Customer" in page.content()
    assert "+91 12345 67890" in page.content()


def test_customer_detail_shows_address(page):
    page.click("a[href='/customers']")
    page.wait_for_timeout(500)

    # Click on the customer name link
    if "UI Test Customer" in page.content():
        page.click("a:has-text('UI Test Customer')")
        page.wait_for_timeout(500)

        # Verify address is shown
        assert "42 UI Test Street" in page.content()
        assert "Home" in page.content()


def test_customer_search_in_order_form(page):
    # Navigate directly to new order form
    page.goto("http://localhost/orders/new")
    page.wait_for_timeout(500)

    # Type in customer search
    page.fill('#customer-search', "UI Test")
    page.wait_for_timeout(1000)  # Wait for HTMX debounce (300ms) + response

    # Dropdown should show the customer
    results = page.locator('#customer-results')
    assert "UI Test Customer" in results.text_content()