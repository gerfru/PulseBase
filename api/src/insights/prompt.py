"""Prompt-Bau fuer die Erklaer-Schicht (ADR-0003, Schicht 2).

Baut den deutschen Prompt strikt aus dem ``WeeklyInsight`` + Evidenz-Katalog.
``assert_no_identifier`` laeuft VOR jedem Prompt (Invariante 2). Zahlen werden
in derselben normalisierten Form gerendert, die ``allowed_number_tokens``
akzeptiert — sonst wuerde ein vom Modell kopiertes ``75.0`` das Gate verfehlen.
"""

from __future__ import annotations

from decimal import Decimal

from src.insights.bands import band_label
from src.insights.evidence import VALID_EVIDENCE_KEYS, caveats_for, statement_for
from src.insights.guard import assert_no_identifier
from src.insights.models import Metric, MetricKey, WeeklyInsight
from src.insights.templates import SEGMENT_DISCLAIMERS

_SEGMENT_TONE: dict[str, str] = {
    "hobby": "kurz, motivierend, alltagssprachlich",
    "pro": "sachlich-knapp, mit Zahlen und Evidenz (fuer Trainer/Health-Pros)",
    "profi": "praezise und fachlich (fuer Profi-Sportler und Staff)",
}

# Kanonische deutsche Labels (konsistent mit dem Dashboard) — sonst erfindet das
# Modell eigene Bezeichnungen ("Motivationshoehe" etc.).
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


def _num(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _metric_line(m: Metric) -> str:
    label = METRIC_LABEL.get(m.key, m.key.value)
    base = f"- {label}: {_num(m.value)} {m.unit.value}"
    if m.change_pct is not None:
        base += f", Aenderung {_num(m.change_pct)} %"
    band = band_label(m.key, m.value)
    if band is not None:
        base += f" — Niveau: {band}"
    return base


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
        "- Nutze die kanonischen Bezeichnungen der Kennzahlen; erfinde keine neuen.",
        "- 'Niveau' zeigt das aktuelle Level. Rahme einen Anstieg/Abfall IMMER im "
        "Kontext des Niveaus: ein Anstieg bei niedrigem Niveau ist 'beginnende "
        "Erholung', nicht 'gut'; ein Wert kann steigen UND trotzdem niedrig sein.",
        "- Keine vagen Mengen wie 'knapp', 'fast', 'etwa', 'rund', 'Haelfte'.",
        "- Keine individuelle medizinische Empfehlung; nutze nur die Evidenz-Hinweise.",
        "- Kein Disclaimer noetig — der wird automatisch ergaenzt.",
        "",
        f"Woche {insight.iso_week}/{insight.iso_year}.",
        "Kennzahlen:",
    ]
    parts += [_metric_line(m) for m in insight.metrics] or ["- (keine Kennzahlen)"]

    ev_keys = [k for k in insight.evidence if k in VALID_EVIDENCE_KEYS]
    statements = [f"- {statement_for(k)}" for k in ev_keys if statement_for(k)]
    if statements:
        parts += ["", "Evidenz-Hinweise (nur diese verwenden):", *statements]
    caveats = [f"- {caveats_for(k)}" for k in ev_keys if caveats_for(k)]
    if caveats:
        parts += ["", "Beachte (NICHT behaupten):", *caveats]
    if insight.unavailable:
        keys = ", ".join(k.value for k in insight.unavailable)
        parts += ["", f"Keine Daten fuer: {keys}."]
    return "\n".join(parts)
