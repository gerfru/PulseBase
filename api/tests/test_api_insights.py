"""Tests fuer die Insights-Endpoints (rollierend, async/Hintergrund-Generierung)."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.db.weekly_insights import StoredInsight, TextRecord
from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight
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
        texts={
            "hobby": TextRecord("Hobby-Text", "llm", "m"),
            "pro": TextRecord("Pro-Text", "fallback_template", None),
        },
        catalog_version="1.0.0",
        created_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )


def test_serialize_shape():
    d = _serialize(_stored())
    assert d["status"] == "ready"
    assert d["period_start"] == "2026-06-08" and d["period_end"] == "2026-06-14"
    assert d["texts"]["hobby"]["generator"] == "llm"
    assert d["ai_generated"] is True
    assert d["insight"]["metrics"][0]["key"] == "time_in_range"
    assert d["created_at"].startswith("2026-06-16")


def test_current_period_end_is_yesterday():
    assert _current_period_end() == date.today() - timedelta(days=1)


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
    assert body["texts"]["hobby"]["body"] == "Hobby-Text"
    assert g.await_args.args[0] == TEST_USER["id"]  # BOLA: session user


async def test_get_pending_kicks_background(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch(
            "src.routes.api_insights.get_weekly_insight", AsyncMock(return_value=None)
        ),
        patch("src.routes.api_insights._kick", MagicMock()) as kick,
    ):
        r = await client.get("/api/insights")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    kick.assert_called_once()
    assert kick.call_args.args[0] == TEST_USER["id"]
    assert kick.call_args.kwargs.get("force") is False


async def test_regenerate_kicks_force(client):
    with (
        patch("src.deps.require_user", AsyncMock(return_value=TEST_USER)),
        patch("src.routes.api_insights._kick", MagicMock()) as kick,
    ):
        r = await client.post("/api/insights/regenerate")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    kick.assert_called_once()
    assert kick.call_args.kwargs.get("force") is True


# --- Hintergrund-Generierung ---------------------------------------------- #


async def test_generate_bg_clears_inflight_on_success():
    from src.routes.api_insights import _generate_bg, _inflight

    _inflight.add((1, _END))
    with patch("src.routes.api_insights.get_or_generate", AsyncMock()):
        await _generate_bg(1, _END, False)
    assert (1, _END) not in _inflight


async def test_generate_bg_clears_inflight_on_error():
    from src.routes.api_insights import _generate_bg, _inflight

    _inflight.add((1, _END))
    with patch(
        "src.routes.api_insights.get_or_generate",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        await _generate_bg(1, _END, False)  # darf nicht werfen
    assert (1, _END) not in _inflight


def test_kick_dedupes_same_window():
    from src.routes.api_insights import _inflight, _kick

    _inflight.discard((9, _END))
    with (
        patch("src.routes.api_insights._generate_bg"),
        patch("src.routes.api_insights.asyncio.create_task") as ct,
    ):
        _kick(9, _END, force=False)
        _kick(9, _END, force=False)  # dedupliziert → kein zweiter Task
    ct.assert_called_once()
    _inflight.discard((9, _END))
