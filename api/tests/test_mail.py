"""Tests for api/src/mail.py email helper functions."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSendEmail:
    @pytest.mark.asyncio
    async def test_returns_false_when_no_api_key(self):
        with patch("src.mail.settings") as mock_settings:
            mock_settings.resend_api_key = ""
            from src.mail import _send_email

            result = await _send_email("a@b.com", "Subject", "<p>body</p>", "test")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        with (
            patch("src.mail.settings") as mock_settings,
            patch("src.mail.resend_client") as mock_resend,
        ):
            mock_settings.resend_api_key = "re_test_123"  # pragma: allowlist secret
            mock_settings.resend_from_email = "no-reply@example.com"
            mock_resend.Emails.send_async = AsyncMock(return_value={"id": "ok"})
            from src.mail import _send_email

            result = await _send_email("a@b.com", "Subject", "<p>body</p>", "test")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_resend_error(self):
        import resend.exceptions as resend_exc

        err = resend_exc.ResendError.__new__(resend_exc.ResendError)
        err.message = "invalid api key"
        with (
            patch("src.mail.settings") as mock_settings,
            patch("src.mail.resend_client") as mock_resend,
        ):
            mock_settings.resend_api_key = "re_bad"  # pragma: allowlist secret
            mock_settings.resend_from_email = "no-reply@example.com"
            mock_resend.Emails.send_async = AsyncMock(side_effect=err)
            from src.mail import _send_email

            result = await _send_email("a@b.com", "Subject", "<p>body</p>", "test")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_unexpected_exception(self):
        with (
            patch("src.mail.settings") as mock_settings,
            patch("src.mail.resend_client") as mock_resend,
        ):
            mock_settings.resend_api_key = "re_test"  # pragma: allowlist secret
            mock_settings.resend_from_email = "no-reply@example.com"
            mock_resend.Emails.send_async = AsyncMock(
                side_effect=RuntimeError("network")
            )
            from src.mail import _send_email

            result = await _send_email("a@b.com", "Subject", "<p>body</p>", "test")
        assert result is False


class TestPublicMailFunctions:
    @pytest.mark.asyncio
    async def test_send_lockout_email_delegates(self):
        with patch(
            "src.mail._send_email", new_callable=AsyncMock, return_value=True
        ) as mock_send:
            from src.mail import send_lockout_email

            result = await send_lockout_email("a@b.com", lockout_minutes=15)
        assert result is True
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["log_key"] == "lockout"

    @pytest.mark.asyncio
    async def test_send_reset_email_delegates(self):
        with (
            patch(
                "src.mail._send_email", new_callable=AsyncMock, return_value=True
            ) as mock_send,
            patch("src.mail.settings") as mock_settings,
        ):
            mock_settings.app_base_url = "https://example.com"
            from src.mail import send_reset_email

            result = await send_reset_email("a@b.com", "tok123")
        assert result is True
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["log_key"] == "reset"

    @pytest.mark.asyncio
    async def test_send_verify_email_delegates(self):
        with (
            patch(
                "src.mail._send_email", new_callable=AsyncMock, return_value=True
            ) as mock_send,
            patch("src.mail.settings") as mock_settings,
        ):
            mock_settings.app_base_url = "https://example.com"
            from src.mail import send_verify_email

            result = await send_verify_email("a@b.com", "vtok")
        assert result is True
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["log_key"] == "verify"
