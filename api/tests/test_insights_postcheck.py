"""Tests fuer das fail-secure Output-Gate (P3)."""

from decimal import Decimal

from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight
from src.insights.postcheck import post_check, run_gate


def _insight(**kw) -> WeeklyInsight:
    base = dict(
        iso_year=2026,
        iso_week=24,
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


_DISCLAIMER = "Hinweis: kein medizinischer Rat."


def test_post_check_passes_grounded_text():
    text = f"Woche 24: Zielbereich 58 % (-4.1 %). {_DISCLAIMER}"
    assert post_check(text, _insight(), "hobby").passed


def test_post_check_flags_hallucinated_number():
    text = f"Zielbereich 58 % und HRV 999 ms. {_DISCLAIMER}"
    assert "number_grounding" in post_check(text, _insight(), "hobby").failures


def test_post_check_flags_number_word():
    text = f"Zielbereich knapp 60 %. {_DISCLAIMER}"
    assert "number_words" in post_check(text, _insight(), "hobby").failures


def test_post_check_flags_missing_disclaimer():
    text = "Woche 24: Zielbereich 58 %."
    assert "disclaimer" in post_check(text, _insight(), "hobby").failures


def test_post_check_flags_trend_contradiction():
    # Metrik-Trend ist SLIGHTLY_DOWN, Prosa sagt "gestiegen" (positiv).
    text = f"Der Zielbereich 58 % ist gestiegen. {_DISCLAIMER}"
    assert "trend_direction" in post_check(text, _insight(), "hobby").failures


def test_post_check_flags_free_recommendation_without_evidence():
    text = f"Zielbereich 58 %. Ich empfehle mehr Schlaf. {_DISCLAIMER}"
    assert "evidence_grounding" in post_check(text, _insight(), "hobby").failures


def test_post_check_recommendation_ok_with_evidence():
    insight = _insight(
        metrics=[
            Metric(
                key=MetricKey.TIME_IN_RANGE,
                value=Decimal("58"),
                unit=Unit.PERCENT,
                change_pct=None,
                trend=Trend.STABLE,
            )
        ],
        flags=["low_time_in_range"],
        evidence=["glucose.time_in_range"],
    )
    text = f"Zielbereich 58 %. Ratsam ist eine Anpassung. {_DISCLAIMER}"
    assert "evidence_grounding" not in post_check(text, insight, "hobby").failures


def test_post_check_flags_identifier_leak():
    text = f"Zielbereich 58 %, mailto a@b.com. {_DISCLAIMER}"
    assert "identifier_leak" in post_check(text, _insight(), "hobby").failures


def test_run_gate_returns_llm_text_when_valid():
    good = f"Woche 24: Zielbereich 58 % (-4.1 %). {_DISCLAIMER}"
    out = run_gate(lambda: good, _insight(), "hobby")
    assert out.generator == "llm"
    assert out.attempts == 1


def test_run_gate_falls_back_after_failures():
    out = run_gate(lambda: "halluzinierte 999 zahl", _insight(), "hobby")
    assert out.generator == "fallback_template"
    assert out.attempts == 3
    # Der Fallback selbst besteht den Post-Check.
    assert post_check(out.text, _insight(), "hobby").passed
