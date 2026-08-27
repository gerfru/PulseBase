"""Energy history backfill — fills gaps in ml_predictions for energy scores.

Called automatically by run_on_request / run_all_users when gaps are detected.
Safe to call repeatedly: uses ON CONFLICT DO UPDATE.
"""

import structlog
from datetime import date, timedelta
from typing import Any

from db import (
    get_backfill_activity_hrv_data,
    get_backfill_sleep_daily_gaps,
)
from models.body_battery import compute_body_battery
from models.energy_metrics import (
    compute_autonomic_energy,
    compute_cognitive_energy,
    compute_physical_energy,
)
from models.hrv_recovery import compute_hrv_recovery_trajectory
from models.running_economy import compute_running_economy
from models.stress_metrics import compute_stress_score
from repositories.predictions import PredictionRepository

logger = structlog.get_logger(__name__)
prediction_repository = PredictionRepository()


async def save_prediction(*args: Any, **kwargs: Any) -> None:
    await prediction_repository.save(*args, **kwargs)


async def get_prediction_for_date(
    user_id: int, prediction_date: date, model: str
) -> float | None:
    return await prediction_repository.get_for_date(user_id, prediction_date, model)


def _compute_trimp(act_rows: list[dict[str, Any]], hrmax: float, target: date) -> float:
    """TRIMP for a given date using HRF² formula; returns 0 when data is missing."""
    rows = [r for r in act_rows if r.get("activity_date") == target]
    if not rows or not rows[0].get("avg_hr") or not rows[0].get("duration_seconds"):
        return 0.0
    row = rows[0]
    rhr = row.get("resting_hr") or 60.0
    denom = hrmax - rhr
    if denom <= 0:
        return 0.0
    hfr = max(0.0, (row["avg_hr"] - rhr) / denom)
    return (row["duration_seconds"] / 60.0) * hfr * (hfr * 4 + 1)


async def _backfill_energy_scores(
    user_id: int, target: date, data: dict[str, Any]
) -> None:
    """Save physical, autonomic, and cognitive energy scores for a single historical date."""
    phys = compute_physical_energy(
        data["act_rows"], data["hrmax"], target, window_days=50
    )
    await save_prediction(user_id, target, "energy_physical", phys.get("score"), phys)

    cutoff_hrv = target - timedelta(days=90)
    hrv_window = [
        data["hrv_by_date"][d]
        for d in data["hrv_dates_sorted"]
        if cutoff_hrv <= d <= target
    ]
    auton = compute_autonomic_energy(hrv_window)
    await save_prediction(
        user_id, target, "energy_autonomic", auton.get("score"), auton
    )

    sleep_7d = [
        data["sleep_by_date"][target - timedelta(days=k)]
        for k in range(1, 8)
        if (target - timedelta(days=k)) in data["sleep_by_date"]
    ]
    cog = compute_cognitive_energy(sleep_7d)
    await save_prediction(user_id, target, "energy_cognitive", cog.get("score"), cog)


async def _save_body_battery(
    user_id: int,
    target: date,
    data: dict[str, Any],
    yesterday_bb: float | None,
    hrv_valid: list,
    hrv_baseline: float,
    avg_stress: float | None,
) -> None:
    sleep_entry = data["sleep_by_date"].get(target, {})
    bb_result = compute_body_battery(
        yesterday_bb,
        sleep_entry.get("total_h") or 0.0,
        sleep_entry.get("deep_h"),
        sleep_entry.get("rem_h"),
        hrv_valid[-1] if hrv_valid else None,
        hrv_baseline,
        _compute_trimp(data["act_rows"], data["hrmax"], target),
        avg_stress,
    )
    if bb_result.get("score") is not None:
        await save_prediction(
            user_id, target, "body_battery_custom", bb_result["score"], bb_result
        )


async def _save_stress_score(
    user_id: int,
    target: date,
    hrv_window: list,
    avg_stress: float | None,
) -> None:
    stress_result = compute_stress_score(hrv_window, avg_stress)
    if stress_result.get("score") is not None:
        await save_prediction(
            user_id,
            target,
            "stress_score_custom",
            stress_result["score"],
            stress_result,
        )


async def _save_running_economy(
    user_id: int,
    target: date,
    data: dict[str, Any],
) -> None:
    run_acts = [
        r
        for r in data["act_rows"]
        if r.get("activity_date") == target
        and r.get("sport_type") in ("running", "trail_running")
        and r.get("avg_ground_contact_time")
    ]
    if not run_acts:
        return
    re_result = compute_running_economy(run_acts)
    if re_result.get("score") is not None:
        await save_prediction(
            user_id, target, "running_economy", re_result["score"], re_result
        )


async def _save_hrv_recovery(
    user_id: int,
    target: date,
    hrv_window: list,
    data: dict[str, Any],
) -> None:
    hrv_rec = compute_hrv_recovery_trajectory(
        hrv_window, data["act_rows"], data["hrmax"], target, lookback=30
    )
    if hrv_rec.get("recovery_speed") is not None:
        await save_prediction(
            user_id, target, "hrv_recovery", hrv_rec["recovery_speed"], hrv_rec
        )


async def _backfill_custom_scores(
    user_id: int, target: date, data: dict[str, Any]
) -> None:
    """Save body_battery_custom, stress_score_custom, running_economy, and hrv_recovery for one date."""
    cutoff_hrv = target - timedelta(days=90)
    hrv_window = [
        data["hrv_by_date"][d]
        for d in data["hrv_dates_sorted"]
        if cutoff_hrv <= d <= target
    ]

    yesterday_bb = None
    if target > data["gap_dates"][0]:
        yesterday_bb = await get_prediction_for_date(
            user_id, target - timedelta(days=1), "body_battery_custom"
        )
    if yesterday_bb is None and target in data["daily_by_date"]:
        yesterday_bb = data["daily_by_date"][target].get("body_battery_high")

    hrv_valid = [v for v in hrv_window if v is not None]
    hrv_baseline = (
        sum(hrv_valid[-30:]) / len(hrv_valid[-30:]) if len(hrv_valid) >= 7 else 0
    )
    avg_stress = data["daily_by_date"].get(target, {}).get("avg_stress")

    await _save_body_battery(
        user_id, target, data, yesterday_bb, hrv_valid, hrv_baseline, avg_stress
    )
    await _save_stress_score(user_id, target, hrv_window, avg_stress)
    await _save_running_economy(user_id, target, data)
    await _save_hrv_recovery(user_id, target, hrv_window, data)


async def backfill_user(user_id: int) -> int:
    """Compute and upsert energy scores for all historical gaps. Returns count of dates written."""
    activity_hrv = await get_backfill_activity_hrv_data(user_id)
    sleep_daily_gaps = await get_backfill_sleep_daily_gaps(user_id)

    gap_dates = sleep_daily_gaps["gap_dates"]
    if not gap_dates:
        return 0

    data = {**activity_hrv, **sleep_daily_gaps}
    logger.info("backfill.started", user_id=user_id, gaps=len(gap_dates))

    for target in gap_dates:
        await _backfill_energy_scores(user_id, target, data)
        await _backfill_custom_scores(user_id, target, data)

    logger.info("backfill.complete", user_id=user_id, dates=len(gap_dates))
    return len(gap_dates)
