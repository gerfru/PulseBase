"""Tests fuer den lesenden Insights-Tagesbericht."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from src.db.weekly_insights import StoredInsight, TextRecord
from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight
from src.insights.window import current_period_end
from src.routes.api_insights import _current_period_end, _serialize
from tests.conftest import TEST_USER

_END = date(2026, 6, 14)


def _stored() -> StoredInsight:
    insight = WeeklyInsight(
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
        flags=[],
        evidence=[],
        catalog_version="1.0.0",
    )
    return StoredInsight(
        insight=insight,
        text=TextRecord("Bericht", "llm", "m"),
        catalog_version="1.0.0",
        created_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )


def test_serialize_shape():
    d = _serialize(_stored())
    assert d["status"] == "ready"
    assert d["period_start"] == "2026-06-08" and d["period_end"] == "2026-06-14"
    assert d["text"]["generator"] == "llm"
    assert "texts" not in d
    assert d["ai_generated"] is True
    assert d["insight"]["metrics"][0]["key"] == "time_in_range"
    assert d["created_at"].startswith("2026-06-16")


def test_route_uses_local_window():
    with patch("src.routes.api_insights.current_period_end", return_value=_END):
        assert _current_period_end() == _END


def test_current_period_end_uses_vienna_calendar_date():
    assert current_period_end(
        datetime(2026, 9, 28, 22, 30, tzinfo=timezone.utc)
    ) == date(2026, 9, 28)


async def test_get_ready_from_cache_scoped(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_insights.get_weekly_insight",
            AsyncMock(return_value=_stored()),
        ) as g,
    ):
        r = await client.get("/api/insights")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["text"]["body"] == "Bericht"
    assert g.await_args.args[0] == TEST_USER["id"]  # BOLA: session user


async def test_get_pending_does_not_start_generation(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_insights.get_weekly_insight", AsyncMock(return_value=None)
        ),
        patch(
            "src.routes.api_insights.get_daily_job_status",
            AsyncMock(return_value="processing"),
        ) as status,
        patch(
            "src.routes.api_insights.get_latest_weekly_insight",
            AsyncMock(return_value=None),
        ) as latest,
    ):
        r = await client.get("/api/insights")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    assert r.json()["report"] is None
    status.assert_awaited_once()
    assert status.await_args.args[0] == TEST_USER["id"]
    latest.assert_awaited_once()


async def test_regeneration_endpoint_is_gone(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.post("/api/insights/regenerate")
    assert r.status_code in (404, 405)


async def test_get_stale_when_only_legacy_segments_exist(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_insights.get_weekly_insight",
            AsyncMock(return_value=None),
        ),
        patch(
            "src.routes.api_insights.get_daily_job_status", AsyncMock(return_value=None)
        ),
        patch(
            "src.routes.api_insights.get_latest_weekly_insight",
            AsyncMock(return_value=None),
        ),
    ):
        r = await client.get("/api/insights")
    assert r.status_code == 200
    assert r.json()["status"] == "stale"
    assert r.json()["report"] is None


async def test_get_stale_returns_previous_with_its_own_dates(client):
    target = date(2026, 6, 15)
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_insights.current_period_end", return_value=target),
        patch(
            "src.routes.api_insights.get_weekly_insight", AsyncMock(return_value=None)
        ),
        patch(
            "src.routes.api_insights.get_daily_job_status", AsyncMock(return_value=None)
        ),
        patch(
            "src.routes.api_insights.get_latest_weekly_insight",
            AsyncMock(return_value=_stored()),
        ) as latest,
    ):
        r = await client.get("/api/insights")
    body = r.json()
    assert body["status"] == "stale"
    assert body["period_end"] == "2026-06-15"
    assert body["report"]["period_end"] == "2026-06-14"
    assert body["report"]["text"]["body"] == "Bericht"
    latest.assert_awaited_once_with(TEST_USER["id"], target)


async def test_get_failed_retains_previous_report(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_insights.get_weekly_insight", AsyncMock(return_value=None)
        ),
        patch(
            "src.routes.api_insights.get_daily_job_status",
            AsyncMock(return_value="failed"),
        ),
        patch(
            "src.routes.api_insights.get_latest_weekly_insight",
            AsyncMock(return_value=_stored()),
        ),
    ):
        r = await client.get("/api/insights")
    assert r.json()["status"] == "failed"
    assert r.json()["report"]["period_end"] == "2026-06-14"


async def test_segment_parameter_rejected(client):
    with patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)):
        r = await client.get("/api/insights?segment=profi")
    assert r.status_code == 422
