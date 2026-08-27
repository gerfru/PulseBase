"""Unit tests for ml-service db/ layer (users_ml, activities, health, pool).

All tests mock the asyncpg pool so no database connection is required.
"""

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from db.users_ml import (
    count_energy_gaps,
    get_active_users,
    get_ml_requested_users,
    get_user_profile,
    get_yesterday_prediction,
    mark_ml_done,
    save_prediction,
)
from db.events import (
    claim_ml_events,
    complete_event,
    fail_event,
    requeue_stale_ml_events,
)


@pytest.fixture
def pool():
    mock = MagicMock()
    mock.execute = AsyncMock()
    mock.fetch = AsyncMock(return_value=[])
    mock.fetchrow = AsyncMock(return_value=None)
    mock.fetchval = AsyncMock(return_value=None)
    with patch("db.pool._pool", mock):
        yield mock


# ── save_prediction ───────────────────────────────────────────────────────────


class TestSavePrediction:
    async def test_executes_upsert(self, pool):
        await save_prediction(1, date(2026, 5, 1), "energy_physical", 75.0)
        pool.execute.assert_called_once()

    async def test_passes_correct_date_model_value(self, pool):
        await save_prediction(1, date(2026, 5, 1), "test_model", 42.0)
        args = pool.execute.call_args.args
        assert date(2026, 5, 1) in args
        assert "test_model" in args
        assert 42.0 in args

    async def test_serializes_metadata_as_json_string(self, pool):
        meta = {"score": 75.0, "reason": "ok"}
        await save_prediction(1, date(2026, 5, 1), "m", 1.0, meta)
        args = pool.execute.call_args.args
        json_args = [a for a in args if isinstance(a, str) and "{" in a]
        assert json_args, "metadata must be JSON-encoded"
        assert json.loads(json_args[0]) == meta

    async def test_none_metadata_passes_none(self, pool):
        await save_prediction(1, date(2026, 5, 1), "m", 1.0, None)
        args = pool.execute.call_args.args
        assert None in args


@pytest.fixture
def event_pool():
    pool = MagicMock()
    pool.execute = AsyncMock()
    conn = MagicMock()
    conn.fetch = AsyncMock()
    transaction = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=transaction)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
    with patch("db.pool._pool", pool):
        yield pool, conn


class TestMlEvents:
    async def test_claims_pending_ml_events_atomically(self, event_pool):
        pool, conn = event_pool
        conn.fetch.return_value = [{"id": 7, "user_id": 42, "attempts": 1}]

        result = await claim_ml_events(limit=3)

        assert result == [{"id": 7, "user_id": 42, "attempts": 1}]
        conn.transaction.return_value.__aenter__.assert_awaited_once()
        assert conn.fetch.call_args.args[1] == 3
        assert "FOR UPDATE SKIP LOCKED" in conn.fetch.call_args.args[0]

    async def test_complete_event_updates_only_processing_ml_event(self, event_pool):
        pool, conn = event_pool

        await complete_event(7)

        pool.execute.assert_awaited_once()
        assert pool.execute.call_args.args[1] == 7
        assert "status = 'completed'" in pool.execute.call_args.args[0]

    async def test_fail_event_requeues_with_bounded_error(self, event_pool):
        pool, conn = event_pool
        error = "x" * 5000

        await fail_event(7, error, max_attempts=4, retry_delay_seconds=30)

        args = pool.execute.call_args.args
        assert args[1:4] == (7, 4, 30)
        assert len(args[4]) == 2000
        assert "status = CASE" in args[0]

    async def test_requeues_stale_events_and_returns_count(self, event_pool):
        pool, conn = event_pool
        pool.execute.return_value = "UPDATE 2"

        assert await requeue_stale_ml_events(lease_seconds=900) == 2
        assert pool.execute.call_args.args[1] == 900

    async def test_none_value_is_passed_through(self, pool):
        await save_prediction(1, date(2026, 5, 1), "m", None)
        args = pool.execute.call_args.args
        assert None in args


# ── get_active_users ──────────────────────────────────────────────────────────


