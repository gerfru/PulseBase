import asyncio
import signal
import uuid
from datetime import date
from pathlib import Path

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backfill import backfill_user
from config import Settings
from db import (
    close_pool,
    get_pool,
    count_energy_gaps,
    get_active_users,
    get_activity_trimp_inputs,
    get_body_battery_history,
    get_hrmax,
    get_hrv_history_for_energy,
    get_ml_requested_users,
    get_readiness_training_rows,
    get_sleep_data_7d,
    get_today_daily_summary,
    get_todays_activity_hr_records,
    init_pool,
    mark_ml_done,
    save_prediction,
)
from inference_anomaly import (
    _run_anomaly,
    _run_anomaly_sleep,
    _run_anomaly_spo2,
    _run_anomaly_steps,
    _run_anomaly_stress,
    _run_correlations,
)
from inference_energy import _run_energy_metrics
from inference_models import (
    _run_battery_pattern,
    _run_body_battery_and_stress,
    _run_hrv_and_recovery,
    _run_readiness,
    _run_running_and_intensity,
    _run_sleep_and_spo2,
    _run_training_effect,
)
from health_server import start_health_server
from logging_config import configure_logging, configure_sentry
from models.battery_pattern import fit_and_save as battery_fit_and_save
from models.readiness import train_and_save

configure_logging()
logger = structlog.get_logger(__name__)


async def run_inference(user_id: int, settings: Settings) -> None:
    """Orchestrate all ML inference models for one user. All results written to ml_predictions."""
    bind_contextvars(job_id=str(uuid.uuid4())[:8])
    try:
        today = date.today()
        act_rows = await get_activity_trimp_inputs(user_id)
        hrmax = await get_hrmax(user_id)
        hrv_hist = await get_hrv_history_for_energy(user_id)
        sleep_h = await get_sleep_data_7d(user_id)
        daily_today = await get_today_daily_summary(user_id)
        hr_records, resting_hr_today = await get_todays_activity_hr_records(user_id)

        await asyncio.gather(
            _run_anomaly(user_id, today),
            _run_anomaly_spo2(user_id, today),
            _run_anomaly_sleep(user_id, today),
            _run_anomaly_steps(user_id, today),
            _run_anomaly_stress(user_id, today),
            _run_correlations(user_id, today),
        )
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
    finally:
        clear_contextvars()


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
            "rf_model.trained",
            user_id=user_id,
            n_rows=meta["n_rows"],
            model_path=str(model_path),
            importances=meta["importances"],
        )
    else:
        logger.info("rf_model.insufficient_data", user_id=user_id, rows=len(rows))

    history = await get_body_battery_history(user_id)
    bp_trained = battery_fit_and_save(history, str(settings.model_dir), user_id)
    if bp_trained:
        logger.info("battery_pattern.trained", user_id=user_id, days=len(history))
    else:
        logger.info(
            "battery_pattern.insufficient_data", user_id=user_id, days=len(history)
        )


async def _backfill_and_train(uid: int, settings: Settings) -> None:
    gaps = await count_energy_gaps(uid)
    if gaps > 0:
        logger.info("backfill.needed", user_id=uid, gaps=gaps)
        await backfill_user(uid)
    await run_training(uid, settings)


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
            await _backfill_and_train(uid, settings)
            await run_inference(uid, settings)
            logger.info("ml_request.done", user_id=uid)
        except Exception as e:
            logger.error("ml_request.failed", user_id=uid, error=str(e), exc_info=True)
        finally:
            await mark_ml_done(uid)


async def run_all_users(settings: Settings, include_training: bool = False) -> None:
    users = await get_active_users()
    if not users:
        logger.info("ml.no_users")
        return
    for user in users:
        uid = user["id"]
        try:
            if include_training:
                await _backfill_and_train(uid, settings)
            await run_inference(uid, settings)
        except Exception as e:
            logger.error("ml.failed", user_id=uid, error=str(e), exc_info=True)


async def _write_alive_sentinel() -> None:
    Path("/tmp/ml_alive").touch()  # nosec B108


def _configure_ml_scheduler(settings: Settings) -> AsyncIOScheduler:
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
    scheduler.add_job(_write_alive_sentinel, "interval", minutes=1, id="healthcheck")
    scheduler.start()
    logger.info("scheduler.started", infer_hour=settings.ml_infer_hour)
    return scheduler


async def main() -> None:  # pragma: no cover
    settings = Settings()  # type: ignore[call-arg]
    await init_pool(settings.db_url)

    configure_sentry(settings)

    shutdown_event = asyncio.Event()

    def _on_sigterm() -> None:
        logger.info("shutdown.sigterm_received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, _on_sigterm)

    await start_health_server(pool=await get_pool())

    logger.info("ml.initial_run")
    initial_task = asyncio.create_task(run_all_users(settings, include_training=True))
    shutdown_task = asyncio.create_task(shutdown_event.wait())
    await asyncio.wait(
        {initial_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED
    )
    shutdown_task.cancel()
    if not initial_task.done():
        initial_task.cancel()
        try:
            await initial_task
        except asyncio.CancelledError:
            logger.info("ml.initial_run_cancelled")

    scheduler = _configure_ml_scheduler(settings)

    try:
        await shutdown_event.wait()
    finally:
        logger.info("shutdown.graceful_start")
        scheduler.shutdown(wait=True)
        await close_pool()
        logger.info("shutdown.complete")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
