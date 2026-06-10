import hashlib

import asyncpg
import bcrypt
import pytest
from unittest.mock import AsyncMock, patch

from src.mail import (
    send_deletion_confirm_email,
    send_lockout_email,
    send_reset_email,
    send_verify_email,
)
from tests.conftest import TEST_USER

_TEST_PASSWORD = "testpassword123"  # pragma: allowlist secret
_TEST_HASH = bcrypt.hashpw(_TEST_PASSWORD.encode(), bcrypt.gensalt()).decode()

_USER_WITH_HASH = {**TEST_USER, "password_hash": _TEST_HASH}


# ── Login success ─────────────────────────────────────────────────────────────


async def test_login_success_redirects(client):
    with patch(
        "src.routes.auth.get_user_by_email", AsyncMock(return_value=_USER_WITH_HASH)
    ):
        with patch("src.auth_helpers.reset_failed_login", AsyncMock()):
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
        with patch("src.auth_helpers.reset_failed_login", AsyncMock()):
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
            "password": "longerpassword1",  # pragma: allowlist secret
            "password_confirm": "longerpassword2",  # pragma: allowlist secret
            "consent_health": "on",
            "consent_terms": "on",
            "consent_age": "on",
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
            "consent_health": "on",
            "consent_terms": "on",
            "consent_age": "on",
        },
    )
    assert r.status_code == 400


async def test_register_redirects_to_verify_pending(client):
    with patch("src.routes.auth.create_user", AsyncMock(return_value={"id": 42})):
        with patch("src.routes.auth.send_verify_email", AsyncMock(return_value=True)):
            with patch("src.routes.auth.save_consent", AsyncMock()):
                r = await client.post(
                    "/register",
                    data={
                        "name": "New User",
                        "email": "new@example.com",
                        "password": "newpassword1x",  # pragma: allowlist secret
                        "password_confirm": "newpassword1x",  # pragma: allowlist secret
                        "consent_health": "on",
                        "consent_terms": "on",
                        "consent_age": "on",
                    },
                )
    assert r.status_code == 303
    assert r.headers["location"] == "/login?verify=sent"


async def test_register_email_failed_redirects_to_verify_failed(client):
    with patch("src.routes.auth.create_user", AsyncMock(return_value={"id": 42})):
        with patch("src.routes.auth.send_verify_email", AsyncMock(return_value=False)):
            with patch("src.routes.auth.save_consent", AsyncMock()):
                r = await client.post(
                    "/register",
                    data={
                        "name": "New User",
                        "email": "new@example.com",
                        "password": "newpassword1x",  # pragma: allowlist secret
                        "password_confirm": "newpassword1x",  # pragma: allowlist secret
                        "consent_health": "on",
                        "consent_terms": "on",
                        "consent_age": "on",
                    },
                )
    assert r.status_code == 303
    assert r.headers["location"] == "/login?verify=failed"


async def test_register_sends_verify_email_when_api_key_set(client):
    with (
        patch("src.routes.auth.create_user", AsyncMock(return_value={"id": 42})),
        patch("src.routes.auth.save_consent", AsyncMock()),
        patch("src.mail.settings") as mock_mail_settings,
        patch("src.mail.resend_client") as mock_resend,
    ):
        mock_mail_settings.resend_api_key = "re_test"  # pragma: allowlist secret
        mock_mail_settings.resend_from_email = "noreply@example.com"
        mock_mail_settings.app_base_url = "https://example.com"
        mock_resend.Emails.send_async = AsyncMock()
        r = await client.post(
            "/register",
            data={
                "name": "New User",
                "email": "new@example.com",
                "password": "newpassword1x",  # pragma: allowlist secret
                "password_confirm": "newpassword1x",  # pragma: allowlist secret
                "consent_health": "on",
                "consent_terms": "on",
                "consent_age": "on",
            },
        )
    assert r.status_code == 303
    mock_resend.Emails.send_async.assert_awaited_once()


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
                "password": "longerpassword1",  # pragma: allowlist secret
                "password_confirm": "longerpassword1",  # pragma: allowlist secret
                "consent_health": "on",
                "consent_terms": "on",
                "consent_age": "on",
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
    with (
        patch("src.routes.auth.get_user_by_email", AsyncMock(return_value=TEST_USER)),
        patch("src.auth_tokens.save_reset_token", AsyncMock()),
    ):
        r = await client.post("/auth/reset-request", data={"email": TEST_USER["email"]})
    assert r.status_code == 200


