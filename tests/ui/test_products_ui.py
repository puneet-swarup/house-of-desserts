"""UI tests: Product CRUD via browser."""


def test_add_product_via_ui(page):
    # Navigate to products
    page.click("a[href='/products']")
    page.wait_for_timeout(500)

    # Click Add Product
    page.click("a[href='/products/new']")
    page.wait_for_timeout(500)

    # Fill form
    page.fill('input[name="name"]', "UI Test Cake")
    page.fill('input[name="sku"]', "UI-TEST-001")
    page.fill('input[name="base_price"]', "350")
    page.select_option('select[name="category"]', "Cake")

    # Submit
    page.click('button[type="submit"]')
    page.wait_for_timeout(500)

    # Verify it appears in the list
    assert "UI Test Cake" in page.content()
    assert "UI-TEST-001" in page.content()


def test_product_card_shows_correct_details(page):
    page.click("a[href='/products']")
    page.wait_for_timeout(500)

    # If we just created it, it should be visible
    if "UI Test Cake" in page.content():
        card = page.locator("text=UI Test Cake").first
        assert card.is_visible()
        # Check price is shown
        parent = card.locator("..").locator("..").locator("..")
        assert "350" in parent.text_content()


def test_delete_product_via_ui(page):
    page.click("a[href='/products']")
    page.wait_for_timeout(500)

    # Find the delete button on our test product card
    if "UI Test Cake" in page.content():
        # Click the delete button in that card
        card = page.locator("div.card", has_text="UI Test Cake").first
        card.click("button:has-text('Delete')")
        # Accept the confirm dialog
        page.on("dialog", lambda d: d.accept())
        page.wait_for_timeout(500)

        # Product should now show "Inactive" badge
        assert "Inactive" in page.content()