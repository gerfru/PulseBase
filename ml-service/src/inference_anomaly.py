import asyncio
from collections.abc import Callable
from datetime import date

import structlog

from db import (
    get_bb_resting_hr_pairs,
    get_resting_hr_history,
    get_sleep_duration_history,
    get_sleep_hrv_pairs,
    get_sleep_resting_hr_pairs,
    get_spo2_history_flat,
    get_steps_history,
    get_stress_history,
    get_today_resting_hr,
    get_today_sleep_duration,
    get_today_spo2,
    get_today_steps,
    get_today_stress,
)
from models.anomaly import detect_metric_anomaly
from models.correlation import compute_sleep_hrv_correlation
from repositories.predictions import PredictionRepository

logger = structlog.get_logger(__name__)
prediction_repository = PredictionRepository()


async def _run_anomaly_for(
    user_id: int,
    today: date,
    history_fn: Callable,
    today_fn: Callable,
    model_key: str,
    log_key: str,
) -> None:
    history = await history_fn(user_id)
    today_val = await today_fn(user_id)
    result = detect_metric_anomaly(history, today_val)
    await prediction_repository.save(
        user_id, today, model_key, result.get("z_score"), result
    )
    logger.info(
        "anomaly.done",
        metric=log_key,
        user_id=user_id,
        z=result.get("z_score"),
        is_anomaly=result.get("is_anomaly"),
    )


async def _run_anomaly(user_id: int, today: date) -> None:
    await _run_anomaly_for(
        user_id,
        today,
        get_resting_hr_history,
        get_today_resting_hr,
        "anomaly_hr",
        "anomaly_hr",
    )


async def _run_anomaly_spo2(user_id: int, today: date) -> None:
    await _run_anomaly_for(
        user_id,
        today,
        get_spo2_history_flat,
        get_today_spo2,
        "anomaly_spo2",
        "anomaly_spo2",
    )


async def _run_anomaly_sleep(user_id: int, today: date) -> None:
    await _run_anomaly_for(
        user_id,
        today,
        get_sleep_duration_history,
        get_today_sleep_duration,
        "anomaly_sleep_duration",
        "anomaly_sleep",
    )


async def _run_anomaly_steps(user_id: int, today: date) -> None:
    await _run_anomaly_for(
        user_id,
        today,
        get_steps_history,
        get_today_steps,
        "anomaly_steps",
        "anomaly_steps",
    )


async def _run_anomaly_stress(user_id: int, today: date) -> None:
    await _run_anomaly_for(
        user_id,
        today,
        get_stress_history,
        get_today_stress,
        "anomaly_stress",
        "anomaly_stress",
    )


async def _run_correlations(user_id: int, today: date) -> None:
    keys = ["correlation_sleep_hrv", "correlation_sleep_rhr", "correlation_bb_rhr"]
    results = await asyncio.gather(
        get_sleep_hrv_pairs(user_id),
        get_sleep_resting_hr_pairs(user_id),
        get_bb_resting_hr_pairs(user_id),
    )
    for pairs, model_key in zip(results, keys):
        if len(pairs) < 2:
            continue
        xs, ys = zip(*pairs)
        corr = compute_sleep_hrv_correlation(list(xs), list(ys))
        await prediction_repository.save(user_id, today, model_key, corr.get("r"), corr)
        logger.info(
            "correlation.done",
            user_id=user_id,
            model=model_key,
            r=corr.get("r"),
            n=corr.get("n"),
        )
