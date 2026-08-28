import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
import structlog

from repositories.service_events import TimescaleServiceEventRepository
from repositories.timescale import TimescaleRepository
from sync_runner import sync_user

logger = structlog.get_logger(__name__)


async def process_sync_events(
    queue: TimescaleServiceEventRepository,
    repo: TimescaleRepository,
    settings: Any,
    *,
    batch_size: int = 10,
    sync_user_fn: Callable[..., Awaitable[None]] = sync_user,
) -> None:
    stale = await queue.requeue_stale_events()
    if stale:
        logger.warning("sync_queue.stale_requeued", count=stale)

    while True:
        events = await queue.claim_sync_events(batch_size)
        if not events:
            break
        for event in events:
            event_id = int(event["id"])
            user_id = int(event["user_id"])
            attempts = int(event["attempts"])
            user = await repo.get_sync_user(user_id)
            if user is None:
                await repo.clear_sync_requested(user_id)
                status = await queue.complete_event(event_id)
                logger.info(
                    "sync_event.skipped_ineligible",
                    event_id=event_id,
                    user_id=user_id,
                    status=status,
                )
                continue

            logger.info("sync_event.started", event_id=event_id, user_id=user_id)
            try:
                await sync_user_fn(
                    user,
                    repo,
                    days=settings.sync_daily_days,
                    settings=settings,
                )
                await repo.set_ml_requested(user_id)
                await repo.mark_sync_done(user_id)
                status = await queue.complete_event(event_id)
                logger.info(
                    "sync_event.completed",
                    event_id=event_id,
                    user_id=user_id,
                    status=status,
                )
            except Exception as error:
                status = await queue.fail_event(
                    event_id,
                    str(error),
                    attempts,
                )
                logger.error(
                    "sync_event.failed",
                    event_id=event_id,
                    user_id=user_id,
                    attempts=attempts,
                    terminal=status == "failed",
                    error_type=type(error).__name__,
                    exc_info=True,
                )

    metrics = await queue.queue_metrics()
    logger.info("sync_queue.snapshot", **metrics)


async def run_sync_event_consumer(
    db_url: str,
    queue: TimescaleServiceEventRepository,
    repo: TimescaleRepository,
    settings: Any,
    stop_event: asyncio.Event,
    *,
    process_events: Callable[[], Awaitable[None]] | None = None,
) -> None:
    drain = process_events or (lambda: process_sync_events(queue, repo, settings))
    sweep_seconds = max(int(settings.sync_event_sweep_seconds), 1)

    while not stop_event.is_set():
        connection: asyncpg.Connection | None = None
        wakeup = asyncio.Event()

        def on_event(*_args: object) -> None:
            wakeup.set()

        try:
            connection = await asyncpg.connect(db_url)
            await connection.add_listener("service_events", on_event)
            logger.info("sync_event_listener.connected")

            while not stop_event.is_set():
                await drain()
                if stop_event.is_set():
                    break
                wakeup_task = asyncio.create_task(wakeup.wait())
                stop_task = asyncio.create_task(stop_event.wait())
                done, pending = await asyncio.wait(
                    {wakeup_task, stop_task},
                    timeout=sweep_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    task.result()
                wakeup.clear()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning(
                "sync_event_listener.disconnected",
                error_type=type(error).__name__,
            )
            try:
                await drain()
            except Exception as drain_error:
                logger.error(
                    "sync_event_consumer.sweep_failed",
                    error_type=type(drain_error).__name__,
                    exc_info=True,
                )
            if not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=5)
                except TimeoutError:
                    pass
        finally:
            if connection is not None:
                await connection.close()
                logger.info("sync_event_listener.closed")
