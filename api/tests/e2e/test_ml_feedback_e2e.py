"""
E2E tests for the ML-feedback endpoints (UX-Review [D3-1], PR4).

These run against the real test stack and DB (no mocks), so they exercise the
actual ON CONFLICT upsert in db/ml_feedback.py and the per-user scoping of
GET /api/ml-feedback under the real garmin_app DB role — behaviour that unit
tests (mocked pool) cannot prove.

Auth uses an injected, pre-signed session cookie (make_session_cookie) instead
of the rate-limited /login form. This is the rate-limit-safe pattern for browser
auth: the whole E2E suite shares a 10/min login budget, so consuming login
requests here would flake unrelated tests. We still exercise the real
require_user → DB → ml_feedback chain.
"""

import json

from playwright.async_api import async_playwright

from tests.e2e.conftest import BASE_URL, make_session_cookie


async def _auth_ctx(pw, user_id: int, secret: str):
    browser = await pw.chromium.launch()
    ctx = await browser.new_context(base_url=BASE_URL)
    await ctx.add_cookies(
        [
            {
                "name": "session",
                "value": make_session_cookie(user_id, secret),
                "url": BASE_URL,
            }
        ]
    )
    return browser, ctx


async def _post_feedback(ctx, model: str, helpful: bool):
    return await ctx.request.post(
        f"{BASE_URL}/api/ml-feedback",
        data=json.dumps({"model": model, "helpful": helpful}),
        headers={"Content-Type": "application/json"},
    )


async def test_ml_feedback_persists_and_toggles(ml_feedback_pair, session_secret):
    """Owner posts 👍, reads it back, then 👎 overwrites it (real-DB upsert)."""
    owner = ml_feedback_pair["userA"]
    async with async_playwright() as pw:
        browser, ctx = await _auth_ctx(pw, owner["id"], session_secret)

        up = await _post_feedback(ctx, "readiness_rf", True)
        assert up.status == 200

        got = await ctx.request.get(f"{BASE_URL}/api/ml-feedback")
        assert got.status == 200
        assert (await got.json()) == {"readiness_rf": True}

        # Toggle: 👎 for the same model/day must overwrite, not duplicate.
        down = await _post_feedback(ctx, "readiness_rf", False)
        assert down.status == 200
        got2 = await ctx.request.get(f"{BASE_URL}/api/ml-feedback")
        assert (await got2.json()) == {"readiness_rf": False}

        await browser.close()


async def test_ml_feedback_is_per_user(ml_feedback_pair, session_secret):
    """User B never sees user A's feedback (per-user WHERE filter)."""
    a = ml_feedback_pair["userA"]
    b = ml_feedback_pair["userB"]
    async with async_playwright() as pw:
        browser_a, ctx_a = await _auth_ctx(pw, a["id"], session_secret)
        assert (await _post_feedback(ctx_a, "anomaly_hr", True)).status == 200
        await browser_a.close()

        browser_b, ctx_b = await _auth_ctx(pw, b["id"], session_secret)
        got = await ctx_b.request.get(f"{BASE_URL}/api/ml-feedback")
        assert got.status == 200
        assert (await got.json()) == {}, "user B must not see user A's feedback"
        await browser_b.close()


async def test_ml_feedback_invalid_model_rejected(ml_feedback_pair, session_secret):
    """An unknown model is rejected (422) — Pydantic whitelist over the wire."""
    owner = ml_feedback_pair["userA"]
    async with async_playwright() as pw:
        browser, ctx = await _auth_ctx(pw, owner["id"], session_secret)
        resp = await _post_feedback(ctx, "bogus_model", True)
        assert resp.status == 422
        await browser.close()
