import json
from datetime import date, datetime, timedelta

import asyncpg
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "garmin"
    db_user: str
    db_password: str
    db_app_user: str
    db_app_password: str
    session_secret: str
    https_only: bool = True
    trimp_lookback_days: int = 7
    trimp_forecast_days: int = 7

    @property
    def db_url(self) -> str:
        return f"postgresql://{self.db_app_user}:{self.db_app_password}@{self.db_host}:{self.db_port}/{self.db_name}"


_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = Settings()  # type: ignore[call-arg]
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
    if row is None:
        raise RuntimeError("create_user: INSERT RETURNING returned no row")
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
        """
        SELECT id, name, email, garmin_linked, garmin_email, libre_linked, libre_email,
               date_of_birth, sex, epilepsy_mode
        FROM users WHERE id = $1
        """,
        user_id,
    )
    return dict(row) if row else None


async def update_user_profile(
    user_id: int,
    date_of_birth: date | None,
    sex: str | None,
    epilepsy_mode: bool | None = None,
) -> None:
    pool = await get_pool()
    if epilepsy_mode is not None:
        await pool.execute(
            "UPDATE users SET date_of_birth = $1, sex = $2, epilepsy_mode = $3 WHERE id = $4",
            date_of_birth,
            sex,
            epilepsy_mode,
            user_id,
        )
    else:
        await pool.execute(
            "UPDATE users SET date_of_birth = $1, sex = $2 WHERE id = $3",
            date_of_birth,
            sex,
            user_id,
        )


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
    user_id: int, limit: int = 500, days: int = 7, end_date: date | None = None
) -> list[dict]:
    pool = await get_pool()
    end = end_date if end_date is not None else date.today()
    rows = await pool.fetch(
        """
        SELECT id, sport_type, started_at, duration_seconds, distance_meters,
               avg_hr, calories
        FROM activities
        WHERE user_id = $1
          AND started_at >= ($3::date - ($2 * INTERVAL '1 day'))::timestamp
          AND started_at < ($3::date + INTERVAL '1 day')::timestamp
        ORDER BY started_at DESC
        LIMIT $4
        """,
        user_id,
        days,
        end,
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
               a.user_rpe,
               a.avg_ground_contact_time, a.avg_vertical_oscillation,
               a.avg_stride_length, a.avg_vertical_ratio, a.avg_running_power,
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


async def set_activity_rpe(user_id: int, activity_id: int, rpe: int) -> bool:
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE activities SET user_rpe = $1 WHERE id = $2 AND user_id = $3",
        rpe,
        activity_id,
        user_id,
    )
    return result == "UPDATE 1"


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
        SELECT date(start_time) AS date, sleep_score, total_sleep_seconds,
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


async def get_readiness(user_id: int) -> dict:
    # Readiness = gewichteter Durchschnitt der eigenen Energie-Dimensionen
    # Physical (0.35) + Autonomic (0.40) + Cognitive (0.25)
    # Keine Garmin-Blackbox-Werte (HRV-Status Firstbeat, Body Battery, Stress)
    energy = await get_energy_metrics(user_id)
    phys = energy.get("energy_physical", {})
    auton = energy.get("energy_autonomic", {})
    cog = energy.get("energy_cognitive", {})

    components: list[tuple[float, float]] = []
    if phys.get("score") is not None:
        components.append((phys["score"], 0.35))
    if auton.get("score") is not None:
        components.append((auton["score"], 0.40))
    if cog.get("score") is not None:
        components.append((cog["score"], 0.25))

    if not components:
        return {
            "score": None,
            "label": "Keine Daten",
            "cls": "badge-poor",
            "energy_physical": None,
            "energy_autonomic": None,
            "energy_cognitive": None,
        }

    total_w = sum(w for _, w in components)
    score = round(max(0, min(100, sum(s * w / total_w for s, w in components))))

    if score >= 75:
        label, cls = "Bereit", "badge-balanced"
    elif score >= 55:
        label, cls = "In Ordnung", "badge-balanced"
    elif score >= 35:
        label, cls = "Erholen", "badge-unbalanced"
    else:
        label, cls = "Pause", "badge-poor"

    return {
        "score": score,
        "label": label,
        "cls": cls,
        "energy_physical": phys.get("score"),
        "energy_autonomic": auton.get("score"),
        "energy_cognitive": cog.get("score"),
    }


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


