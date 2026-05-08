import asyncio
import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import Settings
from db import (
    close_pool,
    get_active_users,
    get_bb_resting_hr_pairs,
    get_body_battery_history,
    get_body_battery_today,
    get_latest_features,
    get_readiness_training_rows,
    get_resting_hr_history,
    get_sleep_hrv_pairs,
    get_sleep_resting_hr_pairs,
    get_today_resting_hr,
    init_pool,
    save_prediction,
)
from models.anomaly import detect_resting_hr_anomaly
from models.battery_pattern import fit_and_save as battery_fit_and_save
from models.battery_pattern import predict_today as battery_predict_today
from models.correlation import compute_sleep_hrv_correlation
from models.readiness import predict_tomorrow, train_and_save

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run_inference(user_id: int, settings: Settings) -> None:
    # Anomaly detection
    history = await get_resting_hr_history(user_id)
    today_hr = await get_today_resting_hr(user_id)
    anomaly = detect_resting_hr_anomaly(history, today_hr)
    await save_prediction(
        user_id, date.today(), "anomaly_hr", anomaly.get("z_score"), anomaly
    )
    logger.info(
        f"user={user_id} anomaly z={anomaly.get('z_score')} is_anomaly={anomaly.get('is_anomaly')}"
    )

    # Sleep → HRV correlation
    pairs = await get_sleep_hrv_pairs(user_id)
    if pairs:
        sleep_scores, hrv_vals = zip(*pairs)
        corr = compute_sleep_hrv_correlation(list(sleep_scores), list(hrv_vals))
        await save_prediction(
            user_id, date.today(), "correlation_sleep_hrv", corr.get("r"), corr
        )
        logger.info(
            f"user={user_id} correlation_sleep_hrv r={corr.get('r')} n={corr.get('n')}"
        )

    # Sleep → Resting HR correlation
    pairs_srhr = await get_sleep_resting_hr_pairs(user_id)
    if pairs_srhr:
        xs, ys = zip(*pairs_srhr)
        corr = compute_sleep_hrv_correlation(list(xs), list(ys))
        await save_prediction(
            user_id, date.today(), "correlation_sleep_rhr", corr.get("r"), corr
        )
        logger.info(
            f"user={user_id} correlation_sleep_rhr r={corr.get('r')} n={corr.get('n')}"
        )

    # Body Battery → Resting HR correlation
    pairs_bbrhr = await get_bb_resting_hr_pairs(user_id)
    if pairs_bbrhr:
        xs, ys = zip(*pairs_bbrhr)
        corr = compute_sleep_hrv_correlation(list(xs), list(ys))
        await save_prediction(
            user_id, date.today(), "correlation_bb_rhr", corr.get("r"), corr
        )
        logger.info(
            f"user={user_id} correlation_bb_rhr r={corr.get('r')} n={corr.get('n')}"
        )

    # Readiness prediction (uses pre-trained model if available)
    model_path = settings.model_dir / f"readiness_rf_{user_id}.joblib"
    features = await get_latest_features(user_id)
    predicted = predict_tomorrow(features, model_path)
    if predicted is not None:
        tomorrow = date.today() + timedelta(days=1)
        await save_prediction(user_id, tomorrow, "readiness_rf", predicted, {})
        logger.info(f"user={user_id} predicted tomorrow readiness={predicted}")

    # Body battery pattern classification
    today_bb = await get_body_battery_today(user_id)
    bp = battery_predict_today(today_bb, str(settings.model_dir), user_id)
    if bp is not None:
        await save_prediction(
            user_id, date.today(), "battery_pattern", float(bp["cluster"]), bp
        )
        logger.info(
            f"user={user_id} battery_pattern={bp['pattern']} cluster={bp['cluster']}"
        )


async def run_training(user_id: int, settings: Settings) -> None:
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

    # Battery pattern k-means training
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


async def run_all_users(settings: Settings, include_training: bool = False) -> None:
    users = await get_active_users()
    if not users:
        logger.info("No active Garmin users found")
        return
    for user in users:
        uid = user["id"]
        try:
            if include_training:
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
