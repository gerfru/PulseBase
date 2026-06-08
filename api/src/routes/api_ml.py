"""ML insights, history, status, and per-day feedback.

Part of the /api/* surface — split out of the former monolithic api.py
(ARCH-L5 400-line trigger). Registered via src.routes.api aggregator.
"""

from datetime import date

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, field_validator

import src.deps as _deps
from src.db import (
    get_ml_feedback,
    get_ml_history,
    get_ml_insights,
    get_ml_status,
    save_ml_feedback,
)
from src.db.ml_feedback import FEEDBACK_MODELS

router = APIRouter()


@router.get("/api/ml-insights")
async def api_ml_insights(request: Request) -> dict:
    user = await _deps.require_user(request)
    return await get_ml_insights(user["id"])


@router.get("/api/ml-history", response_model=None)
async def api_ml_history(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    end_date: date | None = Query(default=None),
) -> dict:
    user = await _deps.require_user(request)
    return await get_ml_history(user["id"], days, end_date=end_date)


@router.get("/api/ml-status")
async def api_ml_status(request: Request) -> dict:
    user = await _deps.require_user(request)
    return await get_ml_status(user["id"])


class MLFeedbackBody(BaseModel):
    model: str
    helpful: bool

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if v not in FEEDBACK_MODELS:
            raise ValueError(f"model must be one of {FEEDBACK_MODELS}")
        return v


@router.post("/api/ml-feedback")
async def api_ml_feedback(request: Request, body: MLFeedbackBody) -> dict:
    user = await _deps.require_user(request)
    await save_ml_feedback(user["id"], body.model, body.helpful)
    return {"ok": True}


@router.get("/api/ml-feedback")
async def api_get_ml_feedback(request: Request) -> dict:
    user = await _deps.require_user(request)
    return await get_ml_feedback(user["id"])
