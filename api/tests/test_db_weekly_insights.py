"""Tests fuer die Insight-Persistenz (gemockter Pool, keine echte DB)."""

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.db.weekly_insights import (
    TextRecord,
    get_latest_weekly_insight,
    get_weekly_insight,
    save_weekly_insight,
)
from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight

_END = date(2026, 6, 14)


def _insight() -> WeeklyInsight:
    return WeeklyInsight(
        period_start=date(2026, 6, 8),
        period_end=_END,
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


async def test_save_writes_parent_and_one_report_under_period_lock():
    pool, conn = _save_pool()
    conn.fetchval.return_value = None
    text = TextRecord(body="Bericht", generator="llm", model_id="m")
    with patch("src.db.weekly_insights.get_pool", AsyncMock(return_value=pool)):
        await save_weekly_insight(1, _insight(), text)
    assert "pg_advisory_xact_lock" in conn.execute.await_args_list[0].args[0]
    assert conn.execute.await_args_list[0].args[1:] == (1, _END.toordinal())
    assert conn.fetchval.await_count == 1
    assert conn.execute.await_count == 4
    assert "segment <> 'report'" in conn.execute.await_args_list[2].args[0]
    assert "'report'" in conn.execute.await_args.args[0]


async def test_save_never_overwrites_published_report():
    pool, conn = _save_pool()
    conn.fetchval.return_value = 1
    text = TextRecord(body="Anderer Bericht", generator="llm", model_id="m")

    with patch("src.db.weekly_insights.get_pool", AsyncMock(return_value=pool)):
        await save_weekly_insight(1, _insight(), text)

    assert conn.execute.await_count == 1
    assert "pg_advisory_xact_lock" in conn.execute.await_args.args[0]


async def test_get_reconstructs_only_the_report():
    ins = _insight()
    row = {
        "insight_obj": json.dumps(ins.model_dump(mode="json")),
        "catalog_version": "1.0.0",
        "created_at": datetime(2026, 6, 16, tzinfo=timezone.utc),
        "body": "Bericht",
        "generator": "llm",
        "model_id": "m",
    }
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=row)
    with patch("src.db.weekly_insights.get_pool", AsyncMock(return_value=pool)):
        stored = await get_weekly_insight(1, _END)
    assert stored is not None
    assert stored.insight.period_end == _END
    assert stored.text.body == "Bericht"
    assert stored.text.generator == "llm"
    assert stored.catalog_version == "1.0.0"
    assert "t.segment = 'report'" in pool.fetchrow.await_args.args[0]


async def test_get_miss_returns_none():
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    with patch("src.db.weekly_insights.get_pool", AsyncMock(return_value=pool)):
        assert await get_weekly_insight(1, _END) is None


async def test_latest_report_is_user_scoped_and_older_than_target():
    ins = _insight()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        return_value={
            "insight_obj": json.dumps(ins.model_dump(mode="json")),
            "catalog_version": "1.0.0",
            "created_at": datetime(2026, 6, 16, tzinfo=timezone.utc),
            "body": "Bericht",
            "generator": "llm",
            "model_id": "m",
        }
    )
    with patch("src.db.weekly_insights.get_pool", AsyncMock(return_value=pool)):
        stored = await get_latest_weekly_insight(7, date(2026, 6, 15))
    assert stored is not None and stored.insight.period_end == _END
    query, user_id, before = pool.fetchrow.await_args.args
    assert (user_id, before) == (7, date(2026, 6, 15))
    assert "i.user_id = $1 AND i.period_end < $2" in query
    assert "t.segment = 'report'" in query
    assert "ORDER BY i.period_end DESC" in query
