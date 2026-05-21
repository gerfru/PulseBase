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
        with patch("src.routes.auth.reset_failed_login", AsyncMock()):
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
        with patch("src.routes.auth.reset_failed_login", AsyncMock()):
            r = await client.post(
                "/login",
                data={"email": TEST_USER["email"], "password": _TEST_PASSWORD},
            )
    assert r.status_code == 303
    assert "session" in r.cookies or r.headers.get("set-cookie", "")


# ── Register success ──────────────────────────────────────────────────────────


async def test_login_form_returns_200(client):
    r = await client.get("/login")
    assert r.status_code == 200


async def test_register_form_returns_200(client):
    r = await client.get("/register")
    assert r.status_code == 200


async def test_register_password_mismatch_returns_400(client):
    r = await client.post(
        "/register",
        data={
            "name": "User",
            "email": "user@example.com",
            "password": "password123",  # pragma: allowlist secret
            "password_confirm": "different99",  # pragma: allowlist secret
        },
    )
    assert r.status_code == 400


async def test_register_password_too_short_returns_400(client):
    r = await client.post(
        "/register",
        data={
            "name": "User",
            "email": "user@example.com",
            "password": "short",  # pragma: allowlist secret
            "password_confirm": "short",  # pragma: allowlist secret
        },
    )
    assert r.status_code == 400


async def test_register_redirects_to_verify_pending(client):
    with patch("src.routes.auth.create_user", AsyncMock(return_value={"id": 42})):
        with patch("src.routes.auth._send_verify_email", AsyncMock(return_value=True)):
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
    assert r.headers["location"] == "/login?verify=sent"


async def test_register_email_failed_redirects_to_verify_failed(client):
    with patch("src.routes.auth.create_user", AsyncMock(return_value={"id": 42})):
        with patch("src.routes.auth._send_verify_email", AsyncMock(return_value=False)):
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
    assert r.headers["location"] == "/login?verify=failed"


async def test_register_sends_verify_email_when_api_key_set(client):
    with patch("src.routes.auth.create_user", AsyncMock(return_value={"id": 42})):
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
                    "/register",
                    data={
                        "name": "New User",
                        "email": "new@example.com",
                        "password": "newpassword1",  # pragma: allowlist secret
                        "password_confirm": "newpassword1",  # pragma: allowlist secret
                    },
                )
    assert r.status_code == 303
    mock_resend.Emails.send.assert_called_once()


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


# ── Account lockout ───────────────────────────────────────────────────────────


async def test_lockout_email_skipped_when_no_api_key(client):
    with patch("src.routes.auth.settings") as mock_settings:
        mock_settings.resend_api_key = ""
        from src.routes.auth import _send_lockout_email

        result = await _send_lockout_email("victim@example.com")
    assert result is False


async def test_lockout_email_exception_returns_false(client):
    with patch("src.routes.auth.settings") as mock_settings:
        mock_settings.resend_api_key = "re_test"  # pragma: allowlist secret
        mock_settings.resend_from_email = "noreply@example.com"
        mock_settings.app_base_url = "https://example.com"
        with patch("src.routes.auth.resend_client") as mock_resend:
            mock_resend.Emails.send = MagicMock(side_effect=Exception("send failed"))
            from src.routes.auth import _send_lockout_email

            result = await _send_lockout_email("victim@example.com")
    assert result is False


async def test_reset_email_exception_returns_false(client):
    with patch("src.routes.auth.settings") as mock_settings:
        mock_settings.resend_api_key = "re_test"  # pragma: allowlist secret
        mock_settings.resend_from_email = "noreply@example.com"
        mock_settings.app_base_url = "https://example.com"
        mock_settings.session_secret = (
            "test-secret-key-for-testing-only!"  # pragma: allowlist secret
        )
        with patch("src.routes.auth.resend_client") as mock_resend:
            mock_resend.Emails.send = MagicMock(side_effect=Exception("send failed"))
            from src.routes.auth import _send_reset_email

            result = await _send_reset_email("user@example.com", "sometoken")
    assert result is False


async def test_verify_email_skipped_returns_false(client):
    with patch("src.routes.auth.settings") as mock_settings:
        mock_settings.resend_api_key = ""
        from src.routes.auth import _send_verify_email

        result = await _send_verify_email("user@example.com", "sometoken")
    assert result is False


async def test_verify_email_exception_returns_false(client):
    with patch("src.routes.auth.settings") as mock_settings:
        mock_settings.resend_api_key = "re_test"  # pragma: allowlist secret
        mock_settings.resend_from_email = "noreply@example.com"
        mock_settings.app_base_url = "https://example.com"
        mock_settings.session_secret = (
            "test-secret-key-for-testing-only!"  # pragma: allowlist secret
        )
        with patch("src.routes.auth.resend_client") as mock_resend:
            mock_resend.Emails.send = MagicMock(side_effect=Exception("send failed"))
            from src.routes.auth import _send_verify_email

            result = await _send_verify_email("user@example.com", "sometoken")
    assert result is False


async def test_lockout_email_sends_when_api_key_set(client):
    with patch("src.routes.auth.settings") as mock_settings:
        mock_settings.resend_api_key = "re_test"  # pragma: allowlist secret
        mock_settings.resend_from_email = "noreply@example.com"
        mock_settings.app_base_url = "https://example.com"
        with patch("src.routes.auth.resend_client") as mock_resend:
            mock_resend.Emails.send = MagicMock()
            from src.routes.auth import _send_lockout_email

            await _send_lockout_email("victim@example.com")
    mock_resend.Emails.send.assert_called_once()
    call_kwargs = mock_resend.Emails.send.call_args[0][0]
    assert call_kwargs["to"] == "victim@example.com"
    assert "gesperrt" in call_kwargs["subject"]


