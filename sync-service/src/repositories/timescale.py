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
    """asyncpg-backed implementation of all sync repositories against TimescaleDB.

    Each method acquires a connection from the pool independently — there is no
    cross-method transaction. Callers that need atomicity must manage their own
    connection/transaction outside this class.
    `bulk_insert` validates the table name against an allowlist before interpolating
    it into SQL (the only dynamic SQL in this class).
    """

    def __init__(self, db_url: str) -> None:
        self._db_url = db_url
        self._pool: asyncpg.Pool | None = None

    @property
    def _db(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Pool not initialized — call init() first")
        return self._pool

    async def init(self) -> None:
        self._pool = await asyncpg.create_pool(self._db_url, min_size=2, max_size=5)
        logger.info("Database connection pool initialized")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    # ── Activities ────────────────────────────────────────────────────────────

    async def save_activity(self, activity: Activity) -> int | None:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO activities (
                    user_id, garmin_activity_id, started_at, duration_seconds,
                    sport_type, distance_meters, calories, avg_hr, max_hr,
                    avg_pace_sec_per_km, avg_cadence, avg_power, elevation_gain,
                    avg_speed_kmh, aerobic_effect, anaerobic_effect,
                    avg_ground_contact_time, avg_vertical_oscillation,
                    avg_stride_length, avg_vertical_ratio, avg_running_power
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
                ON CONFLICT (garmin_activity_id) DO UPDATE SET
                    sport_type               = EXCLUDED.sport_type,
                    aerobic_effect           = EXCLUDED.aerobic_effect,
                    anaerobic_effect         = EXCLUDED.anaerobic_effect,
                    avg_ground_contact_time  = EXCLUDED.avg_ground_contact_time,
                    avg_vertical_oscillation = EXCLUDED.avg_vertical_oscillation,
                    avg_stride_length        = EXCLUDED.avg_stride_length,
                    avg_vertical_ratio       = EXCLUDED.avg_vertical_ratio,
                    avg_running_power        = EXCLUDED.avg_running_power
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
                activity.avg_ground_contact_time,
                activity.avg_vertical_oscillation,
                activity.avg_stride_length,
                activity.avg_vertical_ratio,
                activity.avg_running_power,
            )
            return row["id"] if row else None

    async def records_exist(self, activity_id: int) -> bool:
        async with self._db.acquire() as conn:
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
        async with self._db.acquire() as conn:
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
        logger.info("Inserted %d GPS records for activity %d", len(rows), activity_id)

    # ── Daily Summary ─────────────────────────────────────────────────────────

    async def upsert_daily(self, summary: DailySummary) -> None:
        async with self._db.acquire() as conn:
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
        async with self._db.acquire() as conn:
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
        async with self._db.acquire() as conn:
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
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM sleep_sessions WHERE garmin_sleep_id = $1",
                garmin_sleep_id,
            )
            return row is not None

    # ── HRV ──────────────────────────────────────────────────────────────────

    async def upsert_hrv(self, hrv: HRVDaily) -> None:
        async with self._db.acquire() as conn:
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
        async with self._db.acquire() as conn:
            await conn.executemany(
                f"INSERT INTO {table} (time, user_id, value) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",  # nosec B608 — table validated against allowlist above
                [(ts, user_id, val) for ts, val in readings],
            )
        logger.info(
            "Inserted %d rows into %s for user %d", len(readings), table, user_id
        )

    # ── Tokens ────────────────────────────────────────────────────────────────

    async def get_user_token(self, user_id: int, service: str) -> bytes | None:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT token_data FROM user_tokens WHERE user_id = $1 AND service = $2",
                user_id,
                service,
            )
        return bytes(row["token_data"]) if row else None

    async def save_user_token(
        self, user_id: int, service: str, token_data: bytes
    ) -> None:
        async with self._db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_tokens (user_id, service, token_data)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, service) DO UPDATE
                    SET token_data = $3, updated_at = NOW()
                """,
                user_id,
                service,
                token_data,
            )

    # ── Users ─────────────────────────────────────────────────────────────────

    async def get_active_users(self) -> list[dict]:
        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, garmin_email FROM users "
                "WHERE garmin_linked = true AND is_active = true"
            )
        return [dict(r) for r in rows]

    async def get_sync_requested_users(self) -> list[dict]:
        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, garmin_email FROM users "
                "WHERE garmin_linked = true AND is_active = true AND sync_requested = true"
            )
        return [dict(r) for r in rows]

    async def get_libre_users(self) -> list[dict]:
        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name FROM users WHERE libre_linked = true AND is_active = true"
            )
        return [dict(r) for r in rows]

    async def mark_sync_done(self, user_id: int) -> None:
        async with self._db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET sync_requested = false, last_sync_at = NOW() WHERE id = $1",
                user_id,
            )

    async def set_ml_requested(self, user_id: int) -> None:
        async with self._db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET ml_requested = true WHERE id = $1",
                user_id,
            )

    # ── Glucose ───────────────────────────────────────────────────────────────

    async def bulk_insert_glucose(self, user_id: int, rows: list[dict]) -> None:
        if not rows:
            return
        async with self._db.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO glucose_readings (time, user_id, value_mgdl, trend, is_high, is_low)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id, time) DO NOTHING
                """,
                [
                    (
                        r["time"],
                        r["user_id"],
                        r["value_mgdl"],
                        r["trend"],
                        r["is_high"],
                        r["is_low"],
                    )
                    for r in rows
                ],
            )
        logger.info("Inserted %d glucose readings for user %d", len(rows), user_id)
