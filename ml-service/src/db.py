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


def get_pool() -> asyncpg.Pool:
    return _pool_or_raise()


async def count_energy_gaps(user_id: int) -> int:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT COUNT(*) AS gaps
        FROM daily_summary d
        WHERE d.user_id = $1
          AND d.date < CURRENT_DATE
          AND NOT EXISTS (
            SELECT 1 FROM ml_predictions p
            WHERE p.user_id = d.user_id
              AND p.date    = d.date
              AND p.model   = 'energy_physical'
          )
        """,
        user_id,
    )
    return int(row["gaps"]) if row else 0


async def get_active_users() -> list[dict[str, Any]]:
    rows = await _pool_or_raise().fetch(
        "SELECT id, name FROM users WHERE is_active = true AND garmin_linked = true"
    )
    return [dict(r) for r in rows]


async def get_ml_requested_users() -> list[dict[str, Any]]:
    rows = await _pool_or_raise().fetch(
        "SELECT id FROM users WHERE ml_requested = true AND is_active = true"
    )
    return [dict(r) for r in rows]


async def mark_ml_done(user_id: int) -> None:
    await _pool_or_raise().execute(
        "UPDATE users SET ml_requested = false, last_ml_at = NOW() WHERE id = $1",
        user_id,
    )


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
               d.avg_stress,
               COALESCE(atrain.aerobic_effect_daily,   0) AS aerobic_effect_daily,
               COALESCE(atrain.anaerobic_effect_daily, 0) AS anaerobic_effect_daily,
               ep.value AS energy_physical_score,
               ea.value AS energy_autonomic_score,
               ec.value AS energy_cognitive_score
        FROM daily_summary d
        LEFT JOIN hrv_daily h ON h.date = d.date AND h.user_id = d.user_id
        LEFT JOIN sleep_sessions s
               ON DATE(s.start_time AT TIME ZONE 'UTC') = d.date
              AND s.user_id = d.user_id
        LEFT JOIN (
            SELECT DATE(started_at AT TIME ZONE 'UTC') AS activity_date,
                   SUM(aerobic_effect)                  AS aerobic_effect_daily,
                   SUM(anaerobic_effect)                AS anaerobic_effect_daily
            FROM activities
            WHERE user_id = $1 AND started_at >= $2
            GROUP BY 1
        ) atrain ON atrain.activity_date = d.date
        LEFT JOIN ml_predictions ep
               ON ep.date = d.date AND ep.user_id = d.user_id AND ep.model = 'energy_physical'
        LEFT JOIN ml_predictions ea
               ON ea.date = d.date AND ea.user_id = d.user_id AND ea.model = 'energy_autonomic'
        LEFT JOIN ml_predictions ec
               ON ec.date = d.date AND ec.user_id = d.user_id AND ec.model = 'energy_cognitive'
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


async def get_sleep_resting_hr_pairs(
    user_id: int, days: int = 90
) -> list[tuple[float, float]]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT s.sleep_score, d2.resting_hr
        FROM sleep_sessions s
        JOIN daily_summary d2
          ON d2.date    = DATE(s.start_time AT TIME ZONE 'UTC') + 1
         AND d2.user_id = s.user_id
        WHERE s.user_id = $1
          AND DATE(s.start_time AT TIME ZONE 'UTC') >= $2
          AND s.sleep_score IS NOT NULL
          AND d2.resting_hr IS NOT NULL
        ORDER BY s.start_time
        """,
        user_id,
        cutoff,
    )
    return [(float(r["sleep_score"]), float(r["resting_hr"])) for r in rows]


async def get_bb_resting_hr_pairs(
    user_id: int, days: int = 90
) -> list[tuple[float, float]]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT d1.body_battery_high, d2.resting_hr
        FROM daily_summary d1
        JOIN daily_summary d2
          ON d2.date    = d1.date + 1
         AND d2.user_id = d1.user_id
        WHERE d1.user_id = $1
          AND d1.date >= $2
          AND d1.body_battery_high IS NOT NULL
          AND d2.resting_hr IS NOT NULL
        ORDER BY d1.date
        """,
        user_id,
        cutoff,
    )
    return [(float(r["body_battery_high"]), float(r["resting_hr"])) for r in rows]


async def get_activity_trimp_inputs(
    user_id: int, days: int = 50
) -> list[dict[str, Any]]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT DATE(a.started_at AT TIME ZONE 'UTC') AS activity_date,
               AVG(a.avg_hr)::float                  AS avg_hr,
               SUM(a.duration_seconds)::float         AS duration_seconds,
               MAX(d.resting_hr)::float               AS resting_hr
        FROM activities a
        LEFT JOIN daily_summary d
               ON d.date    = DATE(a.started_at AT TIME ZONE 'UTC')
              AND d.user_id = a.user_id
        WHERE a.user_id = $1
          AND a.started_at >= $2
          AND a.avg_hr IS NOT NULL
          AND a.duration_seconds IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """,
        user_id,
        cutoff,
    )
    return [dict(r) for r in rows]


async def get_hrmax(user_id: int) -> float:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT MAX(max_hr)::float AS hrmax FROM activities
        WHERE user_id = $1
          AND started_at >= CURRENT_DATE - INTERVAL '12 months'
          AND max_hr IS NOT NULL
        """,
        user_id,
    )
    return float(row["hrmax"]) if row and row["hrmax"] else 190.0


async def get_hrv_history_for_energy(
    user_id: int, days: int = 97
) -> list[float | None]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT hrv_last_night FROM hrv_daily
        WHERE user_id = $1
          AND date >= $2
        ORDER BY date
        """,
        user_id,
        cutoff,
    )
    return [r["hrv_last_night"] for r in rows]


