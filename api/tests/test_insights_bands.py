"""Tests fuer die Niveau-Einordnung (band_label)."""

from decimal import Decimal

from src.insights.bands import band_label
from src.insights.models import MetricKey


def test_training_form_low_is_high_load():
    # 28 ist niedrig -> "hohe Belastung" (nicht "gute Form")
    assert band_label(MetricKey.TRAINING_FORM, Decimal("28")) == "hohe Belastung"
    assert band_label(MetricKey.TRAINING_FORM, Decimal("70")) == "frisch/erholt"


def test_readiness_bands():
    assert band_label(MetricKey.READINESS, Decimal("79")) == "gut erholt"
    assert band_label(MetricKey.READINESS, Decimal("30")) == "erschoepft"


def test_stress_is_inverted():
    assert band_label(MetricKey.STRESS, Decimal("70")) == "hoch"
    assert band_label(MetricKey.STRESS, Decimal("37")) == "moderat"
    assert band_label(MetricKey.STRESS, Decimal("20")) == "niedrig"


def test_no_band_for_hrv_and_volume():
    assert band_label(MetricKey.HRV, Decimal("71")) is None
    assert band_label(MetricKey.TRAINING_VOLUME, Decimal("3.6")) is None
