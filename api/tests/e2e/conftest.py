import os
import pathlib
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
    """Session-scoped: login once, share page across tests.
    Tests using this fixture must navigate to their target page explicitly.
    For a completely unauthenticated context use an isolated browser (see test_account_export_unauthenticated_redirects_to_login)."""
    p = await browser_context.new_page()
    await p.goto("/login")
    await p.fill("input[name=email]", TEST_EMAIL)
    await p.fill("input[name=password]", TEST_PASSWORD)
    await p.click("button[type=submit]")
    await p.wait_for_url("**/dashboard", timeout=10000)
    yield p
    await p.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture a screenshot when an E2E test fails."""
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.failed:
        page: Page | None = item.funcargs.get(
            "authenticated_page"
        ) or item.funcargs.get("page")
        if page is not None:
            out_dir = pathlib.Path("test-results")
            out_dir.mkdir(exist_ok=True)
            safe_name = item.nodeid.replace("/", "_").replace("::", "__")
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(page.screenshot(path=out_dir / f"{safe_name}.png"))
                else:
                    loop.run_until_complete(
                        page.screenshot(path=out_dir / f"{safe_name}.png")
                    )
            except Exception:
                pass
