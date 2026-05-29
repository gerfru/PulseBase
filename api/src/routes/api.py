import asyncio
from datetime import date, datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from src.evidence_catalog import EVIDENCE

from src.db import (
    get_activity_detail,
    get_daily_summaries,
    get_energy_metrics,
    get_glucose_recent,
    get_glucose_stats,
    get_hrv_trend,
    get_latest_hrv,
    get_latest_training_status,
    get_ml_history,
    get_ml_insights,
    get_ml_status,
    get_readiness,
    get_recent_activities,
    get_seizure_risk,
    get_seizures,
    get_sleep_sessions,
    get_sync_status,
    get_training_load_inputs,
    get_activity_hrmax,
    get_user_sex,
    get_weekly_stats,
    request_sync,
    save_seizure,
    set_activity_rpe,
    update_epilepsy_mode,
    update_spo2_enabled,
    update_user_profile,
)
import src.deps as _deps
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
async def api_hrv(request: Request) -> dict | list:
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


@router.get("/api/training-status")
async def api_training_status(request: Request) -> dict:
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
    return await get_readiness(user["id"])


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


# ── ML ────────────────────────────────────────────────────────────────────────


@router.get("/api/ml-insights")
async def api_ml_insights(request: Request) -> dict:
    user = await _deps.require_user(request)
    return await get_ml_insights(user["id"])


@router.get("/api/ml-history")
async def api_ml_history(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    end_date: date | None = Query(default=None),
) -> list:
    user = await _deps.require_user(request)
    return await get_ml_history(user["id"], days, end_date=end_date)


@router.get("/api/ml-status")
async def api_ml_status(request: Request) -> dict:
    user = await _deps.require_user(request)
    return await get_ml_status(user["id"])


# ── Sync ──────────────────────────────────────────────────────────────────────


@router.post("/api/sync", response_model=None)
async def api_sync(request: Request) -> dict | JSONResponse:
    user = await _deps.require_user(request)
    if not user.get("garmin_linked"):
        return JSONResponse(
            status_code=400,
            content={
                "error": {"code": "NOT_LINKED", "message": "Garmin account not linked"}
            },
        )
    await request_sync(user["id"])
    return {"status": "requested"}


@router.get("/api/sync-status")
async def api_sync_status(request: Request) -> dict:
    user = await _deps.require_user(request)
    return await get_sync_status(user["id"])


# ── Profile ───────────────────────────────────────────────────────────────────


class ProfileBody(BaseModel):
    date_of_birth: date | None = None
    sex: str | None = None
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


@router.patch("/api/profile")
async def api_update_profile(request: Request, body: ProfileBody) -> dict:
    user = await _deps.require_user(request)
    fields = body.model_fields_set
    if "epilepsy_mode" in fields and body.epilepsy_mode is not None:
        await update_epilepsy_mode(user["id"], body.epilepsy_mode)
    if "spo2_enabled" in fields and body.spo2_enabled is not None:
        await update_spo2_enabled(user["id"], body.spo2_enabled)
    if "date_of_birth" in fields or "sex" in fields:
        await update_user_profile(user["id"], body.date_of_birth, body.sex)
    return {"ok": True}


# ── Seizures ──────────────────────────────────────────────────────────────────


class SeizureBody(BaseModel):
    occurred_at: datetime
    duration_seconds: int | None = None
    type: str = "unknown"
    severity: int | None = None
    notes: str | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("focal", "generalized", "unknown"):
            raise ValueError("type must be focal, generalized, or unknown")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 5):
            raise ValueError("severity must be 1–5")
        return v


@router.post("/api/seizures")
async def api_log_seizure(request: Request, body: SeizureBody) -> dict:
    user = await _deps.require_user(request)
    id_ = await save_seizure(
        user["id"],
        body.occurred_at,
        body.duration_seconds,
        body.type,
        body.severity,
        body.notes,
    )
    return {"ok": True, "id": id_}


@router.get("/api/seizures")
async def api_get_seizures(
    request: Request,
    days: int = Query(default=365, ge=1, le=365),
) -> list:
    user = await _deps.require_user(request)
    return await get_seizures(user["id"], days)


@router.get("/api/seizures/risk")
async def api_seizure_risk(request: Request) -> dict:
    user = await _deps.require_user(request)
    return await get_seizure_risk(user["id"])


# ── Glucose ───────────────────────────────────────────────────────────────────


@router.get("/api/glucose")
async def api_glucose(
    request: Request, hours: int = Query(default=24, ge=1, le=168)
) -> list:
    user = await _deps.require_user(request)
    return await get_glucose_recent(user["id"], hours)


@router.get("/api/glucose/stats")
async def api_glucose_stats(
    request: Request, days: int = Query(default=14, ge=1, le=90)
) -> dict:
    user = await _deps.require_user(request)
    return await get_glucose_stats(user["id"], days)


# ── Evidence Catalog ──────────────────────────────────────────────────────────


@router.get("/api/evidence")
async def api_evidence() -> dict:
    return EVIDENCE
