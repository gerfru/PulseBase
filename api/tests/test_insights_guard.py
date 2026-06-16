"""Tests fuer die Riegel: Identifier, Number-Tokens, Post-Check, Gate."""

from decimal import Decimal

import pytest

from src.insights.guard import (
    allowed_number_tokens,
    assert_no_identifier,
    post_check,
    run_gate,
)
from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight


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


# --- assert_no_identifier -------------------------------------------------- #


def test_assert_no_identifier_passes_clean_object():
    assert_no_identifier(_insight())  # must not raise


def test_assert_no_identifier_catches_key():
    with pytest.raises(ValueError):
        assert_no_identifier({"metrics": [{"user_id": 1}]})


def test_assert_no_identifier_catches_email_value():
    with pytest.raises(ValueError):
        assert_no_identifier({"note": "contact me at a@b.com"})


# --- allowed_number_tokens ------------------------------------------------- #


def test_allowed_number_tokens_includes_comma_and_sign():
    tokens = allowed_number_tokens(_insight())
    assert "58" in tokens
    assert "4.1" in tokens and "4,1" in tokens
    assert "-4.1" in tokens and "−4,1" in tokens
    assert "24" in tokens  # iso_week


# --- post_check riegels ---------------------------------------------------- #

_DISCLAIMER = "Hinweis: kein medizinischer Rat."


def test_post_check_passes_grounded_text():
    text = f"Woche 24: Zielbereich 58 % (-4.1 %). {_DISCLAIMER}"
    assert post_check(text, _insight(), "hobby").passed


def test_post_check_flags_hallucinated_number():
    text = f"Zielbereich 58 % und HRV 999 ms. {_DISCLAIMER}"
    result = post_check(text, _insight(), "hobby")
    assert "number_grounding" in result.failures


def test_post_check_flags_number_word():
    text = f"Zielbereich knapp 60 %. {_DISCLAIMER}"
    result = post_check(text, _insight(), "hobby")
    assert "number_words" in result.failures


def test_post_check_flags_missing_disclaimer():
    text = "Woche 24: Zielbereich 58 %."
    result = post_check(text, _insight(), "hobby")
    assert "disclaimer" in result.failures


def test_post_check_flags_trend_contradiction():
    # Metrik-Trend ist SLIGHTLY_DOWN, Prosa sagt "gestiegen" (positiv).
    text = f"Der Zielbereich 58 % ist gestiegen. {_DISCLAIMER}"
    result = post_check(text, _insight(), "hobby")
    assert "trend_direction" in result.failures


def test_post_check_flags_free_recommendation_without_evidence():
    text = f"Zielbereich 58 %. Ich empfehle mehr Schlaf. {_DISCLAIMER}"
    result = post_check(text, _insight(), "hobby")
    assert "evidence_grounding" in result.failures


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
    result = post_check(text, insight, "hobby")
    assert "evidence_grounding" not in result.failures


def test_post_check_flags_identifier_leak():
    text = f"Zielbereich 58 %, mailto a@b.com. {_DISCLAIMER}"
    result = post_check(text, _insight(), "hobby")
    assert "identifier_leak" in result.failures


# --- run_gate -------------------------------------------------------------- #


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
