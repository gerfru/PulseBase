"""Targeted tests closing the remaining coverage gaps in sync-service.

Covers small glue/branch paths not exercised by the broader suite:
config.require_fernet_key, logging _sentry_error_processor, health_server,
scheduler, and a few main.py error/orchestration branches.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── config.require_fernet_key ─────────────────────────────────────────────────


def test_require_fernet_key_raises_when_empty():
    from config import require_fernet_key

    settings = MagicMock()
    settings.fernet_key = ""
    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        require_fernet_key(settings)


def test_require_fernet_key_returns_value():
    from config import require_fernet_key

    settings = MagicMock()
    settings.fernet_key = "abc"
    assert require_fernet_key(settings) == "abc"


# ── logging_config._sentry_error_processor ────────────────────────────────────


def test_sentry_processor_captures_exception_when_exc_info_true():
    import logging_config

    with patch.object(logging_config.sentry_sdk, "capture_exception") as cap:
        logging_config._sentry_error_processor(None, "error", {"exc_info": True})
        cap.assert_called_once_with()


def test_sentry_processor_captures_exc_info_tuple():
    import logging_config

    exc = (ValueError, ValueError("x"), None)
    with patch.object(logging_config.sentry_sdk, "capture_exception") as cap:
        logging_config._sentry_error_processor(None, "critical", {"exc_info": exc})
        cap.assert_called_once_with(exc)


# ── health_server ─────────────────────────────────────────────────────────────


async def test_health_handle_writes_ok_and_closes():
    from health_server import _handle

    reader = MagicMock()
    reader.read = AsyncMock(return_value=b"GET / HTTP/1.1\r\n\r\n")
    writer = MagicMock()
    writer.drain = AsyncMock()

    await _handle(reader, writer)

    writer.write.assert_called_once()
    assert b"200 OK" in writer.write.call_args[0][0]
    writer.close.assert_called_once()


async def test_start_health_server_starts_serving(monkeypatch):
    import health_server

    async def _served():
        return None

    fake_server = MagicMock()
    fake_server.serve_forever = lambda: _served()

    async def fake_start_server(handler, host, port):
        assert port == 9999
        return fake_server

    monkeypatch.setattr(health_server.asyncio, "start_server", fake_start_server)
    await health_server.start_health_server(port=9999)
    await asyncio.sleep(0)  # let the scheduled serve task run to completion


# ── scheduler ─────────────────────────────────────────────────────────────────


async def test_write_alive_sentinel_touches_file(monkeypatch):
    import scheduler

    touched = {}
    monkeypatch.setattr(
        scheduler.Path, "touch", lambda self: touched.__setitem__("done", True)
    )
    await scheduler._write_alive_sentinel()
    assert touched["done"] is True


def test_configure_scheduler_adds_jobs_and_starts(monkeypatch):
    import scheduler

    fake = MagicMock()
    monkeypatch.setattr(scheduler, "AsyncIOScheduler", lambda: fake)
    settings = MagicMock()
    settings.sync_interval_hours = 6
    settings.sync_daily_days = 2

    result = scheduler.configure_scheduler(
        repo=MagicMock(),
        settings=settings,
        sync_all_users_fn=lambda: None,
        process_sync_requests_fn=lambda: None,
        sync_all_libre_fn=lambda: None,
    )

    assert result is fake
    assert fake.add_job.call_count == 4
    fake.start.assert_called_once()


# ── main._sync_date_range: activity-sync failure is logged, not raised ─────────


async def test_sync_date_range_handles_activity_failure(monkeypatch):
    import main

    monkeypatch.setattr(
        main, "_sync_activities", AsyncMock(side_effect=RuntimeError("boom"))
    )
    monkeypatch.setattr(main, "_sync_day", AsyncMock())

    # days=0 → single day loop; must complete without raising despite the failure
    await main._sync_date_range(MagicMock(), MagicMock(), user_id=1, days=0)
    main._sync_day.assert_awaited()


# ── main.sync_libre_user: invalid token JSON → LibreAuthError ─────────────────


async def test_sync_libre_user_invalid_token_format_raises(monkeypatch):
    import main
    from libre.client import LibreAuthError

    repo = MagicMock()
    repo.get_user_token = AsyncMock(return_value=b"encrypted-blob")
    monkeypatch.setattr(main, "require_fernet_key", lambda s: "key")
    monkeypatch.setattr(main, "fernet_decrypt", lambda blob, key: b"not-json")

    with pytest.raises(LibreAuthError, match="Ungültiges Token-Format"):
        await main.sync_libre_user({"id": 1}, repo, MagicMock())


# ── main._run_initial_sync: completes vs shutdown ─────────────────────────────


async def test_run_initial_sync_completes_without_shutdown(monkeypatch):
    import main

    monkeypatch.setattr(main, "sync_all_users", AsyncMock())
    settings = MagicMock()
    settings.sync_lookback_days = 1
    ev = asyncio.Event()

    result = await main._run_initial_sync(MagicMock(), settings, ev)
    assert result is False
    ev.set()
    await asyncio.sleep(0)  # let the leftover shutdown-wait task resolve


async def test_run_initial_sync_returns_true_on_shutdown(monkeypatch):
    import main

    monkeypatch.setattr(main, "sync_all_users", AsyncMock())
    settings = MagicMock()
    settings.sync_lookback_days = 1
    ev = asyncio.Event()
    ev.set()  # shutdown already requested

    result = await main._run_initial_sync(MagicMock(), settings, ev)
    assert result is True
