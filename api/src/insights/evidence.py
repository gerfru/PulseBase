"""Evidenz fuer KI-Wochen-Insights — Wiederverwendung des kuratierten Katalogs.

Single Source of Truth: ``api/src/data/evidence_catalog.json`` (geladen via
``src.evidence_catalog``), der schon im Dashboard genutzt wird und echte
Primaerzitate traegt. ``VALID_EVIDENCE_KEYS`` speist den ``evidence``-Validator
von ``WeeklyInsight`` (Grounding bei Konstruktion). ``statement_for`` liefert die
erlaubte Kern-Aussage fuer den Prompt, ``caveats_for`` die Leitplanken
(``not_for``/``limitations`` — was NICHT behauptet werden darf, Regulatorik-Guard).
"""

from __future__ import annotations

from src.evidence_catalog import EVIDENCE

# Manuell gepflegte Provenance-Marke; bumpen, wenn sich der fuer Insights
# relevante Katalog-Inhalt aendert (wird pro persistierter Insight gespeichert).
CATALOG_VERSION = "evid-2026-06"

VALID_EVIDENCE_KEYS: frozenset[str] = frozenset(EVIDENCE)


def statement_for(key: str) -> str:
    """Erlaubte Kern-Aussage zu einem Evidenz-Key (summary + intended_use)."""
    entry = EVIDENCE.get(key, {})
    parts = [
        str(entry.get("summary", "")).strip(),
        str(entry.get("intended_use", "")).strip(),
    ]
    return " ".join(p for p in parts if p)


def caveats_for(key: str) -> str:
    """Leitplanken zu einem Evidenz-Key (not_for + limitations)."""
    entry = EVIDENCE.get(key, {})
    parts = [
        str(entry.get("not_for", "")).strip(),
        str(entry.get("limitations", "")).strip(),
    ]
    return " ".join(p for p in parts if p)
