"""Schicht-1-Builder: deterministisches ``WeeklyInsight`` aus bestehenden Reads.

Kein LLM. ``build_weekly_insight`` ist rein und voll testbar; ``gather_inputs``
adaptiert die vorhandenen ``db/``-Funktionen.

Hinweis (ADR-0003 offene Punkte): ``gather_inputs`` verdrahtet in v1 nur
``TIME_IN_RANGE`` (exakt aus ``get_glucose_stats`` verfuegbar). Weitere Metriken
(HRV, Trainingslast-TSS, Glukose-CV) und Vorwochen-Deltas folgen, sobald
wochen-gebundene Queries existieren — bewusst keine erfundenen Formeln.
Falls die Generierung spaeter nach ml-service zieht, wandert dieses Modul mit.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.db.glucose import get_glucose_stats
from src.insights.evidence import CATALOG_VERSION, VALID_EVIDENCE_KEYS
from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight

_STABLE_BAND = Decimal("2")
_STRONG_BAND = Decimal("10")
_SPIKE_PCT = Decimal("30")
_LOW_TIR_PCT = Decimal("70")

# Flag -> Evidenz-Keys (beim Bauen gegen den Katalog gefiltert).
_FLAG_EVIDENCE: dict[str, tuple[str, ...]] = {
    "training_load_spike": ("training.acwr_injury_risk",),
    "low_time_in_range": ("glucose.time_in_range",),
}


@dataclass(frozen=True)
class MetricInput:
    key: MetricKey
    unit: Unit
    value: Decimal | None  # None -> unavailable
    prev_value: Decimal | None = None


def _trend_for(change_pct: Decimal | None) -> Trend:
    if change_pct is None:
        return Trend.STABLE
    mag = abs(change_pct)
    if mag < _STABLE_BAND:
        return Trend.STABLE
    if change_pct > 0:
        return Trend.SLIGHTLY_UP if mag < _STRONG_BAND else Trend.UP
    return Trend.SLIGHTLY_DOWN if mag < _STRONG_BAND else Trend.DOWN


def _change_pct(value: Decimal, prev: Decimal | None) -> Decimal | None:
    if prev is None or prev == 0:
        return None
    return ((value - prev) / prev * Decimal(100)).quantize(Decimal("0.1"))


def _metric_from_input(mi: MetricInput) -> Metric | None:
    if mi.value is None:
        return None
    change = _change_pct(mi.value, mi.prev_value)
    return Metric(
        key=mi.key,
        value=mi.value,
        unit=mi.unit,
        change_pct=change,
        trend=_trend_for(change),
    )


def detect_flags(metrics: list[Metric]) -> list[str]:
    """Deterministische Flag-Erkennung aus fertigen Metriken."""
    flags: list[str] = []
    by_key = {m.key: m for m in metrics}
    tl = by_key.get(MetricKey.TRAINING_LOAD)
    if tl is not None and tl.change_pct is not None and tl.change_pct > _SPIKE_PCT:
        flags.append("training_load_spike")
    tir = by_key.get(MetricKey.TIME_IN_RANGE)
    if tir is not None and tir.value < _LOW_TIR_PCT:
        flags.append("low_time_in_range")
    return flags


def _evidence_for(flags: list[str]) -> list[str]:
    keys: list[str] = []
    for flag in flags:
        for key in _FLAG_EVIDENCE.get(flag, ()):
            if key in VALID_EVIDENCE_KEYS and key not in keys:
                keys.append(key)
    return keys


def build_weekly_insight(
    iso_year: int,
    iso_week: int,
    inputs: list[MetricInput],
    *,
    catalog_version: str = CATALOG_VERSION,
) -> WeeklyInsight:
    """Baut das Trust-Objekt deterministisch aus normalisierten Inputs."""
    metrics: list[Metric] = []
    unavailable: list[MetricKey] = []
    for mi in inputs:
        metric = _metric_from_input(mi)
        if metric is None:
            unavailable.append(mi.key)
        else:
            metrics.append(metric)
    flags = detect_flags(metrics)
    return WeeklyInsight(
        iso_year=iso_year,
        iso_week=iso_week,
        metrics=metrics,
        unavailable=unavailable,
        flags=flags,
        evidence=_evidence_for(flags),
        catalog_version=catalog_version,
    )


async def gather_inputs(
    user_id: int, iso_year: int, iso_week: int
) -> list[MetricInput]:
    """Adapter auf die bestehenden ``db/``-Reads. v1: nur TIME_IN_RANGE."""
    inputs: list[MetricInput] = []
    stats = await get_glucose_stats(user_id, days=7)
    tir = stats.get("tir_pct")
    inputs.append(
        MetricInput(
            key=MetricKey.TIME_IN_RANGE,
            unit=Unit.PERCENT,
            value=Decimal(str(tir)) if tir is not None else None,
        )
    )
    return inputs
