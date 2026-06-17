"""Tests fuer den Prompt-Builder (Schicht 2)."""

from datetime import date
from decimal import Decimal

import pytest

from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight
from src.insights.prompt import build_prompt


def _insight(**kw) -> WeeklyInsight:
    base = dict(
        period_start=date(2026, 6, 8),
        period_end=date(2026, 6, 14),
        metrics=[
            Metric(
                key=MetricKey.TIME_IN_RANGE,
                value=Decimal("58"),
                unit=Unit.PERCENT,
                change_pct=Decimal("-4.1"),
                trend=Trend.SLIGHTLY_DOWN,
            )
        ],
        flags=[],
        evidence=[],
        catalog_version="1.0.0",
    )
    base.update(kw)
    return WeeklyInsight(**base)  # type: ignore[arg-type]


def test_prompt_contains_numbers_but_not_disclaimer():
    p = build_prompt(_insight(), "hobby")
    assert "58" in p and "-4.1" in p
    # Disclaimer wird deterministisch angehaengt, NICHT vom Modell verlangt.
    assert "kein medizinischer Rat" not in p
    # Datum/Jahr gehoeren nicht in den Prompt (Number-Grounding-Schutz).
    assert "2026" not in p


def test_prompt_normalizes_numbers():
    # 75.0 muss als "75" erscheinen (sonst kollidiert es mit dem Gate).
    ins = _insight(
        metrics=[
            Metric(
                key=MetricKey.TIME_IN_RANGE,
                value=Decimal("75.0"),
                unit=Unit.PERCENT,
                change_pct=None,
                trend=Trend.STABLE,
            )
        ]
    )
    p = build_prompt(ins, "hobby")
    assert "75 %" in p and "75.0" not in p


def test_prompt_includes_evidence_statement():
    ins = _insight(flags=["low_time_in_range"], evidence=["glucose_tir"])
    p = build_prompt(ins, "pro")
    assert "Evidenz-Hinweise" in p


def test_prompt_uses_label_band_and_context_rule():
    ins = _insight(
        metrics=[
            Metric(
                key=MetricKey.TRAINING_FORM,
                value=Decimal("28"),
                unit=Unit.POINTS,
                change_pct=Decimal("55.6"),
                trend=Trend.UP,
            )
        ]
    )
    p = build_prompt(ins, "pro")
    assert "Trainingsform" in p  # kanonisches Label, nicht der rohe Key
    assert "Niveau: hohe Belastung" in p  # 28 ist niedrig -> Belastung
    assert "im Kontext des Niveaus" in p  # Interpretations-Regel
    assert "training_form" not in p


def test_prompt_unknown_segment_raises():
    with pytest.raises(ValueError):
        build_prompt(_insight(), "enterprise")