async def test_login_locked_account_returns_400(client):
    from datetime import datetime, timedelta, timezone

    locked_user = {
        **_USER_WITH_HASH,
        "failed_login_attempts": 5,
        "locked_until": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    with patch(
        "src.routes.auth.get_user_by_email", AsyncMock(return_value=locked_user)
    ):
        r = await client.post(
            "/login",
            data={"email": TEST_USER["email"], "password": _TEST_PASSWORD},
        )
    assert r.status_code == 400
    assert "gesperrt" in r.text


async def test_login_failed_increments_counter(client):
    with patch(
        "src.routes.auth.get_user_by_email", AsyncMock(return_value=_USER_WITH_HASH)
    ):
        with patch("src.routes.auth.increment_failed_login", AsyncMock()) as mock_inc:
            r = await client.post(
                "/login",
                data={
                    "email": TEST_USER["email"],
                    "password": "wrongpassword",  # pragma: allowlist secret
                },
            )
    assert r.status_code == 400
    mock_inc.assert_awaited_once_with(TEST_USER["id"])


async def test_login_triggers_lockout_on_max_attempts(client):
    almost_locked = {
        **_USER_WITH_HASH,
        "failed_login_attempts": 4,
        "locked_until": None,
    }
    with patch(
        "src.routes.auth.get_user_by_email", AsyncMock(return_value=almost_locked)
    ):
        with patch("src.routes.auth.increment_failed_login", AsyncMock()):
            with patch("src.routes.auth.lock_user_until", AsyncMock()) as mock_lock:
                with patch(
                    "src.routes.auth._send_lockout_email", AsyncMock()
                ) as mock_mail:
                    r = await client.post(
                        "/login",
                        data={
                            "email": TEST_USER["email"],
                            "password": "wrongpassword",  # pragma: allowlist secret
                        },
                    )
    assert r.status_code == 400
    mock_lock.assert_awaited_once()
    mock_mail.assert_awaited_once_with(TEST_USER["email"])


async def test_login_success_resets_counter(client):
    with patch(
        "src.routes.auth.get_user_by_email", AsyncMock(return_value=_USER_WITH_HASH)
    ):
        with patch("src.routes.auth.reset_failed_login", AsyncMock()) as mock_reset:
            r = await client.post(
                "/login",
                data={"email": TEST_USER["email"], "password": _TEST_PASSWORD},
            )
    assert r.status_code == 303
    mock_reset.assert_awaited_once_with(TEST_USER["id"])


# ── E-Mail verification ───────────────────────────────────────────────────────


async def test_login_unverified_user_returns_400(client):
    unverified = {**_USER_WITH_HASH, "email_verified_at": None}
    with patch("src.routes.auth.get_user_by_email", AsyncMock(return_value=unverified)):
        r = await client.post(
            "/login",
            data={"email": TEST_USER["email"], "password": _TEST_PASSWORD},
        )
    assert r.status_code == 400
    assert "bestätige" in r.text


async def test_verify_valid_token_sets_verified_and_redirects(client):
    from src.routes.auth import _make_verify_token

    token = _make_verify_token(TEST_USER["id"])
    with patch("src.routes.auth.set_email_verified", AsyncMock()) as mock_verify:
        r = await client.get(f"/auth/verify/{token}")
    assert r.status_code == 303
    assert r.headers["location"] == "/login?verified=1"
    mock_verify.assert_awaited_once_with(TEST_USER["id"])


async def test_verify_invalid_token_returns_400(client):
    r = await client.get("/auth/verify/not-a-valid-token")
    assert r.status_code == 400


async def test_resend_verify_form_returns_200(client):
    r = await client.get("/auth/resend-verify")
    assert r.status_code == 200


async def test_resend_verify_always_returns_200(client):
    with patch("src.routes.auth.get_user_by_email", AsyncMock(return_value=None)):
        r = await client.post(
            "/auth/resend-verify", data={"email": "unknown@example.com"}
        )
    assert r.status_code == 200


async def test_resend_verify_send_failure_shows_warning(client):
    unverified_user = {**TEST_USER, "email_verified_at": None}
    with patch(
        "src.routes.auth.get_user_by_email", AsyncMock(return_value=unverified_user)
    ):
        with patch("src.routes.auth._send_verify_email", AsyncMock(return_value=False)):
            r = await client.post(
                "/auth/resend-verify", data={"email": TEST_USER["email"]}
            )
    assert r.status_code == 200
    assert "konnte nicht gesendet" in r.text


async def test_verify_email_sends_when_api_key_set(client):
    unverified_user = {**TEST_USER, "email_verified_at": None}
    with patch(
        "src.routes.auth.get_user_by_email", AsyncMock(return_value=unverified_user)
    ):
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
                    "/auth/resend-verify", data={"email": TEST_USER["email"]}
                )
    assert r.status_code == 200
    mock_resend.Emails.send.assert_called_once()
    call_kwargs = mock_resend.Emails.send.call_args[0][0]
    assert call_kwargs["to"] == TEST_USER["email"]
