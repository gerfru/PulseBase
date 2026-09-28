"""Praesentations-Bausteine: Disclaimer und deterministischer Fallback.

Der Fallback-Text ist zahlen-treu und post-check-konform — er wird ausgeliefert,
wenn das LLM den Riegel wiederholt nicht besteht (ADR-0003, Security C1).
Hier liegt die Single Source of Truth fuer die Disclaimer-Strings, die der
Post-Check (``guard``) ebenfalls prueft.
"""

from __future__ import annotations

from src.insights.bands import band_label
from src.insights.models import MetricKey, Trend, WeeklyInsight

DISCLAIMER = "Hinweis: kein medizinischer Rat."

METRIC_LABEL: dict[MetricKey, str] = {
    MetricKey.READINESS: "Erholung (Readiness)",
    MetricKey.SLEEP: "Schlaf",
    MetricKey.TRAINING_FORM: "Trainingsform",
    MetricKey.STRESS: "Stress",
    MetricKey.BODY_BATTERY: "Body Battery",
    MetricKey.HRV: "HRV",
    MetricKey.TRAINING_VOLUME: "Trainingsvolumen",
    MetricKey.TIME_IN_RANGE: "Zeit im Zielbereich",
    MetricKey.GLUCOSE_CV: "Glukose-Variabilitaet",
    MetricKey.TRAINING_LOAD: "Trainingslast",
}

_TREND_WORD: dict[Trend, str] = {
    Trend.UP: "gestiegen",
    Trend.SLIGHTLY_UP: "leicht gestiegen",
    Trend.STABLE: "stabil",
    Trend.SLIGHTLY_DOWN: "leicht gesunken",
    Trend.DOWN: "gesunken",
}


def _format_decimal(value: object) -> str:
    # Punkt-Notation ohne Exponent/ueberfluessige Nullen; deckt sich mit einer
    # der von ``allowed_number_tokens`` erzeugten Varianten.
    from decimal import Decimal

    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return str(value)


def fallback_text(insight: WeeklyInsight) -> str:
    """Deterministischer, post-check-konformer Standardtext (kein LLM).

    Nennt nur Zahlen aus dem Objekt, vermeidet Hedging-Woerter und
    Richtungs-Aussagen, und enthaelt den Disclaimer.
    """
    metric_lines = []
    level_lines = []
    for m in insight.metrics:
        val = _format_decimal(m.value)
        label = METRIC_LABEL.get(m.key, m.key.value)
        line = f"- {label}: {val} {m.unit.value}."
        if m.change_pct is not None:
            line += f" Veränderung: {_format_decimal(m.change_pct)} %."
        line += f" Entwicklung: {_TREND_WORD[m.trend]}."
        metric_lines.append(line)
        level = band_label(m.key, m.value)
        if level is not None:
            level_lines.append(
                f"{label}: Das Niveau liegt laut hinterlegter Skala im Bereich {level}."
            )

    if metric_lines:
        summary = (
            "Die Auswertung fasst die verfügbaren Kennzahlen des aktuellen Zeitraums "
            "und ihre Entwicklung gegenüber dem vorherigen Zeitraum zusammen."
        )
        metrics = "\n".join(metric_lines)
        interpretation = (
            ("\n".join(level_lines) + "\n" if level_lines else "")
            + "Die Niveau-Einordnung verwendet nur die hinterlegten Skalen. "
            "Ein einzelner Trend erklärt keine Ursache und ist keine medizinische Bewertung."
        )
    else:
        summary = "Für den aktuellen Zeitraum liegen nicht genügend Daten für eine Auswertung vor."
        metrics = "Keine Kennzahlen verfügbar."
        interpretation = (
            "Ohne ausreichende Messwerte ist keine Einordnung der Entwicklung möglich."
        )

    return (
        f"Zusammenfassung\n{summary}\n\n"
        f"Kennzahlen\n{metrics}\n\n"
        f"Einordnung\n{interpretation}\n\n"
        f"Hinweis\n{DISCLAIMER}"
    )
