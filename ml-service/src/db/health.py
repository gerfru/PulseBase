# 361 lines — approaching 400-line threshold.
# Split trigger: sleep/HRV queries → db/sleep.py when file exceeds 400 lines.
from datetime import date, timedelta
from typing import Any

from .pool import _pool_or_raise


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


async def get_spo2_history_flat(user_id: int, days: int = 31) -> list[float | None]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT avg_spo2 FROM daily_summary
        WHERE user_id = $1
          AND date >= $2
          AND date < CURRENT_DATE
        ORDER BY date
        """,
        user_id,
        cutoff,
    )
    return [r["avg_spo2"] for r in rows]


async def get_today_spo2(user_id: int) -> float | None:
    row = await _pool_or_raise().fetchrow(
        "SELECT avg_spo2 FROM daily_summary WHERE user_id = $1 AND date = CURRENT_DATE",
        user_id,
    )
    return row["avg_spo2"] if row else None


async def get_sleep_duration_history(
    user_id: int, days: int = 31
) -> list[float | None]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT DISTINCT ON (sleep_date)
               DATE(start_time AT TIME ZONE 'UTC') AS sleep_date,
               total_sleep_seconds
        FROM sleep_sessions
        WHERE user_id = $1
          AND DATE(start_time AT TIME ZONE 'UTC') >= $2
          AND DATE(start_time AT TIME ZONE 'UTC') < CURRENT_DATE
        ORDER BY sleep_date, total_sleep_seconds DESC NULLS LAST
        """,
        user_id,
        cutoff,
    )
    return [r["total_sleep_seconds"] for r in rows]


async def get_today_sleep_duration(user_id: int) -> float | None:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT total_sleep_seconds FROM sleep_sessions
        WHERE user_id = $1
          AND DATE(start_time AT TIME ZONE 'UTC') = CURRENT_DATE
        ORDER BY start_time DESC
        LIMIT 1
        """,
        user_id,
    )
    return row["total_sleep_seconds"] if row else None


async def get_steps_history(user_id: int, days: int = 31) -> list[float | None]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT steps FROM daily_summary
        WHERE user_id = $1
          AND date >= $2
          AND date < CURRENT_DATE
        ORDER BY date
        """,
        user_id,
        cutoff,
    )
    return [r["steps"] for r in rows]


async def get_today_steps(user_id: int) -> float | None:
    row = await _pool_or_raise().fetchrow(
        "SELECT steps FROM daily_summary WHERE user_id = $1 AND date = CURRENT_DATE",
        user_id,
    )
    return row["steps"] if row else None


