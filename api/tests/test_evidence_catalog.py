"""Tests for evidence_catalog JSON loader."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evidence_catalog import EVIDENCE

_REQUIRED_FIELDS = {
    "level",
    "label",
    "metric_type",
    "time_horizon",
    "intended_use",
    "not_for",
    "name",
    "summary",
}
_VALID_LEVELS = {"meta", "replicated", "model"}
_VALID_METRIC_TYPES = {"recovery", "capacity", "trend", "prediction", "screening"}


class TestEvidenceCatalog:
    def test_loads_nonempty_dict(self):
        assert isinstance(EVIDENCE, dict)
        assert len(EVIDENCE) > 0

    def test_all_entries_have_required_fields(self):
        for key, entry in EVIDENCE.items():
            missing = _REQUIRED_FIELDS - entry.keys()
            assert not missing, f"{key!r} missing fields: {missing}"

    def test_all_levels_are_valid(self):
        for key, entry in EVIDENCE.items():
            assert entry["level"] in _VALID_LEVELS, (
                f"{key!r} has invalid level: {entry['level']!r}"
            )

    def test_all_metric_types_are_valid(self):
        for key, entry in EVIDENCE.items():
            assert entry["metric_type"] in _VALID_METRIC_TYPES, (
                f"{key!r} has invalid metric_type: {entry['metric_type']!r}"
            )

    def test_known_keys_present(self):
        expected = {
            "energy_physical",
            "energy_autonomic",
            "energy_cognitive",
            "body_battery_custom",
            "readiness_rf",
            "anomaly_hr",
        }
        assert expected <= EVIDENCE.keys()

    def test_refs_are_lists(self):
        for key, entry in EVIDENCE.items():
            if "refs" in entry:
                assert isinstance(entry["refs"], list), f"{key!r} refs must be a list"
