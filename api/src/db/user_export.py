"""DSGVO Art. 20 data export — split out of users.py (ARCH-L5 400-line trigger).

Re-exported via src.db so `from src.db import export_user_data` keeps working.
"""

from datetime import datetime, timezone

import asyncpg

from .pool import get_pool

_EXPORT_ACTIVITIES_SQL = """
    SELECT id, user_id, garmin_activity_id, started_at, duration_seconds,
           sport_type, distance_meters, calories, avg_hr, max_hr,
           avg_pace_sec_per_km, avg_cadence, avg_power, elevation_gain,
           avg_speed_kmh, aerobic_effect, anaerobic_effect, user_rpe, created_at
    FROM activities WHERE user_id = $1 ORDER BY started_at LIMIT 50000
"""
_EXPORT_SLEEP_SQL = """
    SELECT id, user_id, garmin_sleep_id, start_time, end_time,
           total_sleep_seconds, deep_sleep_seconds, light_sleep_seconds,
           rem_sleep_seconds, awake_seconds, sleep_score
    FROM sleep_sessions WHERE user_id = $1 ORDER BY start_time LIMIT 50000
"""
_EXPORT_HRV_SQL = """
    SELECT date, user_id, hrv_last_night, hrv_weekly_avg, hrv_status
    FROM hrv_daily WHERE user_id = $1 ORDER BY date LIMIT 50000
"""
_EXPORT_DAILY_SQL = """
    SELECT date, user_id, steps, calories_total, avg_stress, max_stress,
           avg_spo2, min_spo2, body_battery_high, body_battery_low, resting_hr
    FROM daily_summary WHERE user_id = $1 ORDER BY date LIMIT 50000
"""
_EXPORT_SEIZURES_SQL = """
    SELECT id, user_id, occurred_at, duration_seconds, type, severity, notes, created_at
    FROM seizure_events WHERE user_id = $1 ORDER BY occurred_at LIMIT 50000
"""
_EXPORT_GLUCOSE_SQL = """
    SELECT time, user_id, value_mgdl, trend, is_high, is_low
    FROM glucose_readings WHERE user_id = $1 ORDER BY time LIMIT 50000
"""


async def _load_user_records(
    conn: asyncpg.Connection | asyncpg.pool.PoolConnectionProxy,  # type: ignore[type-arg]
    query: str,
    user_id: int,
) -> list[dict]:
    return [dict(r) for r in await conn.fetch(query, user_id)]


async def export_user_data(user_id: int) -> dict:
    """Export all personal data for a user (DSGVO Art. 20 data portability).

    Returns user profile + 6 data tables: activities, sleep_sessions, hrv_daily,
    daily_summary, seizure_events, glucose_readings.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, name, email, created_at, email_verified_at,
                      date_of_birth, sex, epilepsy_mode, spo2_enabled,
                      garmin_linked, garmin_email, libre_linked, libre_email
               FROM users WHERE id = $1""",
            user_id,
        )
        if row is None:
            raise RuntimeError(f"export_user_data: user {user_id} not found")
        user = dict(row)
        activities = await _load_user_records(conn, _EXPORT_ACTIVITIES_SQL, user_id)
        sleep = await _load_user_records(conn, _EXPORT_SLEEP_SQL, user_id)
        hrv = await _load_user_records(conn, _EXPORT_HRV_SQL, user_id)
        daily = await _load_user_records(conn, _EXPORT_DAILY_SQL, user_id)
        seizures = await _load_user_records(conn, _EXPORT_SEIZURES_SQL, user_id)
        glucose = await _load_user_records(conn, _EXPORT_GLUCOSE_SQL, user_id)
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "user": user,
        "activities": activities,
        "sleep_sessions": sleep,
        "hrv_daily": hrv,
        "daily_summary": daily,
        "seizure_events": seizures,
        "glucose_readings": glucose,
    }
