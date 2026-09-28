"""Tests fuer die Generierungs-Orchestrierung (FakeProvider, kein DB/Modell)."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from src.insights.collect import MetricInput
from src.insights.generate import generate_insight
from src.insights.models import MetricKey, Unit

_END = date(2026, 6, 14)

# TIME_IN_RANGE 58 (< 70) -> flag low_time_in_range + evidence; trend STABLE.
_INPUTS = [
    MetricInput(key=MetricKey.TIME_IN_RANGE, unit=Unit.PERCENT, value=Decimal("58"))
]
_VALID = (
    "Zusammenfassung\nDie Kennzahl beschreibt den aktuellen Zeitraum.\n\n"
    "Kennzahlen\nZeit im Zielbereich: 58 %.\n\n"
    "Einordnung\nEin einzelner Wert erklärt keine Ursache."
)


class _FakeProvider:
    model = "fake"

    def __init__(self, text: str) -> None:
        self._text = text

    async def complete(self, prompt: str) -> str:
        return self._text


async def test_generate_returns_llm_text_when_valid():
    with patch("src.insights.generate.gather_inputs", AsyncMock(return_value=_INPUTS)):
        insight, out = await generate_insight(1, _END, provider=_FakeProvider(_VALID))
    assert insight.period_end == _END
    assert out.generator == "llm"


async def test_generate_falls_back_on_bad_llm_output():
    with patch("src.insights.generate.gather_inputs", AsyncMock(return_value=_INPUTS)):
        _, out = await generate_insight(1, _END, provider=_FakeProvider("999 quatsch"))
    assert out.generator == "fallback_template"


async def test_generate_falls_back_when_provider_disabled():
    with (
        patch("src.insights.generate.gather_inputs", AsyncMock(return_value=_INPUTS)),
        patch("src.insights.generate.get_provider", return_value=None),
    ):
        _, out = await generate_insight(1, _END)
    assert out.generator == "fallback_template"
    assert out.attempts == 0
