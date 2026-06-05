from datetime import date
from typing import Any

import structlog

from db import save_prediction
from models.energy_metrics import (
    compute_autonomic_energy,
    compute_cognitive_energy,
    compute_physical_energy,
)
from models.training_load import compute_acwr, compute_training_monotony

logger = structlog.get_logger(__name__)


async def _run_physical_energy(
    user_id: int,
    today: date,
    act_rows: list[dict[str, Any]],
    hrmax: float,
) -> dict[str, Any]:
    phys = compute_physical_energy(act_rows, hrmax, today)
    await save_prediction(user_id, today, "energy_physical", phys.get("score"), phys)
    logger.info(
        "energy_physical.done",
        user_id=user_id,
        score=phys.get("score"),
        tsb=phys.get("tsb"),
    )
    return phys


async def _run_acwr(user_id: int, today: date, phys: dict[str, Any]) -> None:
    if phys.get("atl") is not None and phys.get("ctl") is not None:
        acwr_result = compute_acwr(phys["atl"], phys["ctl"])
        await save_prediction(
            user_id, today, "acwr", acwr_result.get("acwr"), acwr_result
        )
        logger.info(
            "acwr.done",
            user_id=user_id,
            acwr=acwr_result.get("acwr"),
            level=acwr_result.get("level"),
        )


async def _run_training_monotony(
    user_id: int,
    today: date,
    act_rows: list[dict[str, Any]],
    hrmax: float,
) -> None:
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
            "training_monotony.done",
            user_id=user_id,
            monotony=mono_result.get("monotony"),
            strain=mono_result.get("strain"),
        )


async def _run_autonomic_energy(user_id: int, today: date, hrv_hist: list) -> None:
    auton = compute_autonomic_energy(hrv_hist)
    await save_prediction(user_id, today, "energy_autonomic", auton.get("score"), auton)
    logger.info(
        "energy_autonomic.done",
        user_id=user_id,
        score=auton.get("score"),
        dev=auton.get("deviation"),
    )


async def _run_cognitive_energy(user_id: int, today: date, sleep_h: list) -> None:
    cog = compute_cognitive_energy(sleep_h)
    await save_prediction(user_id, today, "energy_cognitive", cog.get("score"), cog)
    logger.info(
        "energy_cognitive.done",
        user_id=user_id,
        score=cog.get("score"),
        debt_hours=cog.get("debt_hours"),
    )


async def _run_energy_metrics(
    user_id: int,
    today: date,
    act_rows: list[dict[str, Any]],
    hrmax: float,
    hrv_hist: list,
    sleep_h: list,
) -> None:
    phys = await _run_physical_energy(user_id, today, act_rows, hrmax)
    await _run_acwr(user_id, today, phys)
    await _run_training_monotony(user_id, today, act_rows, hrmax)
    await _run_autonomic_energy(user_id, today, hrv_hist)
    await _run_cognitive_energy(user_id, today, sleep_h)
