"""Dauerhafte Tagesauftraege fuer einen Insights-Bericht pro Zeitraum."""

from __future__ import annotations

from datetime import date
from typing import Any

from .pool import get_pool


async def enqueue_daily_jobs(period_end: date) -> int:
    pool = await get_pool()
    result = await pool.execute(
        """INSERT INTO insights_daily_jobs (user_id, period_end)
                     SELECT users.id, $1 FROM users
                     WHERE users.is_active = true
                         AND (users.garmin_linked = true OR users.libre_linked = true)
                         AND NOT EXISTS (
                                 SELECT 1 FROM weekly_insight_texts AS text
                                 WHERE text.user_id = users.id AND text.period_end = $1
                                     AND text.segment = 'report'
                         )
           ON CONFLICT (user_id, period_end) DO NOTHING""",
        period_end,
    )
    return int(result.rsplit(" ", 1)[-1])


async def claim_daily_jobs(limit: int = 1) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn, conn.transaction():
        rows = await conn.fetch(
            """WITH candidates AS (
                   SELECT user_id, period_end FROM insights_daily_jobs
                   WHERE status = 'pending' AND available_at <= NOW()
                   ORDER BY period_end, user_id
                   FOR UPDATE SKIP LOCKED
                   LIMIT $1
               )
               UPDATE insights_daily_jobs AS job
               SET status = 'processing', claimed_at = NOW(),
                   attempts = job.attempts + 1, last_error = NULL
               FROM candidates
               WHERE job.user_id = candidates.user_id
                 AND job.period_end = candidates.period_end
               RETURNING job.user_id, job.period_end, job.attempts""",
            limit,
        )
    return [dict(row) for row in rows]


async def complete_daily_job(user_id: int, period_end: date, attempts: int) -> None:
    pool = await get_pool()
    await pool.execute(
        """UPDATE insights_daily_jobs
           SET status = 'completed', claimed_at = NULL,
               finished_at = NOW(), last_error = NULL
           WHERE user_id = $1 AND period_end = $2
             AND status = 'processing' AND attempts = $3""",
        user_id,
        period_end,
        attempts,
    )


async def fail_daily_job(
    user_id: int,
    period_end: date,
    attempts: int,
    error_code: str,
    max_attempts: int = 3,
) -> str | None:
    pool = await get_pool()
    delay = min(30 * 2 ** (attempts - 1), 900)
    return await pool.fetchval(
        """UPDATE insights_daily_jobs
           SET status = CASE WHEN $3 >= $4 THEN 'failed' ELSE 'pending' END,
               available_at = CASE WHEN $3 >= $4 THEN available_at
                                   ELSE NOW() + ($6 * INTERVAL '1 second') END,
               claimed_at = NULL,
               finished_at = CASE WHEN $3 >= $4 THEN NOW() ELSE NULL END,
               last_error = $5
           WHERE user_id = $1 AND period_end = $2
             AND status = 'processing' AND attempts = $3
           RETURNING status""",
        user_id,
        period_end,
        attempts,
        max_attempts,
        error_code,
        delay,
    )


async def requeue_stale_daily_jobs(
    lease_seconds: int = 1800, max_attempts: int = 3
) -> int:
    pool = await get_pool()
    result = await pool.execute(
        """WITH stale AS (
               SELECT job.user_id, job.period_end,
                      EXISTS (
                          SELECT 1 FROM weekly_insight_texts AS text
                          WHERE text.user_id = job.user_id
                            AND text.period_end = job.period_end
                            AND text.segment = 'report'
                      ) AS has_report
               FROM insights_daily_jobs AS job
               WHERE job.status = 'processing'
                 AND job.claimed_at < NOW() - ($1 * INTERVAL '1 second')
               FOR UPDATE SKIP LOCKED
           )
           UPDATE insights_daily_jobs AS job
           SET status = CASE
                   WHEN stale.has_report THEN 'completed'
                   WHEN job.attempts >= $2 THEN 'failed'
                   ELSE 'pending' END,
               claimed_at = NULL,
               available_at = NOW(),
               finished_at = CASE WHEN stale.has_report OR job.attempts >= $2
                                  THEN NOW() ELSE NULL END,
               last_error = CASE WHEN stale.has_report THEN NULL
                                 ELSE 'lease_expired' END
           FROM stale
           WHERE job.user_id = stale.user_id
             AND job.period_end = stale.period_end""",
        lease_seconds,
        max_attempts,
    )
    return int(result.rsplit(" ", 1)[-1])


async def get_daily_job_status(user_id: int, period_end: date) -> str | None:
    pool = await get_pool()
    return await pool.fetchval(
        """SELECT status FROM insights_daily_jobs
           WHERE user_id = $1 AND period_end = $2""",
        user_id,
        period_end,
    )
