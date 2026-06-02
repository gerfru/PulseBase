"""E2E tests for auth flows not covered by test_smoke.py:
register, email-verify, and password-reset.
"""

from itsdangerous import URLSafeTimedSerializer
from playwright.async_api import async_playwright

from tests.e2e.conftest import BASE_URL


# ── Register — isolierter Browser (kein shared-Context-Overlap mit auth'd Session) ──


async def test_register_success_redirects_to_login(clean_register_email):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(base_url=BASE_URL)
        p = await ctx.new_page()
        await p.goto("/register")
        await p.fill("input[name=name]", "E2E Tester")
        await p.fill("input[name=email]", clean_register_email)
        await p.fill("input[name=password]", "SecurePass!2026")
        await p.fill("input[name=password_confirm]", "SecurePass!2026")
        await p.check("input[name=consent_health]")
        await p.check("input[name=consent_terms]")
        await p.check("input[name=consent_age]")
        await p.click("button[type=submit]")
        await p.wait_for_url("**/login**", timeout=10000)
        assert "/login" in p.url
        await browser.close()


async def test_register_duplicate_email_shows_error(registered_test_user):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(base_url=BASE_URL)
        p = await ctx.new_page()
        await p.goto("/register")
        await p.fill("input[name=name]", "E2E Tester")
        await p.fill("input[name=email]", registered_test_user["email"])
        await p.fill("input[name=password]", "SecurePass!2026")
        await p.fill("input[name=password_confirm]", "SecurePass!2026")
        await p.check("input[name=consent_health]")
        await p.check("input[name=consent_terms]")
        await p.check("input[name=consent_age]")
        await p.click("button[type=submit]")
        await p.wait_for_load_state("networkidle")
        assert "/register" in p.url
        # Template: <div class="... text-red-300">{{ error }}</div>
        await p.locator("text=bereits registriert").wait_for(
            state="visible", timeout=5000
        )
        await browser.close()


# ── E-Mail-Verify ─────────────────────────────────────────────────────────────


async def test_email_verify_valid_token_redirects_to_login(
    page, unverified_test_user, session_secret
):
    token = URLSafeTimedSerializer(session_secret).dumps(
        unverified_test_user["id"], salt="email-verify"
    )
    await page.goto(f"/auth/verify/{token}")
    await page.wait_for_url("**/login**", timeout=10000)
    assert "verified=1" in page.url


async def test_email_verify_invalid_token_shows_error(page):
    await page.goto("/auth/verify/invalid-garbage-token-xyz")
    await page.wait_for_load_state("networkidle")
    error = page.locator("text=ungültig")
    await error.wait_for(state="visible", timeout=5000)


# ── Passwort-Reset ────────────────────────────────────────────────────────────


async def test_password_reset_request_shows_info(page, reset_test_user):
    await page.goto("/auth/reset-request")
    await page.fill("input[name=email]", reset_test_user["email"])
    await page.click("button[type=submit]")
    await page.wait_for_load_state("networkidle")
    info = page.locator("text=Falls diese E-Mail registriert ist")
    await info.wait_for(state="visible", timeout=5000)


async def test_password_reset_with_valid_token(page, reset_test_user):
    raw_token = reset_test_user["raw_token"]
    await page.goto(f"/auth/reset/{raw_token}")
    await page.wait_for_load_state("networkidle")
    await page.fill("input[name=password]", "NewPassword!2026x")
    await page.fill("input[name=password_confirm]", "NewPassword!2026x")
    await page.click("button[type=submit]")
    await page.wait_for_url("**/login**", timeout=10000)
    assert "reset=1" in page.url
