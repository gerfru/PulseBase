"""Tests for sync-service config.py and logging_config.py."""

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import Settings


def _base_env(
    monkeypatch, *, fernet_key: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
) -> None:
    monkeypatch.setenv("DB_APP_USER", "app_user")
    monkeypatch.setenv("DB_APP_PASSWORD", "app_pass")
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
    monkeypatch.setenv("DB_APP_USER", "myuser")
    monkeypatch.setenv("DB_APP_PASSWORD", "mypass")
    monkeypatch.setenv("DB_HOST", "dbhost")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "mydb")
    monkeypatch.setenv("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    settings = Settings()  # type: ignore[call-arg]
    expected = "postgresql://myuser:mypass@dbhost:5433/mydb"  # pragma: allowlist secret
    assert settings.db_url == expected
