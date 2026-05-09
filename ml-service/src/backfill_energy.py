"""
Backfill historical energy scores into ml_predictions.

Computes energy_physical / energy_autonomic / energy_cognitive for every date
in daily_summary and upserts the results. Safe to re-run — uses ON CONFLICT
DO UPDATE so existing rows are overwritten with freshly computed values.

Usage (inside ml-service container):
    python /app/src/backfill_energy.py

Or via Makefile:
    make backfill-energy
"""

import asyncio
import json
import logging
from datetime import date, timedelta
from typing import Any

import asyncpg

from config import Settings
from models.energy_metrics import (
    compute_autonomic_energy,
    compute_cognitive_energy,
    compute_physical_energy,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def _upsert(
    pool: asyncpg.Pool,
    user_id: int,
    d: date,
    model: str,
    value: float | None,
    metadata: dict[str, Any],
) -> None:
    await pool.execute(
        """
        INSERT INTO ml_predictions (date, user_id, model, value, metadata)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (date, user_id, model) DO UPDATE SET
            value      = EXCLUDED.value,
            metadata   = EXCLUDED.metadata,
            created_at = NOW()
        """,
        d,
        user_id,
        model,
        value,
        json.dumps(metadata),
    )


async def backfill_user(pool: asyncpg.Pool, user_id: int) -> None:
    # hrmax — same logic as db.get_hrmax
    hrmax_row = await pool.fetchrow(
        """
        SELECT MAX(max_hr)::float AS hrmax FROM activities
        WHERE user_id = $1 AND max_hr IS NOT NULL
          AND started_at >= CURRENT_DATE - INTERVAL '12 months'
        """,
        user_id,
    )
    hrmax = float(hrmax_row["hrmax"]) if hrmax_row and hrmax_row["hrmax"] else 190.0

    # All activity rows (no day-limit — the compute function handles the window)
    act_rows = [
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

    # Full HRV history, sorted ascending
    hrv_rows = await pool.fetch(
        "SELECT date, hrv_last_night FROM hrv_daily WHERE user_id = $1 ORDER BY date",
        user_id,
    )
    hrv_by_date: dict[date, float | None] = {
        r["date"]: r["hrv_last_night"] for r in hrv_rows
    }
    hrv_dates_sorted = sorted(hrv_by_date.keys())

    # Full sleep history
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

    # All calendar dates to backfill
    all_dates = [
        r["date"]
        for r in await pool.fetch(
            "SELECT date FROM daily_summary WHERE user_id = $1 ORDER BY date",
            user_id,
        )
    ]

    logger.info(
        f"user={user_id}: {len(all_dates)} dates to backfill — "
        f"{len(act_rows)} activity days, {len(hrv_by_date)} HRV days, "
        f"{len(sleep_by_date)} sleep days, hrmax={hrmax}"
    )

    for i, target in enumerate(all_dates, 1):
        # ── Physical energy ──────────────────────────────────────────────────
        phys = compute_physical_energy(act_rows, hrmax, target, window_days=50)
        await _upsert(pool, user_id, target, "energy_physical", phys.get("score"), phys)

        # ── Autonomic energy ─────────────────────────────────────────────────
        # HRV values in [target−90d, target], ascending; last element = target
        cutoff_hrv = target - timedelta(days=90)
        hrv_window = [
            hrv_by_date[d] for d in hrv_dates_sorted if cutoff_hrv <= d <= target
        ]
        auton = compute_autonomic_energy(hrv_window)
        await _upsert(
            pool, user_id, target, "energy_autonomic", auton.get("score"), auton
        )

        # ── Cognitive energy ─────────────────────────────────────────────────
        # 7 nights whose start_date falls in [target−7, target−1]
        # (the sleep that ended on target morning started the night before)
        sleep_7d = [
            sleep_by_date[target - timedelta(days=k)]
            for k in range(1, 8)
            if (target - timedelta(days=k)) in sleep_by_date
        ]
        cog = compute_cognitive_energy(sleep_7d)
        await _upsert(pool, user_id, target, "energy_cognitive", cog.get("score"), cog)

        if i % 100 == 0:
            logger.info(f"user={user_id}: {i}/{len(all_dates)} days done…")

    logger.info(f"user={user_id}: backfill complete ({len(all_dates)} days)")


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    pool = await asyncpg.create_pool(settings.db_url, min_size=1, max_size=3)
    try:
        users = await pool.fetch(
            "SELECT id FROM users WHERE is_active = true AND garmin_linked = true"
        )
        if not users:
            logger.warning("No active Garmin users found")
            return
        for user in users:
            await backfill_user(pool, user["id"])
        logger.info(
            "All users backfilled. Trigger RF retraining with:\n"
            "  make sync   (or: docker compose exec db psql ... -c "
            '"UPDATE users SET ml_requested = true")'
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
