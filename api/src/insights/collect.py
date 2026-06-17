"""Schicht-1-Builder: deterministisches ``WeeklyInsight`` aus bestehenden Reads.

Kein LLM. ``build_weekly_insight`` ist rein und voll testbar; ``gather_inputs``
adaptiert die vorhandenen ``db/``-Funktionen **wochen-gebunden** (ISO-Woche via
``end_date``). Die Tageswerte sind im ml-service bereits fachlich berechnet —
hier wird nur ehrlich aggregiert (Wochen-Mittel) und mit der Vorwoche verglichen
(``change_pct``); keine erfundenen Formeln.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from src.db.activities import get_recent_activities
from src.db.glucose import get_glucose_stats
from src.db.health import get_hrv_trend
from src.db.ml import get_ml_history
from src.insights.evidence import CATALOG_VERSION, VALID_EVIDENCE_KEYS
from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight

_STABLE_BAND = Decimal("2")
_STRONG_BAND = Decimal("10")

# Flag-Schwellen (Werte spiegeln die Produkt-Baender wider).
_LOW_READINESS = Decimal("35")
_LOW_SLEEP = Decimal("50")
_LOW_TRAINING_FORM = Decimal("42")
_HIGH_STRESS = Decimal("60")
_LOW_BODY_BATTERY = Decimal("40")
_VOL_SPIKE_PCT = Decimal("50")
_LOW_TIR_PCT = Decimal("70")

# Flag -> Evidenz-Keys (gegen den bestehenden Katalog gefiltert).
_FLAG_EVIDENCE: dict[str, tuple[str, ...]] = {
    "low_readiness": ("energy_autonomic", "energy_cognitive"),
    "sleep_low": ("sleep_score_custom",),
    "high_training_load": ("energy_physical",),
    "high_stress": ("stress_score_custom",),
    "low_body_battery": ("body_battery_custom",),
    "training_volume_spike": ("acwr_injury_risk",),
    "low_time_in_range": ("glucose_tir",),
}

# ML-Modelle, deren Tages-``value`` (0–100-Score) direkt wochenweise gemittelt wird.
_SCORE_MODELS: tuple[tuple[MetricKey, str], ...] = (
    (MetricKey.SLEEP, "sleep_score_custom"),
    (MetricKey.TRAINING_FORM, "energy_physical"),
    (MetricKey.STRESS, "stress_score_custom"),
    (MetricKey.BODY_BATTERY, "body_battery_custom"),
)


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
    """Deterministische Flag-Erkennung aus fertigen Metriken (Produkt-Schwellen)."""
    by_key = {m.key: m for m in metrics}

    def val(key: MetricKey) -> Decimal | None:
        m = by_key.get(key)
        return m.value if m is not None else None

    flags: list[str] = []
    r = val(MetricKey.READINESS)
    if r is not None and r < _LOW_READINESS:
        flags.append("low_readiness")
    s = val(MetricKey.SLEEP)
    if s is not None and s < _LOW_SLEEP:
        flags.append("sleep_low")
    tf = val(MetricKey.TRAINING_FORM)
    if tf is not None and tf < _LOW_TRAINING_FORM:
        flags.append("high_training_load")
    st = val(MetricKey.STRESS)
    if st is not None and st > _HIGH_STRESS:
        flags.append("high_stress")
    bb = val(MetricKey.BODY_BATTERY)
    if bb is not None and bb < _LOW_BODY_BATTERY:
        flags.append("low_body_battery")
    vol = by_key.get(MetricKey.TRAINING_VOLUME)
    if (
        vol is not None
        and vol.change_pct is not None
        and vol.change_pct > _VOL_SPIKE_PCT
    ):
        flags.append("training_volume_spike")
    tir = val(MetricKey.TIME_IN_RANGE)
    if tir is not None and tir < _LOW_TIR_PCT:
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
    period_start: date,
    period_end: date,
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
        period_start=period_start,
        period_end=period_end,
        metrics=metrics,
        unavailable=unavailable,
        flags=flags,
        evidence=_evidence_for(flags),
        catalog_version=catalog_version,
    )


# --------------------------------------------------------------------------- #
# Wochen-Aggregation aus bestehenden db/-Reads
# --------------------------------------------------------------------------- #


def _dec(value: object, places: str = "1") -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal(places))


def _model_mean(hist: dict, model: str) -> float | None:
    vals = [r["value"] for r in hist.get(model, []) if r.get("value") is not None]
    return sum(vals) / len(vals) if vals else None


def _readiness_mean(hist: dict) -> float | None:
    # Gleiche Gewichtung wie readiness.py: autonom 60 % + kognitiv 40 %.
    auton = _model_mean(hist, "energy_autonomic")
    cog = _model_mean(hist, "energy_cognitive")
    comps = [(v, w) for v, w in ((auton, 0.6), (cog, 0.4)) if v is not None]
    if not comps:
        return None
    total_w = sum(w for _, w in comps)
    return sum(v * w / total_w for v, w in comps)


def _hrv_mean(rows: Sequence[dict]) -> float | None:
    vals = [r["hrv_last_night"] for r in rows if r.get("hrv_last_night") is not None]
    return sum(vals) / len(vals) if vals else None


def _volume_hours(activities: Sequence[dict]) -> float | None:
    secs = [a["duration_seconds"] for a in activities if a.get("duration_seconds")]
    return sum(secs) / 3600.0 if secs else None


async def gather_inputs(user_id: int, period_end: date) -> list[MetricInput]:
    """Sammelt bis zu 7 Metriken fuer das rollierende 7-Tage-Fenster
    [period_end-6 .. period_end] — Mittel + Vorfenster-Delta."""
    prev_end = period_end - timedelta(days=7)

    cur = await get_ml_history(user_id, days=6, end_date=period_end)
    prev = await get_ml_history(user_id, days=6, end_date=prev_end)
    hrv_cur = await get_hrv_trend(user_id, days=6, end_date=period_end)
    hrv_prev = await get_hrv_trend(user_id, days=6, end_date=prev_end)
    acts_cur = await get_recent_activities(user_id, days=7, end_date=period_end)
    acts_prev = await get_recent_activities(user_id, days=7, end_date=prev_end)

    inputs: list[MetricInput] = [
        MetricInput(
            MetricKey.READINESS,
            Unit.POINTS,
            _dec(_readiness_mean(cur)),
            _dec(_readiness_mean(prev)),
        )
    ]
    inputs += [
        MetricInput(
            key,
            Unit.POINTS,
            _dec(_model_mean(cur, model)),
            _dec(_model_mean(prev, model)),
        )
        for key, model in _SCORE_MODELS
    ]
    inputs.append(
        MetricInput(
            MetricKey.HRV, Unit.MS, _dec(_hrv_mean(hrv_cur)), _dec(_hrv_mean(hrv_prev))
        )
    )
    inputs.append(
        MetricInput(
            MetricKey.TRAINING_VOLUME,
            Unit.H,
            _dec(_volume_hours(acts_cur), "0.1"),
            _dec(_volume_hours(acts_prev), "0.1"),
        )
    )
    # Glukose-TIR nutzt eine NOW-basierte Query → nur fuer das aktuelle Fenster
    # sinnvoll; fuer aeltere Fenster weggelassen (sonst falsches Zeitfenster).
    if period_end >= date.today() - timedelta(days=1):
        stats = await get_glucose_stats(user_id, days=7)
        inputs.append(
            MetricInput(
                MetricKey.TIME_IN_RANGE,
                Unit.PERCENT,
                _dec(stats.get("tir_pct"), "0.1"),
            )
        )
    return inputs
