import logging
from datetime import datetime, date, timezone
from typing import Any

from domain.models import (
    Activity,
    ActivityRecord,
    DailySummary,
    HRVDaily,
    SleepSession,
    SportType,
)

logger = logging.getLogger(__name__)

_SPORT_TYPE_MAP = {s.value for s in SportType}


def map_activity(raw: dict[str, Any], user_id: int) -> Activity:
    sport_raw = raw.get("activityType", {}).get("typeKey", "other")
    sport = SportType(sport_raw) if sport_raw in _SPORT_TYPE_MAP else SportType.OTHER

    speed_ms = raw.get("averageSpeed")
    avg_speed_kmh = round(speed_ms * 3.6, 2) if speed_ms else None

    return Activity(
        garmin_activity_id=raw["activityId"],
        user_id=user_id,
        started_at=datetime.fromisoformat(raw["startTimeLocal"]),
        duration_seconds=int(raw.get("duration") or 0) or None,
        sport_type=sport,
        distance_meters=raw.get("distance"),
        calories=raw.get("calories"),
        avg_hr=raw.get("averageHR"),
        max_hr=raw.get("maxHR"),
        avg_pace_sec_per_km=_pace_to_sec(speed_ms),
        avg_cadence=_int_or_none(
            raw.get("averageRunningCadenceInStepsPerMinute")
            or raw.get("averageBikingCadenceInRevPerMinute")
        ),
        avg_power=_int_or_none(raw.get("avgPower")),
        elevation_gain=raw.get("elevationGain"),
        avg_speed_kmh=avg_speed_kmh,
        aerobic_effect=raw.get("aerobicTrainingEffect"),
        anaerobic_effect=raw.get("anaerobicTrainingEffect"),
    )


def map_records(details: dict[str, Any] | None) -> list[ActivityRecord]:
    if not details:
        return []
    records: list[ActivityRecord] = []

    metrics = details.get("activityDetailMetrics") or []
    polyline = (details.get("geoPolylineDTO") or {}).get("polyline", [])

    metric_by_index: dict[int, dict] = {}
    for metric_group in metrics:
        for entry in metric_group.get("metrics", []):
            if not isinstance(entry, dict):
                continue
            idx = entry.get("sequenceNumber", 0)
            if idx not in metric_by_index:
                metric_by_index[idx] = {}
            metric_by_index[idx][metric_group.get("metricType")] = entry.get("value")

    for i, point in enumerate(polyline):
        ts_raw = point.get("time")
        if not ts_raw:
            continue
        ts = datetime.fromtimestamp(ts_raw / 1000, tz=timezone.utc)
        m = metric_by_index.get(i, {})
        speed_ms = m.get("directSpeed") or m.get("directEnhancedSpeed")

        records.append(
            ActivityRecord(
                time=ts,
                heart_rate=_int_or_none(m.get("directHeartRate")),
                pace_sec_per_km=_pace_to_sec(speed_ms),
                cadence=_int_or_none(
                    m.get("directRunCadence") or m.get("directBikeCadence")
                ),
                power=_int_or_none(m.get("directPower")),
                elevation=m.get("directElevation") or m.get("directGrade"),
                distance=m.get("sumDistance"),
                lat=point.get("lat"),
                lng=point.get("lon"),
            )
        )

    return records


def map_summary(raw: dict[str, Any], user_id: int, day: date) -> DailySummary:
    bb = raw.get("bodyBatteryHighest"), raw.get("bodyBatteryLowest")
    return DailySummary(
        date=day,
        user_id=user_id,
        steps=raw.get("totalSteps"),
        calories_total=raw.get("totalKilocalories"),
        avg_stress=raw.get("averageStressLevel"),
        max_stress=raw.get("maxStressLevel"),
        avg_spo2=raw.get("averageSpO2"),
        min_spo2=raw.get("lowestSpO2"),
        body_battery_high=bb[0],
        body_battery_low=bb[1],
        resting_hr=raw.get("restingHeartRate"),
        intensity_moderate=_int_or_none(raw.get("moderateIntensityMinutes")),
        intensity_vigorous=_int_or_none(raw.get("vigorousIntensityMinutes")),
    )


_TRAINING_STATUS_MAP = {
    2: "DETRAINING",
    3: "OVERREACHING",
    4: "UNPRODUCTIVE",
    5: "RECOVERY",
    6: "MAINTAINING",
    7: "PRODUCTIVE",
}


def map_training_status(raw: dict[str, Any]) -> str | None:
    latest = (raw.get("mostRecentTrainingStatus") or {}).get(
        "latestTrainingStatusData"
    ) or {}
    device = next(
        (v for v in latest.values() if v.get("primaryTrainingDevice")),
        next(iter(latest.values()), None),
    )
    if not device:
        return None
    return _TRAINING_STATUS_MAP.get(device.get("trainingStatus"))


def map_sleep(raw: dict[str, Any], user_id: int) -> SleepSession | None:
    daily = raw.get("dailySleepDTO")
    if not daily:
        return None

    start_ts = daily.get("sleepStartTimestampLocal")
    end_ts = daily.get("sleepEndTimestampLocal")
    if not start_ts or not end_ts:
        return None

    return SleepSession(
        garmin_sleep_id=daily.get("id"),
        user_id=user_id,
        start_time=datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc),
        end_time=datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc),
        total_sleep_seconds=daily.get("sleepTimeSeconds"),
        deep_sleep_seconds=daily.get("deepSleepSeconds"),
        light_sleep_seconds=daily.get("lightSleepSeconds"),
        rem_sleep_seconds=daily.get("remSleepSeconds"),
        awake_seconds=daily.get("awakeSleepSeconds"),
        sleep_score=daily.get("sleepScores", {}).get("overall", {}).get("value"),
    )


def map_hrv(raw: dict[str, Any], user_id: int, day: date) -> HRVDaily | None:
    summary = raw.get("hrvSummary")
    if not summary:
        return None
    return HRVDaily(
        date=day,
        user_id=user_id,
        hrv_last_night=summary.get("lastNight"),
        hrv_weekly_avg=summary.get("weeklyAvg"),
        hrv_status=summary.get("status"),
    )


def map_body_battery(raw: list[dict], user_id: int) -> list[tuple]:
    readings = []
    for day_data in raw:
        for entry in day_data.get("bodyBatteryValuesArray", []):
            ts_ms, value = entry[0], entry[1]
            if ts_ms and value is not None:
                readings.append(
                    (datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc), value)
                )
    return readings


def map_stress(raw: dict[str, Any], user_id: int) -> list[tuple]:
    readings = []
    for entry in raw.get("stressValuesArray", []):
        ts_ms, value = entry[0], entry[1]
        if ts_ms and value is not None and value >= 0:
            readings.append(
                (datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc), value)
            )
    return readings


def _pace_to_sec(speed_ms: float | None) -> float | None:
    if not speed_ms or speed_ms == 0:
        return None
    return round(1000 / speed_ms, 2)


def _int_or_none(val: Any) -> int | None:
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None
