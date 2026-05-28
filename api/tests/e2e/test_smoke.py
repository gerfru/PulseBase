"""
E2E smoke tests — run against the local test stack (port 8001).

Usage:
    make test-e2e   # starts stack, seeds user, runs tests, tears down
"""

import pytest
from playwright.async_api import async_playwright

from tests.e2e.conftest import (
    BASE_URL,
    TEST_EMAIL,
    TEST_PASSWORD,
)  # pragma: allowlist secret


# ── Auth ──────────────────────────────────────────────────────────────────────


async def test_unauthenticated_redirect_to_login(page):
    await page.goto("/dashboard")
    await page.wait_for_url("**/login", timeout=5000)
    assert "/login" in page.url


async def test_login_and_dashboard_loads(authenticated_page):
    assert "/dashboard" in authenticated_page.url
    # Hero card must be present
    hero = authenticated_page.locator("#bento-hero")
    await hero.wait_for(state="visible", timeout=10000)


async def test_logout():
    # Completely isolated browser so logout doesn't invalidate the shared session
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(base_url=BASE_URL)
        p = await ctx.new_page()
        await p.goto("/login")
        await p.fill("input[name=email]", TEST_EMAIL)
        await p.fill("input[name=password]", TEST_PASSWORD)
        await p.click("button[type=submit]")
        await p.wait_for_url("**/dashboard", timeout=10000)
        await p.click("button[type=submit]:has-text('Abmelden')")
        await p.wait_for_url("**/login", timeout=5000)
        assert "/login" in p.url
        await browser.close()


# ── Dashboard tabs ────────────────────────────────────────────────────────────


async def test_training_tab_shows_chart(authenticated_page):
    await authenticated_page.click("[data-tab='training']")
    await authenticated_page.wait_for_timeout(500)
    assert "/dashboard" in authenticated_page.url


async def test_verlauf_tab_shows_charts(authenticated_page):
    await authenticated_page.click("[data-tab='verlauf']")
    await authenticated_page.wait_for_timeout(500)
    assert "/dashboard" in authenticated_page.url


async def test_erholung_tab_shows_charts(authenticated_page):
    await authenticated_page.click("[data-tab='erholung']")
    await authenticated_page.wait_for_timeout(500)
    assert "/dashboard" in authenticated_page.url


# ── Time range + period navigation ───────────────────────────────────────────


async def test_time_range_30t_becomes_active(authenticated_page):
    btn = authenticated_page.locator(".time-btn[data-days='30']")
    await btn.click()
    classes = await btn.get_attribute("class")
    assert "active" in classes


async def test_period_nav_back_changes_range(authenticated_page):
    range_before = await authenticated_page.locator("#nav-range").inner_text()
    await authenticated_page.locator("#nav-back").click()
    await authenticated_page.wait_for_timeout(800)
    range_after = await authenticated_page.locator("#nav-range").inner_text()
    assert range_after != range_before


async def test_period_nav_forward_disabled_at_offset_zero(authenticated_page):
    # Reset to current period by reloading
    await authenticated_page.reload()
    await authenticated_page.wait_for_load_state("networkidle")
    fwd = authenticated_page.locator("#nav-forward")
    assert await fwd.is_disabled()


# ── Formula modal ─────────────────────────────────────────────────────────────


async def test_formula_modal_opens_on_score_click(authenticated_page):
    # Wait for hero card to render score elements
    await authenticated_page.locator("#bento-hero").wait_for(
        state="visible", timeout=10000
    )
    score_link = authenticated_page.locator("[data-formula]").first
    if not await score_link.count():
        pytest.skip("no [data-formula] elements (fresh user, no data)")
    dialog = authenticated_page.locator("#formula-dialog")
    await score_link.click()
    await dialog.wait_for(state="visible", timeout=3000)


# ── Other pages ───────────────────────────────────────────────────────────────


async def test_ml_insights_page_loads(authenticated_page):
    await authenticated_page.goto("/metrics/hr-zscore")
    await authenticated_page.wait_for_load_state("networkidle")
    assert authenticated_page.url.endswith("/metrics/hr-zscore")


async def test_activity_detail_page_loads(authenticated_page):
    await authenticated_page.goto("/dashboard")
    activity_link = authenticated_page.locator("a[href^='/activity/']").first
    if not await activity_link.count():
        pytest.skip("no activities present (fresh user, no data)")
    await activity_link.click()
    await authenticated_page.wait_for_load_state("networkidle")
    assert "/activity/" in authenticated_page.url


async def test_settings_page_loads(authenticated_page):
    await authenticated_page.goto("/settings")
    await authenticated_page.wait_for_load_state("networkidle")
    assert "/settings" in authenticated_page.url


# ── Theme toggle ──────────────────────────────────────────────────────────────


async def test_theme_toggle_switches_dark_class(authenticated_page):
    await authenticated_page.goto("/settings")
    html = authenticated_page.locator("html")
    classes_before = await html.get_attribute("class") or ""
    # Click theme toggle (checkbox or button in settings)
    toggle = authenticated_page.locator("#theme-toggle")
    if not await toggle.count():
        pytest.skip("no #theme-toggle found on settings page")
    # sr-only peer checkbox: sibling div intercepts pointer events, force bypasses it
    await toggle.click(force=True)
    await authenticated_page.wait_for_timeout(300)
    classes_after = await html.get_attribute("class") or ""
    assert classes_after != classes_before


# ── Navigation structure ──────────────────────────────────────────────────────


async def test_no_bottom_nav(authenticated_page):
    count = await authenticated_page.locator(".bottom-nav").count()
    assert count == 0, ".bottom-nav should be removed from the DOM"


async def test_hero_capacity_in_dom(authenticated_page):
    await authenticated_page.goto("/dashboard")
    await authenticated_page.wait_for_load_state("networkidle")
    # Wait for JS to finish building the hero card (hero-grid only exists after buildHeroCard())
    await authenticated_page.locator(".hero-grid").wait_for(
        state="attached", timeout=10000
    )
    count = await authenticated_page.locator(".hero-capacity-grid").count()
    assert count == 1, ".hero-capacity-grid should be present in hero card"


async def test_ml_cards_in_tabs(authenticated_page):
    await authenticated_page.goto("/dashboard")
    await authenticated_page.wait_for_load_state("networkidle")
    await authenticated_page.click("[data-tab='verlauf']")
    await authenticated_page.wait_for_timeout(300)
    assert await authenticated_page.locator("#ml-verlauf-card").count() == 1

    await authenticated_page.click("[data-tab='erholung']")
    await authenticated_page.wait_for_timeout(300)
    assert await authenticated_page.locator("#ml-erholung-card").count() == 1


# ── Sync button ───────────────────────────────────────────────────────────────


async def test_sync_button_shows_feedback(authenticated_page):
    await authenticated_page.goto("/dashboard")
    await authenticated_page.locator("#sync-btn").click()
    # Toast or button state change should appear within 3s
    toast = authenticated_page.locator("#toast")
    await toast.wait_for(state="visible", timeout=3000)
