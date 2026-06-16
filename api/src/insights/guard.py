"""Deterministische Riegel fuer KI-Wochen-Insights (ADR-0003, Security C1).

Kein LLM, keine DB. Drei Aufgaben:

* ``assert_no_identifier`` — Input-PII-Gate (Invariante 2), vor jedem LLM-Call.
* ``allowed_number_tokens`` — erlaubte Zahl-Varianten (inkl. deutschem Komma).
* ``post_check`` / ``run_gate`` — fail-secure Output-Gate; faengt halluzinierte
  Zahlen, Hedging-Woerter, Trend-Widersprueche, fehlende Disclaimer u.a. ab.
  Bei wiederholtem Fail wird der deterministische Fallback ausgeliefert.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

from src.insights.models import Trend, WeeklyInsight
from src.insights.templates import SEGMENT_DISCLAIMERS, fallback_text

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
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


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
        if _EMAIL_RE.search(node):
            raise ValueError("e-mail-shaped value not allowed")


# --------------------------------------------------------------------------- #
# Erlaubte Zahl-Varianten (Number-Grounding)
# --------------------------------------------------------------------------- #


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _number_variants(value: Decimal) -> set[str]:
    mag = abs(value)
    plain = _plain(mag)
    variants = {plain, plain.replace(".", ",")}
    rounded = str(int(mag.to_integral_value(rounding=ROUND_HALF_UP)))
    variants.add(rounded)
    if value < 0:
        signed = set()
        for v in variants:
            signed.add(f"-{v}")
            signed.add(f"−{v}")  # U+2212 MINUS SIGN
        variants |= signed
    return variants


def allowed_number_tokens(insight: WeeklyInsight) -> set[str]:
    """Alle Zahl-Strings, die im Text vorkommen DUERFEN — Werte und
    Aenderungen der Metriken plus Jahr/Woche, jeweils mit Punkt- und
    Komma-Variante, signiert und ganzzahlig gerundet."""
    tokens: set[str] = {str(insight.iso_year), str(insight.iso_week)}
    for m in insight.metrics:
        tokens |= _number_variants(m.value)
        if m.change_pct is not None:
            tokens |= _number_variants(m.change_pct)
    return tokens


# --------------------------------------------------------------------------- #
# Post-Check (Output-Gate)
# --------------------------------------------------------------------------- #

_NUMBER_RE = re.compile(r"[-−+]?\d+(?:[.,]\d+)?")

# Hedging-/Zahlwoerter, die jeden Ziffern-Check umgehen wuerden.
_NUMBER_WORDS_RE = re.compile(
    r"(?<!\w)(knapp|fast|etwa|ungef[aae]hr|rund|circa|ca\.|beinahe|"
    r"ann[aae]hernd|grob|h[aae]lfte|drittel|viertel|f[uue]nftel|dutzend)(?!\w)",
    re.IGNORECASE,
)

# Reine Richtungs-Woerter (kein Werturteil) -> Vorzeichen.
_DIRECTION_WORDS: dict[str, int] = {
    "gestiegen": +1,
    "steigt": +1,
    "hoeher": +1,
    "mehr": +1,
    "zugenommen": +1,
    "anstieg": +1,
    "gesunken": -1,
    "sinkt": -1,
    "niedriger": -1,
    "weniger": -1,
    "abgenommen": -1,
    "rueckgang": -1,
    "gefallen": -1,
}
_DIRECTION_RE = re.compile(
    r"(?<!\w)(" + "|".join(_DIRECTION_WORDS) + r")(?!\w)", re.IGNORECASE
)

# Empfehlungs-Marker — frei nur erlaubt, wenn Evidenz vorhanden ist.
# Bewusst ohne "rät": kollidiert mit dem Substantiv "Rat" im Disclaimer.
_RECOMMENDATION_RE = re.compile(
    r"(?<!\w)(empfehl\w*|empfiehlt|sollte|solltest|ratsam)(?!\w)",
    re.IGNORECASE,
)

_TREND_SIGN: dict[Trend, int] = {
    Trend.UP: +1,
    Trend.SLIGHTLY_UP: +1,
    Trend.STABLE: 0,
    Trend.SLIGHTLY_DOWN: -1,
    Trend.DOWN: -1,
}


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    failures: tuple[str, ...] = ()


def _check_number_grounding(text: str, insight: WeeklyInsight) -> bool:
    allowed = allowed_number_tokens(insight)
    for token in _NUMBER_RE.findall(text):
        normalized = token.lstrip("+")
        if normalized not in allowed:
            return False
    return True


def _check_number_words(text: str) -> bool:
    return _NUMBER_WORDS_RE.search(text) is None


def _check_identifier_leak(text: str) -> bool:
    return _EMAIL_RE.search(text) is None


def _check_disclaimer(text: str, segment: str) -> bool:
    disclaimer = SEGMENT_DISCLAIMERS.get(segment)
    return disclaimer is not None and disclaimer in text


def _check_coverage(text: str, insight: WeeklyInsight) -> bool:
    # Jede vorhandene Metrik muss mit einer ihrer Zahl-Varianten auftauchen.
    for m in insight.metrics:
        if not (_number_variants(m.value) & set(_NUMBER_RE.findall(text))):
            return False
    return True


def _check_evidence_grounding(text: str, insight: WeeklyInsight) -> bool:
    # Freie Empfehlung ohne Evidenz ist verboten (Regulatorik-Guard).
    if _RECOMMENDATION_RE.search(text) and not insight.evidence:
        return False
    return True


def _check_trend_direction(text: str, insight: WeeklyInsight) -> bool:
    # Pro Satz, der die Zahl einer Metrik nennt: ein Richtungs-Wort mit
    # entgegengesetztem Vorzeichen zum Trend ist ein Widerspruch.
    sentences = re.split(r"[.!?]\s+", text)
    for m in insight.metrics:
        sign = _TREND_SIGN[m.trend]
        if sign == 0:
            continue
        variants = _number_variants(m.value)
        for sentence in sentences:
            nums = set(_NUMBER_RE.findall(sentence))
            if not (variants & nums):
                continue
            for word in _DIRECTION_RE.findall(sentence):
                if _DIRECTION_WORDS[word.lower()] == -sign:
                    return False
    return True


def post_check(text: str, insight: WeeklyInsight, segment: str) -> CheckResult:
    """Fail-secure Output-Gate. Jeder Riegel ist deterministisch; das Ergebnis
    nennt die gescheiterten Riegel."""
    checks: list[tuple[str, bool]] = [
        ("number_grounding", _check_number_grounding(text, insight)),
        ("number_words", _check_number_words(text)),
        ("identifier_leak", _check_identifier_leak(text)),
        ("disclaimer", _check_disclaimer(text, segment)),
        ("coverage", _check_coverage(text, insight)),
        ("evidence_grounding", _check_evidence_grounding(text, insight)),
        ("trend_direction", _check_trend_direction(text, insight)),
    ]
    failures = tuple(name for name, ok in checks if not ok)
    return CheckResult(passed=not failures, failures=failures)


@dataclass(frozen=True)
class GateOutput:
    text: str
    generator: str  # "llm" | "fallback_template"
    attempts: int
    failures: tuple[str, ...] = field(default_factory=tuple)


def run_gate(
    generate: Callable[[], str],
    insight: WeeklyInsight,
    segment: str,
    *,
    max_retries: int = 2,
) -> GateOutput:
    """Ruft ``generate`` (spaeter das LLM) bis zu ``max_retries + 1`` mal auf.
    Besteht der Post-Check, wird der Text zurueckgegeben; sonst der
    deterministische Fallback. Es wird nie ein ungeprueftes Ergebnis geliefert
    (Invariante 1)."""
    last: CheckResult | None = None
    for attempt in range(1, max_retries + 2):
        text = generate()
        result = post_check(text, insight, segment)
        if result.passed:
            return GateOutput(text=text, generator="llm", attempts=attempt)
        last = result
    return GateOutput(
        text=fallback_text(insight, segment),
        generator="fallback_template",
        attempts=max_retries + 1,
        failures=last.failures if last else (),
    )
