"""UI tests: /reports page, generation, download links."""

from playwright.sync_api import expect


def test_reports_page_loads(app_page, seeded, live_server):
    app_page.goto(live_server + "/reports")
    expect(app_page.locator("h1:has-text('Monthly Reports')")).to_be_visible(timeout=8000)


def test_generate_report_creates_download_links(app_page, seeded, live_server):
    app_page.goto(live_server + "/reports")

    # Pick a month and year, submit
    app_page.select_option('select[name="month"]', "9")
    app_page.select_option('select[name="year"]', "2026")
    app_page.click('button[type="submit"]')

    # Success alert appears
    expect(app_page.locator("text=generated successfully")).to_be_visible(timeout=10000)

    # Both download buttons should now be present for the generated month
    expect(app_page.locator("a:has-text('PDF')").first).to_be_visible()
    expect(app_page.locator("a:has-text('CSV')").first).to_be_visible()


def test_download_csv_via_ui(app_page, seeded, live_server):
    # Generate first
    app_page.goto(live_server + "/reports")
    app_page.select_option('select[name="month"]', "9")
    app_page.select_option('select[name="year"]', "2026")
    app_page.click('button[type="submit"]')
    expect(app_page.locator("text=generated successfully")).to_be_visible(timeout=10000)

    # Click the CSV link — the browser will download it, which Playwright
    # captures as a download event. We just verify the link exists and the
    # href is well-formed.
    csv_link = app_page.locator("a:has-text('CSV')").first
    href = csv_link.get_attribute("href")
    assert href and href.startswith("/reports/download/")
    assert href.endswith(".csv")
