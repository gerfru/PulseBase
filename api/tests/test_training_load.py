"""Tests for training_load.py — Banister TRIMP model."""

import math
from datetime import date, timedelta


# ── _trimp ────────────────────────────────────────────────────────────────────


def test_trimp_hrmax_at_or_below_resting_returns_zero():
    from src.training_load import _trimp

    assert _trimp(3600, 150, 60, 60, "male") == 0.0  # hrmax == resting
    assert _trimp(3600, 150, 60, 50, "male") == 0.0  # hrmax < resting


def test_trimp_avg_hr_at_or_below_resting_returns_zero():
    from src.training_load import _trimp

    assert _trimp(3600, 55, 55, 185, "male") == 0.0  # avg_hr == resting
    assert _trimp(3600, 40, 55, 185, "male") == 0.0  # avg_hr < resting


def test_trimp_normal_male():
    from src.training_load import _trimp

    result = _trimp(3600, 150, 55, 185, "male")
    hrr = (150 - 55) / (185 - 55)
    expected = 60.0 * hrr * math.exp(1.92 * hrr)
    assert abs(result - expected) < 0.001


def test_trimp_normal_female():
    from src.training_load import _trimp

    result = _trimp(3600, 150, 55, 185, "female")
    hrr = (150 - 55) / (185 - 55)
    expected = 60.0 * hrr * math.exp(1.67 * hrr)
    assert abs(result - expected) < 0.001


def test_trimp_female_lower_than_male_at_same_intensity():
    from src.training_load import _trimp

    assert _trimp(3600, 150, 55, 185, "female") < _trimp(3600, 150, 55, 185, "male")


# ── build_training_load ───────────────────────────────────────────────────────


def test_build_returns_expected_keys():
    from src.training_load import build_training_load

    result = build_training_load(
        [], hrmax=185, sex="male", lookback_days=7, forecast_days=0
    )
    assert set(result.keys()) == {"history", "forecast", "today"}
    assert set(result["today"].keys()) == {"atl", "ctl", "tsb"}


def test_build_history_length_matches_lookback():
    from src.training_load import build_training_load

    result = build_training_load(
        [], hrmax=185, sex="male", lookback_days=7, forecast_days=0
    )
    assert len(result["history"]) == 7


def test_build_forecast_length_and_flag():
    from src.training_load import build_training_load

    result = build_training_load(
        [], hrmax=185, sex="male", lookback_days=7, forecast_days=5
    )
    assert len(result["forecast"]) == 5
    for entry in result["forecast"]:
        assert entry["forecast"] is True
        assert entry["trimp"] == 0.0


def test_build_with_activity_raises_atl_ctl():
    from src.training_load import build_training_load

    today = date.today()
    rows = [
        {
            "activity_date": today,
            "duration_seconds": 3600,
            "avg_hr": 150,
            "resting_hr": 55,
        }
    ]
    result = build_training_load(
        rows, hrmax=185, sex="male", lookback_days=7, forecast_days=0
    )
    today_entry = result["history"][-1]
    assert today_entry["date"] == today.isoformat()
    assert today_entry["trimp"] > 0
    assert today_entry["atl"] > 0
    assert today_entry["ctl"] > 0


def test_build_skips_rows_before_warmup_window():
    from src.training_load import build_training_load, _WARMUP_DAYS

    too_old = date.today() - timedelta(days=_WARMUP_DAYS + 5)
    rows = [
        {
            "activity_date": too_old,
            "duration_seconds": 3600,
            "avg_hr": 160,
            "resting_hr": 55,
        }
    ]
    result = build_training_load(
        rows, hrmax=185, sex="male", lookback_days=7, forecast_days=0
    )
    assert result["history"][-1]["atl"] == 0.0
    assert result["history"][-1]["ctl"] == 0.0


def test_build_activity_with_none_resting_hr_uses_default():
    from src.training_load import build_training_load

    today = date.today()
    rows = [
        {
            "activity_date": today,
            "duration_seconds": 3600,
            "avg_hr": 150,
            "resting_hr": None,
        }
    ]
    result = build_training_load(
        rows, hrmax=185, sex="male", lookback_days=1, forecast_days=0
    )
    assert result["history"][0]["trimp"] > 0


def test_build_empty_history_today_values_are_none():
    from src.training_load import build_training_load

    # lookback_days=0 → display_from = tomorrow → history stays empty
    result = build_training_load(
        [], hrmax=185, sex="male", lookback_days=0, forecast_days=0
    )
    assert result["history"] == []
    assert result["today"]["atl"] is None
    assert result["today"]["ctl"] is None
    assert result["today"]["tsb"] is None


def test_build_tsb_is_ctl_minus_atl():
    from src.training_load import build_training_load

    today = date.today()
    rows = [
        {
            "activity_date": today,
            "duration_seconds": 7200,
            "avg_hr": 160,
            "resting_hr": 55,
        }
    ]
    result = build_training_load(
        rows, hrmax=185, sex="male", lookback_days=1, forecast_days=0
    )
    entry = result["history"][0]
    # TSB is round(ctl_raw - atl_raw); ctl/atl are already rounded → max drift 0.1 each
    assert abs(entry["tsb"] - (entry["ctl"] - entry["atl"])) < 0.15


def test_build_multiple_activities_same_day_accumulated():
    from src.training_load import build_training_load

    today = date.today()
    rows = [
        {
            "activity_date": today,
            "duration_seconds": 1800,
            "avg_hr": 140,
            "resting_hr": 55,
        },
        {
            "activity_date": today,
            "duration_seconds": 1800,
            "avg_hr": 140,
            "resting_hr": 55,
        },
    ]
    result_two = build_training_load(
        rows, hrmax=185, sex="male", lookback_days=1, forecast_days=0
    )
    rows_one = [
        {
            "activity_date": today,
            "duration_seconds": 3600,
            "avg_hr": 140,
            "resting_hr": 55,
        }
    ]
    result_one = build_training_load(
        rows_one, hrmax=185, sex="male", lookback_days=1, forecast_days=0
    )
    assert (
        abs(result_two["history"][0]["trimp"] - result_one["history"][0]["trimp"]) < 0.1
    )
