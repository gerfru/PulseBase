"""
CSRF failure path tests.
Overrides the conftest _bypass_csrf fixture so that verify_csrf_token
runs for real — session has no csrf_token → all CSRF checks fail.
"""

import sys
import types
import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_USER


def _fake_libre_module():
    """Minimal libre.client stub needed for the import inside libre_link."""
    mod = types.ModuleType("libre.client")
    mod.LibreAuthError = type("LibreAuthError", (Exception,), {})
    mod.authenticate = lambda *a, **kw: None
    return mod


@pytest.fixture(autouse=True)
def _bypass_csrf():
    """Override conftest bypass — real CSRF validation for these tests."""
    yield


# ── auth/login ───────────────────────────────────────────────────────────────


async def test_login_csrf_failure_returns_400(client):
    r = await client.post(
        "/login",
        data={
            "email": "x@example.com",
            "password": "wrong",  # pragma: allowlist secret
        },
    )
    assert r.status_code == 400
    assert "Ungültige Anfrage" in r.text


# ── auth/register ─────────────────────────────────────────────────────────────


async def test_register_csrf_failure_returns_400(client):
    r = await client.post(
        "/register",
        data={
            "name": "User",
            "email": "x@example.com",
            "password": "strongpassword1",  # pragma: allowlist secret
            "password_confirm": "strongpassword1",  # pragma: allowlist secret
            "consent_health": "on",
            "consent_terms": "on",
            "consent_age": "on",
        },
    )
    assert r.status_code == 400
    assert "Ungültige Anfrage" in r.text


# ── logout ────────────────────────────────────────────────────────────────────


async def test_logout_csrf_failure_returns_403(client):
    r = await client.post("/logout")
    assert r.status_code == 403
    assert "Ungültige Anfrage" in r.text


# ── account/delete ────────────────────────────────────────────────────────────


async def test_account_delete_csrf_failure_returns_400(client):
    with patch("src.routes.account.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post(
            "/account/delete",
            data={"email": TEST_USER["email"], "password": "any"},
        )
    assert r.status_code == 400
    assert "Ungültige Anfrage" in r.text


# ── auth/reset ────────────────────────────────────────────────────────────────


async def test_reset_password_csrf_failure_returns_403(client):
    r = await client.post(
        "/auth/reset/any-token",
        data={
            "password": "newpassword1",  # pragma: allowlist secret
            "password_confirm": "newpassword1",  # pragma: allowlist secret
        },
    )
    assert r.status_code == 403
    assert "Ungültige Anfrage" in r.text


# ── auth/resend-verify ────────────────────────────────────────────────────────


async def test_resend_verify_csrf_failure_returns_400(client):
    r = await client.post("/auth/resend-verify", data={"email": "x@example.com"})
    assert r.status_code == 400
    assert "Ungültige Anfrage" in r.text


# ── auth/reset-request ────────────────────────────────────────────────────────


async def test_reset_request_csrf_failure_returns_400(client):
    r = await client.post("/auth/reset-request", data={"email": "x@example.com"})
    assert r.status_code == 400
    assert "Ungültige Anfrage" in r.text


# ── garmin/link ───────────────────────────────────────────────────────────────


async def test_garmin_link_csrf_failure_returns_403(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post(
            "/garmin/link",
            data={
                "garmin_email": "t@garmin.com",
                "garmin_password": "pass",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 403
    assert "Ungültige Anfrage" in r.text


# ── garmin/unlink ─────────────────────────────────────────────────────────────


async def test_garmin_unlink_csrf_failure_returns_403(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post("/garmin/unlink", data={"csrf_token": ""})
    assert r.status_code == 403


# ── libre/link ────────────────────────────────────────────────────────────────


async def test_libre_link_csrf_failure_returns_403(client):
    with (
        patch.dict(sys.modules, {"libre.client": _fake_libre_module()}),
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
    ):
        r = await client.post(
            "/libre/link",
            data={
                "libre_email": "t@libre.com",
                "libre_password": "pass",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 403
    assert "Ungültige Anfrage" in r.text


# ── libre/unlink ──────────────────────────────────────────────────────────────


async def test_libre_unlink_csrf_failure_returns_403(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post("/libre/unlink", data={"csrf_token": ""})
    assert r.status_code == 403
