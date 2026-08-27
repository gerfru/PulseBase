from typing import Any

from .pool import _pool_or_raise


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
                    attempts = event.attempts + 1,
                    last_error = NULL
                FROM candidates
                WHERE event.id = candidates.id
                RETURNING event.id, event.user_id, event.attempts
                """,
                limit,
            )
    return [dict(row) for row in rows]


async def complete_event(event_id: int) -> None:
    await _pool_or_raise().execute(
        """
        UPDATE service_events
        SET status = 'completed', processed_at = NOW(), claimed_at = NULL
        WHERE id = $1 AND event_type = 'ml_requested' AND status = 'processing'
        """,
        event_id,
    )


async def fail_event(
    event_id: int,
    error: str,
    max_attempts: int = 5,
    retry_delay_seconds: int = 60,
) -> None:
    await _pool_or_raise().execute(
        """
        UPDATE service_events
        SET status = CASE WHEN attempts >= $2 THEN 'failed' ELSE 'pending' END,
            available_at = CASE
                WHEN attempts >= $2 THEN available_at
                ELSE NOW() + ($3 * INTERVAL '1 second')
            END,
            claimed_at = NULL,
            processed_at = CASE WHEN attempts >= $2 THEN NOW() ELSE processed_at END,
            last_error = $4
        WHERE id = $1 AND event_type = 'ml_requested' AND status = 'processing'
        """,
        event_id,
        max_attempts,
        retry_delay_seconds,
        error[:2000],
    )


async def requeue_stale_ml_events(lease_seconds: int = 900) -> int:
    result = await _pool_or_raise().execute(
        """
        UPDATE service_events
        SET status = 'pending', claimed_at = NULL,
            available_at = NOW(),
            last_error = 'processing lease expired'
        WHERE event_type = 'ml_requested'
          AND status = 'processing'
          AND claimed_at < NOW() - ($1 * INTERVAL '1 second')
        """,
        lease_seconds,
    )
    return int(result.rsplit(" ", 1)[-1])
