"""Lesender Insights-Endpunkt fuer den Tagesbericht (ADR-0008)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request

import src.deps as _deps
from src.db.insight_jobs import get_daily_job_status
from src.db.weekly_insights import (
    StoredInsight,
    get_latest_weekly_insight,
    get_weekly_insight,
)
from src.deps import limiter
from src.insights.window import current_period_end

router = APIRouter()


def _current_period_end() -> date:
    return current_period_end()


def _serialize(stored: StoredInsight) -> dict[str, Any]:
    text = stored.text
    return {
        "status": "ready",
        "period_start": stored.insight.period_start.isoformat(),
        "period_end": stored.insight.period_end.isoformat(),
        "insight": stored.insight.model_dump(mode="json"),
        "text": {
            "body": text.body,
            "generator": text.generator,
            "model_id": text.model_id,
        },
        "catalog_version": stored.catalog_version,
        "created_at": stored.created_at.isoformat(),
        "ai_generated": text.generator == "llm",
    }


@router.get("/api/insights")
@limiter.limit("30/minute")
async def api_insights(request: Request) -> dict[str, Any]:
    user = await _deps.require_user(request)
    if "segment" in request.query_params:
        raise HTTPException(status_code=422, detail="segment no longer supported")
    period_end = _current_period_end()
    stored = await get_weekly_insight(user["id"], period_end)
    if stored is not None:
        return _serialize(stored)
    job_status = await get_daily_job_status(user["id"], period_end)
    previous = await get_latest_weekly_insight(user["id"], period_end)
    status = (
        "pending"
        if job_status in ("pending", "processing")
        else "failed"
        if job_status == "failed"
        else "stale"
    )
    return {
        "status": status,
        "period_start": (period_end - timedelta(days=6)).isoformat(),
        "period_end": period_end.isoformat(),
        "report": _serialize(previous) if previous else None,
    }
