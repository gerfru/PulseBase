from datetime import date

import asyncpg

from domain.models import DailySummary, HRVDaily, SleepSession


class TimescaleDailyRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert_daily(self, summary: DailySummary) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO daily_summary (date, user_id, steps, calories_total, avg_stress, max_stress,
                    avg_spo2, min_spo2, body_battery_high, body_battery_low, resting_hr,
                    intensity_moderate, intensity_vigorous)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                ON CONFLICT (date, user_id) DO UPDATE SET
                    steps=EXCLUDED.steps, calories_total=EXCLUDED.calories_total,
                    avg_stress=EXCLUDED.avg_stress, max_stress=EXCLUDED.max_stress,
                    avg_spo2=EXCLUDED.avg_spo2, min_spo2=EXCLUDED.min_spo2,
                    body_battery_high=EXCLUDED.body_battery_high,
                    body_battery_low=EXCLUDED.body_battery_low, resting_hr=EXCLUDED.resting_hr,
                    intensity_moderate=EXCLUDED.intensity_moderate,
                    intensity_vigorous=EXCLUDED.intensity_vigorous
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
                """INSERT INTO daily_summary (user_id, date, training_status)
                VALUES ($1, $2, $3) ON CONFLICT (user_id, date)
                DO UPDATE SET training_status = EXCLUDED.training_status""",
                user_id,
                day,
                status,
            )


class TimescaleSleepRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save_sleep(self, session: SleepSession) -> int | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO sleep_sessions (user_id, garmin_sleep_id, start_time, end_time,
                    total_sleep_seconds, deep_sleep_seconds, light_sleep_seconds,
                    rem_sleep_seconds, awake_seconds, sleep_score)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                ON CONFLICT (garmin_sleep_id) DO NOTHING RETURNING id""",
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


class TimescaleHrvRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert_hrv(self, hrv: HRVDaily) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO hrv_daily (date, user_id, hrv_last_night, hrv_weekly_avg, hrv_status)
                VALUES ($1,$2,$3,$4,$5) ON CONFLICT (date, user_id) DO UPDATE SET
                    hrv_last_night=EXCLUDED.hrv_last_night, hrv_weekly_avg=EXCLUDED.hrv_weekly_avg,
                    hrv_status=EXCLUDED.hrv_status""",
                hrv.date,
                hrv.user_id,
                hrv.hrv_last_night,
                hrv.hrv_weekly_avg,
                hrv.hrv_status,
            )
