"""
E2E ownership / IDOR test for the activity detail endpoint.

Runs against the real test stack and DB (no mocks): exercises the actual
`WHERE a.id = $1 AND a.user_id = $2` filter in db/activities.py under the
real garmin_app DB role — cross-user isolation that unit tests cannot prove.
"""

import os

import pytest
from playwright.async_api import async_playwright

from tests.e2e.conftest import BASE_URL

pytestmark = pytest.mark.skipif(
    not os.getenv("CI_HAS_DATA"),
    reason="requires live test DB with CI_HAS_DATA=true",
)


async def _login(ctx, email: str, password: str):
    p = await ctx.new_page()
    await p.goto("/login")
    await p.fill("input[name=email]", email)
    await p.fill("input[name=password]", password)
    await p.click("button[type=submit]")
    await p.wait_for_url("**/dashboard", timeout=10000)
    return p


async def test_activity_idor_cross_user_blocked(idor_activity_pair):
    """User B's GET /api/activities/{id} returns 404 for User A's activity."""
    aid = idor_activity_pair["activity_id"]
    attacker = idor_activity_pair["userB"]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(base_url=BASE_URL)
        await _login(ctx, attacker["email"], attacker["password"])

        resp = await ctx.request.get(f"{BASE_URL}/api/activities/{aid}")
        assert resp.status == 404, (
            f"attacker GET /api/activities/{aid} should be 404, got {resp.status}"
        )

        await browser.close()
