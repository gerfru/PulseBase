import bcrypt
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_USER, make_session

_TEST_PASSWORD = "testpassword123"  # pragma: allowlist secret
_TEST_HASH = bcrypt.hashpw(_TEST_PASSWORD.encode(), bcrypt.gensalt()).decode()

_USER_WITH_HASH = {**TEST_USER, "password_hash": _TEST_HASH}


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
    with patch("src.routes.account.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post(
            "/account/delete",
            data={"email": "wrong@example.com", "password": _TEST_PASSWORD},
        )
    assert r.status_code == 400
    assert "E-Mail" in r.text


async def test_delete_account_wrong_password_returns_400(client):
    with patch("src.routes.account.require_user", AsyncMock(return_value=TEST_USER)):
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
    with patch("src.routes.account.require_user", AsyncMock(return_value=TEST_USER)):
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


# ── Delete: NeedsLogin when require_user raises ───────────────────────────────


async def test_delete_account_require_user_raises_redirects_to_login(client):
    from src.deps import NeedsLogin

    make_session(client)
    with patch("src.routes.account.require_user", AsyncMock(side_effect=NeedsLogin())):
        r = await client.post(
            "/account/delete",
            data={
                "email": "test@example.com",
                "password": _TEST_PASSWORD,
            },  # pragma: allowlist secret
        )
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


# ── Export ────────────────────────────────────────────────────────────────────


async def test_export_returns_json_with_correct_structure(client):
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
    with patch("src.routes.account.require_user", AsyncMock(return_value=TEST_USER)):
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
    with patch("src.routes.account.require_user", AsyncMock(return_value=TEST_USER)):
        with patch(
            "src.routes.account.export_user_data", AsyncMock(return_value=export_data)
        ):
            r = await client.get("/account/export")
    assert r.status_code == 200
    assert "password_hash" not in r.text
    assert "failed_login_attempts" not in r.text
