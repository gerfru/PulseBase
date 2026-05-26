import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backfill import backfill_user
from config import Settings
from db import (
    close_pool,
    count_energy_gaps,
    get_active_users,
    get_activity_trimp_inputs,
    get_bb_resting_hr_pairs,
    get_body_battery_history,
    get_body_battery_today,
    get_hrmax,
    get_hrv_history_for_energy,
    get_last_sleep_session,
    get_latest_features,
    get_ml_requested_users,
    get_readiness_training_rows,
    get_resting_hr_history,
    get_running_economy_activities,
    get_sleep_data_7d,
    get_sleep_duration_history,
    get_sleep_hrv_pairs,
    get_sleep_resting_hr_pairs,
    get_sleep_sessions_14d,
    get_spo2_history,
    get_spo2_history_flat,
    get_steps_history,
    get_stress_history,
    get_today_daily_summary,
    get_today_resting_hr,
    get_today_sleep_duration,
    get_today_spo2,
    get_today_steps,
    get_today_stress,
    get_todays_activity_hr_records,
    get_user_profile,
    get_yesterday_prediction,
    init_pool,
    mark_ml_done,
    save_prediction,
)
from models.anomaly import detect_metric_anomaly
from models.battery_pattern import fit_and_save as battery_fit_and_save
from models.battery_pattern import predict_today as battery_predict_today
from models.body_battery import compute_body_battery
from models.correlation import compute_sleep_hrv_correlation
from models.energy_metrics import (
    compute_autonomic_energy,
    compute_cognitive_energy,
    compute_physical_energy,
)
from models.hrv_recovery import compute_hrv_recovery_trajectory
from models.hrv_status import classify_hrv_status
from models.intensity_minutes import compute_intensity_minutes
from models.readiness import predict_tomorrow, train_and_save
from models.running_economy import compute_running_economy
from models.sleep_metrics import compute_sleep_consistency
from models.sleep_score import compute_custom_sleep_score
from models.spo2_metrics import compute_spo2_trend
from models.stress_metrics import compute_stress_score
from models.training_effect import compute_banister_trimp, compute_training_effect_today
from models.training_load import compute_acwr, compute_training_monotony

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


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


async def _run_anomaly(user_id: int, today: date) -> None:
    history = await get_resting_hr_history(user_id)
    today_hr = await get_today_resting_hr(user_id)
    anomaly = detect_metric_anomaly(history, today_hr)
    await save_prediction(user_id, today, "anomaly_hr", anomaly.get("z_score"), anomaly)
    logger.info(
        f"user={user_id} anomaly_hr z={anomaly.get('z_score')} is_anomaly={anomaly.get('is_anomaly')}"
    )


async def _run_anomaly_spo2(user_id: int, today: date) -> None:
    history = await get_spo2_history_flat(user_id)
    today_val = await get_today_spo2(user_id)
    result = detect_metric_anomaly(history, today_val)
    await save_prediction(user_id, today, "anomaly_spo2", result.get("z_score"), result)
    logger.info(
        f"user={user_id} anomaly_spo2 z={result.get('z_score')} is_anomaly={result.get('is_anomaly')}"
    )


async def _run_anomaly_sleep(user_id: int, today: date) -> None:
    history = await get_sleep_duration_history(user_id)
    today_val = await get_today_sleep_duration(user_id)
    result = detect_metric_anomaly(history, today_val)
    await save_prediction(
        user_id, today, "anomaly_sleep_duration", result.get("z_score"), result
    )
    logger.info(
        f"user={user_id} anomaly_sleep z={result.get('z_score')} is_anomaly={result.get('is_anomaly')}"
    )


async def _run_anomaly_steps(user_id: int, today: date) -> None:
    history = await get_steps_history(user_id)
    today_val = await get_today_steps(user_id)
    result = detect_metric_anomaly(history, today_val)
    await save_prediction(
        user_id, today, "anomaly_steps", result.get("z_score"), result
    )
    logger.info(
        f"user={user_id} anomaly_steps z={result.get('z_score')} is_anomaly={result.get('is_anomaly')}"
    )


