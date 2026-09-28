"""Tests fuer dauerhaft geplante Insights-Berichte."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from src.db.insight_jobs import (
    claim_daily_jobs,
    complete_daily_job,
    enqueue_daily_jobs,
    fail_daily_job,
    get_daily_job_status,
    requeue_stale_daily_jobs,
)


class _Transaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *args):
        return False


class _Connection:
    def __init__(self):
        self.fetch = AsyncMock()

    def transaction(self):
        return _Transaction()


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *args):
        return False


async def test_enqueue_only_active_linked_users_once_per_period():
    pool = AsyncMock()
    pool.execute.return_value = "INSERT 0 2"
    period_end = date(2026, 6, 14)

    with patch("src.db.insight_jobs.get_pool", AsyncMock(return_value=pool)):
        queued = await enqueue_daily_jobs(period_end)

    assert queued == 2
    query, actual_end = pool.execute.await_args.args
    assert actual_end == period_end
    assert "is_active = true" in query
    assert "users.garmin_linked = true OR users.libre_linked = true" in query
    assert "text.user_id = users.id AND text.period_end = $1" in query
    assert "text.segment = 'report'" in query
    assert "ON CONFLICT (user_id, period_end) DO NOTHING" in query


async def test_claim_jobs_is_atomic_and_bounded():
    connection = _Connection()
    connection.fetch.return_value = [
        {"user_id": 9, "period_end": date(2026, 6, 14), "attempts": 1}
    ]
    pool = MagicMock()
    pool.acquire.return_value = _Acquire(connection)

    with patch("src.db.insight_jobs.get_pool", AsyncMock(return_value=pool)):
        jobs = await claim_daily_jobs(limit=2)

    assert jobs == [{"user_id": 9, "period_end": date(2026, 6, 14), "attempts": 1}]
    query, limit = connection.fetch.await_args.args
    assert limit == 2
    assert "FOR UPDATE SKIP LOCKED" in query
    assert "attempts = job.attempts + 1" in query


async def test_complete_job_requires_claimed_status():
    pool = AsyncMock()
    with patch("src.db.insight_jobs.get_pool", AsyncMock(return_value=pool)):
        await complete_daily_job(9, date(2026, 6, 14), 2)
    query, user_id, period_end, attempts = pool.execute.await_args.args
    assert (user_id, period_end, attempts) == (9, date(2026, 6, 14), 2)
    assert "status = 'processing'" in query
    assert "status = 'completed'" in query
    assert "attempts = $3" in query


async def test_fail_job_limits_retries_and_sanitizes_error():
    pool = AsyncMock()
    pool.fetchval.return_value = "failed"
    with patch("src.db.insight_jobs.get_pool", AsyncMock(return_value=pool)):
        result = await fail_daily_job(9, date(2026, 6, 14), 3, "TimeoutError")
    assert result == "failed"
    query, user_id, period_end, attempts, max_attempts, error_code, delay = (
        pool.fetchval.await_args.args
    )
    assert (user_id, period_end, attempts, max_attempts) == (9, date(2026, 6, 14), 3, 3)
    assert error_code == "TimeoutError"
    assert delay > 0
    assert "WHEN $3 >= $4 THEN 'failed'" in query


async def test_requeue_stale_claims_up_to_retry_limit():
    pool = AsyncMock()
    pool.execute.return_value = "UPDATE 2"
    with patch("src.db.insight_jobs.get_pool", AsyncMock(return_value=pool)):
        recovered = await requeue_stale_daily_jobs()
    assert recovered == 2
    query = pool.execute.await_args.args[0]
    assert "claimed_at < NOW()" in query
    assert "WHEN job.attempts >= $2 THEN 'failed'" in query
    assert "WHEN stale.has_report THEN 'completed'" in query
    assert "WHEN stale.has_report OR job.attempts >= $2" in query
    assert "last_error = CASE WHEN stale.has_report THEN NULL" in query


async def test_job_status_is_scoped_to_user_and_period():
    pool = AsyncMock()
    pool.fetchval.return_value = "pending"
    with patch("src.db.insight_jobs.get_pool", AsyncMock(return_value=pool)):
        status = await get_daily_job_status(9, date(2026, 6, 14))
    assert status == "pending"
    query, user_id, period_end = pool.fetchval.await_args.args
    assert "user_id = $1 AND period_end = $2" in query
    assert (user_id, period_end) == (9, date(2026, 6, 14))
