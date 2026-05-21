import asyncpg
import bcrypt
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import TEST_USER

_TEST_PASSWORD = "testpassword123"  # pragma: allowlist secret
_TEST_HASH = bcrypt.hashpw(_TEST_PASSWORD.encode(), bcrypt.gensalt()).decode()

_USER_WITH_HASH = {**TEST_USER, "password_hash": _TEST_HASH}


# ── Login success ─────────────────────────────────────────────────────────────


async def test_login_success_redirects(client):
    with patch(
        "src.routes.auth.get_user_by_email", AsyncMock(return_value=_USER_WITH_HASH)
    ):
        r = await client.post(
            "/login",
            data={"email": TEST_USER["email"], "password": _TEST_PASSWORD},
        )
    assert r.status_code == 303
    assert r.headers["location"] == "/"


async def test_login_success_sets_session(client):
    with patch(
        "src.routes.auth.get_user_by_email", AsyncMock(return_value=_USER_WITH_HASH)
    ):
        r = await client.post(
            "/login",
            data={"email": TEST_USER["email"], "password": _TEST_PASSWORD},
        )
    assert r.status_code == 303
    assert "session" in r.cookies or r.headers.get("set-cookie", "")


# ── Register success ──────────────────────────────────────────────────────────


async def test_register_success_redirects(client):
    with patch("src.routes.auth.create_user", AsyncMock(return_value={"id": 42})):
        r = await client.post(
            "/register",
            data={
                "name": "New User",
                "email": "new@example.com",
                "password": "newpassword1",  # pragma: allowlist secret
                "password_confirm": "newpassword1",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 303
    assert r.headers["location"] == "/"


async def test_register_duplicate_email_returns_400(client):
    with patch(
        "src.routes.auth.create_user",
        AsyncMock(side_effect=asyncpg.UniqueViolationError()),
    ):
        r = await client.post(
            "/register",
            data={
                "name": "User",
                "email": "existing@example.com",
                "password": "password123",  # pragma: allowlist secret
                "password_confirm": "password123",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 400


# ── Logout ────────────────────────────────────────────────────────────────────


async def test_logout_redirects_to_login(client):
    r = await client.post("/logout")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


async def test_logout_clears_session_so_dashboard_requires_login_again(client):
    await client.post("/logout")
    r = await client.get("/dashboard")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


# ── Password reset — request form ─────────────────────────────────────────────


async def test_reset_request_page_returns_200(client):
    r = await client.get("/auth/reset-request")
    assert r.status_code == 200


async def test_reset_request_unknown_email_returns_200(client):
    # Non-leaking: same response whether email exists or not
    with patch("src.routes.auth.get_user_by_email", AsyncMock(return_value=None)):
        r = await client.post("/auth/reset-request", data={"email": "nope@example.com"})
    assert r.status_code == 200


async def test_reset_request_valid_email_returns_200(client):
    with patch("src.routes.auth.get_user_by_email", AsyncMock(return_value=TEST_USER)):
        r = await client.post("/auth/reset-request", data={"email": TEST_USER["email"]})
    assert r.status_code == 200


async def test_reset_request_sends_email_when_api_key_set(client):
    with patch("src.routes.auth.get_user_by_email", AsyncMock(return_value=TEST_USER)):
        with patch("src.routes.auth.settings") as mock_settings:
            mock_settings.session_secret = (
                "test-secret-key-for-testing-only!"  # pragma: allowlist secret
            )
            mock_settings.resend_api_key = "re_test"  # pragma: allowlist secret
            mock_settings.resend_from_email = "noreply@example.com"
            mock_settings.app_base_url = "https://example.com"
            with patch("src.routes.auth.resend_client") as mock_resend:
                mock_resend.Emails.send = MagicMock()
                r = await client.post(
                    "/auth/reset-request", data={"email": TEST_USER["email"]}
                )
    assert r.status_code == 200
    mock_resend.Emails.send.assert_called_once()


# ── Password reset — reset form ───────────────────────────────────────────────


async def test_reset_form_valid_token_returns_200(client):
    from src.routes.auth import _make_reset_token

    token = _make_reset_token(TEST_USER["id"])
    r = await client.get(f"/auth/reset/{token}")
    assert r.status_code == 200


async def test_reset_form_invalid_token_returns_400(client):
    r = await client.get("/auth/reset/not-a-valid-token")
    assert r.status_code == 400


# ── Password reset — submit ───────────────────────────────────────────────────


async def test_reset_password_success_redirects_to_login(client):
    from src.routes.auth import _make_reset_token

    token = _make_reset_token(TEST_USER["id"])
    with patch("src.routes.auth.update_password", AsyncMock()):
        r = await client.post(
            f"/auth/reset/{token}",
            data={
                "password": "newpassword1",  # pragma: allowlist secret
                "password_confirm": "newpassword1",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 303
    assert r.headers["location"] == "/login?reset=1"


async def test_reset_password_mismatch_returns_400(client):
    from src.routes.auth import _make_reset_token

    token = _make_reset_token(TEST_USER["id"])
    r = await client.post(
        f"/auth/reset/{token}",
        data={
            "password": "newpassword1",  # pragma: allowlist secret
            "password_confirm": "different99",  # pragma: allowlist secret
        },
    )
    assert r.status_code == 400


async def test_reset_password_too_short_returns_400(client):
    from src.routes.auth import _make_reset_token

    token = _make_reset_token(TEST_USER["id"])
    r = await client.post(
        f"/auth/reset/{token}",
        data={
            "password": "short",  # pragma: allowlist secret
            "password_confirm": "short",  # pragma: allowlist secret
        },
    )
    assert r.status_code == 400


async def test_reset_password_invalid_token_returns_400(client):
    r = await client.post(
        "/auth/reset/not-a-valid-token",
        data={
            "password": "newpassword1",  # pragma: allowlist secret
            "password_confirm": "newpassword1",  # pragma: allowlist secret
        },
    )
    assert r.status_code == 400