async def _run_anomaly_stress(user_id: int, today: date) -> None:
    history = await get_stress_history(user_id)
    today_val = await get_today_stress(user_id)
    result = detect_metric_anomaly(history, today_val)
    await save_prediction(
        user_id, today, "anomaly_stress", result.get("z_score"), result
    )
    logger.info(
        f"user={user_id} anomaly_stress z={result.get('z_score')} is_anomaly={result.get('is_anomaly')}"
    )


async def _run_correlations(user_id: int, today: date) -> None:
    correlation_tasks = [
        (get_sleep_hrv_pairs(user_id), "correlation_sleep_hrv"),
        (get_sleep_resting_hr_pairs(user_id), "correlation_sleep_rhr"),
        (get_bb_resting_hr_pairs(user_id), "correlation_bb_rhr"),
    ]
    for coro, model_key in correlation_tasks:
        pairs = await coro
        if not pairs:
            continue
        xs, ys = zip(*pairs)
        corr = compute_sleep_hrv_correlation(list(xs), list(ys))
        await save_prediction(user_id, today, model_key, corr.get("r"), corr)
        logger.info(f"user={user_id} {model_key} r={corr.get('r')} n={corr.get('n')}")


async def _run_readiness(user_id: int, today: date, settings: Settings) -> None:
    model_path = settings.model_dir / f"readiness_rf_{user_id}.joblib"
    features = await get_latest_features(user_id)
    predicted = predict_tomorrow(features, model_path)
    if predicted is None:
        return
    pred_meta = {
        "confidence_low": predicted["confidence_low"],
        "confidence_high": predicted["confidence_high"],
    }
    await save_prediction(user_id, today, "readiness_rf", predicted["score"], pred_meta)
    await save_prediction(
        user_id,
        today + timedelta(days=1),
        "readiness_rf",
        predicted["score"],
        pred_meta,
    )
    logger.info(
        f"user={user_id} predicted tomorrow readiness={predicted['score']} "
        f"CI=[{predicted['confidence_low']}, {predicted['confidence_high']}]"
    )


async def _run_battery_pattern(user_id: int, today: date, settings: Settings) -> None:
    today_bb = await get_body_battery_today(user_id)
    bp = battery_predict_today(today_bb, str(settings.model_dir), user_id)
    if bp is None:
        return
    await save_prediction(user_id, today, "battery_pattern", float(bp["cluster"]), bp)
    logger.info(
        f"user={user_id} battery_pattern={bp['pattern']} cluster={bp['cluster']}"
    )


async def _run_energy_metrics(
    user_id: int,
    today: date,
    act_rows: list[dict[str, Any]],
    hrmax: float,
    hrv_hist: list,
    sleep_h: list,
) -> None:
    phys = compute_physical_energy(act_rows, hrmax, today)
    await save_prediction(user_id, today, "energy_physical", phys.get("score"), phys)
    logger.info(
        f"user={user_id} energy_physical score={phys.get('score')} tsb={phys.get('tsb')}"
    )

    if phys.get("atl") is not None and phys.get("ctl") is not None:
        acwr_result = compute_acwr(phys["atl"], phys["ctl"])
        await save_prediction(
            user_id, today, "acwr", acwr_result.get("acwr"), acwr_result
        )
        logger.info(
            f"user={user_id} acwr={acwr_result.get('acwr')} level={acwr_result.get('level')}"
        )

    mono_result = compute_training_monotony(act_rows, hrmax, today)
    if mono_result.get("monotony") is not None:
        await save_prediction(
            user_id,
            today,
            "training_monotony",
            mono_result.get("monotony"),
            mono_result,
        )
        logger.info(
            f"user={user_id} training_monotony={mono_result.get('monotony')} strain={mono_result.get('strain')}"
        )

    auton = compute_autonomic_energy(hrv_hist)
    await save_prediction(user_id, today, "energy_autonomic", auton.get("score"), auton)
    logger.info(
        f"user={user_id} energy_autonomic score={auton.get('score')} dev={auton.get('deviation')}"
    )

    cog = compute_cognitive_energy(sleep_h)
    await save_prediction(user_id, today, "energy_cognitive", cog.get("score"), cog)
    logger.info(
        f"user={user_id} energy_cognitive score={cog.get('score')} debt={cog.get('debt_hours')}"
    )


