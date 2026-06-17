"""Prompt-Bau fuer die Erklaer-Schicht (ADR-0003, Schicht 2).

Baut den deutschen Prompt strikt aus dem ``WeeklyInsight`` + Evidenz-Katalog.
``assert_no_identifier`` laeuft VOR jedem Prompt (Invariante 2). Zahlen werden
in derselben normalisierten Form gerendert, die ``allowed_number_tokens``
akzeptiert — sonst wuerde ein vom Modell kopiertes ``75.0`` das Gate verfehlen.
"""

from __future__ import annotations

from decimal import Decimal

from src.insights.evidence import CATALOG
from src.insights.guard import assert_no_identifier
from src.insights.models import Metric, WeeklyInsight
from src.insights.templates import SEGMENT_DISCLAIMERS

_SEGMENT_TONE: dict[str, str] = {
    "hobby": "kurz, motivierend, alltagssprachlich",
    "pro": "sachlich-knapp, mit Zahlen und Evidenz (fuer Trainer/Health-Pros)",
    "profi": "praezise und fachlich (fuer Profi-Sportler und Staff)",
}


def _num(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _metric_line(m: Metric) -> str:
    base = f"- {m.key.value}: {_num(m.value)} {m.unit.value}"
    if m.change_pct is not None:
        return f"{base}, Aenderung {_num(m.change_pct)} % ({m.trend.value})"
    return f"{base} ({m.trend.value})"


def build_prompt(insight: WeeklyInsight, segment: str) -> str:
    if segment not in SEGMENT_DISCLAIMERS:
        raise ValueError(f"unknown segment: {segment!r}")
    assert_no_identifier(insight)  # Invariante 2 — vor jedem Prompt

    # Der Disclaimer wird deterministisch angehaengt (siehe generate.py) — nicht
    # vom Modell verlangt, da es ihn unzuverlaessig woertlich reproduziert.
    parts: list[str] = [
        "Du bist ein Gesundheits-Assistent. Schreibe eine kurze Wochen-Auswertung.",
        f"Tonlage: {_SEGMENT_TONE[segment]}.",
        "",
        "REGELN (strikt einhalten):",
        "- Verwende AUSSCHLIESSLICH die unten genannten Zahlen. Erfinde keine Zahlen.",
        "- Keine vagen Mengen wie 'knapp', 'fast', 'etwa', 'rund', 'Haelfte'.",
        "- Keine individuelle medizinische Empfehlung; nutze nur die Evidenz-Hinweise.",
        "- Kein Disclaimer noetig — der wird automatisch ergaenzt.",
        "",
        f"Woche {insight.iso_week}/{insight.iso_year}.",
        "Kennzahlen:",
    ]
    parts += [_metric_line(m) for m in insight.metrics] or ["- (keine Kennzahlen)"]

    evidence_lines = [
        f"- {CATALOG.entries[k].statement}"
        for k in insight.evidence
        if k in CATALOG.entries
    ]
    if evidence_lines:
        parts += ["", "Evidenz-Hinweise (nur diese verwenden):", *evidence_lines]
    if insight.unavailable:
        keys = ", ".join(k.value for k in insight.unavailable)
        parts += ["", f"Keine Daten fuer: {keys}."]
    return "\n".join(parts)