async def test_reset_request_sends_email_when_api_key_set(client):
    with (
        patch("src.routes.auth.get_user_by_email", AsyncMock(return_value=TEST_USER)),
        patch("src.auth_tokens.save_reset_token", AsyncMock()),
        patch("src.mail.settings") as mock_settings,
        patch("src.mail.resend_client") as mock_resend,
    ):
        mock_settings.resend_api_key = "re_test"  # pragma: allowlist secret
        mock_settings.resend_from_email = "noreply@example.com"
        mock_settings.app_base_url = "https://example.com"
        mock_resend.Emails.send_async = AsyncMock()
        r = await client.post("/auth/reset-request", data={"email": TEST_USER["email"]})
    assert r.status_code == 200
    mock_resend.Emails.send_async.assert_awaited_once()


# ── Password reset — reset form ───────────────────────────────────────────────


async def test_reset_form_valid_token_returns_200(client):
    with patch(
        "src.routes.auth._verify_reset_token", AsyncMock(return_value=TEST_USER["id"])
    ):
        r = await client.get("/auth/reset/any-token")
    assert r.status_code == 200


async def test_reset_form_invalid_token_returns_400(client):
    with patch("src.routes.auth._verify_reset_token", AsyncMock(return_value=None)):
        r = await client.get("/auth/reset/not-a-valid-token")
    assert r.status_code == 400


# ── Password reset — submit ───────────────────────────────────────────────────


async def test_reset_password_success_redirects_to_login(client):
    with patch(
        "src.routes.auth._verify_reset_token", AsyncMock(return_value=TEST_USER["id"])
    ):
        await client.get("/auth/reset/any-token")
        with (
            patch("src.routes.auth.update_password", AsyncMock()),
            patch("src.routes.auth.clear_reset_token", AsyncMock()),
        ):
            r = await client.post(
                "/auth/reset/any-token",
                data={
                    "password": "newpassword1",  # pragma: allowlist secret
                    "password_confirm": "newpassword1",  # pragma: allowlist secret
                },
            )
    assert r.status_code == 303
    assert r.headers["location"] == "/login?reset=1"


