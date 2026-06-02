from datetime import date, timedelta
from typing import Any

from .pool import _pool_or_raise


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
               ec.value AS energy_cognitive_score,
               acwr_mp.value AS acwr_ratio
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
        LEFT JOIN ml_predictions acwr_mp
               ON acwr_mp.date = d.date AND acwr_mp.user_id = d.user_id AND acwr_mp.model = 'acwr'
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


async def get_latest_features(user_id: int) -> dict[str, Any]:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT h.hrv_last_night, h.hrv_status, s.sleep_score,
               d.resting_hr, d.body_battery_high, d.avg_stress,
               COALESCE(atrain.aerobic_effect_daily,   0) AS aerobic_effect_daily,
               COALESCE(atrain.anaerobic_effect_daily, 0) AS anaerobic_effect_daily,
               acwr_mp.value AS acwr_ratio
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
        LEFT JOIN ml_predictions acwr_mp
               ON acwr_mp.date = d.date AND acwr_mp.user_id = d.user_id AND acwr_mp.model = 'acwr'
        WHERE d.user_id = $1 AND d.date >= CURRENT_DATE - 2
        ORDER BY d.date DESC
        LIMIT 1
        """,
        user_id,
    )
    return dict(row) if row else {}


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


async def get_running_economy_activities(
    user_id: int, limit: int = 10
) -> list[dict[str, Any]]:
    rows = await _pool_or_raise().fetch(
        """
        SELECT avg_ground_contact_time, avg_vertical_oscillation,
               avg_vertical_ratio, avg_stride_length, avg_running_power,
               DATE(started_at AT TIME ZONE 'UTC') AS activity_date
        FROM activities
        WHERE user_id = $1
          AND sport_type IN ('running', 'trail_running')
          AND avg_ground_contact_time IS NOT NULL
        ORDER BY started_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )
    return [dict(r) for r in rows]


async def get_backfill_activity_hrv_data(user_id: int) -> dict[str, Any]:
    """Load hrmax, activity rows, and hrv_by_date for backfill computations."""
    pool = _pool_or_raise()

    hrmax_row = await pool.fetchrow(
        """SELECT MAX(max_hr)::float AS hrmax FROM activities
           WHERE user_id = $1 AND max_hr IS NOT NULL
             AND started_at >= CURRENT_DATE - INTERVAL '12 months'""",
        user_id,
    )
    hrmax = float(hrmax_row["hrmax"]) if hrmax_row and hrmax_row["hrmax"] else 190.0

    act_rows: list[dict[str, Any]] = [
        dict(r)
        for r in await pool.fetch(
            """SELECT DATE(a.started_at AT TIME ZONE 'UTC') AS activity_date,
                      AVG(a.avg_hr)::float                  AS avg_hr,
                      SUM(a.duration_seconds)::float         AS duration_seconds,
                      MAX(d.resting_hr)::float               AS resting_hr,
                      a.avg_ground_contact_time,
                      a.avg_vertical_oscillation,
                      a.avg_vertical_ratio,
                      a.sport_type
               FROM activities a
               LEFT JOIN daily_summary d
                      ON d.date    = DATE(a.started_at AT TIME ZONE 'UTC')
                     AND d.user_id = a.user_id
               WHERE a.user_id = $1
                 AND a.avg_hr IS NOT NULL
                 AND a.duration_seconds IS NOT NULL
               GROUP BY 1, a.id ORDER BY 1""",
            user_id,
        )
    ]

    hrv_rows = await pool.fetch(
        "SELECT date, hrv_last_night FROM hrv_daily WHERE user_id = $1 ORDER BY date",
        user_id,
    )
    hrv_by_date: dict[date, float | None] = {
        r["date"]: r["hrv_last_night"] for r in hrv_rows
    }

    return {
        "hrmax": hrmax,
        "act_rows": act_rows,
        "hrv_by_date": hrv_by_date,
        "hrv_dates_sorted": sorted(hrv_by_date.keys()),
    }
