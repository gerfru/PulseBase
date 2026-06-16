"""Tests fuer den Evidenz-Katalog-Loader."""

import json

import pytest
from pydantic import ValidationError

from src.insights.evidence import (
    VALID_EVIDENCE_KEYS,
    EvidenceCatalog,
    load_catalog,
)


def test_catalog_loads_and_exposes_keys():
    assert "glucose.time_in_range" in VALID_EVIDENCE_KEYS
    assert "training.acwr_injury_risk" in VALID_EVIDENCE_KEYS


def test_unknown_evidence_level_rejected(tmp_path):
    bad = {
        "schema_version": "1.0.0",
        "entries": {
            "x.y": {
                "title": "t",
                "applies_to": ["time_in_range"],
                "statement": "s",
                "recommendation": "r",
                "evidence_level": "made_up",
                "source": {"citation": "c"},
                "added": "2026-06-16",
                "reviewed_by": "owner",
            }
        },
    }
    p = tmp_path / "cat.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_catalog(p)


def test_extra_field_rejected(tmp_path):
    bad = {"schema_version": "1.0.0", "entries": {}, "surprise": 1}
    p = tmp_path / "cat.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValidationError):
        EvidenceCatalog.model_validate(json.loads(p.read_text()))
