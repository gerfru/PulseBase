"""E2E tests for public (unauthenticated) pages and the epilepsy page."""

from playwright.async_api import async_playwright

from tests.e2e.conftest import BASE_URL


# ── Öffentliche Seiten (kein Auth erforderlich) ───────────────────────────────


async def test_privacy_page_loads(page):
    await page.goto("/privacy")
    await page.wait_for_load_state("networkidle")
    assert "/privacy" in page.url
    await page.locator("h1").wait_for(state="visible", timeout=5000)


async def test_terms_page_loads(page):
    await page.goto("/terms")
    await page.wait_for_load_state("networkidle")
    assert "/terms" in page.url
    await page.locator("h1").wait_for(state="visible", timeout=5000)


async def test_imprint_page_loads(page):
    await page.goto("/imprint")
    await page.wait_for_load_state("networkidle")
    assert "/imprint" in page.url
    await page.locator("h1").wait_for(state="visible", timeout=5000)


async def test_accessibility_page_loads(page):
    await page.goto("/accessibility")
    await page.wait_for_load_state("networkidle")
    assert "/accessibility" in page.url
    await page.locator("h1").wait_for(state="visible", timeout=5000)


# ── Epilepsie-Seite ───────────────────────────────────────────────────────────


async def test_epilepsy_page_redirects_when_mode_disabled(authenticated_page):
    await authenticated_page.goto("/epilepsy")
    await authenticated_page.wait_for_url("**/settings**", timeout=5000)
    assert "/settings" in authenticated_page.url


async def test_epilepsy_page_loads_when_mode_enabled(epilepsy_test_user):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(base_url=BASE_URL)
        p = await ctx.new_page()
        await p.goto("/login")
        await p.fill("input[name=email]", epilepsy_test_user["email"])
        await p.fill("input[name=password]", epilepsy_test_user["password"])
        await p.click("button[type=submit]")
        await p.wait_for_url("**/dashboard", timeout=10000)
        await p.goto("/epilepsy")
        await p.wait_for_load_state("networkidle")
        assert "/epilepsy" in p.url
        await p.locator("h1").wait_for(state="visible", timeout=5000)
        await browser.close()
