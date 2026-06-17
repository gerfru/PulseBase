"""Niveau-Einordnung (Band-Label) je Metrik — spiegelt die bestehenden
Produkt-Schwellen (Dashboard/Hilfe).

Gibt dem LLM den **Niveau-Kontext**, damit ein Anstieg/Abfall richtig gerahmt
wird: ein Anstieg bei niedrigem ``training_form`` heisst „beginnende Erholung",
nicht „gute Form". Reine Interpretation — kein Wert wird veraendert.
"""

from __future__ import annotations

from decimal import Decimal

from src.insights.models import MetricKey

# (untere Schwelle inklusive, Label) — absteigend; das erste passende greift.
_BANDS: dict[MetricKey, tuple[tuple[Decimal, str], ...]] = {
    MetricKey.READINESS: (
        (Decimal("75"), "gut erholt"),
        (Decimal("55"), "in Ordnung"),
        (Decimal("35"), "erholungsbeduerftig"),
        (Decimal("0"), "erschoepft"),
    ),
    MetricKey.SLEEP: (
        (Decimal("75"), "gut"),
        (Decimal("50"), "okay"),
        (Decimal("0"), "schlecht"),
    ),
    MetricKey.TRAINING_FORM: (
        (Decimal("65"), "frisch/erholt"),
        (Decimal("42"), "ausgeglichen"),
        (Decimal("0"), "hohe Belastung"),
    ),
    MetricKey.BODY_BATTERY: (
        (Decimal("75"), "gut"),
        (Decimal("40"), "ausreichend"),
        (Decimal("0"), "erschoepft"),
    ),
    MetricKey.TIME_IN_RANGE: (
        (Decimal("70"), "im Zielbereich"),
        (Decimal("0"), "unter Zielbereich"),
    ),
}

# Stress ist invertiert (niedriger = besser).
_STRESS_BANDS: tuple[tuple[Decimal, str], ...] = (
    (Decimal("60"), "hoch"),
    (Decimal("30"), "moderat"),
    (Decimal("0"), "niedrig"),
)


def band_label(key: MetricKey, value: Decimal) -> str | None:
    """Niveau-Label fuer (Metrik, Wert) oder ``None`` (HRV/Volumen: kein fixes Band)."""
    bands = _STRESS_BANDS if key is MetricKey.STRESS else _BANDS.get(key)
    if bands is None:
        return None
    for lower, label in bands:
        if value >= lower:
            return label
    return None
