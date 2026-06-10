import asyncio
import signal
from pathlib import Path

import structlog

from config import Settings
from health_server import set_pool as set_health_pool, start_health_server
from logging_config import configure_logging, configure_sentry
from repositories.timescale import TimescaleRepository
from scheduler import configure_scheduler
from sync_runner import process_sync_requests, sync_all_libre, sync_all_users

configure_logging()
logger = structlog.get_logger(__name__)


async def _run_initial_sync(
    repo: TimescaleRepository, settings: Settings, shutdown_event: asyncio.Event
) -> bool:
    """Run the initial full sync as a cancellable task. Returns True if shutdown triggered."""
    logger.info("sync.initial", lookback_days=settings.sync_lookback_days)
    initial_task = asyncio.create_task(
        sync_all_users(repo, days=settings.sync_lookback_days, settings=settings)
    )
    await asyncio.wait(
        {initial_task, asyncio.create_task(shutdown_event.wait())},
        return_when=asyncio.FIRST_COMPLETED,
    )
    if shutdown_event.is_set():
        initial_task.cancel()
        await asyncio.gather(initial_task, return_exceptions=True)
        logger.info("shutdown.during_initial_sync")
        return True
    return False


async def main() -> None:  # pragma: no cover
    settings = Settings()  # type: ignore[call-arg]
    try:
        from cryptography.fernet import Fernet

        Fernet(settings.fernet_key.encode())
    except Exception:
        raise ValueError("FERNET_KEY invalid — must be 32-byte URL-safe base64")

    configure_sentry(settings)

    # SIGTERM handler registered BEFORE blocking work so make down responds immediately
    shutdown_event = asyncio.Event()

    def _on_sigterm() -> None:
        logger.info("shutdown.sigterm_received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, _on_sigterm)

    await start_health_server()

    repo = TimescaleRepository(settings.db_url)
    await repo.init()
    set_health_pool(repo._pool)

    # Sentinel written at startup so the healthcheck passes during the initial sync
    Path("/tmp/sync_alive").touch()  # nosec B108

    if await _run_initial_sync(repo, settings, shutdown_event):
        await repo.close()
        return

    scheduler = configure_scheduler(
        repo,
        settings,
        sync_all_users_fn=sync_all_users,
        process_sync_requests_fn=process_sync_requests,
        sync_all_libre_fn=sync_all_libre,
    )
    await shutdown_event.wait()

    logger.info("shutdown.graceful_start")
    scheduler.shutdown(wait=True)
    logger.info("shutdown.complete")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
