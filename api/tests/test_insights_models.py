"""Tests fuer das Schicht-1-Schema (kein I/O)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight

_IDENTIFIER_DENYLIST = {"user", "user_id", "userid", "id", "name", "email", "ip"}


def _metric(**kw) -> Metric:
    base = dict(
        key=MetricKey.HRV,
        value=Decimal("58"),
        unit=Unit.MS,
        change_pct=Decimal("-4.1"),
        trend=Trend.STABLE,
    )
    base.update(kw)
    return Metric(**base)  # type: ignore[arg-type]


def test_no_identifier_fields_on_models():
    for model in (Metric, WeeklyInsight):
        fields = {f.lower() for f in model.model_fields}
        assert not (fields & _IDENTIFIER_DENYLIST), model.__name__


def test_extra_field_forbidden():
    with pytest.raises(ValidationError):
        Metric(
            key=MetricKey.HRV,
            value=Decimal("58"),
            unit=Unit.MS,
            change_pct=None,
            trend=Trend.STABLE,
            user_id=1,  # type: ignore[call-arg]
        )


def test_trend_validator_accepts_consistent():
    assert _metric(change_pct=Decimal("18"), trend=Trend.UP).trend is Trend.UP
    assert _metric(change_pct=Decimal("-18"), trend=Trend.DOWN).trend is Trend.DOWN


def test_trend_validator_rejects_contradiction():
    with pytest.raises(ValidationError):
        _metric(change_pct=Decimal("18"), trend=Trend.DOWN)
    with pytest.raises(ValidationError):
        _metric(change_pct=Decimal("-18"), trend=Trend.SLIGHTLY_UP)


def test_trend_validator_allows_none_change():
    m = _metric(change_pct=None, trend=Trend.UP)
    assert m.change_pct is None


def test_iso_week_range():
    with pytest.raises(ValidationError):
        WeeklyInsight(
            iso_year=2026,
            iso_week=54,
            metrics=[],
            flags=[],
            evidence=[],
            catalog_version="1.0.0",
        )


def test_evidence_validated_against_catalog():
    # Bekannter Key passt, unbekannter wird abgelehnt.
    ok = WeeklyInsight(
        iso_year=2026,
        iso_week=24,
        metrics=[],
        flags=[],
        evidence=["glucose_tir"],
        catalog_version="1.0.0",
    )
    assert ok.evidence == ["glucose_tir"]
    with pytest.raises(ValidationError):
        WeeklyInsight(
            iso_year=2026,
            iso_week=24,
            metrics=[],
            flags=[],
            evidence=["does.not.exist"],
            catalog_version="1.0.0",
        )