async def _run_training_effect(
    user_id: int,
    today: date,
    act_rows: list[dict[str, Any]],
    hrmax: float,
    resting_hr_today: float | None,
) -> None:
    profile = await get_user_profile(user_id)
    if not profile.get("has_profile"):
        return
    btr = compute_banister_trimp(act_rows, profile["sex"], hrmax)
    rhr_for_vo2 = resting_hr_today or 60.0
    te = compute_training_effect_today(
        btr["trimp_today"], btr["ctl"], rhr_for_vo2, hrmax
    )
    await save_prediction(
        user_id, today, "training_effect_custom", te.get("score"), {**btr, **te}
    )
    logger.info(
        f"user={user_id} training_effect_custom effect={te.get('effect')} trimp={btr.get('trimp_today')}"
    )


async def _run_sleep_and_spo2(user_id: int, today: date) -> None:
    spo2_rows = await get_spo2_history(user_id, days=7)
    spo2_result = compute_spo2_trend(spo2_rows)
    if spo2_result.get("mean_spo2") is not None:
        await save_prediction(
            user_id, today, "spo2_trend", spo2_result.get("mean_spo2"), spo2_result
        )
        logger.info(
            f"user={user_id} spo2_trend mean={spo2_result.get('mean_spo2')} trend={spo2_result.get('trend')} apnea={spo2_result.get('apnea_flag')}"
        )

    sess_rows = await get_sleep_sessions_14d(user_id)
    cons_result = compute_sleep_consistency(sess_rows)
    if cons_result.get("score") is not None:
        await save_prediction(
            user_id, today, "sleep_consistency", cons_result.get("score"), cons_result
        )
        logger.info(
            f"user={user_id} sleep_consistency score={cons_result.get('score')} std_wake={cons_result.get('std_wake_h')}"
        )

    sleep_row = await get_last_sleep_session(user_id)
    if sleep_row:
        ss = compute_custom_sleep_score(sleep_row)
        await save_prediction(user_id, today, "sleep_score_custom", ss.get("score"), ss)
        logger.info(
            f"user={user_id} sleep_score_custom score={ss.get('score')} total_h={ss.get('total_h')}"
        )


async def _run_hrv_and_recovery(
    user_id: int,
    today: date,
    hrv_hist: list,
    act_rows: list[dict[str, Any]],
    hrmax: float,
) -> None:
    hrv_rec_result = compute_hrv_recovery_trajectory(hrv_hist, act_rows, hrmax, today)
    if hrv_rec_result.get("recovery_speed") is not None:
        await save_prediction(
            user_id,
            today,
            "hrv_recovery",
            hrv_rec_result["recovery_speed"],
            hrv_rec_result,
        )
        logger.info(
            f"user={user_id} hrv_recovery speed={hrv_rec_result['recovery_speed']} n={hrv_rec_result['n_events']}"
        )

    hrv_status = classify_hrv_status(hrv_hist)
    if hrv_status.get("status") is not None:
        await save_prediction(
            user_id, today, "hrv_status_custom", hrv_status.get("score"), hrv_status
        )
        logger.info(
            f"user={user_id} hrv_status_custom status={hrv_status.get('status')} dev={hrv_status.get('deviation')}"
        )


