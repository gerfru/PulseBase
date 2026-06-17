"""Tests fuer Schicht-1-Builder + rollierenden 7-Tage-Adapter."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from src.insights.collect import (
    MetricInput,
    build_weekly_insight,
    gather_inputs,
)
from src.insights.models import MetricKey, Trend, Unit

_S = date(2026, 6, 8)
_E = date(2026, 6, 14)


def _mi(key: MetricKey, unit: Unit, value, prev=None) -> MetricInput:
    return MetricInput(key=key, unit=unit, value=value, prev_value=prev)


def _pts(key, value, prev=None) -> MetricInput:
    return _mi(key, Unit.POINTS, value, prev)


# --- build_weekly_insight (rein) ------------------------------------------- #


def test_empty_window_yields_empty_object():
    insight = build_weekly_insight(_S, _E, [])
    assert insight.metrics == []
    assert insight.flags == []
    assert insight.evidence == []


def test_missing_value_goes_to_unavailable():
    insight = build_weekly_insight(_S, _E, [_pts(MetricKey.READINESS, None)])
    assert insight.metrics == []
    assert MetricKey.READINESS in insight.unavailable


def test_stable_when_change_small():
    insight = build_weekly_insight(
        _S, _E, [_pts(MetricKey.SLEEP, Decimal("80"), Decimal("81"))]
    )
    assert insight.metrics[0].trend is Trend.STABLE


def test_low_readiness_flag_and_evidence():
    insight = build_weekly_insight(_S, _E, [_pts(MetricKey.READINESS, Decimal("30"))])
    assert "low_readiness" in insight.flags
    assert "energy_autonomic" in insight.evidence
    assert "energy_cognitive" in insight.evidence


def test_sleep_low_flag_and_evidence():
    insight = build_weekly_insight(_S, _E, [_pts(MetricKey.SLEEP, Decimal("45"))])
    assert "sleep_low" in insight.flags
    assert "sleep_score_custom" in insight.evidence


def test_high_stress_flag():
    insight = build_weekly_insight(_S, _E, [_pts(MetricKey.STRESS, Decimal("70"))])
    assert "high_stress" in insight.flags
    assert "stress_score_custom" in insight.evidence


def test_training_volume_spike_flag_and_evidence():
    insight = build_weekly_insight(
        _S,
        _E,
        [_mi(MetricKey.TRAINING_VOLUME, Unit.H, Decimal("10.0"), Decimal("5.0"))],
    )
    assert "training_volume_spike" in insight.flags
    assert "acwr_injury_risk" in insight.evidence
    assert insight.metrics[0].trend is Trend.UP


def test_low_time_in_range_flag_and_evidence():
    insight = build_weekly_insight(
        _S, _E, [_mi(MetricKey.TIME_IN_RANGE, Unit.PERCENT, Decimal("58"))]
    )
    assert "low_time_in_range" in insight.flags
    assert "glucose_tir" in insight.evidence


def test_period_order_preserved():
    insight = build_weekly_insight(_S, _E, [])
    assert insight.period_start == _S
    assert insight.period_end == _E


# --- gather_inputs (rollierend, gemockt) ----------------------------------- #

# Klar in der Vergangenheit -> Glukose (NOW-basiert) entfaellt.
_PAST_END = date.today() - timedelta(days=30)


def _patches(ml_cur, ml_prev, hrv, acts_cur, acts_prev):
    return (
        patch(
            "src.insights.collect.get_ml_history",
            AsyncMock(side_effect=[ml_cur, ml_prev]),
        ),
        patch("src.insights.collect.get_hrv_trend", AsyncMock(return_value=hrv)),
        patch(
            "src.insights.collect.get_recent_activities",
            AsyncMock(side_effect=[acts_cur, acts_prev]),
        ),
    )


async def test_gather_inputs_aggregates_window_and_skips_glucose_for_past_window():
    ml_cur = {
        "energy_autonomic": [{"value": 80}, {"value": 78}],
        "energy_cognitive": [{"value": 70}],
        "sleep_score_custom": [{"value": 82}],
        "energy_physical": [{"value": 60}],
        "stress_score_custom": [{"value": 40}],
        "body_battery_custom": [{"value": 65}],
    }
    ml_prev = {"energy_autonomic": [{"value": 70}], "energy_cognitive": [{"value": 60}]}
    hrv = [{"hrv_last_night": 58}, {"hrv_last_night": 62}]
    # 19800 s = 5.5 h Trainingsvolumen im aktuellen Fenster.
    acts_cur = [{"duration_seconds": 19800}]
    acts_prev: list[dict] = []
    p1, p2, p3 = _patches(ml_cur, ml_prev, hrv, acts_cur, acts_prev)
    with p1, p2, p3:
        inputs = await gather_inputs(1, _PAST_END)
    by = {i.key: i for i in inputs}
    assert by[MetricKey.READINESS].value == Decimal(
        "75"
    )  # 79*0.6 + 70*0.4 = 75.4 -> 75
    assert by[MetricKey.SLEEP].value == Decimal("82")
    assert by[MetricKey.HRV].value == Decimal("60")
    assert by[MetricKey.TRAINING_VOLUME].value == Decimal("5.5")
    assert MetricKey.TIME_IN_RANGE not in by  # vergangenes Fenster -> kein NOW-Glukose


async def test_gather_inputs_includes_glucose_for_current_window():
    period_end = date.today() - timedelta(days=1)
    p1, p2, p3 = _patches({}, {}, [], [], [])
    with (
        p1,
        p2,
        p3,
        patch(
            "src.insights.collect.get_glucose_stats",
            AsyncMock(return_value={"tir_pct": 75.0}),
        ),
    ):
        inputs = await gather_inputs(1, period_end)
    by = {i.key: i for i in inputs}
    assert by[MetricKey.TIME_IN_RANGE].value == Decimal("75.0")
