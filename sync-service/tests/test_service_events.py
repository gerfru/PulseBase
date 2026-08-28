import asyncio
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from events.consumer import process_sync_events, run_sync_event_consumer
from repositories.service_events import (
    TimescaleServiceEventRepository,
    retry_delay_seconds,
)


@pytest.fixture
def event_repository():
    pool = MagicMock()
    pool.execute = AsyncMock(return_value="UPDATE 0")
    pool.fetchrow = AsyncMock(return_value=None)
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock()
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return TimescaleServiceEventRepository(pool), pool, conn


def settings():
    result = MagicMock()
    result.sync_daily_days = 2
    result.sync_event_sweep_seconds = 30
    return result


class TestServiceEventRepository:
    async def test_claim_uses_skip_locked_and_records_generation(
        self, event_repository
    ):
        repository, _pool, conn = event_repository
        conn.fetch.return_value = [
            {"id": 7, "user_id": 42, "attempts": 1, "claimed_generation": 3}
        ]

        events = await repository.claim_sync_events(limit=4)

        assert events[0]["claimed_generation"] == 3
        sql = conn.fetch.call_args.args[0]
        assert "FOR UPDATE SKIP LOCKED" in sql
        assert "claimed_generation = event.generation" in sql
        assert conn.fetch.call_args.args[1] == 4

    async def test_complete_preserves_retriggered_work(self, event_repository):
        repository, pool, _conn = event_repository
        pool.fetchrow.return_value = {"status": "pending"}

        status = await repository.complete_event(7)

        assert status == "pending"
        sql = pool.fetchrow.call_args.args[0]
        assert "generation > claimed_generation" in sql
        assert "THEN 'pending'" in sql

    async def test_failure_uses_exponential_backoff_and_bounded_error(
        self, event_repository
    ):
        repository, pool, _conn = event_repository
        pool.fetchrow.return_value = {"status": "pending"}
        error = "x" * 5000

        with patch("repositories.service_events.random.uniform", return_value=1.0):
            status = await repository.fail_event(9, error, attempts=3)

        assert status == "pending"
        args = pool.fetchrow.call_args.args
        assert len(args[2]) == 2000
        assert args[3:6] == (3, 5, 120)

    def test_retry_delay_is_exponential_and_capped(self):
        with patch("repositories.service_events.random.uniform", return_value=1.0):
            assert retry_delay_seconds(1) == 30
            assert retry_delay_seconds(4) == 240
            assert retry_delay_seconds(20) == 900


class TestProcessSyncEvents:
    async def test_success_syncs_user_enqueues_ml_and_completes(self):
        queue = AsyncMock()
        queue.requeue_stale_events.return_value = 0
        queue.claim_sync_events.side_effect = [
            [{"id": 5, "user_id": 42, "attempts": 1}],
            [],
        ]
        queue.complete_event.return_value = "completed"
        queue.queue_metrics.return_value = {
            "pending": 0,
            "processing": 0,
            "failed": 0,
            "oldest_pending_seconds": 0.0,
        }
        repo = AsyncMock()
        repo.get_sync_user.return_value = {"id": 42, "garmin_email": "x@test.com"}
        sync = AsyncMock()

        await process_sync_events(queue, repo, settings(), sync_user_fn=sync)

        sync.assert_awaited_once()
        repo.set_ml_requested.assert_awaited_once_with(42)
        repo.mark_sync_done.assert_awaited_once_with(42)
        queue.complete_event.assert_awaited_once_with(5)
        queue.fail_event.assert_not_awaited()

    async def test_failure_retries_without_marking_sync_done(self):
        queue = AsyncMock()
        queue.requeue_stale_events.return_value = 0
        queue.claim_sync_events.side_effect = [
            [{"id": 6, "user_id": 43, "attempts": 2}],
            [],
        ]
        queue.fail_event.return_value = "pending"
        queue.queue_metrics.return_value = {}
        repo = AsyncMock()
        repo.get_sync_user.return_value = {"id": 43, "garmin_email": "x@test.com"}
        sync = AsyncMock(side_effect=RuntimeError("temporary"))

        await process_sync_events(queue, repo, settings(), sync_user_fn=sync)

        queue.fail_event.assert_awaited_once_with(6, "temporary", 2)
        repo.set_ml_requested.assert_not_awaited()
        repo.mark_sync_done.assert_not_awaited()
        queue.complete_event.assert_not_awaited()

    async def test_ineligible_user_is_completed_without_sync(self):
        queue = AsyncMock()
        queue.requeue_stale_events.return_value = 0
        queue.claim_sync_events.side_effect = [
            [{"id": 8, "user_id": 99, "attempts": 1}],
            [],
        ]
        queue.complete_event.return_value = "completed"
        queue.queue_metrics.return_value = {}
        repo = AsyncMock()
        repo.get_sync_user.return_value = None
        sync = AsyncMock()

        await process_sync_events(queue, repo, settings(), sync_user_fn=sync)

        sync.assert_not_awaited()
        repo.clear_sync_requested.assert_awaited_once_with(99)
        queue.complete_event.assert_awaited_once_with(8)


class TestSyncEventConsumer:
    async def test_notification_wakes_consumer_and_connection_closes(self):
        stop_event = asyncio.Event()
        connection = MagicMock()
        connection.close = AsyncMock()
        wake_callback = None

        async def add_listener(_channel, callback):
            nonlocal wake_callback
            wake_callback = callback

        connection.add_listener = AsyncMock(side_effect=add_listener)
        process = AsyncMock()

        async def drain():
            await process()
            if process.await_count == 1:
                assert wake_callback is not None
                wake_callback(None, 0, "service_events", "1")
            else:
                stop_event.set()

        with patch(
            "events.consumer.asyncpg.connect",
            new_callable=AsyncMock,
            return_value=connection,
        ):
            await run_sync_event_consumer(
                "postgresql://test",
                AsyncMock(),
                AsyncMock(),
                settings(),
                stop_event,
                process_events=drain,
            )

        assert process.await_count == 2
        connection.add_listener.assert_awaited_once_with(
            "service_events", wake_callback
        )
        connection.close.assert_awaited_once()
