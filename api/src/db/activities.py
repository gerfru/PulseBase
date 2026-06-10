from datetime import date, timedelta
from typing import Any

from .pool import get_pool


async def get_recent_activities(
    user_id: int, limit: int = 500, days: int = 7, end_date: date | None = None
) -> list[dict]:
    pool = await get_pool()
    end = end_date if end_date is not None else date.today()
    rows = await pool.fetch(
        """
        SELECT id, sport_type, started_at, duration_seconds, distance_meters,
               avg_hr, calories
        FROM activities
        WHERE user_id = $1
          AND started_at >= ($3::date - ($2 * INTERVAL '1 day'))::timestamp
          AND started_at < ($3::date + INTERVAL '1 day')::timestamp
        ORDER BY started_at DESC
        LIMIT $4
        """,
        user_id,
        days,
        end,
        limit,
    )
    return [dict(r) for r in rows]


async def get_activity_detail(user_id: int, activity_id: int) -> dict[str, Any] | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT a.id, a.sport_type, a.started_at, a.duration_seconds,
               a.distance_meters, a.calories, a.avg_hr, a.max_hr,
               a.avg_pace_sec_per_km, a.avg_speed_kmh, a.avg_cadence,
               a.avg_power, a.elevation_gain, a.aerobic_effect, a.anaerobic_effect,
               a.user_rpe,
               a.avg_ground_contact_time, a.avg_vertical_oscillation,
               a.avg_stride_length, a.avg_vertical_ratio, a.avg_running_power,
               ds.training_status
        FROM activities a
        LEFT JOIN daily_summary ds
               ON ds.user_id = a.user_id
              AND ds.date = date(a.started_at AT TIME ZONE 'UTC')
        WHERE a.id = $1 AND a.user_id = $2
        """,
        activity_id,
        user_id,
    )
    if not row:
        return None
    detail = dict(row)
    records = await pool.fetch(
        """
        SELECT time, heart_rate, pace_sec_per_km, cadence, power,
               elevation, distance, lat, lng
        FROM activity_records
        WHERE activity_id = $1
          AND EXISTS (SELECT 1 FROM activities a WHERE a.id = $1 AND a.user_id = $2)
        ORDER BY time ASC
        """,
        activity_id,
        user_id,
    )
    detail["records"] = [dict(r) for r in records]
    return detail


async def set_activity_rpe(user_id: int, activity_id: int, rpe: int) -> bool:
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE activities SET user_rpe = $1 WHERE id = $2 AND user_id = $3",
        rpe,
        activity_id,
        user_id,
    )
    return result == "UPDATE 1"


async def get_training_load_inputs(user_id: int, days: int = 200) -> list[dict]:
    """Per-activity rows for TRIMP calculation (one row per activity)."""
    cutoff = date.today() - timedelta(days=days)
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT DATE(a.started_at AT TIME ZONE 'UTC') AS activity_date,
               a.avg_hr::float,
               a.duration_seconds::float,
               d.resting_hr::float
        FROM activities a
        LEFT JOIN daily_summary d
               ON d.date    = DATE(a.started_at AT TIME ZONE 'UTC')
              AND d.user_id = a.user_id
        WHERE a.user_id = $1
          AND a.started_at >= $2
          AND a.avg_hr IS NOT NULL
          AND a.avg_hr > 0
          AND a.duration_seconds IS NOT NULL
          AND a.duration_seconds > 0
        ORDER BY activity_date
        """,
        user_id,
        cutoff,
    )
    return [dict(r) for r in rows]


async def get_activity_hrmax(user_id: int) -> float:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT MAX(max_hr)::float AS hrmax FROM activities
        WHERE user_id = $1
          AND started_at >= CURRENT_DATE - INTERVAL '12 months'
          AND max_hr IS NOT NULL
        """,
        user_id,
    )
    return float(row["hrmax"]) if row and row["hrmax"] else 190.0