async def get_ml_insights(user_id: int) -> dict:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT DISTINCT ON (model) model, value, metadata
        FROM ml_predictions
        WHERE user_id = $1
          AND (
              (model != 'model_meta_rf' AND date >= CURRENT_DATE - 1)
              OR model = 'model_meta_rf'
          )
        ORDER BY model, date DESC
        """,
        user_id,
    )
    result: dict = {}
    for row in rows:
        meta = json.loads(row["metadata"]) if row["metadata"] else {}
        result[row["model"]] = {"value": row["value"], **meta}
    return result


async def set_libre_linked(user_id: int, libre_email: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET libre_linked = true, libre_email = $2 WHERE id = $1",
        user_id,
        libre_email,
    )


async def set_libre_unlinked(user_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE users SET libre_linked = false, libre_email = null WHERE id = $1",
                user_id,
            )
            await conn.execute(
                "DELETE FROM glucose_readings WHERE user_id = $1",
                user_id,
            )


async def get_glucose_recent(user_id: int, hours: int = 24) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT time, value_mgdl, trend, is_high, is_low
        FROM glucose_readings
        WHERE user_id = $1
          AND time >= NOW() - ($2 || ' hours')::interval
        ORDER BY time DESC
        """,
        user_id,
        str(hours),
    )
    return [
        {
            "time": r["time"].isoformat(),
            "value_mgdl": r["value_mgdl"],
            "trend": r["trend"],
            "is_high": r["is_high"],
            "is_low": r["is_low"],
        }
        for r in rows
    ]


async def get_glucose_stats(user_id: int, days: int = 14) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT
            COUNT(*)                                                         AS total,
            ROUND(AVG(value_mgdl)::numeric, 1)                              AS avg_mgdl,
            MIN(value_mgdl)                                                  AS min_mgdl,
            MAX(value_mgdl)                                                  AS max_mgdl,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE value_mgdl BETWEEN 70 AND 180)
                / NULLIF(COUNT(*), 0)
            , 1)                                                             AS tir_pct,
            COUNT(*) FILTER (WHERE is_low  = true)                          AS count_low,
            COUNT(*) FILTER (WHERE is_high = true)                          AS count_high
        FROM glucose_readings
        WHERE user_id = $1
          AND time >= NOW() - ($2 * INTERVAL '1 day')
        """,
        user_id,
        days,
    )
    return dict(row) if row else {}


async def get_energy_metrics(user_id: int) -> dict:
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


async def get_ml_history(
    user_id: int, days: int = 30, end_date: date | None = None
) -> dict:
    pool = await get_pool()
    end = end_date if end_date is not None else date.today()
    cutoff = end - timedelta(days=days)
    rows = await pool.fetch(
        """
        SELECT date, model, value, metadata
        FROM ml_predictions
        WHERE user_id = $1 AND date >= $2 AND date <= $3
        ORDER BY date ASC
        """,
        user_id,
        cutoff,
        end,
    )
    result: dict = {}
    for row in rows:
        meta = json.loads(row["metadata"]) if row["metadata"] else {}
        entry = {"date": str(row["date"]), "value": row["value"], **meta}
        result.setdefault(row["model"], []).append(entry)
    return result


async def request_sync(user_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET sync_requested = true WHERE id = $1",
        user_id,
    )


async def get_sync_status(user_id: int) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT sync_requested, last_sync_at FROM users WHERE id = $1",
        user_id,
    )
    return {
        "pending": row["sync_requested"] if row else False,
        "last_sync_at": row["last_sync_at"].isoformat()
        if row and row["last_sync_at"]
        else None,
    }


async def get_ml_status(user_id: int) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT ml_requested, last_ml_at FROM users WHERE id = $1",
        user_id,
    )
    return {
        "pending": row["ml_requested"] if row else False,
        "last_ml_at": row["last_ml_at"].isoformat()
        if row and row["last_ml_at"]
        else None,
    }


async def get_training_load_inputs(user_id: int, days: int = 200) -> list[dict]:
    """Per-activity rows needed for TRIMP calculation (one row per activity)."""
    from datetime import date, timedelta

    cutoff = date.today() - timedelta(days=days)
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT DATE(a.started_at AT TIME ZONE 'UTC') AS activity_date,
               a.avg_hr::float,
               a.duration_seconds::float,
               d.resting_hr::float
        FROM activities a
        LEFT JOIN daily_summary d
               ON d.date    = DATE(a.started_at AT TIME ZONE 'UTC')
              AND d.user_id = a.user_id
        WHERE a.user_id = $1
          AND a.started_at >= $2
          AND a.avg_hr IS NOT NULL
          AND a.avg_hr > 0
          AND a.duration_seconds IS NOT NULL
          AND a.duration_seconds > 0
        ORDER BY activity_date
        """,
        user_id,
        cutoff,
    )
    return [dict(r) for r in rows]


