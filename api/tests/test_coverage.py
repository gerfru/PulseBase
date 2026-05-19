"""
Targeted tests to reach 100% coverage on main.py.
Covers branches not exercised by the broader test suite.
"""

import sys
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import TEST_USER


# ── _get_real_ip ──────────────────────────────────────────────────────────────


def test_get_real_ip_uses_x_forwarded_for():
    from src.main import _get_real_ip

    class FakeRequest:
        headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        client = None

    assert _get_real_ip(FakeRequest()) == "1.2.3.4"


# ── _rate_limit_exceeded_handler ──────────────────────────────────────────────


async def test_rate_limit_exceeded_handler_returns_429():
    from src.main import _rate_limit_exceeded_handler

    r = await _rate_limit_exceeded_handler(MagicMock(), MagicMock())
    assert r.status_code == 429
    assert r.body  # JSONResponse body is set


# ── require_user — user_id in session but not in DB ──────────────────────────


async def test_require_user_user_not_found_raises_needs_login():
    from src.main import require_user, NeedsLogin

    class FakeRequest:
        session = {"user_id": 99}

    with patch("src.main.get_user_by_id", AsyncMock(return_value=None)):
        with pytest.raises(NeedsLogin):
            await require_user(FakeRequest())


async def test_require_user_returns_user_when_found():
    from src.main import require_user

    class FakeRequest:
        session = {"user_id": 1}

    with patch("src.main.get_user_by_id", AsyncMock(return_value=TEST_USER)):
        result = await require_user(FakeRequest())
    assert result == TEST_USER


# ── garmin_link — success path ────────────────────────────────────────────────


async def test_garmin_link_success_redirects(client):
    mock_gc = MagicMock()
    mock_gc.connect = MagicMock()

    with (
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.main.GarminClient", return_value=mock_gc),
        patch("src.main.set_garmin_linked", AsyncMock(return_value=None)),
    ):
        r = await client.post(
            "/garmin/link",
            data={
                "garmin_email": "test@garmin.com",
                "garmin_password": "testpass123",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 303
    assert r.headers["location"] == "/?linked=1"


# ── libre_link — three paths ──────────────────────────────────────────────────


def _make_fake_libre(authenticate_side_effect=None):
    """Build a fake libre.client module for sys.modules injection."""
    fake = types.ModuleType("libre.client")
    LibreAuthError = type("LibreAuthError", (Exception,), {})
    fake.LibreAuthError = LibreAuthError
    if authenticate_side_effect is not None:
        fake.authenticate = MagicMock(side_effect=authenticate_side_effect)
    else:
        fake.authenticate = MagicMock(return_value=MagicMock())
    return fake


async def test_libre_link_success_redirects(client):
    fake = _make_fake_libre()
    with (
        patch.dict(sys.modules, {"libre.client": fake}),
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.main.set_libre_linked", AsyncMock(return_value=None)),
    ):
        r = await client.post(
            "/libre/link",
            data={
                "libre_email": "test@libre.com",
                "libre_password": "pass123",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard"


async def test_libre_link_auth_error_returns_400(client):
    fake = _make_fake_libre()
    fake.authenticate = MagicMock(
        side_effect=fake.LibreAuthError("invalid credentials")
    )
    with (
        patch.dict(sys.modules, {"libre.client": fake}),
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
    ):
        r = await client.post(
            "/libre/link",
            data={
                "libre_email": "test@libre.com",
                "libre_password": "wrong",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 400


async def test_libre_link_generic_error_returns_400(client):
    fake = _make_fake_libre(authenticate_side_effect=Exception("network error"))
    with (
        patch.dict(sys.modules, {"libre.client": fake}),
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
    ):
        r = await client.post(
            "/libre/link",
            data={
                "libre_email": "test@libre.com",
                "libre_password": "pass",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 400


# ── libre_unlink — token dir exists ──────────────────────────────────────────


async def test_libre_unlink_removes_existing_token_dir(client):
    with (
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.main.set_libre_unlinked", AsyncMock(return_value=None)),
        patch("pathlib.Path.exists", return_value=True),
        patch("shutil.rmtree"),
    ):
        r = await client.post("/libre/unlink")
    assert r.status_code == 303


# ── profile validators — valid values ────────────────────────────────────────


async def test_profile_update_valid_sex(client):
    with (
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.main.update_user_profile", AsyncMock(return_value=None)),
    ):
        r = await client.patch("/api/profile", json={"sex": "m"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_profile_update_valid_dob(client):
    with (
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.main.update_user_profile", AsyncMock(return_value=None)),
    ):
        r = await client.patch("/api/profile", json={"date_of_birth": "1990-06-15"})
    assert r.status_code == 200


async def test_profile_update_spo2_enabled(client):
    with (
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.main.update_spo2_enabled", AsyncMock(return_value=None)),
    ):
        r = await client.patch("/api/profile", json={"spo2_enabled": True})
    assert r.status_code == 200


# ── seizure validator — valid severity ───────────────────────────────────────


async def test_seizure_valid_severity(client):
    with (
        patch("src.main.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.main.save_seizure", AsyncMock(return_value=1)),
    ):
        r = await client.post(
            "/api/seizures",
            json={"occurred_at": "2026-05-01T10:00:00Z", "severity": 3},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True
