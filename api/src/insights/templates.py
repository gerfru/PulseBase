"""Praesentations-Bausteine: Segmente, Disclaimer, deterministisches Fallback.

Der Fallback-Text ist zahlen-treu und post-check-konform — er wird ausgeliefert,
wenn das LLM den Riegel wiederholt nicht besteht (ADR-0003, Security C1).
Hier liegt die Single Source of Truth fuer die Disclaimer-Strings, die der
Post-Check (``guard``) ebenfalls prueft.
"""

from __future__ import annotations

from src.insights.models import Trend, WeeklyInsight

SEGMENTS = ("hobby", "pro", "profi")

# Disclaimer-Strings je Segment. Muessen exakt im Text vorkommen (Post-Check
# ``_check_disclaimer``) und werden vom Fallback angehaengt.
SEGMENT_DISCLAIMERS: dict[str, str] = {
    "hobby": "Hinweis: kein medizinischer Rat.",
    "pro": "Entscheidungsunterstützung, keine medizinische Diagnose.",
    "profi": "Entscheidungsunterstützung, keine medizinische Diagnose.",
}

_TREND_WORD: dict[Trend, str] = {
    Trend.UP: "hoeher",
    Trend.SLIGHTLY_UP: "leicht hoeher",
    Trend.STABLE: "stabil",
    Trend.SLIGHTLY_DOWN: "leicht niedriger",
    Trend.DOWN: "niedriger",
}


def _format_decimal(value: object) -> str:
    # Punkt-Notation ohne Exponent/ueberfluessige Nullen; deckt sich mit einer
    # der von ``allowed_number_tokens`` erzeugten Varianten.
    from decimal import Decimal

    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return str(value)


def fallback_text(insight: WeeklyInsight, segment: str) -> str:
    """Deterministischer, post-check-konformer Standardtext (kein LLM).

    Nennt nur Zahlen aus dem Objekt, vermeidet Hedging-Woerter und
    Richtungs-Aussagen, und enthaelt den Segment-Disclaimer.
    """
    if segment not in SEGMENT_DISCLAIMERS:
        raise ValueError(f"unknown segment: {segment!r}")

    disclaimer = SEGMENT_DISCLAIMERS[segment]
    if not insight.metrics:
        return (
            f"Fuer Woche {insight.iso_week} liegen zu wenige Daten fuer eine "
            f"Auswertung vor. {disclaimer}"
        )

    parts = []
    for m in insight.metrics:
        val = _format_decimal(m.value)
        parts.append(f"{m.key.value}: {val} {m.unit.value} ({_TREND_WORD[m.trend]})")
    body = "; ".join(parts)
    return f"Woche {insight.iso_week}: {body}. {disclaimer}"
