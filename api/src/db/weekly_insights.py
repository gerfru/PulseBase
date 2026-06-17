"""Persistenz fuer KI-Wochen-Insights (ADR-0003, P5).

Speichert das identifier-freie ``WeeklyInsight`` als JSONB + einen Text pro
Segment mit Provenance (``generator``/``model_id``). Parent + Texte in einer
Transaktion, idempotenter Upsert (``ON CONFLICT``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

from src.insights.models import WeeklyInsight

from .pool import get_pool


@dataclass(frozen=True)
class TextRecord:
    body: str
    generator: str  # "llm" | "fallback_template"
    model_id: str | None


@dataclass(frozen=True)
class StoredInsight:
    insight: WeeklyInsight
    texts: dict[str, TextRecord]
    catalog_version: str
    created_at: datetime


async def save_weekly_insight(
    user_id: int, insight: WeeklyInsight, texts: dict[str, TextRecord]
) -> None:
    """Upsert von Objekt + Segment-Texten in einer Transaktion."""
    obj_json = json.dumps(insight.model_dump(mode="json"))
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO weekly_insights
                       (user_id, period_start, period_end, insight_obj, catalog_version)
                   VALUES ($1, $2, $3, $4::jsonb, $5)
                   ON CONFLICT (user_id, period_end) DO UPDATE
                   SET period_start = EXCLUDED.period_start,
                       insight_obj = EXCLUDED.insight_obj,
                       catalog_version = EXCLUDED.catalog_version,
                       created_at = NOW()""",
                user_id,
                insight.period_start,
                insight.period_end,
                obj_json,
                insight.catalog_version,
            )
            for segment, rec in texts.items():
                await conn.execute(
                    """INSERT INTO weekly_insight_texts
                           (user_id, period_end, segment, body, generator, model_id)
                       VALUES ($1, $2, $3, $4, $5, $6)
                       ON CONFLICT (user_id, period_end, segment) DO UPDATE
                       SET body = EXCLUDED.body, generator = EXCLUDED.generator,
                           model_id = EXCLUDED.model_id, created_at = NOW()""",
                    user_id,
                    insight.period_end,
                    segment,
                    rec.body,
                    rec.generator,
                    rec.model_id,
                )


async def get_weekly_insight(user_id: int, period_end: date) -> StoredInsight | None:
    """Liest Objekt + Texte; ``None`` wenn (User, Fenster-Ende) nicht gespeichert."""
    pool = await get_pool()
    parent = await pool.fetchrow(
        """SELECT insight_obj, catalog_version, created_at
           FROM weekly_insights
           WHERE user_id = $1 AND period_end = $2""",
        user_id,
        period_end,
    )
    if parent is None:
        return None
    rows = await pool.fetch(
        """SELECT segment, body, generator, model_id
           FROM weekly_insight_texts
           WHERE user_id = $1 AND period_end = $2""",
        user_id,
        period_end,
    )
    obj = parent["insight_obj"]
    if isinstance(obj, str):  # asyncpg liefert JSONB als Text
        obj = json.loads(obj)
    return StoredInsight(
        insight=WeeklyInsight.model_validate(obj),
        texts={
            r["segment"]: TextRecord(
                body=r["body"], generator=r["generator"], model_id=r["model_id"]
            )
            for r in rows
        },
        catalog_version=parent["catalog_version"],
        created_at=parent["created_at"],
    )
