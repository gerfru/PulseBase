"""Tests for config.py, logging_config.py, and backfill_energy.py (CLI script)."""

import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Settings ──────────────────────────────────────────────────────────────────


class TestSettings:
    def test_db_url_contains_credentials(self):
        from config import Settings

        s = Settings(db_app_user="myapp", db_app_password="s3cr3t")
        assert "myapp" in s.db_url
        assert "s3cr3t" in s.db_url
        assert s.db_url.startswith("postgresql://")

    def test_db_url_contains_host_and_db(self):
        from config import Settings

        s = Settings(db_app_user="u", db_app_password="p")
        assert "db" in s.db_url
        assert "garmin" in s.db_url

    def test_defaults(self):
        from config import Settings

        s = Settings(db_app_user="u", db_app_password="p")
        assert s.db_host == "db"
        assert s.db_port == 5432
        assert s.ml_infer_hour == 7
        assert s.ml_train_weekday == 6
        assert s.sentry_dsn == ""

    def test_model_dir_is_path(self):
        from config import Settings

        s = Settings(db_app_user="u", db_app_password="p")
        assert isinstance(s.model_dir, Path)


# ── logging_config ─────────────────────────────────────────────────────────────


class TestConfigureLogging:
    def test_runs_without_error(self):
        from logging_config import configure_logging

        configure_logging()

    def test_suppresses_httpx_to_warning(self):
        from logging_config import configure_logging

        configure_logging()
        assert logging.getLogger("httpx").level == logging.WARNING

    def test_suppresses_apscheduler_to_warning(self):
        from logging_config import configure_logging

        configure_logging()
        assert logging.getLogger("apscheduler").level == logging.WARNING

    def test_log_level_defaults_to_info(self, monkeypatch):
        """M-81: Default LOG_LEVEL must be INFO when env var is absent."""
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        from logging_config import configure_logging

        configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_log_level_from_env_debug(self, monkeypatch):
        """M-81: LOG_LEVEL=DEBUG must set root logger to DEBUG."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        from logging_config import configure_logging

        configure_logging()
        assert logging.getLogger().level == logging.DEBUG


# ── backfill_energy (CLI entry point) ─────────────────────────────────────────


class TestBackfillEnergyMain:
    async def test_skips_when_no_users(self):
        from backfill_energy import main

        mock_pool = MagicMock()
        mock_pool.fetch = AsyncMock(return_value=[])
        mock_settings = MagicMock()
        mock_settings.db_url = "postgresql://u:p@localhost/garmin_test"

        with (
            patch("backfill_energy.init_pool", new_callable=AsyncMock),
            patch("backfill_energy.close_pool", new_callable=AsyncMock),
            patch("backfill_energy.get_pool", return_value=mock_pool),
            patch("backfill_energy.Settings", return_value=mock_settings),
        ):
            await main()

        mock_pool.fetch.assert_called_once()

    async def test_calls_backfill_for_each_user(self):
        from backfill_energy import main

        mock_pool = MagicMock()
        mock_pool.fetch = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        mock_settings = MagicMock()
        mock_settings.db_url = "postgresql://u:p@localhost/garmin_test"

        with (
            patch("backfill_energy.init_pool", new_callable=AsyncMock),
            patch("backfill_energy.close_pool", new_callable=AsyncMock),
            patch("backfill_energy.get_pool", return_value=mock_pool),
            patch("backfill_energy.Settings", return_value=mock_settings),
            patch(
                "backfill_energy.backfill_user", new_callable=AsyncMock, return_value=0
            ) as mock_bf,
        ):
            await main()

        assert mock_bf.call_count == 2

    async def test_close_pool_called_on_error(self):
        from backfill_energy import main

        mock_pool = MagicMock()
        mock_pool.fetch = AsyncMock(side_effect=RuntimeError("db down"))
        mock_settings = MagicMock()
        mock_settings.db_url = "postgresql://u:p@localhost/garmin_test"
        close_mock = AsyncMock()

        with (
            patch("backfill_energy.init_pool", new_callable=AsyncMock),
            patch("backfill_energy.close_pool", close_mock),
            patch("backfill_energy.get_pool", return_value=mock_pool),
            patch("backfill_energy.Settings", return_value=mock_settings),
        ):
            with pytest.raises(RuntimeError):
                await main()

        close_mock.assert_called_once()
