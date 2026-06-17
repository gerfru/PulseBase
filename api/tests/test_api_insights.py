"""Tests fuer die Wochen-Insights-Endpoints."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from src.db.weekly_insights import StoredInsight, TextRecord
from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight
from src.routes.api_insights import _last_complete_week, _serialize
from tests.conftest import TEST_USER


def _stored() -> StoredInsight:
    insight = WeeklyInsight(
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
        flags=[],
        evidence=[],
        catalog_version="1.0.0",
    )
    return StoredInsight(
        insight=insight,
        texts={
            "hobby": TextRecord("Hobby-Text", "llm", "m"),
            "pro": TextRecord("Pro-Text", "fallback_template", None),
        },
        catalog_version="1.0.0",
        created_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )


def test_serialize_shape():
    d = _serialize(_stored(), 2026, 24)
    assert d["iso_year"] == 2026 and d["iso_week"] == 24
    assert d["texts"]["hobby"]["generator"] == "llm"
    assert d["ai_generated"] is True
    assert d["insight"]["metrics"][0]["key"] == "time_in_range"
    assert d["created_at"].startswith("2026-06-16")


def test_last_complete_week_is_in_range():
    year, week = _last_complete_week()
    assert 1 <= week <= 53 and year >= 2024


async def test_get_insights_serialized_and_scoped(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_insights.get_or_generate",
            AsyncMock(return_value=_stored()),
        ) as gen,
    ):
        r = await client.get("/api/insights?iso_year=2026&iso_week=24")
    assert r.status_code == 200
    body = r.json()
    assert body["iso_week"] == 24
    assert body["texts"]["hobby"]["body"] == "Hobby-Text"
    gen.assert_awaited_once()
    assert gen.await_args.args[0] == TEST_USER["id"]  # BOLA: session user
    assert gen.await_args.kwargs.get("force") is False


async def test_regenerate_forces(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_insights.get_or_generate",
            AsyncMock(return_value=_stored()),
        ) as gen,
    ):
        r = await client.post(
            "/api/insights/regenerate", json={"iso_year": 2026, "iso_week": 24}
        )
    assert r.status_code == 200
    gen.assert_awaited_once()
    assert gen.await_args.kwargs.get("force") is True


async def test_regenerate_rejects_bad_week(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post(
            "/api/insights/regenerate", json={"iso_year": 2026, "iso_week": 99}
        )
    assert r.status_code == 422
