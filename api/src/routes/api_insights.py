"""Insights — JSON-Endpoints (ADR-0003 / ADR-0004).

Rollierendes 7-Tage-Fenster (endet gestern). GET liefert die gespeicherte Insight
(``status: ready``) oder stoesst die Generierung im Hintergrund an und antwortet
sofort ``status: pending`` (lokale Generierung dauert; blockiert den Request nicht).
POST ``regenerate`` erzwingt eine Neugenerierung des aktuellen Fensters
(ratenlimitiert, C5). Immer per Session-User gescopet (BOLA, C4); JSON +
sameSite=strict → kein CSRF.

Teil des /api/*-Surface; via src.routes.api Aggregator registriert.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Request

import src.deps as _deps
from src.db.weekly_insights import StoredInsight, get_weekly_insight
from src.deps import limiter
from src.insights.store import get_or_generate

router = APIRouter()
logger = structlog.get_logger(__name__)

# In-Flight-Dedup + Task-Referenzen (verhindert GC der Hintergrund-Tasks).
_inflight: set[tuple[int, date]] = set()
_bg_tasks: set[asyncio.Task[None]] = set()


def _current_period_end() -> date:
    """Letzter vollstaendiger Tag (gestern) — 'heute' ist unvollstaendig."""
    return date.today() - timedelta(days=1)


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


async def _generate_bg(user_id: int, period_end: date, force: bool) -> None:
    try:
        await get_or_generate(user_id, period_end, force=force)
    except Exception:
        logger.exception(
            "insights.bg_generate_failed", period_end=period_end.isoformat()
        )
    finally:
        _inflight.discard((user_id, period_end))


def _kick(user_id: int, period_end: date, *, force: bool) -> None:
    """Startet die Hintergrund-Generierung, dedupliziert pro (user, Fenster)."""
    key = (user_id, period_end)
    if key in _inflight:
        return
    _inflight.add(key)
    task = asyncio.create_task(_generate_bg(user_id, period_end, force))
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
async def api_insights(request: Request) -> dict[str, Any]:
    user = await _deps.require_user(request)
    period_end = _current_period_end()
    stored = await get_weekly_insight(user["id"], period_end)
    if stored is not None:
        return _serialize(stored)
    _kick(user["id"], period_end, force=False)
    return _pending(period_end)


@router.post("/api/insights/regenerate")
@limiter.limit("5/hour")
async def api_insights_regenerate(request: Request) -> dict[str, Any]:
    user = await _deps.require_user(request)
    period_end = _current_period_end()
    _kick(user["id"], period_end, force=True)
    return _pending(period_end)
