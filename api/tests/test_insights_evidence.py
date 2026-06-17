"""Tests fuer die Insights-Evidenz (Wiederverwendung des Produkt-Katalogs)."""

from src.insights.evidence import VALID_EVIDENCE_KEYS, caveats_for, statement_for


def test_valid_keys_include_models_and_new_entries():
    for key in (
        "energy_physical",
        "energy_autonomic",
        "energy_cognitive",
        "sleep_score_custom",
        "stress_score_custom",
        "body_battery_custom",
        "glucose_tir",
        "acwr_injury_risk",
    ):
        assert key in VALID_EVIDENCE_KEYS


def test_statement_and_caveats_return_text():
    assert "Time in Range" in statement_for("glucose_tir")
    assert caveats_for("glucose_tir")  # not_for / limitations vorhanden
    assert statement_for("acwr_injury_risk")
    assert caveats_for("acwr_injury_risk")


def test_unknown_key_yields_empty():
    assert statement_for("does.not.exist") == ""
    assert caveats_for("does.not.exist") == ""
