"""Energy history backfill — fills gaps in ml_predictions for energy scores.

Called automatically by run_on_request / run_all_users when gaps are detected.
Safe to call repeatedly: uses ON CONFLICT DO UPDATE.
"""

import logging
from datetime import date, timedelta
from typing import Any

from db import get_pool, save_prediction
from models.energy_metrics import (
    compute_autonomic_energy,
    compute_cognitive_energy,
    compute_physical_energy,
)

logger = logging.getLogger(__name__)


async def backfill_user(user_id: int) -> int:
    """Compute and upsert energy scores for all historical gaps. Returns dates written."""
    pool = get_pool()

    hrmax_row = await pool.fetchrow(
        """
        SELECT MAX(max_hr)::float AS hrmax FROM activities
        WHERE user_id = $1 AND max_hr IS NOT NULL
          AND started_at >= CURRENT_DATE - INTERVAL '12 months'
        """,
        user_id,
    )
    hrmax = float(hrmax_row["hrmax"]) if hrmax_row and hrmax_row["hrmax"] else 190.0

    act_rows: list[dict[str, Any]] = [
        dict(r)
        for r in await pool.fetch(
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
              AND a.avg_hr IS NOT NULL
              AND a.duration_seconds IS NOT NULL
            GROUP BY 1 ORDER BY 1
            """,
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
    hrv_dates_sorted = sorted(hrv_by_date.keys())

    sleep_rows = await pool.fetch(
        """
        SELECT DATE(start_time AT TIME ZONE 'UTC') AS sleep_date,
               total_sleep_seconds, deep_sleep_seconds
        FROM sleep_sessions WHERE user_id = $1 ORDER BY start_time
        """,
        user_id,
    )
    sleep_by_date: dict[date, dict[str, float | None]] = {
        r["sleep_date"]: {
            "total_h": float(r["total_sleep_seconds"]) / 3600.0
            if r["total_sleep_seconds"] is not None
            else None,
            "deep_h": float(r["deep_sleep_seconds"]) / 3600.0
            if r["deep_sleep_seconds"] is not None
            else None,
        }
        for r in sleep_rows
    }

    # Only dates with gaps (exclude today — inference handles that)
    gap_dates = [
        r["date"]
        for r in await pool.fetch(
            """
            SELECT d.date
            FROM daily_summary d
            WHERE d.user_id = $1
              AND d.date < CURRENT_DATE
              AND NOT EXISTS (
                SELECT 1 FROM ml_predictions p
                WHERE p.user_id = d.user_id
                  AND p.date    = d.date
                  AND p.model   = 'energy_physical'
              )
            ORDER BY d.date
            """,
            user_id,
        )
    ]

    if not gap_dates:
        return 0

    logger.info(f"user={user_id}: backfilling {len(gap_dates)} missing energy dates")

    for target in gap_dates:
        phys = compute_physical_energy(act_rows, hrmax, target, window_days=50)
        await save_prediction(
            user_id, target, "energy_physical", phys.get("score"), phys
        )

        cutoff_hrv = target - timedelta(days=90)
        hrv_window = [
            hrv_by_date[d] for d in hrv_dates_sorted if cutoff_hrv <= d <= target
        ]
        auton = compute_autonomic_energy(hrv_window)
        await save_prediction(
            user_id, target, "energy_autonomic", auton.get("score"), auton
        )

        sleep_7d = [
            sleep_by_date[target - timedelta(days=k)]
            for k in range(1, 8)
            if (target - timedelta(days=k)) in sleep_by_date
        ]
        cog = compute_cognitive_energy(sleep_7d)
        await save_prediction(
            user_id, target, "energy_cognitive", cog.get("score"), cog
        )

    logger.info(f"user={user_id}: backfill complete ({len(gap_dates)} dates)")
    return len(gap_dates)
