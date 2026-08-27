from datetime import date
from typing import Any

import asyncpg
import structlog

from domain.models import Activity, DailySummary, HRVDaily, SleepSession
from repositories.base import (
    ActivityRecordRepository,
    ActivityRepository,
    DailySummaryRepository,
    HRVRepository,
    IntradayRepository,
    SleepRepository,
)
from repositories.tokens import TimescaleTokenRepository
from repositories.user_sync import TimescaleUserSyncRepository
from repositories.activities import (
    TimescaleActivityRecordRepository,
    TimescaleActivityRepository,
)
from repositories.health import (
    TimescaleDailyRepository,
    TimescaleHrvRepository,
    TimescaleSleepRepository,
)
from repositories.intraday import TimescaleIntradayRepository
from repositories.glucose import TimescaleGlucoseRepository

logger = structlog.get_logger(__name__)


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
        self._tokens: TimescaleTokenRepository | None = None
        self._user_sync: TimescaleUserSyncRepository | None = None
        self._activities: TimescaleActivityRepository | None = None
        self._activity_records: TimescaleActivityRecordRepository | None = None
        self._daily: TimescaleDailyRepository | None = None
        self._sleep: TimescaleSleepRepository | None = None
        self._hrv: TimescaleHrvRepository | None = None
        self._intraday: TimescaleIntradayRepository | None = None
        self._glucose: TimescaleGlucoseRepository | None = None

    @property
    def _db(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Pool not initialized — call init() first")
        return self._pool

    async def init(self) -> None:
        self._pool = await asyncpg.create_pool(self._db_url, min_size=2, max_size=5)
        self._tokens = TimescaleTokenRepository(self._pool)
        self._user_sync = TimescaleUserSyncRepository(self._pool)
        self._activities = TimescaleActivityRepository(self._pool)
        self._activity_records = TimescaleActivityRecordRepository(self._pool)
        self._daily = TimescaleDailyRepository(self._pool)
        self._sleep = TimescaleSleepRepository(self._pool)
        self._hrv = TimescaleHrvRepository(self._pool)
        self._intraday = TimescaleIntradayRepository(self._pool)
        self._glucose = TimescaleGlucoseRepository(self._pool)
        logger.info("Database connection pool initialized")

    @property
    def _token_repo(self) -> TimescaleTokenRepository:
        if self._tokens is None:
            self._tokens = TimescaleTokenRepository(self._db)
        return self._tokens

    @property
    def _user_sync_repo(self) -> TimescaleUserSyncRepository:
        if self._user_sync is None:
            self._user_sync = TimescaleUserSyncRepository(self._db)
        return self._user_sync

    def _domain_repo(self, repository, factory):
        if repository is None:
            repository = factory(self._db)
        return repository

    async def records_exist(self, activity_id: int) -> bool:
        return await self._domain_repo(
            self._activities, TimescaleActivityRepository
        ).records_exist(activity_id)

    async def get_activities_without_records(self, user_id: int) -> list[dict]:
        return await self._domain_repo(
            self._activities, TimescaleActivityRepository
        ).get_activities_without_records(user_id)

    async def bulk_insert_records(self, activity_id: int, records: list) -> None:
        await self._domain_repo(
            self._activity_records, TimescaleActivityRecordRepository
        ).bulk_insert_records(activity_id, records)

    async def upsert_daily(self, summary: DailySummary) -> None:
        await self._domain_repo(self._daily, TimescaleDailyRepository).upsert_daily(
            summary
        )

    async def upsert_training_status(
        self, user_id: int, day: date, status: str
    ) -> None:
        await self._domain_repo(
            self._daily, TimescaleDailyRepository
        ).upsert_training_status(user_id, day, status)

    async def save_sleep(self, session: SleepSession) -> int | None:
        return await self._domain_repo(
            self._sleep, TimescaleSleepRepository
        ).save_sleep(session)

    async def sleep_exists(self, garmin_sleep_id: int) -> bool:
        return await self._domain_repo(
            self._sleep, TimescaleSleepRepository
        ).sleep_exists(garmin_sleep_id)

    async def upsert_hrv(self, hrv: HRVDaily) -> None:
        await self._domain_repo(self._hrv, TimescaleHrvRepository).upsert_hrv(hrv)

    async def bulk_insert(
        self, table: str, user_id: int, readings: list[tuple[Any, ...]]
    ) -> None:
        await self._domain_repo(
            self._intraday, TimescaleIntradayRepository
        ).bulk_insert(table, user_id, readings)

    async def bulk_insert_glucose(self, user_id: int, rows: list[dict]) -> None:
        await self._domain_repo(
            self._glucose, TimescaleGlucoseRepository
        ).bulk_insert_glucose(user_id, rows)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    # ── Activities ────────────────────────────────────────────────────────────

    async def save_activity(self, activity: Activity) -> int | None:
        return await self._domain_repo(
            self._activities, TimescaleActivityRepository
        ).save_activity(activity)

    async def _legacy_save_activity(self, activity: Activity) -> int | None:
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

    async def _legacy_records_exist(self, activity_id: int) -> bool:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM activity_records WHERE activity_id = $1 LIMIT 1",
                activity_id,
            )
            return row is not None

    async def _legacy_get_activities_without_records(self, user_id: int) -> list[dict]:
        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT a.id AS db_id, a.garmin_activity_id
                FROM activities a
                WHERE a.user_id = $1
                  AND NOT EXISTS (
                      SELECT 1 FROM activity_records r WHERE r.activity_id = a.id
                  )
                ORDER BY a.started_at DESC
                """,
                user_id,
            )
            return [dict(r) for r in rows]

    # ── Activity Records (GPS Tracks) ─────────────────────────────────────────

    async def _legacy_bulk_insert_records(
        self, activity_id: int, records: list
    ) -> None:
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

    async def _legacy_upsert_daily(self, summary: DailySummary) -> None:
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

    async def _legacy_upsert_training_status(
        self, user_id: int, day: date, status: str
    ) -> None:
        async with self._db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO daily_summary (user_id, date, training_status)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, date)
                DO UPDATE SET training_status = EXCLUDED.training_status
                """,
                user_id,
                day,
                status,
            )

    # ── Sleep ─────────────────────────────────────────────────────────────────

    async def _legacy_save_sleep(self, session: SleepSession) -> int | None:
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

    async def _legacy_sleep_exists(self, garmin_sleep_id: int) -> bool:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM sleep_sessions WHERE garmin_sleep_id = $1",
                garmin_sleep_id,
            )
            return row is not None

    # ── HRV ──────────────────────────────────────────────────────────────────

    async def _legacy_upsert_hrv(self, hrv: HRVDaily) -> None:
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

    async def _legacy_bulk_insert(  # type: ignore[override]
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
        return await self._token_repo.get_user_token(user_id, service)

    async def save_user_token(
        self, user_id: int, service: str, token_data: bytes
    ) -> None:
        await self._token_repo.save_user_token(user_id, service, token_data)

    # ── Users ─────────────────────────────────────────────────────────────────

    async def get_active_users(self) -> list[dict]:
        return await self._user_sync_repo.get_active_users()

    async def get_sync_requested_users(self) -> list[dict]:
        return await self._user_sync_repo.get_sync_requested_users()

    async def get_libre_users(self) -> list[dict]:
        return await self._user_sync_repo.get_libre_users()

    async def mark_sync_done(self, user_id: int) -> None:
        await self._user_sync_repo.mark_sync_done(user_id)

    async def set_ml_requested(self, user_id: int) -> None:
        await self._user_sync_repo.set_ml_requested(user_id)

    # ── Glucose ───────────────────────────────────────────────────────────────

    async def _legacy_bulk_insert_glucose(self, user_id: int, rows: list[dict]) -> None:
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
