import bcrypt
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_USER

_TEST_PASSWORD = "testpassword123"  # pragma: allowlist secret
_TEST_HASH = bcrypt.hashpw(_TEST_PASSWORD.encode(), bcrypt.gensalt()).decode()

_USER_WITH_HASH = {**TEST_USER, "password_hash": _TEST_HASH}


# ── Login success ─────────────────────────────────────────────────────────────


async def test_login_success_redirects(client):
    with patch("src.main.get_user_by_email", AsyncMock(return_value=_USER_WITH_HASH)):
        r = await client.post(
            "/login",
            data={"email": TEST_USER["email"], "password": _TEST_PASSWORD},
        )
    assert r.status_code == 303
    assert r.headers["location"] == "/"


async def test_login_success_sets_session(client):
    with patch("src.main.get_user_by_email", AsyncMock(return_value=_USER_WITH_HASH)):
        r = await client.post(
            "/login",
            data={"email": TEST_USER["email"], "password": _TEST_PASSWORD},
        )
    assert r.status_code == 303
    assert "session" in r.cookies or r.headers.get("set-cookie", "")


# ── Register success ──────────────────────────────────────────────────────────


async def test_register_success_redirects(client):
    with patch("src.main.create_user", AsyncMock(return_value={"id": 42})):
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
    with patch("src.main.create_user", AsyncMock(side_effect=Exception("duplicate"))):
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
