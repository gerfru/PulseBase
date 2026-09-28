"""Tests fuer das deterministische Fallback-Template."""

from datetime import date
from decimal import Decimal

from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight
from src.insights.postcheck import post_check
from src.insights.templates import fallback_text


def _insight(metrics) -> WeeklyInsight:
    return WeeklyInsight(
        period_start=date(2026, 6, 8),
        period_end=date(2026, 6, 14),
        metrics=metrics,
        flags=[],
        evidence=[],
        catalog_version="1.0.0",
    )


def test_fallback_empty_week_is_post_check_conform():
    insight = _insight([])
    text = fallback_text(insight)
    assert "Kennzahlen\nKeine Kennzahlen verfügbar." in text
    assert "Einordnung\n" in text
    assert post_check(text, insight).passed


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
    text = fallback_text(insight)
    assert text.startswith("Zusammenfassung\n")
    assert "\n\nKennzahlen\n" in text
    assert "\n\nEinordnung\n" in text
    assert "\n\nHinweis\n" in text
    assert "Zeit im Zielbereich: 58 %." in text
    assert "Entwicklung: leicht gesunken." in text
    assert "Veränderung: -4.1 %" in text
    assert "Niveau liegt laut hinterlegter Skala im Bereich unter Zielbereich" in text
    assert "time_in_range" not in text
    assert post_check(text, insight).passed


def test_fallback_separates_opposing_trends_for_post_check():
    insight = _insight(
        [
            Metric(
                key=MetricKey.HRV,
                value=Decimal("64"),
                unit=Unit.MS,
                change_pct=Decimal("2"),
                trend=Trend.SLIGHTLY_UP,
            ),
            Metric(
                key=MetricKey.TIME_IN_RANGE,
                value=Decimal("58"),
                unit=Unit.PERCENT,
                change_pct=Decimal("-4.1"),
                trend=Trend.SLIGHTLY_DOWN,
            ),
        ]
    )
    assert post_check(fallback_text(insight), insight).passed


def test_fallback_passes_when_opposing_trends_share_a_value():
    insight = _insight(
        [
            Metric(
                key=MetricKey.HRV,
                value=Decimal("64"),
                unit=Unit.MS,
                change_pct=Decimal("2"),
                trend=Trend.UP,
            ),
            Metric(
                key=MetricKey.TRAINING_FORM,
                value=Decimal("64"),
                unit=Unit.POINTS,
                change_pct=Decimal("-2"),
                trend=Trend.DOWN,
            ),
        ]
    )
    assert post_check(fallback_text(insight), insight).passed
