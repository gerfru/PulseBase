from datetime import datetime, date
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class SportType(str, Enum):
    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    HIKING = "hiking"
    WALKING = "walking"
    STRENGTH_TRAINING = "strength_training"
    YOGA = "yoga"
    INDOOR_CYCLING = "indoor_cycling"
    TRAIL_RUNNING = "trail_running"
    OPEN_WATER_SWIMMING = "open_water_swimming"
    CARDIO = "cardio"
    ELLIPTICAL = "elliptical"
    FITNESS_EQUIPMENT = "fitness_equipment"
    OTHER = "other"


class ActivityRecord(BaseModel):
    time: datetime
    heart_rate: Optional[int] = None
    pace_sec_per_km: Optional[float] = None
    cadence: Optional[int] = None
    power: Optional[int] = None
    elevation: Optional[float] = None
    distance: Optional[float] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class Activity(BaseModel):
    garmin_activity_id: int
    user_id: int
    started_at: datetime
    duration_seconds: Optional[int] = None
    sport_type: SportType
    distance_meters: Optional[float] = None
    calories: Optional[int] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_pace_sec_per_km: Optional[float] = None
    avg_cadence: Optional[int] = None
    avg_power: Optional[int] = None
    elevation_gain: Optional[float] = None
    avg_speed_kmh: Optional[float] = None
    aerobic_effect: Optional[float] = None
    anaerobic_effect: Optional[float] = None
    avg_ground_contact_time: Optional[int] = None
    avg_vertical_oscillation: Optional[float] = None
    avg_stride_length: Optional[float] = None
    avg_vertical_ratio: Optional[float] = None
    avg_running_power: Optional[int] = None
    records: list[ActivityRecord] = []


class DailySummary(BaseModel):
    date: date
    user_id: int
    steps: Optional[int] = None
    calories_total: Optional[int] = None
    avg_stress: Optional[int] = None
    max_stress: Optional[int] = None
    avg_spo2: Optional[int] = None
    min_spo2: Optional[int] = None
    body_battery_high: Optional[int] = None
    body_battery_low: Optional[int] = None
    resting_hr: Optional[int] = None
    intensity_moderate: Optional[int] = None
    intensity_vigorous: Optional[int] = None
    training_status: Optional[str] = None


class SleepSession(BaseModel):
    garmin_sleep_id: Optional[int] = None
    user_id: int
    start_time: datetime
    end_time: datetime
    total_sleep_seconds: Optional[int] = None
    deep_sleep_seconds: Optional[int] = None
    light_sleep_seconds: Optional[int] = None
    rem_sleep_seconds: Optional[int] = None
    awake_seconds: Optional[int] = None
    sleep_score: Optional[int] = None


class HRVDaily(BaseModel):
    date: date
    user_id: int
    hrv_last_night: Optional[int] = None
    hrv_weekly_avg: Optional[int] = None
    hrv_status: Optional[str] = None
