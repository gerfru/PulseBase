import logging
from datetime import date
from typing import Any

import asyncpg

from domain.models import Activity, DailySummary, HRVDaily, SleepSession
from repositories.base import (
    ActivityRecordRepository,
    ActivityRepository,
    DailySummaryRepository,
    HRVRepository,
    IntradayRepository,
    SleepRepository,
)

logger = logging.getLogger(__name__)


class TimescaleRepository(
    ActivityRepository,
    ActivityRecordRepository,
    DailySummaryRepository,
    SleepRepository,
    HRVRepository,
    IntradayRepository,
):
    def __init__(self, db_url: str) -> None:
        self._db_url = db_url
        self._pool: asyncpg.Pool | None = None

    async def init(self) -> None:
        self._pool = await asyncpg.create_pool(self._db_url, min_size=2, max_size=5)
        logger.info("Database connection pool initialized")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    # ── Activities ────────────────────────────────────────────────────────────

    async def save_activity(self, activity: Activity) -> int | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO activities (
                    user_id, garmin_activity_id, started_at, duration_seconds,
                    sport_type, distance_meters, calories, avg_hr, max_hr,
                    avg_pace_sec_per_km, avg_cadence, avg_power, elevation_gain,
                    avg_speed_kmh, aerobic_effect, anaerobic_effect
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                ON CONFLICT (garmin_activity_id) DO UPDATE SET
                    aerobic_effect   = EXCLUDED.aerobic_effect,
                    anaerobic_effect = EXCLUDED.anaerobic_effect
                RETURNING id
                """,
                activity.user_id,
                activity.garmin_activity_id,
                activity.started_at,
                activity.duration_seconds,
                activity.sport_type.value,
                activity.distance_meters,
                activity.calories,
                activity.avg_hr,
                activity.max_hr,
                activity.avg_pace_sec_per_km,
                activity.avg_cadence,
                activity.avg_power,
                activity.elevation_gain,
                activity.avg_speed_kmh,
                activity.aerobic_effect,
                activity.anaerobic_effect,
            )
            return row["id"] if row else None

    async def records_exist(self, activity_id: int) -> bool:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM activity_records WHERE activity_id = $1 LIMIT 1",
                activity_id,
            )
            return row is not None

    # ── Activity Records (GPS Tracks) ─────────────────────────────────────────

    async def bulk_insert_records(self, activity_id: int, records: list) -> None:
        if not records:
            return
        rows = [
            (
                r.time,
                activity_id,
                r.heart_rate,
                r.pace_sec_per_km,
                r.cadence,
                r.power,
                r.elevation,
                r.distance,
                r.lat,
                r.lng,
            )
            for r in records
        ]
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO activity_records
                    (time, activity_id, user_id, heart_rate, pace_sec_per_km,
                     cadence, power, elevation, distance, lat, lng)
                SELECT $1,$2,
                       (SELECT user_id FROM activities WHERE id = $2),
                       $3,$4,$5,$6,$7,$8,$9,$10
                """,
                rows,
            )
        logger.info(f"Inserted {len(rows)} GPS records for activity {activity_id}")

    # ── Daily Summary ─────────────────────────────────────────────────────────

    async def upsert_daily(self, summary: DailySummary) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO daily_summary (
                    date, user_id, steps, calories_total, avg_stress, max_stress,
                    avg_spo2, min_spo2, body_battery_high, body_battery_low, resting_hr,
                    intensity_moderate, intensity_vigorous
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                ON CONFLICT (date, user_id) DO UPDATE SET
                    steps              = EXCLUDED.steps,
                    calories_total     = EXCLUDED.calories_total,
                    avg_stress         = EXCLUDED.avg_stress,
                    max_stress         = EXCLUDED.max_stress,
                    avg_spo2           = EXCLUDED.avg_spo2,
                    min_spo2           = EXCLUDED.min_spo2,
                    body_battery_high  = EXCLUDED.body_battery_high,
                    body_battery_low   = EXCLUDED.body_battery_low,
                    resting_hr         = EXCLUDED.resting_hr,
                    intensity_moderate = EXCLUDED.intensity_moderate,
                    intensity_vigorous = EXCLUDED.intensity_vigorous
                """,
                summary.date,
                summary.user_id,
                summary.steps,
                summary.calories_total,
                summary.avg_stress,
                summary.max_stress,
                summary.avg_spo2,
                summary.min_spo2,
                summary.body_battery_high,
                summary.body_battery_low,
                summary.resting_hr,
                summary.intensity_moderate,
                summary.intensity_vigorous,
            )

    async def upsert_training_status(
        self, user_id: int, day: date, status: str
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO daily_summary (user_id, date, training_status)
                VALUES ($2, $3, $1)
                ON CONFLICT (user_id, date)
                DO UPDATE SET training_status = EXCLUDED.training_status
                """,
                status,
                user_id,
                day,
            )

    # ── Sleep ─────────────────────────────────────────────────────────────────

    async def save_sleep(self, session: SleepSession) -> int | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO sleep_sessions (
                    user_id, garmin_sleep_id, start_time, end_time,
                    total_sleep_seconds, deep_sleep_seconds, light_sleep_seconds,
                    rem_sleep_seconds, awake_seconds, sleep_score
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                ON CONFLICT (garmin_sleep_id) DO NOTHING
                RETURNING id
                """,
                session.user_id,
                session.garmin_sleep_id,
                session.start_time,
                session.end_time,
                session.total_sleep_seconds,
                session.deep_sleep_seconds,
                session.light_sleep_seconds,
                session.rem_sleep_seconds,
                session.awake_seconds,
                session.sleep_score,
            )
            return row["id"] if row else None

    async def sleep_exists(self, garmin_sleep_id: int) -> bool:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM sleep_sessions WHERE garmin_sleep_id = $1",
                garmin_sleep_id,
            )
            return row is not None

    # ── HRV ──────────────────────────────────────────────────────────────────

    async def upsert_hrv(self, hrv: HRVDaily) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hrv_daily (date, user_id, hrv_last_night, hrv_weekly_avg, hrv_status)
                VALUES ($1,$2,$3,$4,$5)
                ON CONFLICT (date, user_id) DO UPDATE SET
                    hrv_last_night = EXCLUDED.hrv_last_night,
                    hrv_weekly_avg = EXCLUDED.hrv_weekly_avg,
                    hrv_status     = EXCLUDED.hrv_status
                """,
                hrv.date,
                hrv.user_id,
                hrv.hrv_last_night,
                hrv.hrv_weekly_avg,
                hrv.hrv_status,
            )

    # ── Intraday (Body Battery, Stress, SpO2) ─────────────────────────────────

    async def bulk_insert(  # type: ignore[override]
        self, table: str, user_id: int, readings: list[tuple[Any, ...]]
    ) -> None:
        if not readings:
            return
        allowed = {"body_battery_intraday", "stress_intraday", "spo2_readings"}
        if table not in allowed:
            raise ValueError(f"Unknown intraday table: {table}")
        async with self._pool.acquire() as conn:
            await conn.executemany(
                f"INSERT INTO {table} (time, user_id, value) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",  # nosec B608 — table validated against allowlist above
                [(ts, user_id, val) for ts, val in readings],
            )
        logger.info(f"Inserted {len(readings)} rows into {table} for user {user_id}")