class TestGetActiveUsers:
    async def test_returns_empty_list_when_no_users(self, pool):
        pool.fetch.return_value = []
        assert await get_active_users() == []

    async def test_returns_dict_list(self, pool):
        pool.fetch.return_value = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        result = await get_active_users()
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["name"] == "Bob"


# ── get_yesterday_prediction ──────────────────────────────────────────────────


class TestGetYesterdayPrediction:
    async def test_returns_none_when_no_row(self, pool):
        pool.fetchrow.return_value = None
        assert await get_yesterday_prediction(1, "energy_physical") is None

    async def test_returns_none_when_value_is_none(self, pool):
        pool.fetchrow.return_value = {"value": None}
        assert await get_yesterday_prediction(1, "energy_physical") is None

    async def test_returns_float_when_row_exists(self, pool):
        pool.fetchrow.return_value = {"value": 72.5}
        result = await get_yesterday_prediction(1, "energy_physical")
        assert result == pytest.approx(72.5)

    async def test_passes_user_id_and_model_to_query(self, pool):
        pool.fetchrow.return_value = None
        await get_yesterday_prediction(99, "anomaly_hr")
        args = pool.fetchrow.call_args.args
        assert 99 in args
        assert "anomaly_hr" in args


# ── count_energy_gaps ─────────────────────────────────────────────────────────


class TestCountEnergyGaps:
    async def test_returns_zero_when_no_gaps(self, pool):
        pool.fetchrow.return_value = {"gaps": 0}
        assert await count_energy_gaps(1) == 0

    async def test_returns_gap_count(self, pool):
        pool.fetchrow.return_value = {"gaps": 7}
        assert await count_energy_gaps(1) == 7

    async def test_returns_zero_on_none_row(self, pool):
        pool.fetchrow.return_value = None
        assert await count_energy_gaps(1) == 0


# ── mark_ml_done ──────────────────────────────────────────────────────────────


class TestMarkMlDone:
    async def test_executes_update(self, pool):
        await mark_ml_done(42)
        pool.execute.assert_called_once()

    async def test_passes_user_id_to_query(self, pool):
        await mark_ml_done(99)
        args = pool.execute.call_args.args
        assert 99 in args


# ── get_user_profile ──────────────────────────────────────────────────────────


class TestGetUserProfile:
    async def test_returns_no_profile_when_no_row(self, pool):
        pool.fetchrow.return_value = None
        result = await get_user_profile(1)
        assert result["has_profile"] is False
        assert result["age"] is None
        assert result["sex"] is None

    async def test_returns_no_profile_when_sex_missing(self, pool):
        pool.fetchrow.return_value = {
            "sex": None,
            "date_of_birth": "1990-01-01",
            "age": 36,
        }
        result = await get_user_profile(1)
        assert result["has_profile"] is False

    async def test_returns_no_profile_when_dob_missing(self, pool):
        pool.fetchrow.return_value = {"sex": "male", "date_of_birth": None, "age": None}
        result = await get_user_profile(1)
        assert result["has_profile"] is False

    async def test_returns_full_profile_when_complete(self, pool):
        pool.fetchrow.return_value = {
            "sex": "male",
            "date_of_birth": "1990-01-01",
            "age": 36,
        }
        result = await get_user_profile(1)
        assert result["has_profile"] is True
        assert result["age"] == 36
        assert result["sex"] == "male"
        assert result["date_of_birth"] == "1990-01-01"


# ── get_ml_requested_users ────────────────────────────────────────────────────


class TestGetMlRequestedUsers:
    async def test_returns_empty_when_none_requested(self, pool):
        pool.fetch.return_value = []
        assert await get_ml_requested_users() == []

    async def test_returns_list_of_dicts(self, pool):
        pool.fetch.return_value = [{"id": 5}, {"id": 7}]
        result = await get_ml_requested_users()
        assert len(result) == 2
        assert result[0]["id"] == 5


# ── db/pool ───────────────────────────────────────────────────────────────────


