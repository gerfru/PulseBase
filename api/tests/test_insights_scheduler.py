"""Tests fuer die taegliche Insights-Planung und ihren Worker."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.insights.scheduler import daily_trigger, enqueue_reports, process_daily_jobs
from src.main import app, lifespan

_END = date(2026, 6, 14)
_JOB = {"user_id": 9, "period_end": _END, "attempts": 1}


def test_daily_trigger_uses_vienna_time_through_dst():
    trigger = daily_trigger()
    assert trigger.get_next_fire_time(
        None, datetime(2026, 3, 28, 4, 1, tzinfo=UTC)
    ) == datetime(2026, 3, 29, 3, tzinfo=UTC)
    assert trigger.get_next_fire_time(
        None, datetime(2026, 10, 24, 3, 1, tzinfo=UTC)
    ) == datetime(2026, 10, 25, 4, tzinfo=UTC)


async def test_daily_trigger_enqueues_yesterdays_window_once():
    with (
        patch("src.insights.scheduler.current_period_end", return_value=_END),
        patch(
            "src.insights.scheduler.enqueue_daily_jobs", AsyncMock(return_value=2)
        ) as enqueue,
    ):
        assert await enqueue_reports() == 2
    enqueue.assert_awaited_once_with(_END)


async def test_worker_completes_one_claimed_period():
    with (
        patch("src.insights.scheduler.requeue_stale_daily_jobs", AsyncMock()),
        patch(
            "src.insights.scheduler.claim_daily_jobs", AsyncMock(return_value=[_JOB])
        ),
        patch("src.insights.scheduler.get_or_generate", AsyncMock()) as generate,
        patch("src.insights.scheduler.complete_daily_job", AsyncMock()) as complete,
    ):
        assert await process_daily_jobs() == 1
    generate.assert_awaited_once_with(9, _END)
    complete.assert_awaited_once_with(9, _END, 1)


async def test_worker_retries_without_storing_sensitive_error_message():
    with (
        patch("src.insights.scheduler.requeue_stale_daily_jobs", AsyncMock()),
        patch(
            "src.insights.scheduler.claim_daily_jobs", AsyncMock(return_value=[_JOB])
        ),
        patch(
            "src.insights.scheduler.get_or_generate",
            AsyncMock(side_effect=TimeoutError("private")),
        ),
        patch(
            "src.insights.scheduler.fail_daily_job", AsyncMock(return_value="pending")
        ) as fail,
    ):
        assert await process_daily_jobs() == 1
    fail.assert_awaited_once_with(9, _END, 1, "TimeoutError")


async def test_api_lifespan_starts_and_stops_daily_worker():
    pool = AsyncMock()
    scheduler = MagicMock()

    async def worker(stop_event):
        await stop_event.wait()

    with (
        patch("src.main.get_pool", AsyncMock(return_value=pool)),
        patch("src.main.configure_sentry"),
        patch("src.main.settings.insights_daily_enabled", True),
        patch("src.main.start_daily_scheduler", return_value=scheduler) as start,
        patch("src.main.run_daily_worker", side_effect=worker),
    ):
        async with lifespan(app):
            start.assert_called_once_with()

    scheduler.shutdown.assert_called_once_with(wait=False)
    pool.close.assert_awaited_once()


async def test_api_lifespan_disables_daily_jobs_with_kill_switch():
    pool = AsyncMock()
    with (
        patch("src.main.get_pool", AsyncMock(return_value=pool)),
        patch("src.main.configure_sentry"),
        patch("src.main.settings.insights_daily_enabled", False),
        patch("src.main.start_daily_scheduler") as start,
        patch("src.main.run_daily_worker", AsyncMock()) as worker,
    ):
        async with lifespan(app):
            start.assert_not_called()
            worker.assert_not_awaited()
    pool.close.assert_awaited_once()
