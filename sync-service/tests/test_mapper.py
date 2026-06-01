import pytest
from datetime import date, timezone

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
    map_body_battery,
    map_hrv,
    map_records,
    map_sleep,
    map_stress,
    map_summary,
    map_training_status,
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

    def test_sub_activity_type_none_falls_back_to_activity_type(self):
        raw = {
            **RAW_ACTIVITY_RUNNING,
            "subActivityType": None,  # explicit None, not missing key
        }
        result = map_activity(raw, user_id=1)
        assert result.sport_type == SportType.RUNNING

    def test_average_speed_none_gives_none_speed_fields(self):
        raw = {**RAW_ACTIVITY_RUNNING, "averageSpeed": None}
        result = map_activity(raw, user_id=1)
        assert result.avg_speed_kmh is None
        assert result.avg_pace_sec_per_km is None

    def test_optional_running_fields_explicitly_none(self):
        raw = {
            **RAW_ACTIVITY_RUNNING,
            "avgGroundContactTime": None,
            "avgVerticalOscillation": None,
            "avgStrideLength": None,
            "avgVerticalRatio": None,
            "avgRunningPower": None,
        }
        result = map_activity(raw, user_id=1)
        assert result.avg_ground_contact_time is None
        assert result.avg_vertical_oscillation is None
        assert result.avg_stride_length is None
        assert result.avg_vertical_ratio is None
        assert result.avg_running_power is None


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

    def test_daily_sleep_dto_explicitly_none_returns_none(self):
        assert map_sleep({"dailySleepDTO": None}, user_id=1) is None

    def test_sleep_score_value_none_maps_to_none(self):
        raw = {
            "dailySleepDTO": {
                **RAW_SLEEP["dailySleepDTO"],
                "sleepScores": {"overall": {"value": None}},
            }
        }
        result = map_sleep(raw, user_id=1)
        assert result is not None
        assert result.sleep_score is None


class TestMapHRV:
    def test_maps_all_fields(self):
        result = map_hrv(RAW_HRV, user_id=1, day=date(2026, 4, 27))
        assert result is not None
        assert result.hrv_last_night == 42
        assert result.hrv_weekly_avg == 45
        assert result.hrv_status == "BALANCED"

    def test_empty_raw_returns_none(self):
        assert map_hrv({}, user_id=1, day=date(2026, 4, 27)) is None

    def test_hrv_summary_with_none_values(self):
        raw = {"hrvSummary": {"lastNightAvg": None, "weeklyAvg": None, "status": None}}
        result = map_hrv(raw, user_id=1, day=date(2026, 4, 27))
        assert result is not None
        assert result.hrv_last_night is None
        assert result.hrv_weekly_avg is None
        assert result.hrv_status is None


class TestIntOrNone:
    def test_converts_int(self):
        assert _int_or_none(42) == 42

    def test_converts_float(self):
        assert _int_or_none(3.7) == 3

    def test_none_returns_none(self):
        assert _int_or_none(None) is None

    def test_invalid_returns_none(self):
        assert _int_or_none("abc") is None


_RAW_RECORDS = {
    "activityDetailMetrics": [
        {
            "metricType": "directHeartRate",
            "metrics": [
                {"sequenceNumber": 0, "value": 140},
                {"sequenceNumber": 1, "value": 145},
            ],
        },
        {
            "metricType": "directSpeed",
            "metrics": [
                {"sequenceNumber": 0, "value": 2.78},
                {"sequenceNumber": 1, "value": 2.90},
            ],
        },
    ],
    "geoPolylineDTO": {
        "polyline": [
            {"time": 1745704800000, "lat": 48.20, "lon": 16.37},
            {"time": 1745704860000, "lat": 48.21, "lon": 16.38},
        ]
    },
}


class TestMapRecords:
    def test_returns_correct_count(self):
        result = map_records(_RAW_RECORDS)
        assert len(result) == 2

    def test_fields_populated(self):
        result = map_records(_RAW_RECORDS)
        r = result[0]
        assert r.heart_rate == 140
        assert r.lat == pytest.approx(48.20)
        assert r.lng == pytest.approx(16.37)
        assert r.time.tzinfo == timezone.utc

    def test_pace_derived_from_speed(self):
        result = map_records(_RAW_RECORDS)
        assert result[0].pace_sec_per_km is not None
        assert result[0].pace_sec_per_km == pytest.approx(1000 / 2.78, rel=0.01)

    def test_none_returns_empty_list(self):
        assert map_records(None) == []

    def test_missing_polyline_returns_empty_list(self):
        assert map_records({}) == []

    def test_both_speed_metrics_none_gives_no_pace(self):
        raw = {
            "activityDetailMetrics": [
                {
                    "metricType": "directSpeed",
                    "metrics": [{"sequenceNumber": 0, "value": None}],
                },
                {
                    "metricType": "directEnhancedSpeed",
                    "metrics": [{"sequenceNumber": 0, "value": None}],
                },
            ],
            "geoPolylineDTO": {
                "polyline": [{"time": 1745704800000, "lat": 48.20, "lon": 16.37}]
            },
        }
        result = map_records(raw)
        assert len(result) == 1
        assert result[0].pace_sec_per_km is None

    def test_polyline_point_with_none_coords(self):
        raw = {
            "activityDetailMetrics": [],
            "geoPolylineDTO": {
                "polyline": [{"time": 1745704800000, "lat": None, "lon": None}]
            },
        }
        result = map_records(raw)
        assert len(result) == 1
        assert result[0].lat is None
        assert result[0].lng is None

    def test_record_without_timestamp_skipped(self):
        raw = {
            "activityDetailMetrics": [],
            "geoPolylineDTO": {"polyline": [{"lat": 48.0, "lon": 16.0}]},
        }
        assert map_records(raw) == []


