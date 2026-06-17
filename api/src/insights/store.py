"""Cache-aware Generierung (ADR-0003, P5).

``get_or_generate`` liefert die gespeicherte Wochen-Insight oder erzeugt sie
lazy beim ersten Aufruf (alle Segmente, eine Transaktion) und cacht sie.
``force=True`` regeneriert trotz Cache — die Naht fuer die GUI-Regenerierung
(P6 verdrahtet Endpoint + Rate-Limit gegen DoS, Security C5).
"""

from __future__ import annotations

from datetime import date

from src.db.weekly_insights import (
    StoredInsight,
    TextRecord,
    get_weekly_insight,
    save_weekly_insight,
)
from src.insights.generate import generate_all_segments, generate_segment
from src.insights.llm import LlmProvider, get_provider


async def get_or_generate(
    user_id: int,
    period_end: date,
    *,
    force: bool = False,
    provider: LlmProvider | None = None,
) -> StoredInsight:
    if not force:
        cached = await get_weekly_insight(user_id, period_end)
        if cached is not None:
            return cached

    prov = provider if provider is not None else get_provider()
    insight, outputs = await generate_all_segments(user_id, period_end, provider=prov)
    model = prov.model if prov is not None else None
    texts = {
        segment: TextRecord(
            body=out.text,
            generator=out.generator,
            model_id=model if out.generator == "llm" else None,
        )
        for segment, out in outputs.items()
    }
    await save_weekly_insight(user_id, insight, texts)

    stored = await get_weekly_insight(user_id, period_end)
    assert stored is not None  # gerade gespeichert
    return stored


async def get_or_generate_segment(
    user_id: int,
    period_end: date,
    segment: str,
    *,
    force: bool = False,
    provider: LlmProvider | None = None,
) -> StoredInsight:
    """Wie ``get_or_generate``, aber nur fuer EIN Segment — lazy.

    Spart die ~2-min-Erstlatenz: nur das sichtbare Segment wird beim ersten
    Laden generiert; die uebrigen erst bei Bedarf (Tab-Wechsel). Texte werden
    pro Segment idempotent upserted (gemeinsames Insight-Objekt)."""
    if not force:
        cached = await get_weekly_insight(user_id, period_end)
        if cached is not None and segment in cached.texts:
            return cached

    prov = provider if provider is not None else get_provider()
    insight, out = await generate_segment(user_id, period_end, segment, provider=prov)
    model = prov.model if prov is not None else None
    rec = TextRecord(
        body=out.text,
        generator=out.generator,
        model_id=model if out.generator == "llm" else None,
    )
    await save_weekly_insight(user_id, insight, {segment: rec})

    stored = await get_weekly_insight(user_id, period_end)
    assert stored is not None  # gerade gespeichert
    return stored
