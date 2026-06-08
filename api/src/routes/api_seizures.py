"""Seizure CRUD + rule-based risk indicator (epilepsy mode, V15).

Part of the /api/* surface — split out of the former monolithic api.py
(ARCH-L5 400-line trigger). Registered via src.routes.api aggregator.
"""

from datetime import datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

import src.deps as _deps
from src.db import (
    delete_seizure,
    get_seizure_risk,
    get_seizures,
    save_seizure,
    update_seizure,
)

router = APIRouter()


class SeizureBody(BaseModel):
    occurred_at: datetime
    duration_seconds: int | None = None
    type: str = "unknown"
    severity: int | None = None
    notes: str | None = Field(default=None, max_length=2000)

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


@router.patch("/api/seizures/{seizure_id}", response_model=None)
async def api_update_seizure(
    request: Request, seizure_id: int, body: SeizureBody
) -> dict | JSONResponse:
    user = await _deps.require_user(request)
    updated = await update_seizure(
        user["id"],
        seizure_id,
        body.occurred_at,
        body.duration_seconds,
        body.type,
        body.severity,
        body.notes,
    )
    if not updated:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "Seizure not found"}},
        )
    return {"ok": True, "id": seizure_id}


@router.delete("/api/seizures/{seizure_id}", response_model=None)
async def api_delete_seizure(request: Request, seizure_id: int) -> dict | JSONResponse:
    user = await _deps.require_user(request)
    deleted = await delete_seizure(user["id"], seizure_id)
    if not deleted:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "Seizure not found"}},
        )
    return {"ok": True}


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
