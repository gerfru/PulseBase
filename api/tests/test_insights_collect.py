"""Tests fuer den Schicht-1-Builder (rein) + db-Adapter (gemockt)."""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

from src.insights.collect import (
    MetricInput,
    build_weekly_insight,
    gather_inputs,
)
from src.insights.models import MetricKey, Trend, Unit


def _tir(value, prev=None) -> MetricInput:
    return MetricInput(
        key=MetricKey.TIME_IN_RANGE, unit=Unit.PERCENT, value=value, prev_value=prev
    )


def _load(value, prev=None) -> MetricInput:
    return MetricInput(
        key=MetricKey.TRAINING_LOAD, unit=Unit.TSS, value=value, prev_value=prev
    )


def test_empty_week_yields_empty_object():
    insight = build_weekly_insight(2026, 24, [])
    assert insight.metrics == []
    assert insight.flags == []
    assert insight.evidence == []


def test_missing_value_goes_to_unavailable():
    insight = build_weekly_insight(2026, 24, [_tir(None)])
    assert insight.metrics == []
    assert MetricKey.TIME_IN_RANGE in insight.unavailable


def test_stable_when_change_small():
    insight = build_weekly_insight(2026, 24, [_tir(Decimal("80"), Decimal("81"))])
    assert insight.metrics[0].trend is Trend.STABLE


def test_training_load_spike_sets_flag_and_evidence():
    insight = build_weekly_insight(2026, 24, [_load(Decimal("412"), Decimal("300"))])
    assert "training_load_spike" in insight.flags
    assert "training.acwr_injury_risk" in insight.evidence
    assert insight.metrics[0].trend is Trend.UP


def test_low_time_in_range_flag_and_evidence():
    insight = build_weekly_insight(2026, 24, [_tir(Decimal("58"))])
    assert "low_time_in_range" in insight.flags
    assert "glucose.time_in_range" in insight.evidence


def test_contradictory_signals_build_cleanly():
    insight = build_weekly_insight(
        2026,
        24,
        [_tir(Decimal("60"), Decimal("90")), _load(Decimal("100"), Decimal("400"))],
    )
    trends = {m.key: m.trend for m in insight.metrics}
    assert trends[MetricKey.TIME_IN_RANGE] is Trend.DOWN
    assert trends[MetricKey.TRAINING_LOAD] is Trend.DOWN


async def test_gather_inputs_wires_tir():
    with patch(
        "src.insights.collect.get_glucose_stats",
        AsyncMock(return_value={"tir_pct": Decimal("75.0")}),
    ):
        inputs = await gather_inputs(1, 2026, 24)
    assert inputs[0].key is MetricKey.TIME_IN_RANGE
    assert inputs[0].value == Decimal("75.0")


async def test_gather_inputs_handles_no_data():
    with patch("src.insights.collect.get_glucose_stats", AsyncMock(return_value={})):
        inputs = await gather_inputs(1, 2026, 24)
    assert inputs[0].value is None
