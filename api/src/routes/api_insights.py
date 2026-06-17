"""Insights — JSON-Endpoints (ADR-0003 / ADR-0004).

Rollierendes 7-Tage-Fenster (endet gestern). GET liefert das gespeicherte
Segment (``status: ready``) oder stoesst dessen Generierung im Hintergrund an und
antwortet sofort ``status: pending`` (lokale Generierung dauert; blockiert den
Request nicht). **Lazy pro Segment:** nur das angeforderte Segment wird erzeugt —
die uebrigen erst bei Bedarf (Tab-Wechsel), das spart die Erstlatenz.
POST ``regenerate`` erzwingt eine Neugenerierung des angeforderten Segments
(ratenlimitiert, C5). Immer per Session-User gescopet (BOLA, C4); JSON +
sameSite=strict → kein CSRF.

Teil des /api/*-Surface; via src.routes.api Aggregator registriert.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query, Request

import src.deps as _deps
from src.db.weekly_insights import StoredInsight, get_weekly_insight
from src.deps import limiter
from src.insights.store import get_or_generate_segment
from src.insights.templates import SEGMENTS

router = APIRouter()
logger = structlog.get_logger(__name__)

# In-Flight-Dedup + Task-Referenzen (verhindert GC der Hintergrund-Tasks).
_inflight: set[tuple[int, date, str]] = set()
_bg_tasks: set[asyncio.Task[None]] = set()


def _current_period_end() -> date:
    """Letzter vollstaendiger Tag (gestern) — 'heute' ist unvollstaendig."""
    return date.today() - timedelta(days=1)


def _valid_segment(segment: str) -> str:
    if segment not in SEGMENTS:
        raise HTTPException(status_code=422, detail="unknown segment")
    return segment


def _serialize(stored: StoredInsight) -> dict[str, Any]:
    return {
        "status": "ready",
        "period_start": stored.insight.period_start.isoformat(),
        "period_end": stored.insight.period_end.isoformat(),
        "insight": stored.insight.model_dump(mode="json"),
        "texts": {
            seg: {"body": t.body, "generator": t.generator, "model_id": t.model_id}
            for seg, t in stored.texts.items()
        },
        "catalog_version": stored.catalog_version,
        "created_at": stored.created_at.isoformat(),
        "ai_generated": any(t.generator == "llm" for t in stored.texts.values()),
    }


async def _generate_bg(
    user_id: int, period_end: date, segment: str, force: bool
) -> None:
    try:
        await get_or_generate_segment(user_id, period_end, segment, force=force)
    except Exception:
        logger.exception(
            "insights.bg_generate_failed",
            period_end=period_end.isoformat(),
            segment=segment,
        )
    finally:
        _inflight.discard((user_id, period_end, segment))


def _kick(user_id: int, period_end: date, segment: str, *, force: bool) -> None:
    """Startet die Hintergrund-Generierung, dedupliziert pro (user, Fenster, Segment)."""
    key = (user_id, period_end, segment)
    if key in _inflight:
        return
    _inflight.add(key)
    task = asyncio.create_task(_generate_bg(user_id, period_end, segment, force))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


def _pending(period_end: date) -> dict[str, Any]:
    return {
        "status": "pending",
        "period_start": (period_end - timedelta(days=6)).isoformat(),
        "period_end": period_end.isoformat(),
    }


@router.get("/api/insights")
@limiter.limit("30/minute")
async def api_insights(
    request: Request, segment: str = Query("hobby")
) -> dict[str, Any]:
    user = await _deps.require_user(request)
    seg = _valid_segment(segment)
    period_end = _current_period_end()
    stored = await get_weekly_insight(user["id"], period_end)
    if stored is not None and seg in stored.texts:
        return _serialize(stored)
    _kick(user["id"], period_end, seg, force=False)
    return _pending(period_end)


@router.post("/api/insights/regenerate")
@limiter.limit("5/hour")
async def api_insights_regenerate(
    request: Request, segment: str = Query("hobby")
) -> dict[str, Any]:
    user = await _deps.require_user(request)
    seg = _valid_segment(segment)
    period_end = _current_period_end()
    _kick(user["id"], period_end, seg, force=True)
    return _pending(period_end)
