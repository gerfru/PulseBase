"""Schicht-1 Trust-Vertrag fuer KI-Wochen-Insights (ADR-0003).

Reine Datenmodelle — kein LLM, keine DB. Das ``WeeklyInsight`` ist der einzige
Payload, der an das LLM geht, und darf nie einen Identifier tragen
(Security-Invariante 2). Zahlen sind ``Decimal`` (exakte Zahlen-Treue fuer den
binaeren Number-Grounding-Check).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class MetricKey(str, Enum):
    HRV = "hrv"
    GLUCOSE_CV = "glucose_cv"
    TIME_IN_RANGE = "time_in_range"
    TRAINING_LOAD = "training_load"
    # Enrichment (append-only — bestehende Keys nie umbenennen):
    READINESS = "readiness"
    SLEEP = "sleep"
    TRAINING_FORM = "training_form"
    STRESS = "stress"
    BODY_BATTERY = "body_battery"
    TRAINING_VOLUME = "training_volume"


class Unit(str, Enum):
    MS = "ms"
    PERCENT = "%"
    TSS = "TSS"
    MGDL = "mg/dL"
    MMOL = "mmol/L"
    POINTS = "Punkte"  # 0–100-Scores; kein "/100" (würde Number-Grounding stören)
    H = "h"


class Trend(str, Enum):
    UP = "up"
    SLIGHTLY_UP = "slightly_up"
    STABLE = "stable"
    SLIGHTLY_DOWN = "slightly_down"
    DOWN = "down"


_UP_TRENDS = (Trend.UP, Trend.SLIGHTLY_UP)
_DOWN_TRENDS = (Trend.DOWN, Trend.SLIGHTLY_DOWN)


class Metric(BaseModel):
    """Eine gepruefte Kennzahl. Immutable; ``trend`` muss zum Vorzeichen von
    ``change_pct`` passen (Defense in Depth zum Trend-Richtungs-Guard)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: MetricKey
    value: Decimal
    unit: Unit
    change_pct: Decimal | None
    trend: Trend

    @model_validator(mode="after")
    def _trend_matches_change(self) -> Metric:
        if self.change_pct is None:
            return self
        if self.change_pct > 0 and self.trend in _DOWN_TRENDS:
            raise ValueError(
                f"trend {self.trend.value} contradicts positive change_pct"
            )
        if self.change_pct < 0 and self.trend in _UP_TRENDS:
            raise ValueError(
                f"trend {self.trend.value} contradicts negative change_pct"
            )
        return self


class WeeklyInsight(BaseModel):
    """Der Trust-Vertrag fuer ein rollierendes 7-Tage-Fenster. Enthaelt nie einen
    Identifier — ``period_start``/``period_end`` sind eine Zeitspanne, keine Person."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    period_start: date
    period_end: date
    metrics: list[Metric]
    flags: list[str]
    evidence: list[str]
    catalog_version: str
    unavailable: list[MetricKey] = []

    @model_validator(mode="after")
    def _period_order(self) -> WeeklyInsight:
        if self.period_end < self.period_start:
            raise ValueError("period_end must be >= period_start")
        return self

    @field_validator("evidence")
    @classmethod
    def _evidence_in_catalog(cls, v: list[str]) -> list[str]:
        # Lazy import vermeidet einen Import-Zyklus und entkoppelt die Modelle
        # von der Ladereihenfolge des Katalogs (Grounding bei Konstruktion).
        from src.insights.evidence import VALID_EVIDENCE_KEYS

        unknown = [k for k in v if k not in VALID_EVIDENCE_KEYS]
        if unknown:
            raise ValueError(f"unknown evidence keys: {unknown}")
        return v
