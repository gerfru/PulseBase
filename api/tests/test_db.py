"""Unit tests for db/ package — seizure helpers (pure Python) and DB functions (mocked pool)."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Seizure risk helpers (pure Python, no DB) ─────────────────────────────────


def test_check_sleep_debt_red():
    from src.db.seizures import _check_sleep_debt

    flags, level = _check_sleep_debt([], 6.0)
    assert level == "red"
    assert flags[0]["color"] == "red"
    assert "6.0h" in flags[0]["detail"]


def test_check_sleep_debt_amber():
    from src.db.seizures import _check_sleep_debt

    flags, level = _check_sleep_debt([], 3.0)
    assert level == "amber"
    assert flags[0]["color"] == "amber"


def test_check_sleep_debt_ok():
    from src.db.seizures import _check_sleep_debt

    flags, level = _check_sleep_debt([], 1.0)
    assert level == "ok"
    assert flags == []


def test_check_high_stress_amber():
    from src.db.seizures import _check_high_stress

    flags, level = _check_high_stress(75)
    assert level == "amber"
    assert "75" in flags[0]["detail"]


def test_check_high_stress_ok():
    from src.db.seizures import _check_high_stress

    flags, level = _check_high_stress(65)
    assert level == "ok"
    assert flags == []


def test_check_hrv_drop_amber():
    from src.db.seizures import _check_hrv_drop

    flags, level = _check_hrv_drop(hrv_now=50.0, hrv_avg=70.0)
    assert level == "amber"
    assert "50" in flags[0]["detail"]


def test_check_hrv_drop_ok_small_drop():
    from src.db.seizures import _check_hrv_drop

    flags, level = _check_hrv_drop(hrv_now=65.0, hrv_avg=70.0)
    assert level == "ok"
    assert flags == []


def test_check_hrv_drop_none_values():
    from src.db.seizures import _check_hrv_drop

    flags, level = _check_hrv_drop(None, None)
    assert level == "ok"
    assert flags == []


def test_check_low_body_battery_amber():
    from src.db.seizures import _check_low_body_battery

    flags, level = _check_low_body_battery(15.0)
    assert level == "amber"
    assert "15" in flags[0]["detail"]


def test_check_low_body_battery_ok():
    from src.db.seizures import _check_low_body_battery

    flags, level = _check_low_body_battery(25.0)
    assert level == "ok"
    assert flags == []


def test_check_low_body_battery_none():
    from src.db.seizures import _check_low_body_battery

    flags, level = _check_low_body_battery(None)
    assert level == "ok"
    assert flags == []


def test_check_intense_training_amber():
    from src.db.seizures import _check_intense_training

    flags, level = _check_intense_training(75)
    assert level == "amber"
    assert "75" in flags[0]["detail"]


def test_check_intense_training_ok():
    from src.db.seizures import _check_intense_training

    flags, level = _check_intense_training(45)
    assert level == "ok"
    assert flags == []


def test_check_resting_hr_spike_amber():
    from src.db.seizures import _check_resting_hr_spike

    flags, level = _check_resting_hr_spike(resting_hr=75.0, baseline=60.0)
    assert level == "amber"
    assert "75" in flags[0]["detail"]


def test_check_resting_hr_spike_ok():
    from src.db.seizures import _check_resting_hr_spike

    flags, level = _check_resting_hr_spike(resting_hr=62.0, baseline=60.0)
    assert level == "ok"
    assert flags == []


def test_check_resting_hr_spike_none():
    from src.db.seizures import _check_resting_hr_spike

    flags, level = _check_resting_hr_spike(None, None)
    assert level == "ok"
    assert flags == []


def test_merge_level_red_wins():
    from src.db.seizures import _merge_level

    assert _merge_level("ok", "red") == "red"
    assert _merge_level("amber", "red") == "red"
    assert _merge_level("red", "ok") == "red"


def test_merge_level_amber():
    from src.db.seizures import _merge_level

    assert _merge_level("ok", "amber") == "amber"
    assert _merge_level("amber", "ok") == "amber"


def test_merge_level_ok():
    from src.db.seizures import _merge_level

    assert _merge_level("ok", "ok") == "ok"


# ── DB helpers ────────────────────────────────────────────────────────────────


def _pool_mock(*, fetchrow=None, fetch=None, execute="UPDATE 1", fetchval=None):
    """Build a minimal asyncpg pool mock for synchronous setup."""
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=fetchrow)
    pool.fetch = AsyncMock(return_value=fetch or [])
    pool.execute = AsyncMock(return_value=execute)
    if fetchval is not None:
        pool.fetchval = AsyncMock(return_value=fetchval)
    return pool


# ── users ─────────────────────────────────────────────────────────────────────


async def test_get_user_by_id_found():
    from src.db.users import get_user_by_id

    row = {
        "id": 1,
        "name": "Alice",
        "email": "a@b.com",
        "garmin_linked": False,
        "garmin_email": None,
        "libre_linked": False,
        "libre_email": None,
        "date_of_birth": None,
        "sex": None,
        "epilepsy_mode": False,
        "spo2_enabled": False,
    }
    with patch(
        "src.db.users.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=row))
    ):
        result = await get_user_by_id(1)
    assert result["id"] == 1


async def test_get_user_by_id_not_found():
    from src.db.users import get_user_by_id

    with patch(
        "src.db.users.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=None))
    ):
        result = await get_user_by_id(99)
    assert result is None


async def test_get_user_by_email_found():
    from src.db.users import get_user_by_email

    row = {
        "id": 1,
        "name": "Alice",
        "email": "a@b.com",
        "password_hash": "h",
        "garmin_linked": False,
        "garmin_email": None,
    }
    with patch(
        "src.db.users.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=row))
    ):
        result = await get_user_by_email("a@b.com")
    assert result["email"] == "a@b.com"


async def test_get_user_by_email_not_found():
    from src.db.users import get_user_by_email

    with patch(
        "src.db.users.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=None))
    ):
        result = await get_user_by_email("x@y.com")
    assert result is None


async def test_create_user_returns_dict():
    from src.db.users import create_user

    row = {
        "id": 5,
        "name": "Bob",
        "email": "b@c.com",
        "garmin_linked": False,
        "garmin_email": None,
    }
    with patch(
        "src.db.users.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=row))
    ):
        result = await create_user("Bob", "b@c.com", "hash")  # pragma: allowlist secret
    assert result["id"] == 5


async def test_create_user_raises_on_null_row():
    from src.db.users import create_user

    with patch(
        "src.db.users.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=None))
    ):
        with pytest.raises(RuntimeError, match="INSERT RETURNING"):
            await create_user("Bob", "b@c.com", "hash")  # pragma: allowlist secret


async def test_update_user_profile():
    from src.db.users import update_user_profile

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await update_user_profile(1, date(1990, 1, 1), "m")
    pool.execute.assert_called_once()


async def test_update_epilepsy_mode():
    from src.db.users import update_epilepsy_mode

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await update_epilepsy_mode(1, True)
    pool.execute.assert_called_once()


async def test_update_spo2_enabled():
    from src.db.users import update_spo2_enabled

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await update_spo2_enabled(1, True)
    pool.execute.assert_called_once()


async def test_set_garmin_linked():
    from src.db.users import set_garmin_linked

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await set_garmin_linked(1, "g@garmin.com")
    pool.execute.assert_called_once()


async def test_set_garmin_unlinked():
    from src.db.users import set_garmin_unlinked

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await set_garmin_unlinked(1)
    pool.execute.assert_called_once()


async def test_set_libre_linked():
    from src.db.users import set_libre_linked

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await set_libre_linked(1, "l@libre.com")
    pool.execute.assert_called_once()


async def test_get_user_sex_returns_sex():
    from src.db.users import get_user_sex

    with patch(
        "src.db.users.get_pool",
        AsyncMock(return_value=_pool_mock(fetchrow={"sex": "f"})),
    ):
        result = await get_user_sex(1)
    assert result == "f"


async def test_get_user_sex_defaults_to_male():
    from src.db.users import get_user_sex

    with patch(
        "src.db.users.get_pool",
        AsyncMock(return_value=_pool_mock(fetchrow={"sex": None})),
    ):
        result = await get_user_sex(1)
    assert result == "male"


async def test_request_sync():
    from src.db.users import request_sync

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await request_sync(1)
    pool.execute.assert_called_once()


async def test_get_sync_status_with_row():
    from src.db.users import get_sync_status

    ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    row = {"sync_requested": True, "last_sync_at": ts}
    with patch(
        "src.db.users.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=row))
    ):
        result = await get_sync_status(1)
    assert result["pending"] is True
    assert "2024" in result["last_sync_at"]


async def test_get_sync_status_no_row():
    from src.db.users import get_sync_status

    with patch(
        "src.db.users.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=None))
    ):
        result = await get_sync_status(1)
    assert result == {"pending": False, "last_sync_at": None}


async def test_get_ml_status_pending():
    from src.db.users import get_ml_status

    ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    row = {"ml_requested": True, "last_ml_at": ts}
    with patch(
        "src.db.users.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=row))
    ):
        result = await get_ml_status(1)
    assert result["pending"] is True


async def test_get_ml_status_no_row():
    from src.db.users import get_ml_status

    with patch(
        "src.db.users.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=None))
    ):
        result = await get_ml_status(1)
    assert result == {"pending": False, "last_ml_at": None}


# ── activities ────────────────────────────────────────────────────────────────


async def test_get_recent_activities_returns_list():
    from src.db.activities import get_recent_activities

    rows = [
        {
            "id": 1,
            "sport_type": "running",
            "started_at": datetime(2024, 1, 1),
            "duration_seconds": 3600,
            "distance_meters": 10000,
            "avg_hr": 150,
            "calories": 500,
        }
    ]
    with patch(
        "src.db.activities.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_recent_activities(1)
    assert len(result) == 1
    assert result[0]["sport_type"] == "running"


async def test_get_recent_activities_empty():
    from src.db.activities import get_recent_activities

    with patch(
        "src.db.activities.get_pool", AsyncMock(return_value=_pool_mock(fetch=[]))
    ):
        result = await get_recent_activities(1)
    assert result == []


async def test_get_activity_detail_found():
    from src.db.activities import get_activity_detail

    row = {
        "id": 1,
        "sport_type": "running",
        "started_at": datetime(2024, 1, 1),
        "duration_seconds": 3600,
        "distance_meters": 10000,
        "calories": 500,
        "avg_hr": 150,
        "max_hr": 180,
        "avg_pace_sec_per_km": 360,
        "avg_speed_kmh": 10.0,
        "avg_cadence": 170,
        "avg_power": None,
        "elevation_gain": 50,
        "aerobic_effect": 3.0,
        "anaerobic_effect": 1.0,
        "user_rpe": None,
        "avg_ground_contact_time": None,
        "avg_vertical_oscillation": None,
        "avg_stride_length": None,
        "avg_vertical_ratio": None,
        "avg_running_power": None,
        "training_status": None,
    }
    pool = _pool_mock(fetchrow=row, fetch=[])
    with patch("src.db.activities.get_pool", AsyncMock(return_value=pool)):
        result = await get_activity_detail(1, 1)
    assert result is not None
    assert result["id"] == 1
    assert result["records"] == []


async def test_get_activity_detail_not_found():
    from src.db.activities import get_activity_detail

    with patch(
        "src.db.activities.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=None))
    ):
        result = await get_activity_detail(1, 99)
    assert result is None


async def test_set_activity_rpe_found():
    from src.db.activities import set_activity_rpe

    with patch(
        "src.db.activities.get_pool",
        AsyncMock(return_value=_pool_mock(execute="UPDATE 1")),
    ):
        result = await set_activity_rpe(1, 1, 7)
    assert result is True


async def test_set_activity_rpe_not_found():
    from src.db.activities import set_activity_rpe

    with patch(
        "src.db.activities.get_pool",
        AsyncMock(return_value=_pool_mock(execute="UPDATE 0")),
    ):
        result = await set_activity_rpe(1, 99, 7)
    assert result is False


async def test_get_activity_hrmax_with_data():
    from src.db.activities import get_activity_hrmax

    with patch(
        "src.db.activities.get_pool",
        AsyncMock(return_value=_pool_mock(fetchrow={"hrmax": 185.0})),
    ):
        result = await get_activity_hrmax(1)
    assert result == 185.0


async def test_get_activity_hrmax_fallback():
    from src.db.activities import get_activity_hrmax

    with patch(
        "src.db.activities.get_pool",
        AsyncMock(return_value=_pool_mock(fetchrow={"hrmax": None})),
    ):
        result = await get_activity_hrmax(1)
    assert result == 190.0


async def test_get_training_load_inputs():
    from src.db.activities import get_training_load_inputs

    rows = [
        {
            "activity_date": date(2024, 1, 1),
            "avg_hr": 150.0,
            "duration_seconds": 3600.0,
            "resting_hr": 55.0,
        }
    ]
    with patch(
        "src.db.activities.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_training_load_inputs(1)
    assert len(result) == 1


# ── glucose ───────────────────────────────────────────────────────────────────


async def test_get_glucose_recent_formats_time():
    from src.db.glucose import get_glucose_recent

    ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    rows = [
        {
            "time": ts,
            "value_mgdl": 100,
            "trend": "flat",
            "is_high": False,
            "is_low": False,
        }
    ]
    with patch(
        "src.db.glucose.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_glucose_recent(1, hours=24)
    assert result[0]["time"] == ts.isoformat()
    assert result[0]["value_mgdl"] == 100


async def test_get_glucose_stats_empty():
    from src.db.glucose import get_glucose_stats

    with patch(
        "src.db.glucose.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=None))
    ):
        result = await get_glucose_stats(1)
    assert result == {}


async def test_get_glucose_stats_with_data():
    from src.db.glucose import get_glucose_stats

    row = {
        "total": 100,
        "avg_mgdl": 110.5,
        "min_mgdl": 70,
        "max_mgdl": 180,
        "tir_pct": 85.0,
        "count_low": 2,
        "count_high": 3,
    }
    with patch(
        "src.db.glucose.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=row))
    ):
        result = await get_glucose_stats(1)
    assert result["avg_mgdl"] == 110.5


# ── ml ────────────────────────────────────────────────────────────────────────


async def test_get_ml_insights_with_metadata():
    from src.db.ml import get_ml_insights
    import json

    rows = [
        {
            "model": "anomaly_hr",
            "value": 2.1,
            "metadata": json.dumps({"is_anomaly": True}),
        },
        {"model": "readiness_rf", "value": 72.0, "metadata": None},
    ]
    with patch("src.db.ml.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))):
        result = await get_ml_insights(1)
    assert result["anomaly_hr"]["is_anomaly"] is True
    assert result["readiness_rf"]["value"] == 72.0


async def test_get_ml_insights_empty():
    from src.db.ml import get_ml_insights

    with patch("src.db.ml.get_pool", AsyncMock(return_value=_pool_mock(fetch=[]))):
        result = await get_ml_insights(1)
    assert result == {}


async def test_get_ml_history_groups_by_model():
    from src.db.ml import get_ml_history
    import json

    rows = [
        {
            "date": date(2024, 1, 1),
            "model": "energy_physical",
            "value": 65.0,
            "metadata": json.dumps({"tsb": 2.1}),
        },
        {
            "date": date(2024, 1, 2),
            "model": "energy_physical",
            "value": 68.0,
            "metadata": None,
        },
    ]
    with patch("src.db.ml.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))):
        result = await get_ml_history(1, days=7)
    assert len(result["energy_physical"]) == 2
    assert result["energy_physical"][0]["tsb"] == 2.1


async def test_get_ml_db_status_no_row():
    from src.db.ml import get_ml_status

    with patch("src.db.ml.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=None))):
        result = await get_ml_status(1)
    assert result == {"pending": False, "last_ml_at": None}


# ── health (spot checks) ──────────────────────────────────────────────────────


async def test_get_daily_summaries_returns_list():
    from src.db.health import get_daily_summaries

    rows = [
        {
            "date": date(2024, 1, 1),
            "steps": 8000,
            "resting_hr": 55,
            "avg_stress": 30,
            "calories_total": 2000,
            "intensity_moderate": 20,
            "intensity_vigorous": 10,
            "body_battery_high": 80,
            "body_battery_low": 20,
        }
    ]
    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_daily_summaries(1, days=7)
    assert len(result) == 1
    assert result[0]["steps"] == 8000


async def test_get_sleep_sessions_returns_list():
    from src.db.health import get_sleep_sessions

    rows = [
        {
            "date": date(2024, 1, 1),
            "start_time": datetime(2024, 1, 1, 22, 0),
            "end_time": datetime(2024, 1, 2, 6, 0),
            "sleep_score": 82,
            "total_sleep_seconds": 28800,
            "deep_sleep_seconds": 7200,
            "light_sleep_seconds": 14400,
            "rem_sleep_seconds": 7200,
            "awake_seconds": 600,
        }
    ]
    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_sleep_sessions(1, days=7)
    assert result[0]["sleep_score"] == 82


async def test_get_readiness_no_data():
    from src.db.health import get_readiness

    with patch("src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetch=[]))):
        result = await get_readiness(1)
    assert result["score"] is None


async def test_get_latest_hrv_found():
    from src.db.health import get_latest_hrv

    row = {"hrv_last_night": 55.0, "hrv_weekly_avg": 58.0, "hrv_status": "balanced"}
    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=row))
    ):
        result = await get_latest_hrv(1)
    assert result["hrv_last_night"] == 55.0


async def test_get_latest_hrv_not_found():
    from src.db.health import get_latest_hrv

    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=None))
    ):
        result = await get_latest_hrv(1)
    assert result is None


async def test_get_hrv_trend_returns_list():
    from src.db.health import get_hrv_trend

    rows = [
        {
            "date": date(2024, 1, 1),
            "hrv_last_night": 52.0,
            "hrv_weekly_avg": 55.0,
            "hrv_status": "balanced",
        },
        {
            "date": date(2024, 1, 2),
            "hrv_last_night": 54.0,
            "hrv_weekly_avg": 55.0,
            "hrv_status": "balanced",
        },
    ]
    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_hrv_trend(1, days=7)
    assert len(result) == 2
    assert result[0]["hrv_last_night"] == 52.0


async def test_get_latest_training_status_found():
    from src.db.health import get_latest_training_status

    row = {"date": date(2024, 1, 1), "training_status": "productive"}
    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=row))
    ):
        result = await get_latest_training_status(1)
    assert result["training_status"] == "productive"


async def test_get_latest_training_status_not_found():
    from src.db.health import get_latest_training_status

    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=None))
    ):
        result = await get_latest_training_status(1)
    assert result is None


async def test_get_weekly_stats_returns_list():
    from src.db.health import get_weekly_stats

    rows = [
        {
            "week": date(2024, 1, 1),
            "activity_count": 4,
            "total_km": 42.0,
            "total_hours": 4.5,
            "run_km": 35.0,
            "ride_km": 7.0,
            "other_hours": 0.0,
        }
    ]
    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_weekly_stats(1, weeks=4)
    assert result[0]["run_km"] == 35.0


async def test_get_energy_metrics_with_data():
    import json

    from src.db.health import get_energy_metrics

    rows = [
        {
            "model": "energy_physical",
            "value": 72.0,
            "metadata": json.dumps({"tsb": 1.5}),
        },
        {"model": "energy_autonomic", "value": 65.0, "metadata": None},
        {
            "model": "energy_cognitive",
            "value": 80.0,
            "metadata": json.dumps({"debt_hours": 0.5}),
        },
    ]
    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_energy_metrics(1)
    assert result["energy_physical"]["score"] == 72.0
    assert result["energy_physical"]["tsb"] == 1.5
    assert result["energy_autonomic"]["score"] == 65.0
    assert "debt_hours" in result["energy_cognitive"]


async def test_get_readiness_gut_erholt():
    # Gewichtung: Autonom 60% + Kognitiv 40% (kein TSB mehr)
    # 85×0.6 + 78×0.4 = 51 + 31.2 = 82.2 → ≥75 "Gut erholt"
    import json

    from src.db.health import get_readiness

    rows = [
        {"model": "energy_autonomic", "value": 85.0, "metadata": json.dumps({})},
        {"model": "energy_cognitive", "value": 78.0, "metadata": json.dumps({})},
    ]
    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_readiness(1)
    assert result["score"] >= 75
    assert result["label"] == "Gut erholt"
    assert "energy_physical" not in result  # TSB bewusst entfernt


async def test_get_readiness_in_ordnung():
    # 60×0.6 + 60×0.4 = 60 → ≥55 "In Ordnung"
    import json

    from src.db.health import get_readiness

    rows = [
        {"model": "energy_autonomic", "value": 60.0, "metadata": json.dumps({})},
        {"model": "energy_cognitive", "value": 60.0, "metadata": json.dumps({})},
    ]
    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_readiness(1)
    assert 55 <= result["score"] < 75
    assert result["label"] == "In Ordnung"


async def test_get_readiness_erholen():
    # 40×0.6 + 40×0.4 = 40 → ≥35 "Erholen"
    import json

    from src.db.health import get_readiness

    rows = [
        {"model": "energy_autonomic", "value": 40.0, "metadata": json.dumps({})},
        {"model": "energy_cognitive", "value": 40.0, "metadata": json.dumps({})},
    ]
    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_readiness(1)
    assert 35 <= result["score"] < 55
    assert result["label"] == "Erholen"


async def test_get_readiness_erschoepft():
    # 20×0.6 + 20×0.4 = 20 → <35 "Erschöpft"
    import json

    from src.db.health import get_readiness

    rows = [
        {"model": "energy_autonomic", "value": 20.0, "metadata": json.dumps({})},
        {"model": "energy_cognitive", "value": 20.0, "metadata": json.dumps({})},
    ]
    with patch(
        "src.db.health.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_readiness(1)
    assert result["score"] < 35
    assert result["label"] == "Erschöpft"


# ── seizures (async DB functions) ─────────────────────────────────────────────


async def test_save_seizure_success():
    from src.db.seizures import save_seizure

    with patch(
        "src.db.seizures.get_pool",
        AsyncMock(return_value=_pool_mock(fetchrow={"id": 42})),
    ):
        result = await save_seizure(
            1, datetime(2024, 1, 15, 10, 30), 90, "tonic-clonic", 3, "notes"
        )
    assert result == 42


async def test_save_seizure_raises_on_null_row():
    from src.db.seizures import save_seizure

    with patch(
        "src.db.seizures.get_pool", AsyncMock(return_value=_pool_mock(fetchrow=None))
    ):
        with pytest.raises(RuntimeError, match="INSERT RETURNING"):
            await save_seizure(1, datetime(2024, 1, 15), None, "absence", None, None)


async def test_get_seizures_formats_datetime():
    from src.db.seizures import get_seizures

    ts = datetime(2024, 3, 1, 8, 0, tzinfo=timezone.utc)
    rows = [
        {
            "id": 1,
            "occurred_at": ts,
            "duration_seconds": 60,
            "type": "tonic-clonic",
            "severity": 2,
            "notes": "",
        }
    ]
    with patch(
        "src.db.seizures.get_pool", AsyncMock(return_value=_pool_mock(fetch=rows))
    ):
        result = await get_seizures(1, days=30)
    assert result[0]["occurred_at"] == ts.isoformat()
    assert result[0]["id"] == 1


async def test_get_seizures_empty():
    from src.db.seizures import get_seizures

    with patch(
        "src.db.seizures.get_pool", AsyncMock(return_value=_pool_mock(fetch=[]))
    ):
        result = await get_seizures(1)
    assert result == []


async def test_get_seizure_risk_ok_no_flags():
    from src.db.seizures import get_seizure_risk

    pool = AsyncMock()
    # 1 night × 8h = no sleep debt
    pool.fetch = AsyncMock(return_value=[{"total_sleep_seconds": 28800}])
    yesterday = {
        "avg_stress": 40,
        "body_battery_low": 50.0,
        "resting_hr": None,
        "intensity_vigorous": 20,
        "hrv_last_night": 62.0,
        "hrv_weekly_avg": 65.0,
    }
    pool.fetchrow = AsyncMock(return_value=yesterday)
    with patch("src.db.seizures.get_pool", AsyncMock(return_value=pool)):
        result = await get_seizure_risk(1)
    assert result["level"] == "ok"
    assert result["flags"] == []


async def test_get_seizure_risk_red_sleep_debt_and_flags():
    from src.db.seizures import get_seizure_risk

    pool = AsyncMock()
    # 7 nights × 6h sleep = 7h debt → red
    pool.fetch = AsyncMock(return_value=[{"total_sleep_seconds": 21600}] * 7)
    yesterday = {
        "avg_stress": 80,
        "body_battery_low": 10.0,
        "resting_hr": 75.0,
        "intensity_vigorous": 90,
        "hrv_last_night": 40.0,
        "hrv_weekly_avg": 65.0,
    }
    hr_baseline = {"baseline": 60.0}
    pool.fetchrow = AsyncMock(side_effect=[yesterday, hr_baseline])
    with patch("src.db.seizures.get_pool", AsyncMock(return_value=pool)):
        result = await get_seizure_risk(1)
    assert result["level"] == "red"
    assert len(result["flags"]) >= 3
    assert result["sleep_debt_h"] == 7.0


async def test_get_seizure_risk_no_yesterday_row():
    from src.db.seizures import get_seizure_risk

    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    with patch("src.db.seizures.get_pool", AsyncMock(return_value=pool)):
        result = await get_seizure_risk(1)
    assert result["level"] == "ok"
    assert result["flags"] == []
    assert result["sleep_debt_h"] == 0.0


# ── users: set_libre_unlinked ─────────────────────────────────────────────────


async def test_set_libre_unlinked():
    from unittest.mock import MagicMock

    from src.db.users import set_libre_unlinked

    conn = AsyncMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=False)
    transaction_ctx = MagicMock()
    transaction_ctx.__aenter__ = AsyncMock(return_value=None)
    transaction_ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.transaction = MagicMock(return_value=transaction_ctx)

    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await set_libre_unlinked(1)

    assert conn.execute.call_count == 3


# ── pool: Settings.db_url property ───────────────────────────────────────────


def test_settings_db_url_format():
    from src.db.pool import Settings

    s = Settings(  # type: ignore[call-arg]  # pragma: allowlist secret
        db_user="admin",
        db_password="secret",  # pragma: allowlist secret
        db_app_user="app",
        db_app_password="pass",  # pragma: allowlist secret
        session_secret="s",  # pragma: allowlist secret
    )
    url = s.db_url
    assert url.startswith("postgresql://app:")
    assert url.endswith("@db:5432/garmin")


async def test_increment_failed_login_executes_update():
    from src.db.users import increment_failed_login

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await increment_failed_login(1)
    pool.execute.assert_awaited_once()
    assert "failed_login_attempts" in pool.execute.call_args[0][0]


async def test_lock_user_until_executes_update():
    from datetime import datetime, timezone

    from src.db.users import lock_user_until

    pool = _pool_mock()
    until = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await lock_user_until(1, until)
    pool.execute.assert_awaited_once()
    call_args = pool.execute.call_args[0]
    assert "locked_until" in call_args[0]
    assert call_args[1] == until
    assert call_args[2] == 1


async def test_reset_failed_login_executes_update():
    from src.db.users import reset_failed_login

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await reset_failed_login(1)
    pool.execute.assert_awaited_once()
    call_args = pool.execute.call_args[0]
    assert "failed_login_attempts" in call_args[0]
    assert "locked_until" in call_args[0]


async def test_set_email_verified_executes_update():
    from src.db.users import set_email_verified

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await set_email_verified(1)
    pool.execute.assert_awaited_once()
    assert "email_verified_at" in pool.execute.call_args[0][0]
    assert pool.execute.call_args[0][1] == 1


async def test_update_password_executes_query():
    from src.db.users import update_password

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await update_password(1, "hashed")  # pragma: allowlist secret

    pool.execute.assert_awaited_once()
    call_args = pool.execute.call_args[0]
    assert "password_hash" in call_args[0].lower()
    assert call_args[1] == "hashed"  # pragma: allowlist secret
    assert call_args[2] == 1


async def test_delete_user_executes_transaction():
    from unittest.mock import MagicMock

    from src.db.users import delete_user

    conn = AsyncMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=False)
    transaction_ctx = MagicMock()
    transaction_ctx.__aenter__ = AsyncMock(return_value=None)
    transaction_ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.transaction = MagicMock(return_value=transaction_ctx)

    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await delete_user(1)

    assert conn.execute.call_count == 9
    deleted_tables = [call[0][0] for call in conn.execute.call_args_list]
    assert any("users" in q for q in deleted_tables)
    assert any("activities" in q for q in deleted_tables)
    assert any("ml_predictions" in q for q in deleted_tables)


async def test_save_consent_executes_upsert():
    from src.db.users import save_consent

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await save_consent(
            1,
            "health_data",
            True,
            "a1b2c3d4e5f6",  # pragma: allowlist secret
        )
    pool.execute.assert_awaited_once()
    sql = pool.execute.call_args[0][0]
    assert "user_consents" in sql
    assert "ON CONFLICT" in sql


async def test_save_consent_uses_ip_address_hash_column():
    """ip_address_hash column name must be used (not ip_address)."""
    from src.db.users import save_consent

    pool = _pool_mock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await save_consent(1, "terms", True, "abc123def456")  # pragma: allowlist secret
    sql = pool.execute.call_args[0][0]
    assert "ip_address_hash" in sql
    assert "::inet" not in sql  # must not cast as INET (raw hash is TEXT)


async def test_delete_user_removes_token_dir_when_exists():
    from unittest.mock import MagicMock, patch

    from src.db.users import delete_user

    conn = AsyncMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=False)
    transaction_ctx = MagicMock()
    transaction_ctx.__aenter__ = AsyncMock(return_value=None)
    transaction_ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.transaction = MagicMock(return_value=transaction_ctx)

    mock_path = MagicMock()
    mock_path.exists.return_value = True

    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        with patch("src.db.users.Path", return_value=mock_path):
            with patch("src.db.users.shutil.rmtree") as mock_rmtree:
                await delete_user(42)

    mock_rmtree.assert_called_once_with(mock_path)


async def test_export_user_data_raises_when_user_not_found():
    from unittest.mock import MagicMock

    from src.db.users import export_user_data

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_ctx)

    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        with pytest.raises(RuntimeError, match="not found"):
            await export_user_data(99)


async def test_export_user_data_returns_dict():
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    from src.db.users import export_user_data

    user_row = {
        "id": 1,
        "name": "Test",
        "email": "test@example.com",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "email_verified_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
        "date_of_birth": None,
        "sex": None,
        "epilepsy_mode": False,
        "spo2_enabled": False,
        "garmin_linked": False,
        "garmin_email": None,
        "libre_linked": False,
        "libre_email": None,
    }
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=user_row)
    conn.fetch = AsyncMock(return_value=[])
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_ctx)

    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        result = await export_user_data(1)

    assert result["schema_version"] == "1.0"
    assert result["user"]["email"] == "test@example.com"
    assert "password_hash" not in result["user"]
    assert "activities" in result
    assert result["activities"] == []


async def test_get_pool_creates_pool_when_none():
    import src.db.pool as pool_module

    saved = pool_module._pool
    pool_module._pool = None
    try:
        mock_pool = AsyncMock()
        mock_settings = MagicMock()
        mock_settings.db_url = (
            "postgresql://app:testpwd@db:5432/garmin"  # pragma: allowlist secret
        )
        with patch(
            "src.db.pool.asyncpg.create_pool", AsyncMock(return_value=mock_pool)
        ):
            with patch("src.db.pool.Settings", return_value=mock_settings):
                result = await pool_module.get_pool()
        assert result is mock_pool
        assert pool_module._pool is mock_pool
    finally:
        pool_module._pool = saved


# ── users: get_user_token / save_user_token ───────────────────────────────────


async def test_get_user_token_returns_bytes_when_row_exists():
    from src.db.users import get_user_token

    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"token_data": b"encrypted-blob"})
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        result = await get_user_token(1, "garmin")
    assert result == b"encrypted-blob"


async def test_get_user_token_returns_none_when_no_row():
    from src.db.users import get_user_token

    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        result = await get_user_token(1, "garmin")
    assert result is None


async def test_save_user_token_executes_upsert():
    from src.db.users import save_user_token

    pool = AsyncMock()
    with patch("src.db.users.get_pool", AsyncMock(return_value=pool)):
        await save_user_token(1, "garmin", b"token-bytes")
    pool.execute.assert_awaited_once()
    call_sql = pool.execute.await_args[0][0]
    assert "ON CONFLICT" in call_sql
    assert "user_tokens" in call_sql
