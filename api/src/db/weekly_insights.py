"""Persistenz fuer KI-Wochen-Insights (ADR-0003, P5).

Speichert das identifier-freie ``WeeklyInsight`` als JSONB + einen Bericht
mit Provenance (``generator``/``model_id``). Parent + Text in einer
Transaktion, idempotenter Upsert (``ON CONFLICT``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

import asyncpg

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
    text: TextRecord
    catalog_version: str
    created_at: datetime


async def save_weekly_insight(
    user_id: int, insight: WeeklyInsight, text: TextRecord
) -> None:
    """Upsert von Objekt + Bericht in einer Transaktion."""
    obj_json = json.dumps(insight.model_dump(mode="json"))
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT pg_advisory_xact_lock($1, $2)",
                user_id,
                insight.period_end.toordinal(),
            )
            exists = await conn.fetchval(
                """SELECT 1 FROM weekly_insight_texts
                   WHERE user_id = $1 AND period_end = $2 AND segment = 'report'""",
                user_id,
                insight.period_end,
            )
            if exists:
                return
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
            await conn.execute(
                """DELETE FROM weekly_insight_texts
                   WHERE user_id = $1 AND period_end = $2 AND segment <> 'report'""",
                user_id,
                insight.period_end,
            )
            await conn.execute(
                """INSERT INTO weekly_insight_texts
                       (user_id, period_end, segment, body, generator, model_id)
                   VALUES ($1, $2, 'report', $3, $4, $5)
                   ON CONFLICT (user_id, period_end, segment) DO UPDATE
                   SET body = EXCLUDED.body, generator = EXCLUDED.generator,
                       model_id = EXCLUDED.model_id, created_at = NOW()""",
                user_id,
                insight.period_end,
                text.body,
                text.generator,
                text.model_id,
            )


async def get_weekly_insight(user_id: int, period_end: date) -> StoredInsight | None:
    """Liest den Bericht; alte Segment-Cache-Eintraege werden nicht ausgeliefert."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT i.insight_obj, i.catalog_version, i.created_at,
                  t.body, t.generator, t.model_id
           FROM weekly_insights AS i
           JOIN weekly_insight_texts AS t
             ON t.user_id = i.user_id AND t.period_end = i.period_end
            AND t.segment = 'report'
           WHERE i.user_id = $1 AND i.period_end = $2""",
        user_id,
        period_end,
    )
    return _stored_from_row(row)


async def get_latest_weekly_insight(user_id: int, before: date) -> StoredInsight | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT i.insight_obj, i.catalog_version, i.created_at,
                  t.body, t.generator, t.model_id
           FROM weekly_insights AS i
           JOIN weekly_insight_texts AS t
             ON t.user_id = i.user_id AND t.period_end = i.period_end
            AND t.segment = 'report'
           WHERE i.user_id = $1 AND i.period_end < $2
           ORDER BY i.period_end DESC
           LIMIT 1""",
        user_id,
        before,
    )
    return _stored_from_row(row)


def _stored_from_row(row: asyncpg.Record | None) -> StoredInsight | None:
    if row is None:
        return None
    obj = row["insight_obj"]
    if isinstance(obj, str):  # asyncpg liefert JSONB als Text
        obj = json.loads(obj)
    return StoredInsight(
        insight=WeeklyInsight.model_validate(obj),
        text=TextRecord(
            body=row["body"], generator=row["generator"], model_id=row["model_id"]
        ),
        catalog_version=row["catalog_version"],
        created_at=row["created_at"],
    )
