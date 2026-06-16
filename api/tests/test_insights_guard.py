"""Tests fuer die Basis-Riegel: Identifier-Gate + Number-Tokens (P1)."""

from decimal import Decimal

import pytest

from src.insights.guard import (
    allowed_number_tokens,
    assert_no_identifier,
)
from src.insights.models import Metric, MetricKey, Trend, Unit, WeeklyInsight


def _insight() -> WeeklyInsight:
    return WeeklyInsight(
        iso_year=2026,
        iso_week=24,
        metrics=[
            Metric(
                key=MetricKey.TIME_IN_RANGE,
                value=Decimal("58"),
                unit=Unit.PERCENT,
                change_pct=Decimal("-4.1"),
                trend=Trend.SLIGHTLY_DOWN,
            )
        ],
        flags=[],
        evidence=[],
        catalog_version="1.0.0",
    )


# --- assert_no_identifier -------------------------------------------------- #


def test_assert_no_identifier_passes_clean_object():
    assert_no_identifier(_insight())  # must not raise


def test_assert_no_identifier_catches_key():
    with pytest.raises(ValueError):
        assert_no_identifier({"metrics": [{"user_id": 1}]})


def test_assert_no_identifier_catches_email_value():
    with pytest.raises(ValueError):
        assert_no_identifier({"note": "contact me at a@b.com"})


# --- allowed_number_tokens ------------------------------------------------- #


def test_allowed_number_tokens_includes_comma_and_sign():
    tokens = allowed_number_tokens(_insight())
    assert "58" in tokens
    assert "4.1" in tokens and "4,1" in tokens
    assert "-4.1" in tokens and "−4,1" in tokens
    assert "24" in tokens  # iso_week
