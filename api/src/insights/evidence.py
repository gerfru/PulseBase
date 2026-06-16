"""Evidenz-Katalog: In-Repo JSON, typisiert geladen (ADR-0003, kein RAG).

Wird beim Import einmal geladen und validiert. ``VALID_EVIDENCE_KEYS`` speist den
``evidence``-Validator von ``WeeklyInsight`` (Evidence-Grounding bei Konstruktion).
``recommendation`` ist die einzige erlaubte Quelle fuer Empfehlungstexte
(Regulatorik-Guard).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

_CATALOG_PATH = Path(__file__).parent / "evidence_catalog.json"

EVIDENCE_LEVELS = frozenset({"guideline", "rct", "observational", "expert_opinion"})


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation: str
    url: str = ""


class EvidenceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    applies_to: list[str]
    statement: str
    recommendation: str
    evidence_level: str
    source: EvidenceSource
    added: str
    reviewed_by: str
    deprecated: bool = False

    @field_validator("evidence_level")
    @classmethod
    def _known_level(cls, v: str) -> str:
        if v not in EVIDENCE_LEVELS:
            raise ValueError(f"unknown evidence_level: {v!r}")
        return v


class EvidenceCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    entries: dict[str, EvidenceEntry]


def load_catalog(path: Path = _CATALOG_PATH) -> EvidenceCatalog:
    data = json.loads(path.read_text(encoding="utf-8"))
    return EvidenceCatalog.model_validate(data)


CATALOG: EvidenceCatalog = load_catalog()
VALID_EVIDENCE_KEYS: frozenset[str] = frozenset(CATALOG.entries.keys())
CATALOG_VERSION: str = CATALOG.schema_version
