"""Tests fuer die Generierungs-Orchestrierung (FakeProvider, kein DB/Modell)."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from src.insights.collect import MetricInput
from src.insights.generate import (
    generate_all_segments,
    generate_insight,
    generate_segment,
)
from src.insights.models import MetricKey, Unit
from src.insights.templates import SEGMENTS

_END = date(2026, 6, 14)

# TIME_IN_RANGE 58 (< 70) -> flag low_time_in_range + evidence; trend STABLE.
_INPUTS = [
    MetricInput(key=MetricKey.TIME_IN_RANGE, unit=Unit.PERCENT, value=Decimal("58"))
]
_VALID = "Zielbereich 58 %. Hinweis: kein medizinischer Rat."


class _FakeProvider:
    model = "fake"

    def __init__(self, text: str) -> None:
        self._text = text

    async def complete(self, prompt: str) -> str:
        return self._text


async def test_generate_returns_llm_text_when_valid():
    with patch("src.insights.generate.gather_inputs", AsyncMock(return_value=_INPUTS)):
        out = await generate_insight(1, _END, "hobby", provider=_FakeProvider(_VALID))
    assert out.generator == "llm"


async def test_generate_segment_returns_insight_and_output():
    with patch("src.insights.generate.gather_inputs", AsyncMock(return_value=_INPUTS)):
        insight, out = await generate_segment(
            1, _END, "hobby", provider=_FakeProvider(_VALID)
        )
    assert insight.period_end == _END
    assert out.generator == "llm"


async def test_generate_falls_back_on_bad_llm_output():
    with patch("src.insights.generate.gather_inputs", AsyncMock(return_value=_INPUTS)):
        out = await generate_insight(
            1, _END, "hobby", provider=_FakeProvider("999 quatsch")
        )
    assert out.generator == "fallback_template"


async def test_generate_falls_back_when_provider_disabled():
    with (
        patch("src.insights.generate.gather_inputs", AsyncMock(return_value=_INPUTS)),
        patch("src.insights.generate.get_provider", return_value=None),
    ):
        out = await generate_insight(1, _END, "hobby")
    assert out.generator == "fallback_template"
    assert out.attempts == 0


async def test_generate_all_segments_builds_once_for_all_segments():
    with (
        patch("src.insights.generate.gather_inputs", AsyncMock(return_value=_INPUTS)),
        patch("src.insights.generate.get_provider", return_value=None),
    ):
        insight, outputs = await generate_all_segments(1, _END)
    assert set(outputs) == set(SEGMENTS)
    assert all(o.generator == "fallback_template" for o in outputs.values())
    assert insight.period_end == _END
