"""Tests fuer das fail-secure Output-Gate (P3)."""

from datetime import date
from decimal import Decimal

from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight
from src.insights.postcheck import arun_gate, post_check, run_gate


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


_DISCLAIMER = "Hinweis: kein medizinischer Rat."


def _report(body: str) -> str:
    return (
        f"Zusammenfassung\nDie Messwerte beschreiben den aktuellen Zeitraum.\n\n"
        f"Kennzahlen\n{body}\n\n"
        f"Einordnung\nEin einzelner Wert erklärt keine Ursache.\n\n"
        f"Hinweis\n{_DISCLAIMER}"
    )


def test_post_check_passes_grounded_text():
    text = _report("Zielbereich 58 % (-4.1 %).")
    assert post_check(text, _insight()).passed


def test_post_check_rejects_missing_or_empty_sections():
    missing = _report("Zielbereich 58 %.").replace("Einordnung\n", "")
    empty = _report("Zielbereich 58 %.").replace(
        "Einordnung\nEin einzelner Wert erklärt keine Ursache.", "Einordnung\n"
    )
    for text in (missing, empty):
        assert "sections" in post_check(text, _insight()).failures


def test_post_check_flags_hallucinated_number():
    text = _report("Zielbereich 58 % und HRV 999 ms.")
    assert "number_grounding" in post_check(text, _insight()).failures


def test_post_check_flags_number_word():
    text = _report("Zielbereich knapp 60 %.")
    assert "number_words" in post_check(text, _insight()).failures


def test_post_check_flags_template_placeholder():
    text = _report("Am [Datum] lag der Zielbereich bei 58 %.")
    assert "placeholder" in post_check(text, _insight()).failures


def test_post_check_flags_missing_disclaimer():
    text = _report("Zielbereich 58 %.").replace(_DISCLAIMER, "")
    assert "disclaimer" in post_check(text, _insight()).failures


def test_post_check_flags_trend_contradiction():
    # Metrik-Trend ist SLIGHTLY_DOWN, Prosa sagt "gestiegen" (positiv).
    text = _report("Der Zielbereich 58 % ist gestiegen.")
    assert "trend_direction" in post_check(text, _insight()).failures


def test_post_check_flags_free_recommendation_without_evidence():
    text = _report("Zielbereich 58 %. Ich empfehle mehr Schlaf.")
    assert "evidence_grounding" in post_check(text, _insight()).failures


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
        evidence=["glucose_tir"],
    )
    text = _report("Zielbereich 58 %. Ratsam ist eine Anpassung.")
    assert "evidence_grounding" not in post_check(text, insight).failures


def test_post_check_flags_identifier_leak():
    text = _report("Zielbereich 58 %, mailto a@b.com.")
    assert "identifier_leak" in post_check(text, _insight()).failures


def test_run_gate_returns_llm_text_when_valid():
    good = _report("Zielbereich 58 % (-4.1 %).")
    out = run_gate(lambda: good, _insight())
    assert out.generator == "llm"
    assert out.attempts == 1


def test_run_gate_falls_back_after_failures():
    out = run_gate(lambda: "halluzinierte 999 zahl", _insight())
    assert out.generator == "fallback_template"
    assert out.attempts == 3
    # Der Fallback selbst besteht den Post-Check.
    assert post_check(out.text, _insight()).passed


# --- arun_gate (async) ----------------------------------------------------- #


async def test_arun_gate_returns_llm_when_valid():
    good = _report("Zielbereich 58 % (-4.1 %).")

    async def gen() -> str:
        return good

    out = await arun_gate(gen, _insight())
    assert out.generator == "llm"
    assert out.attempts == 1


async def test_arun_gate_falls_back_after_failures():
    async def gen() -> str:
        return "halluzinierte 999 zahl"

    out = await arun_gate(gen, _insight())
    assert out.generator == "fallback_template"
    assert out.attempts == 3


async def test_arun_gate_falls_back_on_provider_error():
    async def gen() -> str:
        raise RuntimeError("boom")

    out = await arun_gate(gen, _insight())
    assert out.generator == "fallback_template"
    assert "provider_error" in out.failures
