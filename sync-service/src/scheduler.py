from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = structlog.get_logger(__name__)


async def _write_alive_sentinel() -> None:
    Path("/tmp/sync_alive").touch()  # nosec B108


def configure_scheduler(
    repo: Any,
    settings: Any,
    *,
    sync_all_users_fn: Callable,
    process_sync_requests_fn: Callable,
    sync_all_libre_fn: Callable,
    cleanup_events_fn: Callable | None = None,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        sync_all_users_fn,
        "interval",
        hours=settings.sync_interval_hours,
        args=[repo, settings.sync_daily_days, settings],
    )
    if getattr(settings, "sync_event_consumer_enabled", False) is not True:
        scheduler.add_job(
            process_sync_requests_fn,
            "interval",
            minutes=1,
            args=[repo, settings.sync_daily_days, settings],
        )
    scheduler.add_job(
        sync_all_libre_fn,
        "interval",
        minutes=5,
        args=[repo, settings],
        id="libre_sync",
    )
    scheduler.add_job(_write_alive_sentinel, "interval", minutes=1, id="healthcheck")
    if cleanup_events_fn is not None:
        scheduler.add_job(
            cleanup_events_fn,
            "interval",
            hours=24,
            id="service_events_retention",
        )
    scheduler.start()
    logger.info("scheduler.started", sync_interval_hours=settings.sync_interval_hours)
    return scheduler
