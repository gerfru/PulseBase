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


# ── Delete: two-step e-mail confirmation ─────────────────────────────────────


async def test_delete_account_success_sends_email_and_shows_pending_page(client):
    """L-04: POST /account/delete no longer deletes immediately; sends confirmation e-mail."""
    with (
        patch("src.routes.account.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.account.get_user_by_email",
            AsyncMock(return_value=_USER_WITH_HASH),
        ),
        patch("src.routes.account.set_pending_deletion", AsyncMock()) as mock_pending,
        patch(
            "src.routes.account.send_deletion_confirm_email",
            AsyncMock(return_value=True),
        ) as mock_email,
        patch("src.routes.account._make_deletion_token", return_value="test-token"),
    ):
        r = await client.post(
            "/account/delete",
            data={"email": TEST_USER["email"], "password": _TEST_PASSWORD},
        )
    assert r.status_code == 200
    assert "Bestätigungs-E-Mail" in r.text or "Bestätigung" in r.text
    mock_pending.assert_awaited_once_with(TEST_USER["id"])
    mock_email.assert_awaited_once_with(TEST_USER["email"], "test-token")


async def test_confirm_delete_account_valid_token_deletes_and_redirects(client):
    with (
        patch(
            "src.routes.account._verify_deletion_token",
            return_value=TEST_USER["id"],
        ),
        patch("src.routes.account.get_user_by_id", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.account.delete_user", AsyncMock()) as mock_delete,
    ):
        r = await client.get("/account/delete/confirm/valid-token")
    assert r.status_code == 303
    assert r.headers["location"] == "/login?deleted=1"
    mock_delete.assert_awaited_once_with(TEST_USER["id"])


async def test_confirm_delete_account_invalid_token_returns_400(client):
    with patch("src.routes.account._verify_deletion_token", return_value=None):
        r = await client.get("/account/delete/confirm/bad-token")
    assert r.status_code == 400


async def test_delete_account_email_not_sent_still_shows_pending(client):
    """Even if the confirmation e-mail fails, the pending page is shown (logged warning)."""
    with (
        patch("src.routes.account.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.account.get_user_by_email",
            AsyncMock(return_value=_USER_WITH_HASH),
        ),
        patch("src.routes.account.set_pending_deletion", AsyncMock()),
        patch(
            "src.routes.account.send_deletion_confirm_email",
            AsyncMock(return_value=False),
        ),
        patch("src.routes.account._make_deletion_token", return_value="test-token"),
    ):
        r = await client.post(
            "/account/delete",
            data={"email": TEST_USER["email"], "password": _TEST_PASSWORD},
        )
    assert r.status_code == 200


async def test_confirm_delete_account_user_not_found_redirects_to_login(client):
    """Valid token but the user no longer exists → redirect to /login (not 500)."""
    with (
        patch("src.routes.account._verify_deletion_token", return_value=999),
        patch("src.routes.account.get_user_by_id", AsyncMock(return_value=None)),
    ):
        r = await client.get("/account/delete/confirm/valid-token")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


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