_RAW_SUMMARY = {
    "totalSteps": 8500,
    "totalKilocalories": 2200,
    "averageStressLevel": 35,
    "maxStressLevel": 72,
    "averageSpO2": 97,
    "lowestSpO2": 94,
    "bodyBatteryHighest": 85,
    "bodyBatteryLowest": 22,
    "restingHeartRate": 52,
    "moderateIntensityMinutes": 20,
    "vigorousIntensityMinutes": 10,
}


class TestMapSummary:
    def test_maps_all_fields(self):
        result = map_summary(_RAW_SUMMARY, user_id=1, day=date(2026, 4, 27))
        assert result.steps == 8500
        assert result.calories_total == 2200
        assert result.avg_stress == 35
        assert result.avg_spo2 == 97
        assert result.body_battery_high == 85
        assert result.body_battery_low == 22
        assert result.resting_hr == 52
        assert result.intensity_moderate == 20
        assert result.intensity_vigorous == 10

    def test_user_id_and_date_set(self):
        result = map_summary({}, user_id=7, day=date(2026, 1, 1))
        assert result.user_id == 7
        assert result.date == date(2026, 1, 1)

    def test_missing_optional_fields_are_none(self):
        result = map_summary({}, user_id=1, day=date(2026, 4, 27))
        assert result.steps is None
        assert result.resting_hr is None
        assert result.avg_spo2 is None

    def test_explicit_none_fields_map_to_none(self):
        raw = {
            "totalSteps": None,
            "totalKilocalories": None,
            "averageStressLevel": None,
            "averageSpO2": None,
            "bodyBatteryHighest": None,
            "bodyBatteryLowest": None,
            "restingHeartRate": None,
            "moderateIntensityMinutes": None,
            "vigorousIntensityMinutes": None,
        }
        result = map_summary(raw, user_id=1, day=date(2026, 4, 27))
        assert result.steps is None
        assert result.resting_hr is None
        assert result.avg_spo2 is None
        assert result.body_battery_high is None
        assert result.intensity_moderate is None


class TestMapBodyBattery:
    def test_maps_values(self):
        raw = [
            {"bodyBatteryValuesArray": [[1745704800000, 80], [1745708400000, 75]]},
            {"bodyBatteryValuesArray": [[1745712000000, 70]]},
        ]
        result = map_body_battery(raw, user_id=1)
        assert len(result) == 3
        ts, val = result[0]
        assert val == 80
        assert ts.tzinfo == timezone.utc

    def test_none_value_skipped(self):
        raw = [{"bodyBatteryValuesArray": [[1745704800000, None], [1745708400000, 60]]}]
        result = map_body_battery(raw, user_id=1)
        assert len(result) == 1
        assert result[0][1] == 60

    def test_empty_input_returns_empty_list(self):
        assert map_body_battery([], user_id=1) == []

    def test_empty_battery_array_returns_empty_list(self):
        assert map_body_battery([{"bodyBatteryValuesArray": []}], user_id=1) == []


class TestMapStress:
    def test_maps_values(self):
        raw = {"stressValuesArray": [[1745704800000, 40], [1745708400000, 55]]}
        result = map_stress(raw, user_id=1)
        assert len(result) == 2
        ts, val = result[0]
        assert val == 40
        assert ts.tzinfo == timezone.utc

    def test_negative_stress_skipped(self):
        raw = {"stressValuesArray": [[1745704800000, -1], [1745708400000, 30]]}
        result = map_stress(raw, user_id=1)
        assert len(result) == 1
        assert result[0][1] == 30

    def test_empty_array_returns_empty_list(self):
        assert map_stress({"stressValuesArray": []}, user_id=1) == []

    def test_missing_key_returns_empty_list(self):
        assert map_stress({}, user_id=1) == []


_RAW_TRAINING_STATUS = {
    "mostRecentTrainingStatus": {
        "latestTrainingStatusData": {
            "device_1": {
                "primaryTrainingDevice": True,
                "trainingStatus": 7,
            }
        }
    }
}


class TestMapTrainingStatus:
    def test_maps_productive(self):
        result = map_training_status(_RAW_TRAINING_STATUS)
        assert result == "PRODUCTIVE"

    def test_maps_each_status(self):
        for code, expected in [
            (2, "DETRAINING"),
            (3, "OVERREACHING"),
            (4, "UNPRODUCTIVE"),
            (5, "RECOVERY"),
            (6, "MAINTAINING"),
            (7, "PRODUCTIVE"),
        ]:
            raw = {
                "mostRecentTrainingStatus": {
                    "latestTrainingStatusData": {
                        "d": {"primaryTrainingDevice": True, "trainingStatus": code}
                    }
                }
            }
            assert map_training_status(raw) == expected

    def test_empty_raw_returns_none(self):
        assert map_training_status({}) is None

    def test_missing_device_returns_none(self):
        raw = {"mostRecentTrainingStatus": {"latestTrainingStatusData": {}}}
        assert map_training_status(raw) is None
