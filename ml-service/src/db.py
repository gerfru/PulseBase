import json
import logging
from datetime import date, timedelta
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool(db_url: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    logger.info("ML-Service DB pool initialized")


async def close_pool() -> None:
    if _pool:
        await _pool.close()


def _pool_or_raise() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Pool not initialized")
    return _pool


async def get_active_users() -> list[dict[str, Any]]:
    rows = await _pool_or_raise().fetch(
        "SELECT id, name FROM users WHERE is_active = true AND garmin_linked = true"
    )
    return [dict(r) for r in rows]


async def get_resting_hr_history(user_id: int, days: int = 31) -> list[float | None]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT resting_hr FROM daily_summary
        WHERE user_id = $1
          AND date >= $2
          AND date < CURRENT_DATE
        ORDER BY date
        """,
        user_id,
        cutoff,
    )
    return [r["resting_hr"] for r in rows]


async def get_today_resting_hr(user_id: int) -> float | None:
    row = await _pool_or_raise().fetchrow(
        "SELECT resting_hr FROM daily_summary WHERE user_id = $1 AND date = CURRENT_DATE",
        user_id,
    )
    return row["resting_hr"] if row else None


async def get_readiness_training_rows(
    user_id: int, days: int = 365
) -> list[dict[str, Any]]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT d.date,
               h.hrv_last_night,
               h.hrv_status,
               s.sleep_score,
               d.resting_hr,
               d.body_battery_high,
               d.avg_stress
        FROM daily_summary d
        LEFT JOIN hrv_daily h ON h.date = d.date AND h.user_id = d.user_id
        LEFT JOIN sleep_sessions s
               ON DATE(s.start_time AT TIME ZONE 'UTC') = d.date
              AND s.user_id = d.user_id
        WHERE d.user_id = $1
          AND d.date >= $2
        ORDER BY d.date
        """,
        user_id,
        cutoff,
    )
    return [dict(r) for r in rows]


async def get_sleep_hrv_pairs(
    user_id: int, days: int = 90
) -> list[tuple[float, float]]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT s.sleep_score, h_next.hrv_last_night
        FROM sleep_sessions s
        JOIN hrv_daily h_next
          ON h_next.date = DATE(s.start_time AT TIME ZONE 'UTC') + 1
         AND h_next.user_id = s.user_id
        WHERE s.user_id = $1
          AND DATE(s.start_time AT TIME ZONE 'UTC') >= $2
          AND s.sleep_score IS NOT NULL
          AND h_next.hrv_last_night IS NOT NULL
        ORDER BY s.start_time
        """,
        user_id,
        cutoff,
    )
    return [(float(r["sleep_score"]), float(r["hrv_last_night"])) for r in rows]


async def get_latest_features(user_id: int) -> dict[str, Any]:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT h.hrv_last_night, h.hrv_status, s.sleep_score,
               d.resting_hr, d.body_battery_high, d.avg_stress
        FROM daily_summary d
        LEFT JOIN hrv_daily h ON h.date = d.date AND h.user_id = d.user_id
        LEFT JOIN sleep_sessions s
               ON DATE(s.start_time AT TIME ZONE 'UTC') = d.date
              AND s.user_id = d.user_id
        WHERE d.user_id = $1 AND d.date >= CURRENT_DATE - 2
        ORDER BY d.date DESC
        LIMIT 1
        """,
        user_id,
    )
    return dict(row) if row else {}


async def save_prediction(
    user_id: int,
    pred_date: date,
    model: str,
    value: float | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await _pool_or_raise().execute(
        """
        INSERT INTO ml_predictions (date, user_id, model, value, metadata)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (date, user_id, model) DO UPDATE SET
            value      = EXCLUDED.value,
            metadata   = EXCLUDED.metadata,
            created_at = NOW()
        """,
        pred_date,
        user_id,
        model,
        value,
        json.dumps(metadata) if metadata is not None else None,
    )