async def get_sleep_data_7d(user_id: int) -> list[dict[str, float | None]]:
    rows = await _pool_or_raise().fetch(
        """
        SELECT DISTINCT ON (sleep_date)
               DATE(start_time AT TIME ZONE 'UTC') AS sleep_date,
               total_sleep_seconds,
               deep_sleep_seconds
        FROM sleep_sessions
        WHERE user_id = $1
          AND start_time >= CURRENT_DATE - INTERVAL '8 days'
        ORDER BY sleep_date DESC, total_sleep_seconds DESC NULLS LAST
        LIMIT 7
        """,
        user_id,
    )
    return [
        {
            "total_h": float(r["total_sleep_seconds"]) / 3600.0
            if r["total_sleep_seconds"] is not None
            else None,
            "deep_h": float(r["deep_sleep_seconds"]) / 3600.0
            if r["deep_sleep_seconds"] is not None
            else None,
        }
        for r in rows
    ]


async def get_body_battery_today(user_id: int) -> list[dict[str, Any]]:
    rows = await _pool_or_raise().fetch(
        """
        SELECT time, value FROM body_battery_intraday
        WHERE user_id = $1
          AND date(time AT TIME ZONE 'UTC') = CURRENT_DATE
        ORDER BY time
        """,
        user_id,
    )
    return [dict(r) for r in rows]


async def get_body_battery_history(
    user_id: int, days: int = 90
) -> dict[str, list[dict[str, Any]]]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT time, value FROM body_battery_intraday
        WHERE user_id = $1
          AND date(time AT TIME ZONE 'UTC') >= $2
          AND date(time AT TIME ZONE 'UTC') < CURRENT_DATE
        ORDER BY time
        """,
        user_id,
        cutoff,
    )
    history: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        day = str(r["time"].date())
        history.setdefault(day, []).append({"time": r["time"], "value": r["value"]})
    return history


async def get_latest_features(user_id: int) -> dict[str, Any]:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT h.hrv_last_night, h.hrv_status, s.sleep_score,
               d.resting_hr, d.body_battery_high, d.avg_stress,
               COALESCE(atrain.aerobic_effect_daily,   0) AS aerobic_effect_daily,
               COALESCE(atrain.anaerobic_effect_daily, 0) AS anaerobic_effect_daily
        FROM daily_summary d
        LEFT JOIN hrv_daily h ON h.date = d.date AND h.user_id = d.user_id
        LEFT JOIN sleep_sessions s
               ON DATE(s.start_time AT TIME ZONE 'UTC') = d.date
              AND s.user_id = d.user_id
        LEFT JOIN (
            SELECT DATE(started_at AT TIME ZONE 'UTC') AS activity_date,
                   SUM(aerobic_effect)                  AS aerobic_effect_daily,
                   SUM(anaerobic_effect)                AS anaerobic_effect_daily
            FROM activities
            WHERE user_id = $1 AND started_at >= CURRENT_DATE - 3
            GROUP BY 1
        ) atrain ON atrain.activity_date = d.date
        WHERE d.user_id = $1 AND d.date >= CURRENT_DATE - 2
        ORDER BY d.date DESC
        LIMIT 1
        """,
        user_id,
    )
    return dict(row) if row else {}


async def get_last_sleep_session(user_id: int) -> dict[str, Any] | None:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT total_sleep_seconds, deep_sleep_seconds, light_sleep_seconds,
               rem_sleep_seconds, awake_seconds
        FROM sleep_sessions
        WHERE user_id = $1
          AND DATE(start_time AT TIME ZONE 'UTC') >= CURRENT_DATE - 2
        ORDER BY start_time DESC
        LIMIT 1
        """,
        user_id,
    )
    return dict(row) if row else None


async def get_today_hrv(user_id: int) -> float | None:
    row = await _pool_or_raise().fetchrow(
        "SELECT hrv_last_night FROM hrv_daily WHERE user_id = $1 AND date = CURRENT_DATE",
        user_id,
    )
    return float(row["hrv_last_night"]) if row and row["hrv_last_night"] else None


async def get_todays_activity_hr_records(
    user_id: int,
) -> tuple[list[int], float | None]:
    rows = await _pool_or_raise().fetch(
        """
        SELECT ar.heart_rate
        FROM activity_records ar
        JOIN activities a ON a.id = ar.activity_id
        WHERE a.user_id = $1
          AND DATE(a.started_at AT TIME ZONE 'UTC') = CURRENT_DATE
          AND ar.heart_rate IS NOT NULL
          AND ar.heart_rate > 0
        ORDER BY ar.time
        """,
        user_id,
    )
    hr_records = [int(r["heart_rate"]) for r in rows]
    rhr_row = await _pool_or_raise().fetchrow(
        "SELECT resting_hr FROM daily_summary WHERE user_id = $1 AND date = CURRENT_DATE",
        user_id,
    )
    resting_hr = (
        float(rhr_row["resting_hr"]) if rhr_row and rhr_row["resting_hr"] else None
    )
    return hr_records, resting_hr


async def get_user_profile(user_id: int) -> dict[str, Any]:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT date_of_birth, sex,
               DATE_PART('year', AGE(date_of_birth))::int AS age
        FROM users WHERE id = $1
        """,
        user_id,
    )
    if not row or not row["sex"] or not row["date_of_birth"]:
        return {"has_profile": False, "age": None, "sex": None}
    return {
        "has_profile": True,
        "age": int(row["age"]),
        "sex": row["sex"],
        "date_of_birth": str(row["date_of_birth"]),
    }


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