async def get_stress_history(user_id: int, days: int = 31) -> list[float | None]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT avg_stress FROM daily_summary
        WHERE user_id = $1
          AND date >= $2
          AND date < CURRENT_DATE
        ORDER BY date
        """,
        user_id,
        cutoff,
    )
    return [r["avg_stress"] for r in rows]


async def get_today_stress(user_id: int) -> float | None:
    row = await _pool_or_raise().fetchrow(
        "SELECT avg_stress FROM daily_summary WHERE user_id = $1 AND date = CURRENT_DATE",
        user_id,
    )
    return row["avg_stress"] if row else None


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
               deep_sleep_seconds,
               rem_sleep_seconds
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
            "rem_h": float(r["rem_sleep_seconds"]) / 3600.0
            if r["rem_sleep_seconds"] is not None
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


async def get_spo2_history(user_id: int, days: int = 7) -> list[dict[str, Any]]:
    cutoff = date.today() - timedelta(days=days)
    rows = await _pool_or_raise().fetch(
        """
        SELECT date, avg_spo2, min_spo2
        FROM daily_summary
        WHERE user_id = $1
          AND date >= $2
          AND date < CURRENT_DATE
        ORDER BY date
        """,
        user_id,
        cutoff,
    )
    return [dict(r) for r in rows]


async def get_sleep_sessions_14d(user_id: int) -> list[dict[str, Any]]:
    rows = await _pool_or_raise().fetch(
        """
        SELECT DISTINCT ON (sleep_date)
               DATE(start_time AT TIME ZONE 'UTC') AS sleep_date,
               EXTRACT(HOUR FROM start_time AT TIME ZONE 'UTC')
                 + EXTRACT(MINUTE FROM start_time AT TIME ZONE 'UTC') / 60.0 AS start_h,
               EXTRACT(HOUR FROM (start_time + (total_sleep_seconds || ' seconds')::interval) AT TIME ZONE 'UTC')
                 + EXTRACT(MINUTE FROM (start_time + (total_sleep_seconds || ' seconds')::interval) AT TIME ZONE 'UTC') / 60.0 AS end_h
        FROM sleep_sessions
        WHERE user_id = $1
          AND start_time >= CURRENT_DATE - INTERVAL '15 days'
          AND total_sleep_seconds IS NOT NULL
        ORDER BY sleep_date DESC, total_sleep_seconds DESC NULLS LAST
        LIMIT 14
        """,
        user_id,
    )
    return [dict(r) for r in rows]


async def get_backfill_sleep_daily_gaps(user_id: int) -> dict[str, Any]:
    """Load sleep_by_date, daily_by_date, and gap_dates requiring backfill."""
    pool = _pool_or_raise()

    sleep_rows = await pool.fetch(
        """SELECT DATE(start_time AT TIME ZONE 'UTC') AS sleep_date,
                  total_sleep_seconds, deep_sleep_seconds, rem_sleep_seconds
           FROM sleep_sessions WHERE user_id = $1 ORDER BY start_time""",
        user_id,
    )
    sleep_by_date = {
        r["sleep_date"]: {
            "total_h": float(r["total_sleep_seconds"]) / 3600.0
            if r["total_sleep_seconds"]
            else None,
            "deep_h": float(r["deep_sleep_seconds"]) / 3600.0
            if r["deep_sleep_seconds"]
            else None,
            "rem_h": float(r["rem_sleep_seconds"]) / 3600.0
            if r["rem_sleep_seconds"]
            else None,
        }
        for r in sleep_rows
    }

    daily_rows = await pool.fetch(
        "SELECT date, avg_stress, body_battery_high FROM daily_summary WHERE user_id = $1 ORDER BY date",
        user_id,
    )
    daily_by_date: dict[date, dict[str, Any]] = {
        r["date"]: {
            "avg_stress": r["avg_stress"],
            "body_battery_high": r["body_battery_high"],
        }
        for r in daily_rows
    }

    gap_dates = [
        r["date"]
        for r in await pool.fetch(
            """SELECT d.date FROM daily_summary d
               WHERE d.user_id = $1 AND d.date < CURRENT_DATE
                 AND (
                   NOT EXISTS (
                     SELECT 1 FROM ml_predictions p
                     WHERE p.user_id = d.user_id AND p.date = d.date AND p.model = 'energy_physical'
                   )
                   OR NOT EXISTS (
                     SELECT 1 FROM ml_predictions p
                     WHERE p.user_id = d.user_id AND p.date = d.date AND p.model = 'body_battery_custom'
                   )
                   OR NOT EXISTS (
                     SELECT 1 FROM ml_predictions p
                     WHERE p.user_id = d.user_id AND p.date = d.date AND p.model = 'stress_score_custom'
                   )
                 )
               ORDER BY d.date""",
            user_id,
        )
    ]

    return {
        "sleep_by_date": sleep_by_date,
        "daily_by_date": daily_by_date,
        "gap_dates": gap_dates,
    }


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


async def get_today_daily_summary(user_id: int) -> dict[str, Any] | None:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT avg_stress, body_battery_high, body_battery_low
        FROM daily_summary
        WHERE user_id = $1 AND date = CURRENT_DATE
        """,
        user_id,
    )
    return dict(row) if row else None
