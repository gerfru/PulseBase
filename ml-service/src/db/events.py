import random
from typing import Any

from .pool import _pool_or_raise


def retry_delay_seconds(
    attempt: int, base_seconds: int = 30, cap_seconds: int = 900
) -> int:
    exponential = min(base_seconds * (2 ** max(attempt - 1, 0)), cap_seconds)
    return max(1, round(exponential * random.uniform(0.5, 1.5)))


async def claim_ml_events(limit: int = 10) -> list[dict[str, Any]]:
    pool = _pool_or_raise()
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                """
                WITH candidates AS (
                    SELECT id
                    FROM service_events
                    WHERE event_type = 'ml_requested'
                      AND status = 'pending'
                      AND available_at <= NOW()
                    ORDER BY id
                    FOR UPDATE SKIP LOCKED
                    LIMIT $1
                )
                UPDATE service_events AS event
                SET status = 'processing',
                    claimed_at = NOW(),
                    claimed_generation = event.generation,
                    attempts = event.attempts + 1,
                    last_error = NULL
                FROM candidates
                WHERE event.id = candidates.id
                RETURNING event.id, event.user_id, event.attempts,
                          event.claimed_generation
                """,
                limit,
            )
    return [dict(row) for row in rows]


async def reconcile_ml_events() -> int:
    result = await _pool_or_raise().execute(
        """
                INSERT INTO service_events (event_type, user_id)
                SELECT 'ml_requested', u.id
                FROM users AS u
                WHERE u.ml_requested = true
                    AND u.is_active = true
                    AND NOT EXISTS (
                            SELECT 1
                            FROM service_events AS event
                            WHERE event.event_type = 'ml_requested'
                                AND event.user_id = u.id
                                AND event.status IN ('pending', 'processing')
                    )
                ON CONFLICT (event_type, user_id)
                WHERE status IN ('pending', 'processing') DO NOTHING
                """
    )
    return int(result.rsplit(" ", 1)[-1])


async def complete_event(event_id: int) -> str | None:
    row = await _pool_or_raise().fetchrow(
        """
        UPDATE service_events
        SET status = CASE
                WHEN generation > claimed_generation THEN 'pending'
                ELSE 'completed'
            END,
            available_at = CASE
                WHEN generation > claimed_generation THEN NOW()
                ELSE available_at
            END,
            attempts = CASE
                WHEN generation > claimed_generation THEN 0
                ELSE attempts
            END,
            claimed_at = NULL,
            claimed_generation = NULL,
            processed_at = CASE
                WHEN generation > claimed_generation THEN NULL
                ELSE NOW()
            END,
            last_error = NULL
        WHERE id = $1 AND event_type = 'ml_requested' AND status = 'processing'
        RETURNING status
        """,
        event_id,
    )
    return str(row["status"]) if row else None


async def fail_event(
    event_id: int,
    error: str,
    attempts: int,
    max_attempts: int = 5,
) -> str | None:
    delay = retry_delay_seconds(attempts)
    row = await _pool_or_raise().fetchrow(
        """
        UPDATE service_events
        SET status = CASE
                WHEN generation > claimed_generation THEN 'pending'
                WHEN $3 >= $4 THEN 'failed'
                ELSE 'pending'
            END,
            available_at = CASE
                WHEN generation > claimed_generation THEN NOW()
                WHEN $3 >= $4 THEN available_at
                ELSE NOW() + ($5 * INTERVAL '1 second')
            END,
            attempts = CASE
                WHEN generation > claimed_generation THEN 0
                ELSE attempts
            END,
            claimed_at = NULL,
            claimed_generation = NULL,
            processed_at = CASE
                WHEN generation <= claimed_generation AND $3 >= $4 THEN NOW()
                ELSE NULL
            END,
            last_error = CASE
                WHEN generation > claimed_generation THEN NULL
                ELSE $2
            END
        WHERE id = $1 AND event_type = 'ml_requested' AND status = 'processing'
        RETURNING status
        """,
        event_id,
        error[:2000],
        attempts,
        max_attempts,
        delay,
    )
    return str(row["status"]) if row else None


async def requeue_stale_ml_events(lease_seconds: int = 900) -> int:
    result = await _pool_or_raise().execute(
        """
        UPDATE service_events
        SET status = 'pending',
            attempts = CASE
                WHEN generation > claimed_generation THEN 0
                ELSE attempts
            END,
            claimed_at = NULL,
            claimed_generation = NULL,
            available_at = NOW(),
            last_error = 'processing lease expired'
        WHERE event_type = 'ml_requested'
          AND status = 'processing'
          AND claimed_at < NOW() - ($1 * INTERVAL '1 second')
        """,
        lease_seconds,
    )
    return int(result.rsplit(" ", 1)[-1])


async def delete_completed_ml_events(retention_days: int = 30) -> int:
    result = await _pool_or_raise().execute(
        """
        DELETE FROM service_events
        WHERE event_type = 'ml_requested'
          AND status = 'completed'
          AND processed_at < NOW() - ($1 * INTERVAL '1 day')
        """,
        retention_days,
    )
    return int(result.rsplit(" ", 1)[-1])


async def get_ml_queue_metrics() -> dict[str, int | float]:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT COUNT(*) FILTER (WHERE status = 'pending') AS pending,
               COUNT(*) FILTER (WHERE status = 'processing') AS processing,
               COUNT(*) FILTER (WHERE status = 'failed') AS failed,
               COALESCE(
                   EXTRACT(EPOCH FROM (NOW() - MIN(created_at)
                       FILTER (WHERE status = 'pending'))),
                   0
               ) AS oldest_pending_seconds
        FROM service_events
        WHERE event_type = 'ml_requested'
        """
    )
    if row is None:
        return {
            "pending": 0,
            "processing": 0,
            "failed": 0,
            "oldest_pending_seconds": 0.0,
        }
    return {
        "pending": int(row["pending"]),
        "processing": int(row["processing"]),
        "failed": int(row["failed"]),
        "oldest_pending_seconds": float(row["oldest_pending_seconds"]),
    }


async def replay_failed_ml_event(event_id: int) -> bool:
    result = await _pool_or_raise().execute(
        """
        UPDATE service_events
        SET status = 'pending', attempts = 0, available_at = NOW(),
            claimed_at = NULL, claimed_generation = NULL,
            processed_at = NULL, last_error = NULL
        WHERE id = $1
          AND event_type = 'ml_requested'
          AND status = 'failed'
        """,
        event_id,
    )
    return result == "UPDATE 1"