async def _run_body_battery_and_stress(
    user_id: int,
    today: date,
    act_rows: list[dict[str, Any]],
    hrmax: float,
    hrv_hist: list,
    sleep_h: list,
    daily_today: dict | None,
) -> None:
    yesterday_bb = await get_yesterday_prediction(user_id, "body_battery_custom")
    if yesterday_bb is None and daily_today:
        yesterday_bb = daily_today.get("body_battery_high")
    last_night = sleep_h[-1] if sleep_h else {}
    last_night_h = last_night.get("total_h") or 0.0
    last_night_deep = last_night.get("deep_h")
    last_night_rem = last_night.get("rem_h")
    hrv_valid = [v for v in hrv_hist if v is not None]
    hrv_baseline = (
        sum(hrv_valid[-30:]) / len(hrv_valid[-30:]) if len(hrv_valid) >= 7 else 0
    )
    hrv_last = hrv_valid[-1] if hrv_valid else None

    bb_result = compute_body_battery(
        yesterday_bb,
        last_night_h,
        last_night_deep,
        last_night_rem,
        hrv_last,
        hrv_baseline,
        _compute_trimp(act_rows, hrmax, today),
        daily_today.get("avg_stress") if daily_today else None,
    )
    if bb_result.get("score") is not None:
        await save_prediction(
            user_id, today, "body_battery_custom", bb_result["score"], bb_result
        )
        logger.info(
            f"user={user_id} body_battery_custom score={bb_result['score']} "
            f"sleep_q={bb_result.get('sleep_quality')} hrv_f={bb_result.get('hrv_factor')}"
        )

    stress_result = compute_stress_score(
        hrv_hist, daily_today.get("avg_stress") if daily_today else None
    )
    if stress_result.get("score") is not None:
        await save_prediction(
            user_id, today, "stress_score_custom", stress_result["score"], stress_result
        )
        logger.info(
            f"user={user_id} stress_score_custom score={stress_result['score']} dev={stress_result.get('hrv_deviation')}"
        )


async def _run_running_and_intensity(
    user_id: int,
    today: date,
    hrmax: float,
    hr_records: list,
    resting_hr_today: float | None,
) -> None:
    run_rows = await get_running_economy_activities(user_id)
    re_result = compute_running_economy(run_rows)
    if re_result.get("score") is not None:
        await save_prediction(
            user_id, today, "running_economy", re_result["score"], re_result
        )
        logger.info(
            f"user={user_id} running_economy score={re_result['score']} gct={re_result.get('avg_gct_ms')}"
        )

    if hr_records and resting_hr_today is not None:
        im = compute_intensity_minutes(hr_records, resting_hr_today, hrmax)
        await save_prediction(
            user_id, today, "intensity_minutes_custom", im.get("score"), im
        )
        logger.info(
            f"user={user_id} intensity_minutes_custom mod={im.get('moderate_minutes')} vig={im.get('vigorous_minutes')}"
        )


async def run_inference(user_id: int, settings: Settings) -> None:
    """Orchestrate all ML inference models for one user. All results written to ml_predictions."""
    today = date.today()
    act_rows = await get_activity_trimp_inputs(user_id)
    hrmax = await get_hrmax(user_id)
    hrv_hist = await get_hrv_history_for_energy(user_id)
    sleep_h = await get_sleep_data_7d(user_id)
    daily_today = await get_today_daily_summary(user_id)
    hr_records, resting_hr_today = await get_todays_activity_hr_records(user_id)

    await _run_anomaly(user_id, today)
    await _run_anomaly_spo2(user_id, today)
    await _run_anomaly_sleep(user_id, today)
    await _run_anomaly_steps(user_id, today)
    await _run_anomaly_stress(user_id, today)
    await _run_correlations(user_id, today)
    await _run_readiness(user_id, today, settings)
    await _run_battery_pattern(user_id, today, settings)
    await _run_energy_metrics(user_id, today, act_rows, hrmax, hrv_hist, sleep_h)
    await _run_training_effect(user_id, today, act_rows, hrmax, resting_hr_today)
    await _run_sleep_and_spo2(user_id, today)
    await _run_hrv_and_recovery(user_id, today, hrv_hist, act_rows, hrmax)
    await _run_body_battery_and_stress(
        user_id, today, act_rows, hrmax, hrv_hist, sleep_h, daily_today
    )
    await _run_running_and_intensity(
        user_id, today, hrmax, hr_records, resting_hr_today
    )


