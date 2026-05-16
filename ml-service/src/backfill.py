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
from models.body_battery import compute_body_battery
from models.stress_metrics import compute_stress_score
from models.running_economy import compute_running_economy
from models.hrv_recovery import compute_hrv_recovery_trajectory

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
            GROUP BY 1, a.id ORDER BY 1
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

    # Daily summary for avg_stress + body_battery for backfill
    daily_rows = await pool.fetch(
        """SELECT date, avg_stress, body_battery_high
           FROM daily_summary WHERE user_id = $1 ORDER BY date""",
        user_id,
    )
    daily_by_date: dict[date, dict[str, Any]] = {
        r["date"]: {
            "avg_stress": r["avg_stress"],
            "body_battery_high": r["body_battery_high"],
        }
        for r in daily_rows
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
              AND (
                NOT EXISTS (
                  SELECT 1 FROM ml_predictions p
                  WHERE p.user_id = d.user_id
                    AND p.date    = d.date
                    AND p.model   = 'energy_physical'
                )
                OR NOT EXISTS (
                  SELECT 1 FROM ml_predictions p
                  WHERE p.user_id = d.user_id
                    AND p.date    = d.date
                    AND p.model IN ('body_battery_custom', 'stress_score_custom')
                )
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

        # Body Battery Custom
        yesterday_bb = None
        if target > gap_dates[0]:
            prev_row = await pool.fetchrow(
                "SELECT value FROM ml_predictions WHERE user_id=$1 AND date=$2 AND model='body_battery_custom'",
                user_id,
                target - timedelta(days=1),
            )
            yesterday_bb = prev_row["value"] if prev_row else None
        if yesterday_bb is None and target in daily_by_date:
            yesterday_bb = daily_by_date[target].get("body_battery_high")

        sleep_h = sleep_by_date.get(target, {}).get("total_h") or 0.0
        hrv_valid = [v for v in hrv_window if v is not None]
        hrv_baseline = (
            sum(hrv_valid[-30:]) / len(hrv_valid[-30:]) if len(hrv_valid) >= 7 else 0
        )
        hrv_last = hrv_valid[-1] if hrv_valid else None
        target_trimp_rows = [r for r in act_rows if r.get("activity_date") == target]
        target_trimp = 0.0
        if (
            target_trimp_rows
            and target_trimp_rows[0].get("avg_hr")
            and target_trimp_rows[0].get("duration_seconds")
        ):
            rhr_t = target_trimp_rows[0].get("resting_hr") or 60.0
            denom_t = hrmax - rhr_t
            if denom_t > 0:
                hfr_t = max(0.0, (target_trimp_rows[0]["avg_hr"] - rhr_t) / denom_t)
                target_trimp = (
                    (target_trimp_rows[0]["duration_seconds"] / 60.0)
                    * hfr_t
                    * (hfr_t * 4 + 1)
                )

        avg_stress = daily_by_date.get(target, {}).get("avg_stress")
        bb_result = compute_body_battery(
            yesterday_bb, sleep_h, hrv_last, hrv_baseline, target_trimp, avg_stress
        )
        if bb_result.get("score") is not None:
            await save_prediction(
                user_id, target, "body_battery_custom", bb_result["score"], bb_result
            )

        # Stress Score Custom
        stress_result = compute_stress_score(hrv_window, avg_stress)
        if stress_result.get("score") is not None:
            await save_prediction(
                user_id,
                target,
                "stress_score_custom",
                stress_result["score"],
                stress_result,
            )

        # Running Economy
        run_acts = [
            r
            for r in act_rows
            if r.get("activity_date") == target
            and r.get("sport_type") in ("running", "trail_running")
            and r.get("avg_ground_contact_time")
        ]
        if run_acts:
            re_result = compute_running_economy(run_acts)
            if re_result.get("score") is not None:
                await save_prediction(
                    user_id, target, "running_economy", re_result["score"], re_result
                )

        # HRV Recovery Trajectory (30-day lookback per target date)
        hrv_rec_result = compute_hrv_recovery_trajectory(
            hrv_window, act_rows, hrmax, target, lookback=30
        )
        if hrv_rec_result.get("recovery_speed") is not None:
            await save_prediction(
                user_id,
                target,
                "hrv_recovery",
                hrv_rec_result["recovery_speed"],
                hrv_rec_result,
            )

    logger.info(f"user={user_id}: backfill complete ({len(gap_dates)} dates)")
    return len(gap_dates)
