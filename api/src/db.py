import asyncpg
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "garmin"
    db_user: str
    db_password: str
    session_secret: str
    https_only: bool = True

    @property
    def db_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = Settings()
        _pool = await asyncpg.create_pool(settings.db_url, min_size=1, max_size=5)
    return _pool


async def create_user(name: str, email: str, password_hash: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO users (name, email, password_hash)
        VALUES ($1, $2, $3)
        RETURNING id, name, email, garmin_linked, garmin_email
        """,
        name,
        email,
        password_hash,
    )
    return dict(row)


async def get_user_by_email(email: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, email, password_hash, garmin_linked, garmin_email FROM users WHERE email = $1",
        email,
    )
    return dict(row) if row else None


async def get_user_by_id(user_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, email, garmin_linked, garmin_email FROM users WHERE id = $1",
        user_id,
    )
    return dict(row) if row else None


async def set_garmin_linked(user_id: int, garmin_email: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET garmin_linked = true, garmin_email = $1 WHERE id = $2",
        garmin_email,
        user_id,
    )


async def set_garmin_unlinked(user_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET garmin_linked = false, garmin_email = null WHERE id = $1",
        user_id,
    )


async def get_recent_activities(
    user_id: int, limit: int = 500, days: int = 7
) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT id, sport_type, started_at, duration_seconds, distance_meters,
               avg_hr, calories
        FROM activities
        WHERE user_id = $1
          AND started_at >= NOW() - ($2 * INTERVAL '1 day')
        ORDER BY started_at DESC
        LIMIT $3
        """,
        user_id,
        days,
        limit,
    )
    return [dict(r) for r in rows]


async def get_activity_detail(user_id: int, activity_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT a.id, a.sport_type, a.started_at, a.duration_seconds,
               a.distance_meters, a.calories, a.avg_hr, a.max_hr,
               a.avg_pace_sec_per_km, a.avg_speed_kmh, a.avg_cadence,
               a.avg_power, a.elevation_gain, a.aerobic_effect, a.anaerobic_effect,
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
        ORDER BY time ASC
        """,
        activity_id,
    )
    detail["records"] = [dict(r) for r in records]
    return detail


async def get_daily_summaries(user_id: int, days: int = 30) -> list[dict]:
    pool = await get_pool()
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
        WHERE ds.user_id = $1 AND ds.date >= NOW() - ($2 || ' days')::INTERVAL
        ORDER BY ds.date
        """,
        user_id,
        str(days),
    )
    return [dict(r) for r in rows]


async def get_sleep_sessions(user_id: int, limit: int = 14) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT date(start_time) AS date, sleep_score, total_sleep_seconds,
               deep_sleep_seconds, light_sleep_seconds, rem_sleep_seconds, awake_seconds
        FROM sleep_sessions
        WHERE user_id = $1
        ORDER BY start_time DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )
    return [dict(r) for r in rows]


async def get_hrv_trend(user_id: int, days: int = 30) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT date, hrv_last_night, hrv_weekly_avg, hrv_status
        FROM hrv_daily
        WHERE user_id = $1 AND date >= NOW() - ($2 || ' days')::INTERVAL
        ORDER BY date
        """,
        user_id,
        str(days),
    )
    return [dict(r) for r in rows]


async def get_latest_training_status(user_id: int) -> dict | None:
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


async def get_latest_hrv(user_id: int) -> dict | None:
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