async def get_activity_hrmax(user_id: int) -> float:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT MAX(max_hr)::float AS hrmax FROM activities
        WHERE user_id = $1
          AND started_at >= CURRENT_DATE - INTERVAL '12 months'
          AND max_hr IS NOT NULL
        """,
        user_id,
    )
    return float(row["hrmax"]) if row and row["hrmax"] else 190.0


async def get_user_sex(user_id: int) -> str:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT sex FROM users WHERE id = $1", user_id)
    return str(row["sex"]) if row and row["sex"] else "male"


async def save_seizure(
    user_id: int,
    occurred_at: datetime,
    duration_seconds: int | None,
    type_: str,
    severity: int | None,
    notes: str | None,
) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO seizure_events
               (user_id, occurred_at, duration_seconds, type, severity, notes)
           VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
        user_id,
        occurred_at,
        duration_seconds,
        type_,
        severity,
        notes,
    )
    if row is None:
        raise RuntimeError("save_seizure: INSERT RETURNING returned no row")
    return int(row["id"])


async def get_seizures(user_id: int, days: int = 365) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT id, occurred_at, duration_seconds, type, severity, notes
           FROM seizure_events
           WHERE user_id = $1
             AND occurred_at >= NOW() - ($2 || ' days')::interval
           ORDER BY occurred_at DESC""",
        user_id,
        str(days),
    )
    result = []
    for r in rows:
        d = dict(r)
        d["occurred_at"] = d["occurred_at"].isoformat()
        result.append(d)
    return result


async def get_seizure_risk(user_id: int) -> dict:
    pool = await get_pool()
    sleep_rows = await pool.fetch(
        """SELECT total_sleep_seconds FROM sleep_sessions
           WHERE user_id = $1 AND start_time >= NOW() - INTERVAL '8 days'
           ORDER BY start_time DESC LIMIT 7""",
        user_id,
    )
    sleep_debt_h = sum(
        max(0.0, 7.0 - (r["total_sleep_seconds"] or 0) / 3600.0) for r in sleep_rows
    )
    yesterday = await pool.fetchrow(
        """SELECT d.avg_stress, d.body_battery_low, d.resting_hr, d.intensity_vigorous,
                  h.hrv_last_night, h.hrv_weekly_avg
           FROM daily_summary d
           LEFT JOIN hrv_daily h ON h.user_id = d.user_id AND h.date = d.date
           WHERE d.user_id = $1
           ORDER BY d.date DESC LIMIT 1""",
        user_id,
    )
    flags: list[dict] = []
    level = "ok"

    def _raise(new: str) -> str:
        if new == "red" or level == "red":
            return "red"
        return new

    if sleep_debt_h > 5:
        flags.append(
            {
                "label": "Schlafschuld",
                "detail": f"{sleep_debt_h:.1f}h in 7 Nächten",
                "color": "red",
            }
        )
        level = _raise("red")
    elif sleep_debt_h > 2:
        flags.append(
            {
                "label": "Schlafschuld",
                "detail": f"{sleep_debt_h:.1f}h in 7 Nächten",
                "color": "amber",
            }
        )
        level = _raise("amber")

    if yesterday:
        avg_stress = yesterday["avg_stress"] or 0
        hrv_now = yesterday["hrv_last_night"]
        hrv_avg = yesterday["hrv_weekly_avg"]
        bb_low = yesterday["body_battery_low"]
        resting_hr = yesterday["resting_hr"]
        vigorous = yesterday["intensity_vigorous"] or 0

        if avg_stress > 70:
            flags.append(
                {
                    "label": "Hoher Stress",
                    "detail": f"Ø {avg_stress} gestern",
                    "color": "amber",
                }
            )
            level = _raise("amber")

        if hrv_now and hrv_avg and hrv_avg > 0 and hrv_now < hrv_avg * 0.8:
            drop_pct = round((1 - hrv_now / hrv_avg) * 100)
            flags.append(
                {
                    "label": "HRV-Einbruch",
                    "detail": f"{hrv_now} ms (−{drop_pct}% vom Wochenschnitt)",
                    "color": "amber",
                }
            )
            level = _raise("amber")

        if bb_low is not None and bb_low < 20:
            flags.append(
                {
                    "label": "Niedriger Body Battery",
                    "detail": f"Tiefstwert {bb_low} gestern",
                    "color": "amber",
                }
            )
            level = _raise("amber")

        if vigorous > 60:
            flags.append(
                {
                    "label": "Intensives Training",
                    "detail": f"{vigorous} min vigorous gestern",
                    "color": "amber",
                }
            )
            level = _raise("amber")

        if resting_hr:
            hr_baseline_row = await pool.fetchrow(
                """SELECT ROUND(AVG(resting_hr)) AS baseline
                   FROM daily_summary
                   WHERE user_id = $1 AND resting_hr IS NOT NULL
                     AND date >= CURRENT_DATE - INTERVAL '30 days'
                     AND date < CURRENT_DATE""",
                user_id,
            )
            baseline = hr_baseline_row["baseline"] if hr_baseline_row else None
            if baseline and resting_hr > baseline * 1.1:
                flags.append(
                    {
                        "label": "Erhöhte Ruheherzfrequenz",
                        "detail": f"{resting_hr} bpm (Schnitt {int(baseline)} bpm)",
                        "color": "amber",
                    }
                )
                level = _raise("amber")

    return {"level": level, "flags": flags, "sleep_debt_h": round(sleep_debt_h, 1)}
