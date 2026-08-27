import asyncpg

from domain.models import Activity


class TimescaleActivityRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save_activity(self, activity: Activity) -> int | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO activities (user_id, garmin_activity_id, started_at, duration_seconds,
                    sport_type, distance_meters, calories, avg_hr, max_hr, avg_pace_sec_per_km,
                    avg_cadence, avg_power, elevation_gain, avg_speed_kmh, aerobic_effect,
                    anaerobic_effect, avg_ground_contact_time, avg_vertical_oscillation,
                    avg_stride_length, avg_vertical_ratio, avg_running_power)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
                ON CONFLICT (garmin_activity_id) DO UPDATE SET
                    sport_type=EXCLUDED.sport_type, aerobic_effect=EXCLUDED.aerobic_effect,
                    anaerobic_effect=EXCLUDED.anaerobic_effect,
                    avg_ground_contact_time=EXCLUDED.avg_ground_contact_time,
                    avg_vertical_oscillation=EXCLUDED.avg_vertical_oscillation,
                    avg_stride_length=EXCLUDED.avg_stride_length,
                    avg_vertical_ratio=EXCLUDED.avg_vertical_ratio,
                    avg_running_power=EXCLUDED.avg_running_power
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
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM activity_records WHERE activity_id = $1 LIMIT 1",
                activity_id,
            )
            return row is not None

    async def get_activities_without_records(self, user_id: int) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT a.id AS db_id, a.garmin_activity_id FROM activities a
                WHERE a.user_id = $1 AND NOT EXISTS
                    (SELECT 1 FROM activity_records r WHERE r.activity_id = a.id)
                ORDER BY a.started_at DESC
                """,
                user_id,
            )
            return [dict(row) for row in rows]


class TimescaleActivityRecordRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

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
                INSERT INTO activity_records (time, activity_id, user_id, heart_rate,
                    pace_sec_per_km, cadence, power, elevation, distance, lat, lng)
                SELECT $1,$2,(SELECT user_id FROM activities WHERE id = $2),$3,$4,$5,$6,$7,$8,$9,$10
                """,
                rows,
            )
