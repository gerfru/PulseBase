import pytest
from datetime import date

from conftest import (
    RAW_ACTIVITY_MINIMAL,
    RAW_ACTIVITY_RUNNING,
    RAW_ACTIVITY_UNKNOWN_SPORT,
    RAW_HRV,
    RAW_SLEEP,
)
from garmin.mapper import (
    _int_or_none,
    _pace_to_sec,
    map_activity,
    map_hrv,
    map_sleep,
)
from domain.models import SportType


class TestMapActivity:
    def test_running_sport_type(self):
        result = map_activity(RAW_ACTIVITY_RUNNING, user_id=1)
        assert result.sport_type == SportType.RUNNING

    def test_basic_fields(self):
        result = map_activity(RAW_ACTIVITY_RUNNING, user_id=1)
        assert result.garmin_activity_id == 12345678
        assert result.user_id == 1
        assert result.distance_meters == 10000.0
        assert result.avg_hr == 145
        assert result.max_hr == 172
        assert result.calories == 650
        assert result.elevation_gain == 42.0

    def test_unknown_sport_falls_back_to_other(self):
        result = map_activity(RAW_ACTIVITY_UNKNOWN_SPORT, user_id=1)
        assert result.sport_type == SportType.OTHER

    def test_missing_optional_fields_are_none(self):
        result = map_activity(RAW_ACTIVITY_MINIMAL, user_id=1)
        assert result.avg_hr is None
        assert result.distance_meters is None
        assert result.calories is None
        assert result.avg_pace_sec_per_km is None

    def test_speed_to_pace_conversion(self):
        result = map_activity(RAW_ACTIVITY_RUNNING, user_id=1)
        assert result.avg_pace_sec_per_km == pytest.approx(360.0, rel=0.01)

    def test_speed_to_kmh(self):
        result = map_activity(RAW_ACTIVITY_RUNNING, user_id=1)
        assert result.avg_speed_kmh == pytest.approx(10.0, rel=0.01)


class TestPaceToSec:
    def test_converts_correctly(self):
        assert _pace_to_sec(3.0) == pytest.approx(333.33, rel=0.01)

    def test_zero_returns_none(self):
        assert _pace_to_sec(0) is None

    def test_none_returns_none(self):
        assert _pace_to_sec(None) is None


class TestMapSleep:
    def test_maps_all_fields(self):
        result = map_sleep(RAW_SLEEP, user_id=1)
        assert result is not None
        assert result.garmin_sleep_id == 555
        assert result.sleep_score == 78
        assert result.deep_sleep_seconds == 5400
        assert result.rem_sleep_seconds == 7200

    def test_empty_raw_returns_none(self):
        assert map_sleep({}, user_id=1) is None

    def test_missing_timestamps_returns_none(self):
        raw = {"dailySleepDTO": {"id": 1}}
        assert map_sleep(raw, user_id=1) is None


class TestMapHRV:
    def test_maps_all_fields(self):
        result = map_hrv(RAW_HRV, user_id=1, day=date(2026, 4, 27))
        assert result is not None
        assert result.hrv_last_night == 42
        assert result.hrv_weekly_avg == 45
        assert result.hrv_status == "BALANCED"

    def test_empty_raw_returns_none(self):
        assert map_hrv({}, user_id=1, day=date(2026, 4, 27)) is None


class TestIntOrNone:
    def test_converts_int(self):
        assert _int_or_none(42) == 42

    def test_converts_float(self):
        assert _int_or_none(3.7) == 3

    def test_none_returns_none(self):
        assert _int_or_none(None) is None

    def test_invalid_returns_none(self):
        assert _int_or_none("abc") is None
