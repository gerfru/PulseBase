"""Orchestrierung der Wochen-Insight-Generierung (ADR-0003, Schicht 2).

Verkettet ``collect -> build -> assert_no_identifier -> gate``. Liefert nie
ungeprueften Text (Invariante 1); ist der Provider deaktiviert, kommt direkt das
deterministische Fallback. Loggt nur Metadaten — nie Prompt/Response/Werte (C3).
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import structlog

from src.insights.collect import build_weekly_insight, gather_inputs
from src.insights.guard import assert_no_identifier
from src.insights.llm import LlmProvider, get_provider
from src.insights.models import WeeklyInsight
from src.insights.postcheck import GateOutput, arun_gate
from src.insights.prompt import build_prompt
from src.insights.templates import SEGMENT_DISCLAIMERS, SEGMENTS, fallback_text

logger = structlog.get_logger(__name__)


async def _gate_for_segment(
    insight: WeeklyInsight, segment: str, prov: LlmProvider | None
) -> GateOutput:
    """Ein Segment durchs Gate; ohne Provider direkt das Fallback.

    Der Disclaimer wird deterministisch an die LLM-Ausgabe angehaengt (statt vom
    Modell verlangt) — so ist er rechtlich garantiert vorhanden und der Riegel
    erreichbar."""
    if prov is None:
        return GateOutput(
            text=fallback_text(insight, segment),
            generator="fallback_template",
            attempts=0,
        )
    prompt = build_prompt(insight, segment)
    disclaimer = SEGMENT_DISCLAIMERS[segment]

    async def _generate() -> str:
        raw = await prov.complete(prompt)
        return f"{raw.strip()} {disclaimer}"

    return await arun_gate(_generate, insight, segment)


async def generate_insight(
    user_id: int,
    period_end: date,
    segment: str,
    *,
    provider: LlmProvider | None = None,
) -> GateOutput:
    """Erzeugt geprueften Insight-Text fuer (User, Fenster, Segment)."""
    inputs = await gather_inputs(user_id, period_end)
    insight = build_weekly_insight(period_end - timedelta(days=6), period_end, inputs)
    assert_no_identifier(insight)  # Invariante 2 — vor jedem Prompt

    prov = provider if provider is not None else get_provider()
    start = time.monotonic()
    out = await _gate_for_segment(insight, segment, prov)
    logger.info(
        "insights.generate",
        period_end=period_end.isoformat(),
        segment=segment,
        generator=out.generator,
        attempts=out.attempts,
        failures=out.failures,
        latency_ms=round((time.monotonic() - start) * 1000),
    )
    return out


async def generate_all_segments(
    user_id: int,
    period_end: date,
    *,
    provider: LlmProvider | None = None,
) -> tuple[WeeklyInsight, dict[str, GateOutput]]:
    """Baut das Insight EINMAL und erzeugt geprueften Text fuer alle Segmente."""
    inputs = await gather_inputs(user_id, period_end)
    insight = build_weekly_insight(period_end - timedelta(days=6), period_end, inputs)
    assert_no_identifier(insight)  # Invariante 2 — vor jedem Prompt

    prov = provider if provider is not None else get_provider()
    start = time.monotonic()
    outputs = {seg: await _gate_for_segment(insight, seg, prov) for seg in SEGMENTS}
    logger.info(
        "insights.generate_all",
        period_end=period_end.isoformat(),
        generators={seg: o.generator for seg, o in outputs.items()},
        # Nur Riegel-Namen (z.B. "disclaimer") — kein Health-Payload (C3).
        failures={seg: list(o.failures) for seg, o in outputs.items() if o.failures},
        attempts={seg: o.attempts for seg, o in outputs.items()},
        latency_ms=round((time.monotonic() - start) * 1000),
    )
    return insight, outputs