class TestPool:
    async def test_init_pool_creates_pool(self):
        import db.pool as pool_mod

        mock_pool = MagicMock()
        with patch(
            "asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool
        ):
            await pool_mod.init_pool("postgresql://u:p@localhost/test")
        assert pool_mod._pool is mock_pool
        pool_mod._pool = None  # cleanup

    async def test_close_pool_noop_when_none(self):
        import db.pool as pool_mod

        original = pool_mod._pool
        pool_mod._pool = None
        await pool_mod.close_pool()  # must not raise
        pool_mod._pool = original

    async def test_close_pool_calls_close(self):
        import db.pool as pool_mod

        mock_pool = AsyncMock()
        pool_mod._pool = mock_pool
        await pool_mod.close_pool()
        mock_pool.close.assert_called_once()
        pool_mod._pool = None

    def test_pool_or_raise_raises_when_none(self):
        import db.pool as pool_mod

        original = pool_mod._pool
        pool_mod._pool = None
        with pytest.raises(RuntimeError, match="Pool not initialized"):
            pool_mod._pool_or_raise()
        pool_mod._pool = original


# ── db/activities ─────────────────────────────────────────────────────────────


class TestDbActivities:
    async def test_get_readiness_training_rows_empty(self, pool):
        from db.activities import get_readiness_training_rows

        pool.fetch.return_value = []
        assert await get_readiness_training_rows(1) == []

    async def test_get_readiness_training_rows_returns_dicts(self, pool):
        from db.activities import get_readiness_training_rows

        pool.fetch.return_value = [{"date": date(2026, 4, 27), "resting_hr": 52}]
        result = await get_readiness_training_rows(1)
        assert len(result) == 1
        assert result[0]["resting_hr"] == 52

    async def test_get_sleep_hrv_pairs_empty(self, pool):
        from db.activities import get_sleep_hrv_pairs

        pool.fetch.return_value = []
        assert await get_sleep_hrv_pairs(1) == []

    async def test_get_sleep_hrv_pairs_returns_tuples(self, pool):
        from db.activities import get_sleep_hrv_pairs

        pool.fetch.return_value = [{"sleep_score": 78.0, "hrv_last_night": 52.0}]
        result = await get_sleep_hrv_pairs(1)
        assert result == [(78.0, 52.0)]

    async def test_get_sleep_resting_hr_pairs_returns_tuples(self, pool):
        from db.activities import get_sleep_resting_hr_pairs

        pool.fetch.return_value = [{"sleep_score": 78.0, "resting_hr": 55.0}]
        result = await get_sleep_resting_hr_pairs(1)
        assert result == [(78.0, 55.0)]

    async def test_get_bb_resting_hr_pairs_returns_tuples(self, pool):
        from db.activities import get_bb_resting_hr_pairs

        pool.fetch.return_value = [{"body_battery_high": 80.0, "resting_hr": 52.0}]
        result = await get_bb_resting_hr_pairs(1)
        assert result == [(80.0, 52.0)]

    async def test_get_activity_trimp_inputs_returns_dicts(self, pool):
        from db.activities import get_activity_trimp_inputs

        pool.fetch.return_value = [
            {"activity_date": date(2026, 4, 27), "avg_hr": 145.0}
        ]
        result = await get_activity_trimp_inputs(1)
        assert len(result) == 1
        assert result[0]["avg_hr"] == 145.0

    async def test_get_hrmax_returns_value(self, pool):
        from db.activities import get_hrmax

        pool.fetchrow.return_value = {"hrmax": 185.0}
        assert await get_hrmax(1) == pytest.approx(185.0)

    async def test_get_hrmax_falls_back_to_190_when_no_data(self, pool):
        from db.activities import get_hrmax

        pool.fetchrow.return_value = None
        assert await get_hrmax(1) == 190.0

    async def test_get_hrmax_falls_back_when_value_none(self, pool):
        from db.activities import get_hrmax

        pool.fetchrow.return_value = {"hrmax": None}
        assert await get_hrmax(1) == 190.0

    async def test_get_latest_features_returns_dict(self, pool):
        from db.activities import get_latest_features

        pool.fetchrow.return_value = {"hrv_last_night": 45, "resting_hr": 52}
        result = await get_latest_features(1)
        assert result["resting_hr"] == 52

    async def test_get_latest_features_returns_empty_dict_when_none(self, pool):
        from db.activities import get_latest_features

        pool.fetchrow.return_value = None
        assert await get_latest_features(1) == {}

    async def test_get_todays_activity_hr_records_returns_tuple(self, pool):
        from db.activities import get_todays_activity_hr_records

        pool.fetch.return_value = [{"heart_rate": 140}, {"heart_rate": 155}]
        pool.fetchrow.return_value = {"resting_hr": 52.0}
        hr, rhr = await get_todays_activity_hr_records(1)
        assert hr == [140, 155]
        assert rhr == pytest.approx(52.0)

    async def test_get_todays_activity_hr_records_none_rhr(self, pool):
        from db.activities import get_todays_activity_hr_records

        pool.fetch.return_value = []
        pool.fetchrow.return_value = None
        hr, rhr = await get_todays_activity_hr_records(1)
        assert hr == []
        assert rhr is None

    async def test_get_running_economy_activities_returns_dicts(self, pool):
        from db.activities import get_running_economy_activities

        pool.fetch.return_value = [{"avg_ground_contact_time": 250}]
        result = await get_running_economy_activities(1)
        assert len(result) == 1


