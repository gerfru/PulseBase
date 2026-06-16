"""Deterministische Basis-Riegel fuer KI-Wochen-Insights (ADR-0003, Security C1).

Kein LLM, keine DB. Zwei Aufgaben:

* ``assert_no_identifier`` — Input-PII-Gate (Invariante 2), vor jedem LLM-Call.
* ``allowed_number_tokens`` — erlaubte Zahl-Varianten (inkl. deutschem Komma);
  Grundlage des Number-Grounding-Checks.

Das eigentliche Output-Gate (``post_check`` / ``run_gate``) liegt in
``postcheck.py`` (P3, eigener PR) und baut auf diesen Funktionen auf.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

from src.insights.models import WeeklyInsight

# --------------------------------------------------------------------------- #
# Identifier-Gate (Invariante 2)
# --------------------------------------------------------------------------- #

_IDENTIFIER_KEYS = frozenset(
    {
        "user",
        "user_id",
        "userid",
        "id",
        "name",
        "email",
        "mail",
        "ip",
        "ip_hash",
        "phone",
        "address",
    }
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def assert_no_identifier(obj: object) -> None:
    """Wirft ``ValueError``, wenn ``obj`` (Modell/dict/list) rekursiv einen
    Identifier-Key oder einen E-Mail-foermigen Wert enthaelt."""
    if isinstance(obj, BaseModel):
        obj = obj.model_dump(mode="python")
    _scan(obj)


def _scan(node: object) -> None:
    if isinstance(node, dict):
        for key, val in node.items():
            if isinstance(key, str) and key.lower() in _IDENTIFIER_KEYS:
                raise ValueError(f"identifier key not allowed: {key!r}")
            _scan(val)
    elif isinstance(node, (list, tuple, set)):
        for item in node:
            _scan(item)
    elif isinstance(node, str):
        if EMAIL_RE.search(node):
            raise ValueError("e-mail-shaped value not allowed")


# --------------------------------------------------------------------------- #
# Erlaubte Zahl-Varianten (Number-Grounding)
# --------------------------------------------------------------------------- #


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")


def number_variants(value: Decimal) -> set[str]:
    """Alle zulaessigen Schreibweisen einer Zahl: Punkt- und Komma-Variante,
    signiert (ASCII- und Unicode-Minus) und ganzzahlig gerundet."""
    mag = abs(value)
    plain = _plain(mag)
    variants = {plain, plain.replace(".", ",")}
    variants.add(str(int(mag.to_integral_value(rounding=ROUND_HALF_UP))))
    if value < 0:
        signed = set()
        for v in variants:
            signed.add(f"-{v}")
            signed.add(f"−{v}")  # U+2212 MINUS SIGN
        variants |= signed
    return variants


def allowed_number_tokens(insight: WeeklyInsight) -> set[str]:
    """Alle Zahl-Strings, die im Text vorkommen DUERFEN — Werte und
    Aenderungen der Metriken plus Jahr/Woche."""
    tokens: set[str] = {str(insight.iso_year), str(insight.iso_week)}
    for m in insight.metrics:
        tokens |= number_variants(m.value)
        if m.change_pct is not None:
            tokens |= number_variants(m.change_pct)
    return tokens
