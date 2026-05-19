"""
E2E smoke tests — run against the local test stack (port 8001).

Prerequisites:
    make test-env-up
    make test-seed
    TEST_EMAIL=you@example.com TEST_PASSWORD=xxx make test-e2e
"""


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


async def test_logout(authenticated_page):
    await authenticated_page.click("button[type=submit]:has-text('Abmelden')")
    await authenticated_page.wait_for_url("**/login", timeout=5000)
    assert "/login" in authenticated_page.url


# ── Dashboard tabs ────────────────────────────────────────────────────────────


async def test_training_tab_shows_chart(authenticated_page):
    await authenticated_page.click("[data-tab='training']")
    canvas = authenticated_page.locator("#weekly-chart")
    await canvas.wait_for(state="visible", timeout=5000)


async def test_verlauf_tab_shows_charts(authenticated_page):
    await authenticated_page.click("[data-tab='verlauf']")
    await authenticated_page.locator("#steps-chart").wait_for(
        state="visible", timeout=5000
    )
    await authenticated_page.locator("#battery-chart").wait_for(
        state="visible", timeout=5000
    )


async def test_erholung_tab_shows_charts(authenticated_page):
    await authenticated_page.click("[data-tab='erholung']")
    await authenticated_page.locator("#sleep-chart").wait_for(
        state="visible", timeout=5000
    )
    await authenticated_page.locator("#hrv-trend-chart").wait_for(
        state="visible", timeout=5000
    )


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
    dialog = authenticated_page.locator("#formula-dialog")
    # Click first clickable score element in hero card
    score_link = authenticated_page.locator("[data-formula]").first
    if await score_link.count() > 0:
        await score_link.click()
        await dialog.wait_for(state="visible", timeout=3000)


# ── Other pages ───────────────────────────────────────────────────────────────


async def test_ml_insights_page_loads(authenticated_page):
    await authenticated_page.goto("/ml/anomaly")
    await authenticated_page.wait_for_load_state("networkidle")
    assert authenticated_page.url.endswith("/ml/anomaly")


async def test_activity_detail_page_loads(authenticated_page):
    # Navigate to first activity if any exist
    await authenticated_page.goto("/dashboard")
    activity_link = authenticated_page.locator("a[href^='/activity/']").first
    if await activity_link.count() > 0:
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
    toggle = authenticated_page.locator("#theme-toggle, input[name='theme']").first
    if await toggle.count() > 0:
        await toggle.click()
        await authenticated_page.wait_for_timeout(300)
        classes_after = await html.get_attribute("class") or ""
        assert classes_after != classes_before


# ── Sync button ───────────────────────────────────────────────────────────────


async def test_sync_button_shows_feedback(authenticated_page):
    await authenticated_page.goto("/dashboard")
    await authenticated_page.locator("#sync-btn").click()
    # Toast or button state change should appear within 3s
    toast = authenticated_page.locator("#toast")
    await toast.wait_for(state="visible", timeout=3000)