# ── db/health ─────────────────────────────────────────────────────────────────


class TestDbHealth:
    async def test_get_resting_hr_history_returns_list(self, pool):
        from db.health import get_resting_hr_history

        pool.fetch.return_value = [{"resting_hr": 52}, {"resting_hr": None}]
        result = await get_resting_hr_history(1)
        assert result == [52, None]

    async def test_get_today_resting_hr_returns_value(self, pool):
        from db.health import get_today_resting_hr

        pool.fetchrow.return_value = {"resting_hr": 55.0}
        assert await get_today_resting_hr(1) == 55.0

    async def test_get_today_resting_hr_returns_none(self, pool):
        from db.health import get_today_resting_hr

        pool.fetchrow.return_value = None
        assert await get_today_resting_hr(1) is None

    async def test_get_spo2_history_flat_returns_list(self, pool):
        from db.health import get_spo2_history_flat

        pool.fetch.return_value = [{"avg_spo2": 97.0}, {"avg_spo2": None}]
        result = await get_spo2_history_flat(1)
        assert result == [97.0, None]

    async def test_get_today_spo2_returns_none_when_no_row(self, pool):
        from db.health import get_today_spo2

        pool.fetchrow.return_value = None
        assert await get_today_spo2(1) is None

    async def test_get_sleep_duration_history_returns_list(self, pool):
        from db.health import get_sleep_duration_history

        pool.fetch.return_value = [{"total_sleep_seconds": 28800}]
        result = await get_sleep_duration_history(1)
        assert result == [28800]

    async def test_get_today_sleep_duration_returns_none(self, pool):
        from db.health import get_today_sleep_duration

        pool.fetchrow.return_value = None
        assert await get_today_sleep_duration(1) is None

    async def test_get_steps_history_returns_list(self, pool):
        from db.health import get_steps_history

        pool.fetch.return_value = [{"steps": 8500}, {"steps": None}]
        result = await get_steps_history(1)
        assert result == [8500, None]

    async def test_get_today_steps_returns_value(self, pool):
        from db.health import get_today_steps

        pool.fetchrow.return_value = {"steps": 12000}
        assert await get_today_steps(1) == 12000

    async def test_get_stress_history_returns_list(self, pool):
        from db.health import get_stress_history

        pool.fetch.return_value = [{"avg_stress": 35.0}]
        result = await get_stress_history(1)
        assert result == [35.0]

    async def test_get_today_stress_returns_none(self, pool):
        from db.health import get_today_stress

        pool.fetchrow.return_value = None
        assert await get_today_stress(1) is None

    async def test_get_hrv_history_for_energy_returns_list(self, pool):
        from db.health import get_hrv_history_for_energy

        pool.fetch.return_value = [{"hrv_last_night": 45}, {"hrv_last_night": None}]
        result = await get_hrv_history_for_energy(1)
        assert result == [45, None]

    async def test_get_sleep_data_7d_converts_seconds_to_hours(self, pool):
        from db.health import get_sleep_data_7d

        pool.fetch.return_value = [
            {
                "total_sleep_seconds": 28800,
                "deep_sleep_seconds": 5400,
                "rem_sleep_seconds": 7200,
            }
        ]
        result = await get_sleep_data_7d(1)
        assert len(result) == 1
        assert result[0]["total_h"] == pytest.approx(8.0)
        assert result[0]["deep_h"] == pytest.approx(1.5)

    async def test_get_sleep_data_7d_handles_none_seconds(self, pool):
        from db.health import get_sleep_data_7d

        pool.fetch.return_value = [
            {
                "total_sleep_seconds": None,
                "deep_sleep_seconds": None,
                "rem_sleep_seconds": None,
            }
        ]
        result = await get_sleep_data_7d(1)
        assert result[0]["total_h"] is None

    async def test_get_body_battery_today_returns_dicts(self, pool):
        from db.health import get_body_battery_today

        pool.fetch.return_value = [{"time": "2026-04-27", "value": 80}]
        result = await get_body_battery_today(1)
        assert len(result) == 1

    async def test_get_spo2_history_returns_dicts(self, pool):
        from db.health import get_spo2_history

        pool.fetch.return_value = [
            {"date": date(2026, 4, 27), "avg_spo2": 97, "min_spo2": 94}
        ]
        result = await get_spo2_history(1)
        assert len(result) == 1
        assert result[0]["avg_spo2"] == 97

    async def test_get_sleep_sessions_14d_returns_dicts(self, pool):
        from db.health import get_sleep_sessions_14d

        pool.fetch.return_value = [
            {"sleep_date": date(2026, 4, 27), "start_h": 23.5, "end_h": 7.5}
        ]
        result = await get_sleep_sessions_14d(1)
        assert len(result) == 1

    async def test_get_last_sleep_session_returns_dict(self, pool):
        from db.health import get_last_sleep_session

        pool.fetchrow.return_value = {
            "total_sleep_seconds": 27000,
            "deep_sleep_seconds": 5400,
        }
        result = await get_last_sleep_session(1)
        assert result is not None
        assert result["total_sleep_seconds"] == 27000

    async def test_get_last_sleep_session_returns_none(self, pool):
        from db.health import get_last_sleep_session

        pool.fetchrow.return_value = None
        assert await get_last_sleep_session(1) is None

    async def test_get_today_hrv_returns_float(self, pool):
        from db.health import get_today_hrv

        pool.fetchrow.return_value = {"hrv_last_night": 45}
        assert await get_today_hrv(1) == pytest.approx(45.0)

    async def test_get_today_hrv_returns_none_when_no_row(self, pool):
        from db.health import get_today_hrv

        pool.fetchrow.return_value = None
        assert await get_today_hrv(1) is None

    async def test_get_today_daily_summary_returns_dict(self, pool):
        from db.health import get_today_daily_summary

        pool.fetchrow.return_value = {"steps": 8000, "resting_hr": 52}
        result = await get_today_daily_summary(1)
        assert result is not None
        assert result["steps"] == 8000

    async def test_get_today_daily_summary_returns_none(self, pool):
        from db.health import get_today_daily_summary

        pool.fetchrow.return_value = None
        assert await get_today_daily_summary(1) is None

    async def test_get_body_battery_history_groups_by_day(self, pool):
        from datetime import datetime, timezone
        from db.health import get_body_battery_history

        t1 = datetime(2026, 4, 27, 8, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
        pool.fetch.return_value = [{"time": t1, "value": 80}, {"time": t2, "value": 75}]
        result = await get_body_battery_history(1)
        assert "2026-04-27" in result
        assert len(result["2026-04-27"]) == 2

    async def test_get_body_battery_history_empty(self, pool):
        from db.health import get_body_battery_history

        pool.fetch.return_value = []
        assert await get_body_battery_history(1) == {}


# ── db.pool — get_pool() ──────────────────────────────────────────────────────


class TestGetPool:
    def test_get_pool_delegates_to_pool_or_raise(self, pool):
        from db import pool as pool_mod

        pool_mod._pool = pool
        from db.pool import get_pool

        assert get_pool() is pool
        pool_mod._pool = None


# ── db.users_ml — get_prediction_for_date ────────────────────────────────────


class TestGetPredictionForDate:
    async def test_returns_float_when_row_exists(self, pool):
        from datetime import date
        from db.users_ml import get_prediction_for_date

        pool.fetchrow.return_value = {"value": 72.5}
        result = await get_prediction_for_date(
            1, date(2026, 1, 1), "body_battery_custom"
        )
        assert result == pytest.approx(72.5)

    async def test_returns_none_when_no_row(self, pool):
        from datetime import date
        from db.users_ml import get_prediction_for_date

        pool.fetchrow.return_value = None
        result = await get_prediction_for_date(
            1, date(2026, 1, 1), "body_battery_custom"
        )
        assert result is None

    async def test_returns_none_when_value_is_none(self, pool):
        from datetime import date
        from db.users_ml import get_prediction_for_date

        pool.fetchrow.return_value = {"value": None}
        result = await get_prediction_for_date(
            1, date(2026, 1, 1), "body_battery_custom"
        )
        assert result is None


# ── db.activities — get_backfill_activity_hrv_data ────────────────────────────


class TestGetBackfillActivityHrvData:
    async def test_returns_expected_structure(self, pool):
        from datetime import date
        from db.activities import get_backfill_activity_hrv_data

        pool.fetchrow.return_value = {"hrmax": 185.0}
        pool.fetch.side_effect = [
            [
                {
                    "activity_date": date(2026, 1, 1),
                    "avg_hr": 150.0,
                    "duration_seconds": 3600.0,
                    "resting_hr": 55.0,
                    "avg_ground_contact_time": None,
                    "avg_vertical_oscillation": None,
                    "avg_vertical_ratio": None,
                    "sport_type": "running",
                }
            ],
            [{"date": date(2026, 1, 1), "hrv_last_night": 48.0}],
        ]
        result = await get_backfill_activity_hrv_data(1)
        assert "hrmax" in result
        assert "act_rows" in result
        assert "hrv_by_date" in result
        assert "hrv_dates_sorted" in result

    async def test_defaults_hrmax_when_null(self, pool):
        from db.activities import get_backfill_activity_hrv_data

        pool.fetchrow.return_value = {"hrmax": None}
        pool.fetch.side_effect = [[], []]
        result = await get_backfill_activity_hrv_data(1)
        assert result["hrmax"] == pytest.approx(190.0)


# ── db.health — get_backfill_sleep_daily_gaps ─────────────────────────────────


class TestGetBackfillSleepDailyGaps:
    async def test_returns_expected_structure(self, pool):
        from datetime import date
        from db.health import get_backfill_sleep_daily_gaps

        pool.fetch.side_effect = [
            [
                {
                    "sleep_date": date(2026, 1, 1),
                    "total_sleep_seconds": 27000,
                    "deep_sleep_seconds": 5400,
                    "rem_sleep_seconds": 7200,
                }
            ],
            [{"date": date(2026, 1, 1), "avg_stress": 35, "body_battery_high": 80}],
            [{"date": date(2026, 1, 2)}],
        ]
        result = await get_backfill_sleep_daily_gaps(1)
        assert "sleep_by_date" in result
        assert "daily_by_date" in result
        assert "gap_dates" in result

    async def test_handles_null_sleep_seconds(self, pool):
        from datetime import date
        from db.health import get_backfill_sleep_daily_gaps

        pool.fetch.side_effect = [
            [
                {
                    "sleep_date": date(2026, 1, 1),
                    "total_sleep_seconds": None,
                    "deep_sleep_seconds": None,
                    "rem_sleep_seconds": None,
                }
            ],
            [],
            [],
        ]
        result = await get_backfill_sleep_daily_gaps(1)
        entry = result["sleep_by_date"][date(2026, 1, 1)]
        assert entry["total_h"] is None
