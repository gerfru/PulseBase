"""Glucose readings + stats (Libre users, V9).

Part of the /api/* surface — split out of the former monolithic api.py
(ARCH-L5 400-line trigger). Registered via src.routes.api aggregator.
"""

from fastapi import APIRouter, Query, Request

import src.deps as _deps
from src.db import get_glucose_recent, get_glucose_stats

router = APIRouter()


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
