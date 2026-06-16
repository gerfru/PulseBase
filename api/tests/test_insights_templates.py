"""Tests fuer das deterministische Fallback-Template."""

from decimal import Decimal

import pytest

from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight
from src.insights.postcheck import post_check
from src.insights.templates import fallback_text


def _insight(metrics) -> WeeklyInsight:
    return WeeklyInsight(
        iso_year=2026,
        iso_week=24,
        metrics=metrics,
        flags=[],
        evidence=[],
        catalog_version="1.0.0",
    )


def test_fallback_empty_week_is_post_check_conform():
    insight = _insight([])
    for segment in ("hobby", "pro", "profi"):
        text = fallback_text(insight, segment)
        assert post_check(text, insight, segment).passed


def test_fallback_with_metrics_is_post_check_conform():
    insight = _insight(
        [
            Metric(
                key=MetricKey.TIME_IN_RANGE,
                value=Decimal("58"),
                unit=Unit.PERCENT,
                change_pct=Decimal("-4.1"),
                trend=Trend.SLIGHTLY_DOWN,
            )
        ]
    )
    text = fallback_text(insight, "pro")
    assert post_check(text, insight, "pro").passed


def test_fallback_unknown_segment_raises():
    with pytest.raises(ValueError):
        fallback_text(_insight([]), "enterprise")
