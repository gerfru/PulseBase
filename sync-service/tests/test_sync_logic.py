"""Unit tests for _sync_activities and _sync_day in sync-service main.py.

Tests the Garmin-Sync core orchestration logic. All external dependencies
(GarminClient, TimescaleRepository, mapper functions) are mocked — no network
or DB required. Pattern mirrors test_main.py (AsyncMock repo, MagicMock client).
"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import _sync_activities, _sync_day

_DATE = date(2026, 6, 2)
_USER_ID = 7


# ── _sync_day ─────────────────────────────────────────────────────────────────


class TestSyncDay:
    async def test_all_metrics_saved_on_success(self):
        """Happy path: all 6 metric blocks succeed → all repo upsert/insert methods called."""
        client = MagicMock()
        repo = AsyncMock()
        repo.sleep_exists.return_value = False

        mock_session = MagicMock()
        mock_session.garmin_sleep_id = "sleep-abc"

        with (
            patch("main.garmin_call", side_effect=lambda fn: fn()),
            patch("main.map_summary", return_value=MagicMock()),
            patch("main.map_sleep", return_value=mock_session),
            patch("main.map_hrv", return_value=MagicMock()),
            patch("main.map_body_battery", return_value=[MagicMock()]),
            patch("main.map_stress", return_value=[MagicMock()]),
            patch("main.map_training_status", return_value=MagicMock()),
        ):
            await _sync_day(client, repo, _USER_ID, _DATE)

        repo.upsert_daily.assert_called_once()
        repo.save_sleep.assert_called_once()
        repo.upsert_hrv.assert_called_once()
        assert repo.bulk_insert.call_count == 2  # body_battery + stress
        repo.upsert_training_status.assert_called_once()

    async def test_daily_failure_does_not_stop_sleep(self):
        """Exception in daily_summary block is isolated; sleep block still executes."""
        client = MagicMock()
        repo = AsyncMock()
        client.get_daily_summary.side_effect = RuntimeError("no daily data")
        repo.sleep_exists.return_value = False

        mock_session = MagicMock()
        mock_session.garmin_sleep_id = "sleep-xyz"

        with (
            patch("main.garmin_call", side_effect=lambda fn: fn()),
            patch("main.map_sleep", return_value=mock_session),
            patch("main.map_hrv", return_value=None),
            patch("main.map_body_battery", return_value=[]),
            patch("main.map_stress", return_value=[]),
            patch("main.map_training_status", return_value=None),
        ):
            await _sync_day(client, repo, _USER_ID, _DATE)

        repo.upsert_daily.assert_not_called()
        repo.save_sleep.assert_called_once()

    async def test_all_blocks_fail_does_not_raise(self):
        """All 6 Garmin calls failing is handled gracefully — no exception propagates."""
        client = MagicMock()
        repo = AsyncMock()
        client.get_daily_summary.side_effect = ConnectionError("down")
        client.get_sleep.side_effect = ConnectionError("down")
        client.get_hrv.side_effect = ConnectionError("down")
        client.get_body_battery.side_effect = ConnectionError("down")
        client.get_stress.side_effect = ConnectionError("down")
        client.get_training_status.side_effect = ConnectionError("down")

        with patch("main.garmin_call", side_effect=lambda fn: fn()):
            await _sync_day(client, repo, _USER_ID, _DATE)  # must not raise

        repo.upsert_daily.assert_not_called()
        repo.save_sleep.assert_not_called()
        repo.upsert_hrv.assert_not_called()
        repo.bulk_insert.assert_not_called()
        repo.upsert_training_status.assert_not_called()

    async def test_sleep_not_saved_when_already_in_db(self):
        """Sleep session is skipped if sleep_exists returns True."""
        client = MagicMock()
        repo = AsyncMock()
        repo.sleep_exists.return_value = True  # duplicate guard

        mock_session = MagicMock()
        mock_session.garmin_sleep_id = "sleep-abc"

        with (
            patch("main.garmin_call", side_effect=lambda fn: fn()),
            patch("main.map_summary", return_value=MagicMock()),
            patch("main.map_sleep", return_value=mock_session),
            patch("main.map_hrv", return_value=None),
            patch("main.map_body_battery", return_value=[]),
            patch("main.map_stress", return_value=[]),
            patch("main.map_training_status", return_value=None),
        ):
            await _sync_day(client, repo, _USER_ID, _DATE)

        repo.save_sleep.assert_not_called()

    async def test_hrv_not_saved_when_map_returns_none(self):
        """When map_hrv returns None (no HRV data available), upsert_hrv is not called."""
        client = MagicMock()
        repo = AsyncMock()
        repo.sleep_exists.return_value = True

        with (
            patch("main.garmin_call", side_effect=lambda fn: fn()),
            patch("main.map_summary", return_value=MagicMock()),
            patch("main.map_sleep", return_value=None),
            patch("main.map_hrv", return_value=None),
            patch("main.map_body_battery", return_value=[]),
            patch("main.map_stress", return_value=[]),
            patch("main.map_training_status", return_value=None),
        ):
            await _sync_day(client, repo, _USER_ID, _DATE)

        repo.upsert_hrv.assert_not_called()

    async def test_training_status_not_saved_when_map_returns_none(self):
        """When map_training_status returns None, upsert_training_status is not called."""
        client = MagicMock()
        repo = AsyncMock()
        repo.sleep_exists.return_value = True

        with (
            patch("main.garmin_call", side_effect=lambda fn: fn()),
            patch("main.map_summary", return_value=MagicMock()),
            patch("main.map_sleep", return_value=None),
            patch("main.map_hrv", return_value=None),
            patch("main.map_body_battery", return_value=[]),
            patch("main.map_stress", return_value=[]),
            patch("main.map_training_status", return_value=None),
        ):
            await _sync_day(client, repo, _USER_ID, _DATE)

        repo.upsert_training_status.assert_not_called()


# ── _sync_activities ──────────────────────────────────────────────────────────


class TestSyncActivities:
    async def test_happy_path_saves_activity_and_records(self):
        """Activity with ID + no existing records → save_activity + bulk_insert_records called."""
        client = MagicMock()
        repo = AsyncMock()
        repo.save_activity.return_value = 42
        repo.records_exist.return_value = False

        mock_activity = MagicMock()
        mock_records = [MagicMock()]

        with (
            patch("main.garmin_call", side_effect=lambda fn: fn()),
            patch("main.map_activity", return_value=mock_activity),
            patch("main.map_records", return_value=mock_records),
        ):
            client.get_activities.return_value = [
                {"activityId": 101, "sport": "running"}
            ]
            client.get_activity_details.return_value = {}
            await _sync_activities(client, repo, _USER_ID, _DATE, _DATE)

        repo.save_activity.assert_called_once()
        repo.bulk_insert_records.assert_called_once_with(42, mock_records)

    async def test_skips_raw_without_activity_id(self):
        """Raw activity dict with no activityId is silently skipped."""
        client = MagicMock()
        repo = AsyncMock()

        with patch("main.garmin_call", side_effect=lambda fn: fn()):
            client.get_activities.return_value = [{"sport": "running"}]  # no activityId
            await _sync_activities(client, repo, _USER_ID, _DATE, _DATE)

        repo.save_activity.assert_not_called()

    async def test_skips_bulk_insert_when_records_already_exist(self):
        """Activity already has records in DB → bulk_insert_records not called."""
        client = MagicMock()
        repo = AsyncMock()
        repo.save_activity.return_value = 77
        repo.records_exist.return_value = True  # duplicate guard

        mock_activity = MagicMock()

        with (
            patch("main.garmin_call", side_effect=lambda fn: fn()),
            patch("main.map_activity", return_value=mock_activity),
        ):
            client.get_activities.return_value = [{"activityId": 202}]
            await _sync_activities(client, repo, _USER_ID, _DATE, _DATE)

        repo.bulk_insert_records.assert_not_called()
