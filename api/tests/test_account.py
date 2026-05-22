import json
from base64 import b64encode

import bcrypt
from itsdangerous import TimestampSigner
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_USER

_TEST_PASSWORD = "testpassword123"  # pragma: allowlist secret
_TEST_HASH = bcrypt.hashpw(_TEST_PASSWORD.encode(), bcrypt.gensalt()).decode()

_USER_WITH_HASH = {**TEST_USER, "password_hash": _TEST_HASH}


def _make_session(client, user_id: int = 1):
    """Inject user_id into the session cookie (matches Starlette SessionMiddleware format)."""
    from src.deps import settings

    signer = TimestampSigner(settings.session_secret)
    data = b64encode(json.dumps({"user_id": str(user_id)}).encode("utf-8"))
    signed = signer.sign(data).decode("utf-8")
    client.cookies.set("session", signed)


# ── Unauthenticated ───────────────────────────────────────────────────────────


async def test_delete_account_unauthenticated_redirects_to_login(client):
    r = await client.post(
        "/account/delete",
        data={"email": "test@example.com", "password": _TEST_PASSWORD},
    )
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


async def test_export_unauthenticated_redirects_to_login(client):
    r = await client.get("/account/export")
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


# ── Delete: validation errors ─────────────────────────────────────────────────


async def test_delete_account_wrong_email_returns_400(client):
    _make_session(client)
    with patch("src.routes.account.get_user_by_id", AsyncMock(return_value=TEST_USER)):
        r = await client.post(
            "/account/delete",
            data={"email": "wrong@example.com", "password": _TEST_PASSWORD},
        )
    assert r.status_code == 400
    assert "E-Mail" in r.text


async def test_delete_account_wrong_password_returns_400(client):
    _make_session(client)
    with patch("src.routes.account.get_user_by_id", AsyncMock(return_value=TEST_USER)):
        with patch(
            "src.routes.account.get_user_by_email",
            AsyncMock(return_value=_USER_WITH_HASH),
        ):
            r = await client.post(
                "/account/delete",
                data={
                    "email": TEST_USER["email"],
                    "password": "wrongpassword999",  # pragma: allowlist secret
                },
            )
    assert r.status_code == 400
    assert "Passwort" in r.text


# ── Delete: success ───────────────────────────────────────────────────────────


async def test_delete_account_success_redirects_and_clears_session(client):
    _make_session(client)
    with patch("src.routes.account.get_user_by_id", AsyncMock(return_value=TEST_USER)):
        with patch(
            "src.routes.account.get_user_by_email",
            AsyncMock(return_value=_USER_WITH_HASH),
        ):
            with patch("src.routes.account.delete_user", AsyncMock()) as mock_delete:
                r = await client.post(
                    "/account/delete",
                    data={"email": TEST_USER["email"], "password": _TEST_PASSWORD},
                )
    assert r.status_code == 303
    assert r.headers["location"] == "/login?deleted=1"
    mock_delete.assert_awaited_once_with(TEST_USER["id"])


# ── Export ────────────────────────────────────────────────────────────────────


async def test_export_returns_json_with_correct_structure(client):
    _make_session(client)
    export_data = {
        "exported_at": "2026-01-01T00:00:00+00:00",
        "schema_version": "1.0",
        "user": {"id": 1, "name": "Test User", "email": "test@example.com"},
        "activities": [],
        "sleep_sessions": [],
        "hrv_daily": [],
        "daily_summary": [],
        "seizure_events": [],
        "glucose_readings": [],
    }
    with patch(
        "src.routes.account.export_user_data", AsyncMock(return_value=export_data)
    ):
        r = await client.get("/account/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.json()
    assert body["schema_version"] == "1.0"
    assert "activities" in body


async def test_export_excludes_password_hash(client):
    _make_session(client)
    export_data = {
        "exported_at": "2026-01-01T00:00:00+00:00",
        "schema_version": "1.0",
        "user": {"id": 1, "name": "Test", "email": "test@example.com"},
        "activities": [],
        "sleep_sessions": [],
        "hrv_daily": [],
        "daily_summary": [],
        "seizure_events": [],
        "glucose_readings": [],
    }
    with patch(
        "src.routes.account.export_user_data", AsyncMock(return_value=export_data)
    ):
        r = await client.get("/account/export")
    assert r.status_code == 200
    assert "password_hash" not in r.text
    assert "failed_login_attempts" not in r.text


async def test_delete_account_user_not_found_in_db_redirects(client):
    _make_session(client)
    with patch("src.routes.account.get_user_by_id", AsyncMock(return_value=None)):
        r = await client.post(
            "/account/delete",
            data={
                "email": "test@example.com",
                "password": _TEST_PASSWORD,
            },  # pragma: allowlist secret
        )
    assert r.status_code == 303
    assert "/login" in r.headers["location"]
