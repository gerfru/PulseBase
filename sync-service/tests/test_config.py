"""Tests for sync-service config.py and logging_config.py."""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import Settings


def _base_env(
    monkeypatch, *, fernet_key: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
) -> None:
    monkeypatch.setenv("DB_SYNC_USER", "sync_user")
    monkeypatch.setenv("DB_SYNC_PASSWORD", "sync_pass")
    monkeypatch.setenv("FERNET_KEY", fernet_key)


def test_fernet_key_validator_rejects_empty_string(monkeypatch):
    _base_env(monkeypatch, fernet_key="")
    with pytest.raises(Exception):  # pydantic ValidationError
        Settings()  # type: ignore[call-arg]


def test_log_level_defaults_to_info(monkeypatch):
    """M-81: Default LOG_LEVEL must be INFO when env var is absent."""
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    from logging_config import configure_logging

    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_log_level_from_env_debug(monkeypatch):
    """M-81: LOG_LEVEL=DEBUG must set root logger to DEBUG."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    from logging_config import configure_logging

    configure_logging()
    assert logging.getLogger().level == logging.DEBUG


def test_db_url_property_contains_credentials(monkeypatch):
    monkeypatch.setenv("DB_SYNC_USER", "myuser")
    monkeypatch.setenv("DB_SYNC_PASSWORD", "mypass")
    monkeypatch.setenv("DB_HOST", "dbhost")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "mydb")
    monkeypatch.setenv("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    settings = Settings()  # type: ignore[call-arg]
    expected = "postgresql://myuser:mypass@dbhost:5433/mydb"  # pragma: allowlist secret
    assert settings.db_url == expected


# ── configure_sentry ──────────────────────────────────────────────────────────


def test_configure_sentry_noop_when_no_dsn():
    """M-11: configure_sentry must not call sentry_sdk.init when SENTRY_DSN is not set."""
    from logging_config import configure_sentry

    settings = MagicMock()
    settings.sentry_dsn = ""
    with patch("sentry_sdk.init") as mock_init:
        configure_sentry(settings)
    mock_init.assert_not_called()


def test_configure_sentry_no_pii_when_dsn_set():
    """M-11: configure_sentry must set send_default_pii=False."""
    from logging_config import configure_sentry

    settings = MagicMock()
    settings.sentry_dsn = "https://x@sentry.io/1"
    with patch("sentry_sdk.init") as mock_init:
        configure_sentry(settings)
    mock_init.assert_called_once()
    assert mock_init.call_args.kwargs["send_default_pii"] is False


def test_configure_sentry_release_is_package_version_not_unknown():
    """WS1: Sentry release derives from the installed package, not 'unknown'."""
    from logging_config import configure_sentry

    settings = MagicMock()
    settings.sentry_dsn = "https://x@sentry.io/1"
    with patch("sentry_sdk.init") as mock_init:
        configure_sentry(settings)
    release = mock_init.call_args.kwargs["release"]
    assert release != "unknown"
    assert release[0].isdigit()


def test_release_prefers_app_version_env(monkeypatch):
    """_release(): APP_VERSION env override wins (line 17)."""
    from logging_config import _release

    monkeypatch.setenv("APP_VERSION", "9.9.9")
    assert _release() == "9.9.9"


def test_release_falls_back_to_unknown(monkeypatch):
    """_release(): no env, no dist, unreadable pyproject → 'unknown' (lines 29-30)."""
    import importlib.metadata

    from logging_config import _release

    monkeypatch.delenv("APP_VERSION", raising=False)
    with (
        patch(
            "importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError,
        ),
        patch("pathlib.Path.read_text", side_effect=OSError("boom")),
    ):
        assert _release() == "unknown"