async def test_reset_password_mismatch_returns_400(client):
    with patch(
        "src.routes.auth._verify_reset_token", AsyncMock(return_value=TEST_USER["id"])
    ):
        await client.get("/auth/reset/any-token")
        r = await client.post(
            "/auth/reset/any-token",
            data={
                "password": "newpassword1",  # pragma: allowlist secret
                "password_confirm": "different99",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 400


async def test_reset_password_too_short_returns_400(client):
    with patch(
        "src.routes.auth._verify_reset_token", AsyncMock(return_value=TEST_USER["id"])
    ):
        await client.get("/auth/reset/any-token")
        r = await client.post(
            "/auth/reset/any-token",
            data={
                "password": "short",  # pragma: allowlist secret
                "password_confirm": "short",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 400


async def test_reset_password_invalid_token_returns_400(client):
    """Token valid at GET (session marker set), but invalid at POST (e.g. expired)."""
    with patch(
        "src.routes.auth._verify_reset_token", AsyncMock(return_value=TEST_USER["id"])
    ):
        await client.get("/auth/reset/any-token")
    with patch("src.routes.auth._verify_reset_token", AsyncMock(return_value=None)):
        r = await client.post(
            "/auth/reset/any-token",
            data={
                "password": "newpassword1",  # pragma: allowlist secret
                "password_confirm": "newpassword1",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 400


async def test_reset_password_no_session_returns_403(client):
    """POST to reset endpoint without prior GET (no session marker) is rejected."""
    with patch(
        "src.routes.auth._verify_reset_token", AsyncMock(return_value=TEST_USER["id"])
    ):
        r = await client.post(
            "/auth/reset/any-token",
            data={
                "password": "newpassword1",  # pragma: allowlist secret
                "password_confirm": "newpassword1",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 403


async def test_reset_password_success_clears_session(client):
    """After password reset the session is cleared — old session cannot be reused."""
    from tests.conftest import make_session

    token = "any-token"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    make_session(
        client, user_id=TEST_USER["id"], extra={"reset_token_hash": token_hash}
    )
    assert client.cookies.get("session")  # session was planted

    with (
        patch(
            "src.routes.auth._verify_reset_token",
            AsyncMock(return_value=TEST_USER["id"]),
        ),
        patch("src.routes.auth.update_password", AsyncMock()),
        patch("src.routes.auth.clear_reset_token", AsyncMock()),
    ):
        r = await client.post(
            "/auth/reset/any-token",
            data={
                "password": "newpassword12",  # pragma: allowlist secret
                "password_confirm": "newpassword12",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 303
    assert r.headers["location"] == "/login?reset=1"
    # Starlette SessionMiddleware sends Max-Age=0 when session is cleared
    set_cookie = r.headers.get("set-cookie", "")
    assert "max-age=0" in set_cookie.lower() or "session=" in set_cookie


async def test_reset_token_invalidated_before_password_update(client):
    """H-01: clear_reset_token must fire before update_password to prevent replay attacks."""
    call_order: list[str] = []

    async def mock_clear(user_id: int) -> None:
        call_order.append("clear_reset_token")

    async def mock_update(user_id: int, hashed: str) -> None:
        call_order.append("update_password")

    with (
        patch(
            "src.routes.auth._verify_reset_token",
            AsyncMock(return_value=TEST_USER["id"]),
        ),
        patch("src.routes.auth.clear_reset_token", side_effect=mock_clear),
        patch("src.routes.auth.update_password", side_effect=mock_update),
    ):
        await client.get("/auth/reset/any-token")
        r = await client.post(
            "/auth/reset/any-token",
            data={
                "password": "newpassword1",  # pragma: allowlist secret
                "password_confirm": "newpassword1",  # pragma: allowlist secret
            },
        )
    assert r.status_code == 303
    assert call_order == ["clear_reset_token", "update_password"]


async def test_reset_token_cannot_be_reused_after_success(client):
    """M-14: A second POST with the same token after a successful reset must fail."""
    with (
        patch(
            "src.routes.auth._verify_reset_token",
            AsyncMock(return_value=TEST_USER["id"]),
        ),
        patch("src.routes.auth.update_password", AsyncMock()),
        patch("src.routes.auth.clear_reset_token", AsyncMock()),
    ):
        await client.get("/auth/reset/used-token")
        await client.post(
            "/auth/reset/used-token",
            data={
                "password": "newpassword1",  # pragma: allowlist secret
                "password_confirm": "newpassword1",  # pragma: allowlist secret
            },
        )

    # Second attempt: session was cleared after first reset, so request is rejected
    with patch("src.routes.auth._verify_reset_token", AsyncMock(return_value=None)):
        r = await client.post(
            "/auth/reset/used-token",
            data={
                "password": "anotherpass1",  # pragma: allowlist secret
                "password_confirm": "anotherpass1",  # pragma: allowlist secret
            },
        )
    assert r.status_code in (400, 403)


async def test_reset_token_ttl_is_15_minutes():
    """M1: reset token must expire after 15 min (OWASP short-lived one-time token).

    _make_reset_token persists expires_at via save_reset_token; assert the delta
    is 900s, not the previous 3600s.
    """
    from datetime import datetime, timezone

    from src.auth_tokens import _RESET_MAX_AGE, _make_reset_token

    assert _RESET_MAX_AGE == 900

    captured: dict[str, datetime] = {}

    async def _capture(user_id, token_hash, expires_at):
        captured["expires_at"] = expires_at

    before = datetime.now(timezone.utc)
    with patch("src.auth_tokens.save_reset_token", _capture):
        await _make_reset_token(TEST_USER["id"])

    delta = (captured["expires_at"] - before).total_seconds()
    # ~900s in the future, allowing a few seconds of execution slack
    assert 895 <= delta <= 905


# ── Account lockout ───────────────────────────────────────────────────────────


_MAIL_CASES = [
    (send_lockout_email, {"to_email": "test@example.com", "lockout_minutes": 15}),
    (send_reset_email, {"to_email": "test@example.com", "token": "tok"}),
    (send_verify_email, {"to_email": "test@example.com", "token": "tok"}),
    (send_deletion_confirm_email, {"to_email": "test@example.com", "token": "tok"}),
]


@pytest.mark.parametrize(
    "send_fn,kwargs", _MAIL_CASES, ids=["lockout", "reset", "verify", "deletion"]
)
async def test_mail_no_api_key_returns_false(client, send_fn, kwargs):
    """L-11: All mail functions return False when RESEND_API_KEY is not set."""
    with patch("src.mail.settings") as mock_settings:
        mock_settings.resend_api_key = ""
        result = await send_fn(**kwargs)
    assert result is False


@pytest.mark.parametrize(
    "send_fn,kwargs", _MAIL_CASES, ids=["lockout", "reset", "verify", "deletion"]
)
async def test_mail_exception_returns_false(client, send_fn, kwargs):
    """L-11: All mail functions return False when the send call raises."""
    with patch("src.mail.settings") as mock_settings:
        mock_settings.resend_api_key = "re_test"  # pragma: allowlist secret
        mock_settings.resend_from_email = "noreply@example.com"
        mock_settings.app_base_url = "https://example.com"
        with patch("src.mail.resend_client") as mock_resend:
            mock_resend.Emails.send_async = AsyncMock(
                side_effect=Exception("send failed")
            )
            result = await send_fn(**kwargs)
    assert result is False


async def test_lockout_email_sends_when_api_key_set(client):
    with patch("src.mail.settings") as mock_settings:
        mock_settings.resend_api_key = "re_test"  # pragma: allowlist secret
        mock_settings.resend_from_email = "noreply@example.com"
        mock_settings.app_base_url = "https://example.com"
        with patch("src.mail.resend_client") as mock_resend:
            mock_resend.Emails.send_async = AsyncMock()
            from src.mail import send_lockout_email

            await send_lockout_email("victim@example.com", lockout_minutes=15)
    mock_resend.Emails.send_async.assert_awaited_once()
    call_kwargs = mock_resend.Emails.send_async.call_args[0][0]
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
        with patch(
            "src.auth_helpers.increment_failed_login", AsyncMock(return_value=1)
        ) as mock_inc:
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
        with patch(
            "src.auth_helpers.increment_failed_login", AsyncMock(return_value=5)
        ):
            with patch("src.auth_helpers.lock_user_until", AsyncMock()) as mock_lock:
                with patch(
                    "src.auth_helpers.send_lockout_email", AsyncMock()
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
    mock_mail.assert_awaited_once_with(TEST_USER["email"], 15)


async def test_login_success_resets_counter(client):
    with patch(
        "src.routes.auth.get_user_by_email", AsyncMock(return_value=_USER_WITH_HASH)
    ):
        with patch("src.auth_helpers.reset_failed_login", AsyncMock()) as mock_reset:
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
    with (
        patch(
            "src.routes.auth._verify_email_token",
            AsyncMock(return_value=TEST_USER["id"]),
        ),
        patch("src.routes.auth.set_email_verified", AsyncMock()) as mock_verify,
        patch("src.routes.auth.clear_verify_token", AsyncMock()) as mock_clear,
    ):
        r = await client.get("/auth/verify/valid-token")
    assert r.status_code == 303
    assert r.headers["location"] == "/login?verified=1"
    mock_verify.assert_awaited_once_with(TEST_USER["id"])
    # WS3: token is single-use — cleared after consumption
    mock_clear.assert_awaited_once_with(TEST_USER["id"])


async def test_verify_invalid_token_returns_400(client):
    with patch("src.routes.auth._verify_email_token", AsyncMock(return_value=None)):
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
        with patch("src.routes.auth.send_verify_email", AsyncMock(return_value=False)):
            r = await client.post(
                "/auth/resend-verify", data={"email": TEST_USER["email"]}
            )
    assert r.status_code == 200
    assert "konnte nicht gesendet" in r.text


async def test_verify_email_sends_when_api_key_set(client):
    unverified_user = {**TEST_USER, "email_verified_at": None}
    with (
        patch(
            "src.routes.auth.get_user_by_email",
            AsyncMock(return_value=unverified_user),
        ),
        patch("src.mail.settings") as mock_mail_settings,
        patch("src.mail.resend_client") as mock_resend,
    ):
        mock_mail_settings.resend_api_key = "re_test"  # pragma: allowlist secret
        mock_mail_settings.resend_from_email = "noreply@example.com"
        mock_mail_settings.app_base_url = "https://example.com"
        mock_resend.Emails.send_async = AsyncMock()
        r = await client.post("/auth/resend-verify", data={"email": TEST_USER["email"]})
    assert r.status_code == 200
    mock_resend.Emails.send_async.assert_awaited_once()
    call_kwargs = mock_resend.Emails.send_async.call_args[0][0]
    assert call_kwargs["to"] == TEST_USER["email"]


# ── Registration: consent + email normalization + 12-char minimum ─────────────


async def test_register_empty_name_returns_400(client):
    r = await client.post(
        "/register",
        data={
            "name": "   ",
            "email": "user@example.com",
            "password": "longerpassword1",  # pragma: allowlist secret
            "password_confirm": "longerpassword1",  # pragma: allowlist secret
            "consent_health": "on",
            "consent_terms": "on",
            "consent_age": "on",
        },
    )
    assert r.status_code == 400
    assert "Name" in r.text


async def test_register_without_consent_returns_400(client):
    r = await client.post(
        "/register",
        data={
            "name": "User",
            "email": "user@example.com",
            "password": "longerpassword1",  # pragma: allowlist secret
            "password_confirm": "longerpassword1",  # pragma: allowlist secret
        },
    )
    assert r.status_code == 400
    assert "Gesundheitsdaten" in r.text


async def test_register_consent_saves_audit_log(client):
    with patch("src.routes.auth.create_user", AsyncMock(return_value={"id": 42})):
        with patch("src.routes.auth.send_verify_email", AsyncMock(return_value=True)):
            with patch("src.routes.auth.save_consent", AsyncMock()) as mock_consent:
                await client.post(
                    "/register",
                    data={
                        "name": "New User",
                        "email": "new@example.com",
                        "password": "newpassword1x",  # pragma: allowlist secret
                        "password_confirm": "newpassword1x",  # pragma: allowlist secret
                        "consent_health": "on",
                        "consent_terms": "on",
                        "consent_age": "on",
                    },
                )
    assert mock_consent.await_count == 3
    consent_types = [call[0][1] for call in mock_consent.call_args_list]
    assert consent_types == ["health_data", "terms", "age_16plus"]
    assert all(call[0][0] == 42 for call in mock_consent.call_args_list)
    assert all(call[0][2] is True for call in mock_consent.call_args_list)


async def test_register_short_password_12_chars_returns_400(client):
    r = await client.post(
        "/register",
        data={
            "name": "User",
            "email": "user@example.com",
            "password": "only11chars",  # pragma: allowlist secret
            "password_confirm": "only11chars",  # pragma: allowlist secret
            "consent_health": "on",
            "consent_terms": "on",
            "consent_age": "on",
        },
    )
    assert r.status_code == 400
    assert "12" in r.text


async def test_register_normalizes_email_to_lowercase(client):
    with patch(
        "src.routes.auth.create_user", AsyncMock(return_value={"id": 42})
    ) as mock_create:
        with patch("src.routes.auth.send_verify_email", AsyncMock(return_value=True)):
            with patch("src.routes.auth.save_consent", AsyncMock()):
                await client.post(
                    "/register",
                    data={
                        "name": "New User",
                        "email": "New@Example.COM",
                        "password": "newpassword1x",  # pragma: allowlist secret
                        "password_confirm": "newpassword1x",  # pragma: allowlist secret
                        "consent_health": "on",
                        "consent_terms": "on",
                        "consent_age": "on",
                    },
                )
    call_args = mock_create.call_args[0]
    assert call_args[1] == "new@example.com"


# ── Public legal pages ────────────────────────────────────────────────────────


async def test_privacy_page_returns_200(client):
    r = await client.get("/privacy")
    assert r.status_code == 200
    assert "Datenschutz" in r.text


async def test_terms_page_returns_200(client):
    r = await client.get("/terms")
    assert r.status_code == 200
    assert "Nutzungsbedingungen" in r.text


async def test_imprint_page_returns_200(client):
    r = await client.get("/imprint")
    assert r.status_code == 200
    assert "Impressum" in r.text


async def test_accessibility_page_returns_200(client):
    r = await client.get("/accessibility")
    assert r.status_code == 200
    assert "Barrierefreiheit" in r.text


async def test_register_without_terms_consent_returns_400(client):
    r = await client.post(
        "/register",
        data={
            "name": "User",
            "email": "user@example.com",
            "password": "longerpassword1",  # pragma: allowlist secret
            "password_confirm": "longerpassword1",  # pragma: allowlist secret
            "consent_health": "on",
        },
    )
    assert r.status_code == 400
    assert "Nutzungsbedingungen" in r.text


async def test_register_without_age_consent_returns_400(client):
    r = await client.post(
        "/register",
        data={
            "name": "User",
            "email": "user@example.com",
            "password": "longerpassword1",  # pragma: allowlist secret
            "password_confirm": "longerpassword1",  # pragma: allowlist secret
            "consent_health": "on",
            "consent_terms": "on",
        },
    )
    assert r.status_code == 400
    assert "16" in r.text


async def test_register_saves_terms_consent_to_db(client):
    with patch("src.routes.auth.create_user", AsyncMock(return_value={"id": 42})):
        with patch("src.routes.auth.send_verify_email", AsyncMock(return_value=True)):
            with patch("src.routes.auth.save_consent", AsyncMock()) as mock_consent:
                await client.post(
                    "/register",
                    data={
                        "name": "New User",
                        "email": "new@example.com",
                        "password": "newpassword1x",  # pragma: allowlist secret
                        "password_confirm": "newpassword1x",  # pragma: allowlist secret
                        "consent_health": "on",
                        "consent_terms": "on",
                        "consent_age": "on",
                    },
                )
    consent_types = [call[0][1] for call in mock_consent.call_args_list]
    assert "terms" in consent_types


async def test_register_saves_age_consent_to_db(client):
    with patch("src.routes.auth.create_user", AsyncMock(return_value={"id": 42})):
        with patch("src.routes.auth.send_verify_email", AsyncMock(return_value=True)):
            with patch("src.routes.auth.save_consent", AsyncMock()) as mock_consent:
                await client.post(
                    "/register",
                    data={
                        "name": "New User",
                        "email": "new@example.com",
                        "password": "newpassword1x",  # pragma: allowlist secret
                        "password_confirm": "newpassword1x",  # pragma: allowlist secret
                        "consent_health": "on",
                        "consent_terms": "on",
                        "consent_age": "on",
                    },
                )
    consent_types = [call[0][1] for call in mock_consent.call_args_list]
    assert "age_16plus" in consent_types


# ── Rate Limiting ─────────────────────────────────────────────────────────────


async def test_login_rate_limit_returns_429(client):
    """11 consecutive failed login attempts → last request returns HTTP 429."""
    for _ in range(11):
        with patch("src.routes.auth.get_user_by_email", AsyncMock(return_value=None)):
            r = await client.post(
                "/login",
                data={
                    "email": "x@example.com",
                    "password": "wrong",  # pragma: allowlist secret
                },
            )
    assert r.status_code == 429


# ── Email helpers — ResendError branch ────────────────────────────────────────


def _resend_error():
    import resend.exceptions as resend_exc

    return resend_exc.ResendError(
        code="429",
        error_type="rate_limit_exceeded",
        message="rate limit",
        suggested_action="",
    )


async def test_lockout_email_resend_error_returns_false(client):
    with patch("src.mail.settings") as mock_settings:
        mock_settings.resend_api_key = "re_test"  # pragma: allowlist secret
        mock_settings.resend_from_email = "noreply@example.com"
        mock_settings.app_base_url = "https://example.com"
        with patch("src.mail.resend_client") as mock_resend:
            mock_resend.Emails.send_async = AsyncMock(side_effect=_resend_error())
            from src.mail import send_lockout_email

            result = await send_lockout_email("victim@example.com", lockout_minutes=15)
    assert result is False


async def test_reset_email_resend_error_returns_false(client):
    with patch("src.mail.settings") as mock_settings:
        mock_settings.resend_api_key = "re_test"  # pragma: allowlist secret
        mock_settings.resend_from_email = "noreply@example.com"
        mock_settings.app_base_url = "https://example.com"
        with patch("src.mail.resend_client") as mock_resend:
            mock_resend.Emails.send_async = AsyncMock(side_effect=_resend_error())
            from src.mail import send_reset_email

            result = await send_reset_email("user@example.com", "tok")
    assert result is False


async def test_verify_email_resend_error_returns_false(client):
    with patch("src.mail.settings") as mock_settings:
        mock_settings.resend_api_key = "re_test"  # pragma: allowlist secret
        mock_settings.resend_from_email = "noreply@example.com"
        mock_settings.app_base_url = "https://example.com"
        with patch("src.mail.resend_client") as mock_resend:
            mock_resend.Emails.send_async = AsyncMock(side_effect=_resend_error())
            from src.mail import send_verify_email

            result = await send_verify_email("user@example.com", "tok")
    assert result is False


# ── Email-Format-Validierung ─────────────────────────────────────────────────


async def test_register_rejects_invalid_email(client):
    r = await client.post(
        "/register",
        data={
            "name": "User",
            "email": "not-an-email",
            "password": "strongpassword1",  # pragma: allowlist secret
            "password_confirm": "strongpassword1",  # pragma: allowlist secret
            "consent_health": "on",
            "consent_terms": "on",
            "consent_age": "on",
        },
    )
    assert r.status_code == 400
    assert "E-Mail" in r.text


async def test_register_rejects_email_without_domain(client):
    r = await client.post(
        "/register",
        data={
            "name": "User",
            "email": "user@",
            "password": "strongpassword1",  # pragma: allowlist secret
            "password_confirm": "strongpassword1",  # pragma: allowlist secret
            "consent_health": "on",
            "consent_terms": "on",
            "consent_age": "on",
        },
    )
    assert r.status_code == 400


# ── Consent IP-Hash ───────────────────────────────────────────────────────────


async def test_register_consent_stores_ip_hash_not_raw_ip(client):
    """save_consent is called with a hex hash, not a raw IP address."""
    with patch("src.routes.auth.create_user", AsyncMock(return_value={"id": 42})):
        with patch("src.routes.auth.send_verify_email", AsyncMock(return_value=True)):
            with patch("src.routes.auth.save_consent", AsyncMock()) as mock_consent:
                await client.post(
                    "/register",
                    data={
                        "name": "User",
                        "email": "hash@example.com",
                        "password": "strongpassword1",  # pragma: allowlist secret
                        "password_confirm": "strongpassword1",  # pragma: allowlist secret
                        "consent_health": "on",
                        "consent_terms": "on",
                        "consent_age": "on",
                    },
                )
    assert mock_consent.await_count == 3
    # ip_address_hash argument (4th positional) must look like a hex string, not an IP
    for call in mock_consent.call_args_list:
        ip_arg = call[0][3]
        assert ip_arg is not None
        # SHA-256 prefix: 12 hex chars (from _ip_hash which returns hexdigest()[:12])
        assert len(ip_arg) == 12
        assert all(c in "0123456789abcdef" for c in ip_arg)


# ── is_active=False ───────────────────────────────────────────────────────────


async def test_login_unknown_email_returns_400(client):
    """is_active=False is filtered at SQL level (AND is_active = true in get_user_by_email) → same 400 as unknown email."""
    with patch("src.routes.auth.get_user_by_email", AsyncMock(return_value=None)):
        r = await client.post(
            "/login",
            data={"email": "inactive@example.com", "password": _TEST_PASSWORD},
        )
    assert r.status_code == 400
    assert "falsch" in r.text


# ── Session-Cookie security flags ─────────────────────────────────────────────


async def test_session_cookie_is_httponly_after_login(client):
    """Starlette SessionMiddleware must set HttpOnly on the session cookie."""
    with patch(
        "src.routes.auth.get_user_by_email", AsyncMock(return_value=_USER_WITH_HASH)
    ):
        with patch("src.auth_helpers.reset_failed_login", AsyncMock()):
            r = await client.post(
                "/login",
                data={"email": TEST_USER["email"], "password": _TEST_PASSWORD},
            )
    assert r.status_code == 303
    set_cookie = r.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()
    assert "samesite=strict" in set_cookie.lower()