async def run_training(user_id: int, settings: Settings) -> None:
    """Train RF readiness model first, then k-means battery pattern.

    RF is trained before k-means so that inference (run immediately after on-request)
    can already use the fresh model. Both return None silently when minimum data
    thresholds are not met (RF: 30 rows, k-means: 14 days) — not an error condition.
    """
    model_path = settings.model_dir / f"readiness_rf_{user_id}.joblib"
    rows = await get_readiness_training_rows(user_id)
    meta = train_and_save(rows, model_path)
    if meta:
        await save_prediction(
            user_id, date.today(), "model_meta_rf", float(meta["n_rows"]), meta
        )
        logger.info(
            f"user={user_id} RF model trained on {meta['n_rows']} rows → {model_path}, "
            f"importances={meta['importances']}"
        )
    else:
        logger.info(
            f"user={user_id} insufficient data for RF training ({len(rows)} rows)"
        )

    history = await get_body_battery_history(user_id)
    bp_trained = battery_fit_and_save(history, str(settings.model_dir), user_id)
    if bp_trained:
        logger.info(
            f"user={user_id} battery_pattern k-means trained on {len(history)} days"
        )
    else:
        logger.info(
            f"user={user_id} insufficient data for battery_pattern training ({len(history)} days)"
        )


async def run_on_request(settings: Settings) -> None:
    """Handle manual ML runs triggered by the sync-service after a Garmin sync.

    Checks `ml_requested = true` in users table (set by sync-service). Backfills
    energy history gaps (up to 30 days) before training so the first inference after
    a fresh account link has a complete baseline. mark_ml_done resets the flag and
    records last_ml_at regardless of success or failure.
    """
    users = await get_ml_requested_users()
    for user in users:
        uid = user["id"]
        try:
            gaps = await count_energy_gaps(uid)
            if gaps > 0:
                logger.info(f"user={uid}: {gaps} energy history gaps — backfilling")
                await backfill_user(uid)
            await run_training(uid, settings)
            await run_inference(uid, settings)
            logger.info(f"On-request ML completed for user={uid}")
        except Exception as e:
            logger.error(f"On-request ML failed for user={uid}: {e}", exc_info=True)
        finally:
            await mark_ml_done(uid)


async def run_all_users(settings: Settings, include_training: bool = False) -> None:
    users = await get_active_users()
    if not users:
        logger.info("No active Garmin users found")
        return
    for user in users:
        uid = user["id"]
        try:
            if include_training:
                gaps = await count_energy_gaps(uid)
                if gaps > 0:
                    logger.info(f"user={uid}: {gaps} energy history gaps — backfilling")
                    await backfill_user(uid)
                await run_training(uid, settings)
            await run_inference(uid, settings)
        except Exception as e:
            logger.error(f"ML run failed for user={uid}: {e}", exc_info=True)


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    await init_pool(settings.db_url)

    logger.info("Running initial ML inference + training")
    await run_all_users(settings, include_training=True)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_all_users,
        CronTrigger(hour=settings.ml_infer_hour, minute=0),
        args=[settings, False],
        id="daily_inference",
    )
    scheduler.add_job(
        run_all_users,
        CronTrigger(day_of_week=settings.ml_train_weekday, hour=3, minute=0),
        args=[settings, True],
        id="weekly_training",
    )
    scheduler.add_job(
        run_on_request,
        "interval",
        minutes=2,
        args=[settings],
        id="on_request",
    )
    scheduler.start()
    logger.info(
        f"Scheduler active — inference daily at {settings.ml_infer_hour}:00, "
        f"training weekly Sunday 03:00"
    )

    try:
        await asyncio.Event().wait()
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
