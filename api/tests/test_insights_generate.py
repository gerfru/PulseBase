"""Tests fuer die Generierungs-Orchestrierung (FakeProvider, kein DB/Modell)."""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

from src.insights.collect import MetricInput
from src.insights.generate import generate_insight
from src.insights.models import MetricKey, Unit

# TIME_IN_RANGE 58 (< 70) -> flag low_time_in_range + evidence; trend STABLE.
_INPUTS = [
    MetricInput(key=MetricKey.TIME_IN_RANGE, unit=Unit.PERCENT, value=Decimal("58"))
]
_VALID = "Woche 24: Zielbereich 58 %. Hinweis: kein medizinischer Rat."


class _FakeProvider:
    model = "fake"

    def __init__(self, text: str) -> None:
        self._text = text

    async def complete(self, prompt: str) -> str:
        return self._text


async def test_generate_returns_llm_text_when_valid():
    with patch("src.insights.generate.gather_inputs", AsyncMock(return_value=_INPUTS)):
        out = await generate_insight(
            1, 2026, 24, "hobby", provider=_FakeProvider(_VALID)
        )
    assert out.generator == "llm"


async def test_generate_falls_back_on_bad_llm_output():
    with patch("src.insights.generate.gather_inputs", AsyncMock(return_value=_INPUTS)):
        out = await generate_insight(
            1, 2026, 24, "hobby", provider=_FakeProvider("999 quatsch")
        )
    assert out.generator == "fallback_template"


async def test_generate_falls_back_when_provider_disabled():
    with (
        patch("src.insights.generate.gather_inputs", AsyncMock(return_value=_INPUTS)),
        patch("src.insights.generate.get_provider", return_value=None),
    ):
        out = await generate_insight(1, 2026, 24, "hobby")
    assert out.generator == "fallback_template"
    assert out.attempts == 0
