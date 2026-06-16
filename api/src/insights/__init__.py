"""KI-Wochen-Insights — Schicht 1 (deterministischer Kern) + Safety-Gate.

Siehe docs/adr/0003-ai-weekly-insights.md. Kein LLM, keine DB in diesem Package
ausser den Read-Funktionen, die ``collect`` wiederverwendet. Das ``WeeklyInsight``
ist der einzige LLM-Payload und enthaelt nie einen Identifier (Security-Invariante 2).
"""

from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight

__all__ = ["Metric", "MetricKey", "Trend", "Unit", "WeeklyInsight"]
