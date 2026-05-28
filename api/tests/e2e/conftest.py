import os
import pytest
from playwright.async_api import async_playwright, BrowserContext, Page

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8001")
TEST_EMAIL = os.getenv("TEST_EMAIL", "")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "")  # pragma: allowlist secret


@pytest.fixture(scope="session")
async def browser_context():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(base_url=BASE_URL)
        yield ctx
        await browser.close()


@pytest.fixture
async def page(browser_context: BrowserContext) -> Page:
    p = await browser_context.new_page()
    yield p
    await p.close()


@pytest.fixture(scope="session")
async def authenticated_page(browser_context: BrowserContext) -> Page:
    """Shared authenticated page — login happens once per test session."""
    p = await browser_context.new_page()
    await p.goto("/login")
    await p.fill("input[name=email]", TEST_EMAIL)
    await p.fill("input[name=password]", TEST_PASSWORD)
    await p.click("button[type=submit]")
    await p.wait_for_url("**/dashboard", timeout=10000)
    yield p
    await p.close()
