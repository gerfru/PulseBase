"""Tests fuer die Cache-Orchestrierung get_or_generate."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from src.db.weekly_insights import StoredInsight, TextRecord
from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight
from src.insights.postcheck import GateOutput
from src.insights.store import get_or_generate, get_or_generate_segment

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
        flags=[],
        evidence=[],
        catalog_version="1.0.0",
    )


def _stored() -> StoredInsight:
    return StoredInsight(
        insight=_insight(),
        texts={"hobby": TextRecord("x", "llm", "m")},
        catalog_version="1.0.0",
        created_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )


class _Fake:
    model = "fake"

    async def complete(self, prompt: str) -> str:
        return "egal"


async def test_cache_hit_skips_generation():
    gen = AsyncMock()
    save = AsyncMock()
    with (
        patch(
            "src.insights.store.get_weekly_insight", AsyncMock(return_value=_stored())
        ),
        patch("src.insights.store.generate_all_segments", gen),
        patch("src.insights.store.save_weekly_insight", save),
    ):
        out = await get_or_generate(1, _END)
    gen.assert_not_called()
    save.assert_not_called()
    assert out.insight.period_end == _END


async def test_miss_generates_and_saves_with_provenance():
    ins = _insight()
    outputs = {
        "hobby": GateOutput("x", "llm", 1),
        "pro": GateOutput("y", "fallback_template", 0),
        "profi": GateOutput("z", "llm", 1),
    }
    save = AsyncMock()
    with (
        patch(
            "src.insights.store.get_weekly_insight",
            AsyncMock(side_effect=[None, _stored()]),
        ),
        patch(
            "src.insights.store.generate_all_segments",
            AsyncMock(return_value=(ins, outputs)),
        ),
        patch("src.insights.store.save_weekly_insight", save),
    ):
        out = await get_or_generate(1, _END, provider=_Fake())
    save.assert_awaited_once()
    saved_texts = save.await_args.args[2]
    assert saved_texts["hobby"].model_id == "fake"  # llm -> pinned model
    assert saved_texts["pro"].model_id is None  # fallback -> no model
    assert out.insight.period_end == _END


async def test_force_regenerates_despite_cache():
    ins = _insight()
    outputs = {"hobby": GateOutput("x", "llm", 1)}
    get = AsyncMock(side_effect=[_stored()])  # only the post-save read
    with (
        patch("src.insights.store.get_weekly_insight", get),
        patch(
            "src.insights.store.generate_all_segments",
            AsyncMock(return_value=(ins, outputs)),
        ),
        patch("src.insights.store.save_weekly_insight", AsyncMock()),
    ):
        await get_or_generate(1, _END, force=True, provider=_Fake())
    assert get.await_count == 1  # cache pre-read skipped


# --- lazy pro Segment ------------------------------------------------------ #


async def test_segment_cache_hit_skips_generation():
    gen = AsyncMock()
    with (
        patch(
            "src.insights.store.get_weekly_insight", AsyncMock(return_value=_stored())
        ),
        patch("src.insights.store.generate_segment", gen),
        patch("src.insights.store.save_weekly_insight", AsyncMock()),
    ):
        # _stored() enthaelt das Segment "hobby" -> kein LLM-Aufruf.
        out = await get_or_generate_segment(1, _END, "hobby")
    gen.assert_not_called()
    assert out.insight.period_end == _END


async def test_segment_miss_generates_and_saves_single_segment():
    ins = _insight()
    save = AsyncMock()
    with (
        patch(
            "src.insights.store.get_weekly_insight",
            AsyncMock(side_effect=[_stored(), _stored()]),
        ),
        patch(
            "src.insights.store.generate_segment",
            AsyncMock(return_value=(ins, GateOutput("y", "llm", 1))),
        ),
        patch("src.insights.store.save_weekly_insight", save),
    ):
        # "profi" fehlt im Cache -> nur dieses eine Segment wird generiert/gespeichert.
        await get_or_generate_segment(1, _END, "profi", provider=_Fake())
    save.assert_awaited_once()
    saved_texts = save.await_args.args[2]
    assert set(saved_texts) == {"profi"}
    assert saved_texts["profi"].model_id == "fake"
