"""Tests fuer die Insight-Persistenz (gemockter Pool, keine echte DB)."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.db.weekly_insights import (
    TextRecord,
    get_weekly_insight,
    save_weekly_insight,
)
from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight


def _insight() -> WeeklyInsight:
    return WeeklyInsight(
        iso_year=2026,
        iso_week=24,
        metrics=[
            Metric(
                key=MetricKey.TIME_IN_RANGE,
                value=Decimal("58"),
                unit=Unit.PERCENT,
                change_pct=None,
                trend=Trend.STABLE,
            )
        ],
        flags=["low_time_in_range"],
        evidence=["glucose_tir"],
        catalog_version="1.0.0",
    )


class _ACM:
    def __init__(self, val: object) -> None:
        self._val = val

    async def __aenter__(self) -> object:
        return self._val

    async def __aexit__(self, *a: object) -> bool:
        return False


def _save_pool():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.transaction = MagicMock(return_value=_ACM(None))
    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=_ACM(conn))
    return pool, conn


async def test_save_upserts_parent_and_three_texts():
    pool, conn = _save_pool()
    texts = {
        s: TextRecord(body=f"t-{s}", generator="llm", model_id="m")
        for s in ("hobby", "pro", "profi")
    }
    with patch("src.db.weekly_insights.get_pool", AsyncMock(return_value=pool)):
        await save_weekly_insight(1, _insight(), texts)
    assert conn.execute.await_count == 4  # 1 parent + 3 segment texts


async def test_get_reconstructs_insight_and_texts():
    ins = _insight()
    parent = {
        "insight_obj": json.dumps(ins.model_dump(mode="json")),
        "catalog_version": "1.0.0",
        "created_at": datetime(2026, 6, 16, tzinfo=timezone.utc),
    }
    rows = [{"segment": "hobby", "body": "x", "generator": "llm", "model_id": "m"}]
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=parent)
    pool.fetch = AsyncMock(return_value=rows)
    with patch("src.db.weekly_insights.get_pool", AsyncMock(return_value=pool)):
        stored = await get_weekly_insight(1, 2026, 24)
    assert stored is not None
    assert stored.insight.iso_week == 24
    assert stored.texts["hobby"].generator == "llm"
    assert stored.catalog_version == "1.0.0"


async def test_get_miss_returns_none():
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    with patch("src.db.weekly_insights.get_pool", AsyncMock(return_value=pool)):
        assert await get_weekly_insight(1, 2026, 24) is None
