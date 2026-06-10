import json
from datetime import date
from typing import Any

from .pool import get_pool


async def get_daily_summaries(
    user_id: int, days: int = 30, end_date: date | None = None
) -> list[dict]:
    pool = await get_pool()
    end = end_date if end_date is not None else date.today()
    rows = await pool.fetch(
        """
        SELECT ds.date, ds.steps, ds.resting_hr, ds.avg_stress, ds.calories_total,
               ds.intensity_moderate, ds.intensity_vigorous,
               COALESCE(ds.body_battery_high, bb.max_val) AS body_battery_high,
               COALESCE(ds.body_battery_low,  bb.min_val) AS body_battery_low
        FROM daily_summary ds
        LEFT JOIN (
            SELECT date(time) AS date, MAX(value) AS max_val, MIN(value) AS min_val
            FROM body_battery_intraday
            WHERE user_id = $1
            GROUP BY date(time)
        ) bb ON bb.date = ds.date
        WHERE ds.user_id = $1
          AND ds.date >= $3::date - ($2 * INTERVAL '1 day')
          AND ds.date <= $3::date
        ORDER BY ds.date
        """,
        user_id,
        days,
        end,
    )
    return [dict(r) for r in rows]


async def get_sleep_sessions(
    user_id: int, days: int = 14, end_date: date | None = None
) -> list[dict]:
    pool = await get_pool()
    end = end_date if end_date is not None else date.today()
    rows = await pool.fetch(
        """
        SELECT date(start_time) AS date, start_time, end_time, sleep_score, total_sleep_seconds,
               deep_sleep_seconds, light_sleep_seconds, rem_sleep_seconds, awake_seconds
        FROM sleep_sessions
        WHERE user_id = $1
          AND DATE(start_time) >= $3::date - ($2 * INTERVAL '1 day')
          AND DATE(start_time) <= $3::date
        ORDER BY start_time DESC
        """,
        user_id,
        days,
        end,
    )
    return [dict(r) for r in rows]


async def get_latest_hrv(user_id: int) -> dict[str, Any] | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT hrv_last_night, hrv_weekly_avg, hrv_status
        FROM hrv_daily
        WHERE user_id = $1
        ORDER BY date DESC
        LIMIT 1
        """,
        user_id,
    )
    return dict(row) if row else None


async def get_hrv_trend(
    user_id: int, days: int = 30, end_date: date | None = None
) -> list[dict]:
    pool = await get_pool()
    end = end_date if end_date is not None else date.today()
    rows = await pool.fetch(
        """
        SELECT date, hrv_last_night, hrv_weekly_avg, hrv_status
        FROM hrv_daily
        WHERE user_id = $1
          AND date >= $3::date - ($2 * INTERVAL '1 day')
          AND date <= $3::date
        ORDER BY date
        """,
        user_id,
        days,
        end,
    )
    return [dict(r) for r in rows]


async def get_latest_training_status(user_id: int) -> dict[str, Any] | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT date, training_status
        FROM daily_summary
        WHERE user_id = $1 AND training_status IS NOT NULL
        ORDER BY date DESC
        LIMIT 1
        """,
        user_id,
    )
    return dict(row) if row else None


async def get_weekly_stats(
    user_id: int, weeks: int = 12, end_date: date | None = None
) -> list[dict]:
    pool = await get_pool()
    end = end_date if end_date is not None else date.today()
    rows = await pool.fetch(
        """
        SELECT
            date_trunc('week', started_at AT TIME ZONE 'UTC')::date AS week,
            COUNT(*)::int                                            AS activity_count,
            ROUND((SUM(distance_meters) / 1000.0)::numeric, 1)                 AS total_km,
            ROUND((SUM(duration_seconds) / 3600.0)::numeric, 1)                AS total_hours,
            ROUND((SUM(CASE WHEN sport_type IN
                               ('running','trail_running','hiking','walking')
                           THEN distance_meters ELSE 0 END) / 1000.0)::numeric, 1) AS run_km,
            ROUND((SUM(CASE WHEN sport_type IN ('cycling','indoor_cycling')
                           THEN distance_meters ELSE 0 END) / 1000.0)::numeric, 1) AS ride_km,
            ROUND((SUM(CASE WHEN sport_type NOT IN
                               ('running','trail_running','hiking','walking',
                                'cycling','indoor_cycling')
                           THEN duration_seconds ELSE 0 END) / 3600.0)::numeric, 1) AS other_hours
        FROM activities
        WHERE user_id = $1
          AND started_at >= ($3::date - ($2 * INTERVAL '1 week'))::timestamp
          AND started_at < ($3::date + INTERVAL '1 day')::timestamp
        GROUP BY 1
        ORDER BY 1 ASC
        """,
        user_id,
        weeks,
        end,
    )
    return [dict(r) for r in rows]


async def get_energy_metrics(user_id: int) -> dict[str, Any]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT DISTINCT ON (model) model, value, metadata
        FROM ml_predictions
        WHERE user_id = $1
          AND model IN ('energy_physical', 'energy_autonomic', 'energy_cognitive')
          AND date >= CURRENT_DATE - 1
        ORDER BY model, date DESC
        """,
        user_id,
    )
    result: dict = {}
    for row in rows:
        meta = json.loads(row["metadata"]) if row["metadata"] else {}
        result[row["model"]] = {"score": row["value"], **meta}
    return result
