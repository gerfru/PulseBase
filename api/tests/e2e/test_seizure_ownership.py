"""
E2E ownership / IDOR tests for the seizure diary mutation endpoints.

These run against the real test stack and DB (no mocks), so they exercise the
actual `WHERE id = $1 AND user_id = $2` filter in db/seizures.py under the real
garmin_app DB role — the cross-user isolation that unit tests (mocked pool)
cannot prove.
"""

import json
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


async def _seizure_notes(seizure_id: int):
    from tests.e2e.conftest import _make_db_conn

    conn = await _make_db_conn()
    try:
        return await conn.fetchrow(
            "SELECT notes FROM seizure_events WHERE id = $1", seizure_id
        )
    finally:
        await conn.close()


async def test_seizure_idor_cross_user_blocked(idor_seizure_pair):
    """User B cannot PATCH or DELETE user A's seizure — both return 404 and the
    row stays intact."""
    sid = idor_seizure_pair["seizure_id"]
    attacker = idor_seizure_pair["userB"]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(base_url=BASE_URL)
        await _login(ctx, attacker["email"], attacker["password"])

        delete_resp = await ctx.request.delete(f"{BASE_URL}/api/seizures/{sid}")
        assert delete_resp.status == 404, (
            f"attacker DELETE should be 404, got {delete_resp.status}"
        )

        patch_resp = await ctx.request.patch(
            f"{BASE_URL}/api/seizures/{sid}",
            data=json.dumps({"occurred_at": "2020-01-01T00:00:00Z", "notes": "HACKED"}),
            headers={"Content-Type": "application/json"},
        )
        assert patch_resp.status == 404, (
            f"attacker PATCH should be 404, got {patch_resp.status}"
        )

        await browser.close()

    # The row must still exist and be unchanged.
    row = await _seizure_notes(sid)
    assert row is not None, "seizure row was deleted by a non-owner"
    assert row["notes"] == "ORIGINAL", "seizure row was modified by a non-owner"


async def test_seizure_owner_can_delete(idor_seizure_pair):
    """Positive control: the owner CAN delete their own seizure (the ownership
    filter is not over-restrictive)."""
    sid = idor_seizure_pair["seizure_id"]
    owner = idor_seizure_pair["userA"]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(base_url=BASE_URL)
        await _login(ctx, owner["email"], owner["password"])

        delete_resp = await ctx.request.delete(f"{BASE_URL}/api/seizures/{sid}")
        assert delete_resp.status == 200, (
            f"owner DELETE should be 200, got {delete_resp.status}"
        )

        await browser.close()

    row = await _seizure_notes(sid)
    assert row is None, "owner DELETE did not remove the row"
