"""Wochen-Insights — JSON-Endpoints (ADR-0003, P6).

GET liefert die gespeicherte Insight (``status: ready``) oder stoesst die
Generierung im Hintergrund an und antwortet sofort ``status: pending`` — die
Generierung mit dem lokalen Modell dauert; sie blockiert den Request nicht. POST
``regenerate`` erzwingt eine Neugenerierung (ratenlimitiert, C5). Immer per
Session-User gescopet (BOLA, C4); JSON + sameSite=strict → kein CSRF.

Teil des /api/*-Surface; via src.routes.api Aggregator registriert.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, field_validator

import src.deps as _deps
from src.db.weekly_insights import StoredInsight, get_weekly_insight
from src.deps import limiter
from src.insights.store import get_or_generate

router = APIRouter()
logger = structlog.get_logger(__name__)

# In-Flight-Dedup + Task-Referenzen (verhindert GC der Hintergrund-Tasks).
_inflight: set[tuple[int, int, int]] = set()
_bg_tasks: set[asyncio.Task[None]] = set()


def _last_complete_week() -> tuple[int, int]:
    """Die zuletzt abgeschlossene ISO-Woche (laufende Woche haette Teildaten)."""
    iso = (date.today() - timedelta(weeks=1)).isocalendar()
    return iso.year, iso.week


def _resolve_week(iso_year: int | None, iso_week: int | None) -> tuple[int, int]:
    if iso_year is not None and iso_week is not None:
        return iso_year, iso_week
    return _last_complete_week()


def _serialize(stored: StoredInsight, iso_year: int, iso_week: int) -> dict[str, Any]:
    return {
        "status": "ready",
        "iso_year": iso_year,
        "iso_week": iso_week,
        "insight": stored.insight.model_dump(mode="json"),
        "texts": {
            seg: {"body": t.body, "generator": t.generator, "model_id": t.model_id}
            for seg, t in stored.texts.items()
        },
        "catalog_version": stored.catalog_version,
        "created_at": stored.created_at.isoformat(),
        "ai_generated": any(t.generator == "llm" for t in stored.texts.values()),
    }


async def _generate_bg(user_id: int, year: int, week: int, force: bool) -> None:
    try:
        await get_or_generate(user_id, year, week, force=force)
    except Exception:
        logger.exception("insights.bg_generate_failed", iso_year=year, iso_week=week)
    finally:
        _inflight.discard((user_id, year, week))


def _kick(user_id: int, year: int, week: int, *, force: bool) -> None:
    """Startet die Hintergrund-Generierung, dedupliziert pro (user, Woche)."""
    key = (user_id, year, week)
    if key in _inflight:
        return
    _inflight.add(key)
    task = asyncio.create_task(_generate_bg(user_id, year, week, force))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


@router.get("/api/insights")
@limiter.limit("30/minute")
async def api_insights(
    request: Request,
    iso_year: int | None = Query(default=None),
    iso_week: int | None = Query(default=None, ge=1, le=53),
) -> dict[str, Any]:
    user = await _deps.require_user(request)
    year, week = _resolve_week(iso_year, iso_week)
    stored = await get_weekly_insight(user["id"], year, week)
    if stored is not None:
        return _serialize(stored, year, week)
    _kick(user["id"], year, week, force=False)
    return {"status": "pending", "iso_year": year, "iso_week": week}


class RegenerateBody(BaseModel):
    iso_year: int
    iso_week: int

    @field_validator("iso_week")
    @classmethod
    def _valid_week(cls, v: int) -> int:
        if not 1 <= v <= 53:
            raise ValueError("iso_week must be in 1..53")
        return v


@router.post("/api/insights/regenerate")
@limiter.limit("5/hour")
async def api_insights_regenerate(
    request: Request, body: RegenerateBody
) -> dict[str, Any]:
    user = await _deps.require_user(request)
    _kick(user["id"], body.iso_year, body.iso_week, force=True)
    return {"status": "pending", "iso_year": body.iso_year, "iso_week": body.iso_week}
