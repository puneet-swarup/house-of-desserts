import pytest
from playwright.sync_api import Page, Browser


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    yield browser
    browser.close()
    pw.stop()


@pytest.fixture()
def page(browser):
    page = browser.new_page()
    # Point to your running dev server
    page.goto("http://localhost")
    yield page
    page.close()