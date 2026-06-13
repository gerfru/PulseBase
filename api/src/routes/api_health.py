"""Activities, health metrics, training-load, sync status, profile, evidence.

Part of the /api/* surface — split out of the former monolithic api.py
(ARCH-L5 400-line trigger). Registered via src.routes.api aggregator.
"""

import asyncio
from datetime import date

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

import src.deps as _deps
from src.db import (
    get_activity_detail,
    get_activity_hrmax,
    get_daily_summaries,
    get_energy_metrics,
    get_hrv_trend,
    get_latest_hrv,
    get_latest_training_status,
    get_recent_activities,
    get_sleep_sessions,
    get_sync_status,
    get_training_load_inputs,
    get_user_sex,
    get_weekly_stats,
    set_activity_rpe,
    update_epilepsy_mode,
    update_spo2_enabled,
    update_user_profile,
)
from src.evidence_catalog import EVIDENCE
from src.readiness import compute_readiness
from src.training_load import build_training_load

router = APIRouter()


# ── Activities ────────────────────────────────────────────────────────────────


@router.get("/api/activities")
async def api_activities(
    request: Request,
    days: int = Query(default=7, ge=1, le=365),
    limit: int = Query(default=500, ge=1, le=500),
    end_date: date | None = Query(default=None),
) -> list:
    user = await _deps.require_user(request)
    return await get_recent_activities(
        user["id"], limit=limit, days=days, end_date=end_date
    )


@router.get("/api/activities/{activity_id}", response_model=None)
async def api_activity_detail(
    request: Request, activity_id: int
) -> dict | JSONResponse:
    user = await _deps.require_user(request)
    detail = await get_activity_detail(user["id"], activity_id)
    if not detail:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "Activity not found"}},
        )
    return detail


class RpeBody(BaseModel):
    rpe: int

    @field_validator("rpe")
    @classmethod
    def validate_rpe(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("RPE must be between 1 and 10")
        return v


@router.patch("/api/activities/{activity_id}/rpe", response_model=None)
async def api_set_rpe(
    request: Request, activity_id: int, body: RpeBody
) -> dict | JSONResponse:
    user = await _deps.require_user(request)
    updated = await set_activity_rpe(user["id"], activity_id, body.rpe)
    if not updated:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "Activity not found"}},
        )
    return {"ok": True, "rpe": body.rpe}


# ── Health metrics ────────────────────────────────────────────────────────────


@router.get("/api/daily")
async def api_daily(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    end_date: date | None = Query(default=None),
) -> list:
    user = await _deps.require_user(request)
    return await get_daily_summaries(user["id"], days=days, end_date=end_date)


@router.get("/api/sleep")
async def api_sleep(
    request: Request,
    days: int = Query(default=14, ge=1, le=365),
    end_date: date | None = Query(default=None),
) -> list:
    user = await _deps.require_user(request)
    return await get_sleep_sessions(user["id"], days=days, end_date=end_date)


@router.get("/api/hrv", response_model=None)
async def api_hrv(request: Request) -> dict | None:
    user = await _deps.require_user(request)
    return await get_latest_hrv(user["id"])


@router.get("/api/hrv/trend")
async def api_hrv_trend(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    end_date: date | None = Query(default=None),
) -> list:
    user = await _deps.require_user(request)
    return await get_hrv_trend(user["id"], days=days, end_date=end_date)


@router.get("/api/training-status", response_model=None)
async def api_training_status(request: Request) -> dict | None:
    user = await _deps.require_user(request)
    return await get_latest_training_status(user["id"])


@router.get("/api/weekly")
async def api_weekly(
    request: Request,
    weeks: int = Query(default=12, ge=1, le=56),
    end_date: date | None = Query(default=None),
) -> list:
    user = await _deps.require_user(request)
    return await get_weekly_stats(user["id"], weeks=weeks, end_date=end_date)


@router.get("/api/readiness")
async def api_readiness(request: Request) -> dict:
    user = await _deps.require_user(request)
    return await compute_readiness(user["id"])


@router.get("/api/energy")
async def api_energy(request: Request) -> dict:
    user = await _deps.require_user(request)
    return await get_energy_metrics(user["id"])


@router.get("/api/training-load")
async def api_training_load(
    request: Request,
    lookback_days: int = Query(default=None, ge=1, le=365),
) -> dict:
    user = await _deps.require_user(request)
    rows, hrmax, sex = await asyncio.gather(
        get_training_load_inputs(user["id"]),
        get_activity_hrmax(user["id"]),
        get_user_sex(user["id"]),
    )
    return build_training_load(
        rows,
        hrmax,
        sex,
        lookback_days
        if lookback_days is not None
        else _deps.settings.trimp_lookback_days,
        _deps.settings.trimp_forecast_days,
    )


# ── Sync ──────────────────────────────────────────────────────────────────────


@router.get("/api/sync-status")
async def api_sync_status(request: Request) -> dict:
    user = await _deps.require_user(request)
    return await get_sync_status(user["id"])


# ── Profile ───────────────────────────────────────────────────────────────────


class ProfileBody(BaseModel):
    date_of_birth: date | None = None
    sex: str | None = None
    weight_kg: float | None = None
    epilepsy_mode: bool | None = None
    spo2_enabled: bool | None = None

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v: str | None) -> str | None:
        if v is not None and v not in ("m", "f", "diverse"):
            raise ValueError("sex must be 'm', 'f', or 'diverse'")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date | None) -> date | None:
        if v is not None and v >= date.today():
            raise ValueError("date_of_birth must be in the past")
        return v

    @field_validator("weight_kg")
    @classmethod
    def validate_weight(cls, v: float | None) -> float | None:
        if v is not None and not (30 <= v <= 300):
            raise ValueError("weight_kg must be between 30 and 300")
        return v


@router.patch("/api/profile")
async def api_update_profile(request: Request, body: ProfileBody) -> dict:
    user = await _deps.require_user(request)
    fields = body.model_fields_set
    if "epilepsy_mode" in fields and body.epilepsy_mode is not None:
        await update_epilepsy_mode(user["id"], body.epilepsy_mode)
    if "spo2_enabled" in fields and body.spo2_enabled is not None:
        await update_spo2_enabled(user["id"], body.spo2_enabled)
    if "date_of_birth" in fields or "sex" in fields or "weight_kg" in fields:
        await update_user_profile(
            user["id"], body.date_of_birth, body.sex, body.weight_kg
        )
    return {"ok": True}


# ── Evidence Catalog ──────────────────────────────────────────────────────────


@router.get("/api/evidence")
async def api_evidence(request: Request) -> dict:
    await _deps.require_user(request)
    return EVIDENCE
