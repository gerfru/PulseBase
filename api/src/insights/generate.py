"""Orchestrierung der Wochen-Insight-Generierung (ADR-0003, Schicht 2).

Verkettet ``collect -> build -> assert_no_identifier -> gate``. Liefert nie
ungeprueften Text (Invariante 1); ist der Provider deaktiviert, kommt direkt das
deterministische Fallback. Loggt nur Metadaten — nie Prompt/Response/Werte (C3).
"""

from __future__ import annotations

import time

import structlog

from src.insights.collect import build_weekly_insight, gather_inputs
from src.insights.guard import assert_no_identifier
from src.insights.llm import LlmProvider, get_provider
from src.insights.models import WeeklyInsight
from src.insights.postcheck import GateOutput, arun_gate
from src.insights.prompt import build_prompt
from src.insights.templates import SEGMENTS, fallback_text

logger = structlog.get_logger(__name__)


async def _gate_for_segment(
    insight: WeeklyInsight, segment: str, prov: LlmProvider | None
) -> GateOutput:
    """Ein Segment durchs Gate; ohne Provider direkt das Fallback."""
    if prov is None:
        return GateOutput(
            text=fallback_text(insight, segment),
            generator="fallback_template",
            attempts=0,
        )
    prompt = build_prompt(insight, segment)
    return await arun_gate(lambda: prov.complete(prompt), insight, segment)


async def generate_insight(
    user_id: int,
    iso_year: int,
    iso_week: int,
    segment: str,
    *,
    provider: LlmProvider | None = None,
) -> GateOutput:
    """Erzeugt geprueften Insight-Text fuer (User, Woche, Segment)."""
    inputs = await gather_inputs(user_id, iso_year, iso_week)
    insight = build_weekly_insight(iso_year, iso_week, inputs)
    assert_no_identifier(insight)  # Invariante 2 — vor jedem Prompt

    prov = provider if provider is not None else get_provider()
    start = time.monotonic()
    out = await _gate_for_segment(insight, segment, prov)
    logger.info(
        "insights.generate",
        iso_year=iso_year,
        iso_week=iso_week,
        segment=segment,
        generator=out.generator,
        attempts=out.attempts,
        failures=out.failures,
        latency_ms=round((time.monotonic() - start) * 1000),
    )
    return out


async def generate_all_segments(
    user_id: int,
    iso_year: int,
    iso_week: int,
    *,
    provider: LlmProvider | None = None,
) -> tuple[WeeklyInsight, dict[str, GateOutput]]:
    """Baut das Insight EINMAL und erzeugt geprueften Text fuer alle Segmente."""
    inputs = await gather_inputs(user_id, iso_year, iso_week)
    insight = build_weekly_insight(iso_year, iso_week, inputs)
    assert_no_identifier(insight)  # Invariante 2 — vor jedem Prompt

    prov = provider if provider is not None else get_provider()
    start = time.monotonic()
    outputs = {seg: await _gate_for_segment(insight, seg, prov) for seg in SEGMENTS}
    logger.info(
        "insights.generate_all",
        iso_year=iso_year,
        iso_week=iso_week,
        generators={seg: o.generator for seg, o in outputs.items()},
        latency_ms=round((time.monotonic() - start) * 1000),
    )
    return insight, outputs
