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
from src.insights.generate import generate_all_segments
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
