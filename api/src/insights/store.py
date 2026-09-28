"""Cache-aware Generierung eines Berichts pro Nutzer und Zeitraum."""

from __future__ import annotations

from datetime import date

from src.db.weekly_insights import (
    StoredInsight,
    TextRecord,
    get_weekly_insight,
    save_weekly_insight,
)
from src.insights.generate import generate_insight
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
    insight, out = await generate_insight(user_id, period_end, provider=prov)
    model = prov.model if prov is not None else None
    text = TextRecord(
        body=out.text,
        generator=out.generator,
        model_id=model if out.generator == "llm" else None,
    )
    await save_weekly_insight(user_id, insight, text)

    stored = await get_weekly_insight(user_id, period_end)
    assert stored is not None  # gerade gespeichert
    return stored
