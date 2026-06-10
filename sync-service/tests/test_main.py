"""Unit tests for sync-service main.py orchestration.

Tests the independently testable parts: garmin_call retry logic,
sync_all_users error-tolerance, process_sync_requests ML-flag side-effects,
and sync_all_libre error classification. All external dependencies
(DB, Garmin/Libre clients) are mocked — no network or DB required.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from libre.client import LibreAuthError
from datetime import date
from pathlib import Path

from garmin.client import garmin_call
from sync_runner import (
    _sync_activities,
    _sync_day,
    process_sync_requests,
    sync_all_libre,
    sync_all_users,
    sync_libre_user,
    sync_user,
)


# ── garmin_call — Tenacity retry logic ──────────────────────────────────────


class TestGarminCall:
    @patch("time.sleep")
    def test_succeeds_on_first_try(self, mock_sleep):
        fn = MagicMock(return_value="ok")
        assert garmin_call(fn) == "ok"
        assert fn.call_count == 1
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_retries_on_exception_and_succeeds(self, mock_sleep):
        fn = MagicMock(side_effect=[RuntimeError("fail"), RuntimeError("fail"), "ok"])
        result = garmin_call(fn)
        assert result == "ok"
        assert fn.call_count == 3

    @patch("time.sleep")
    def test_raises_after_max_retries(self, mock_sleep):
        fn = MagicMock(side_effect=ValueError("always fails"))
        with pytest.raises(ValueError, match="always fails"):
            garmin_call(fn)
        assert fn.call_count == 3

    @patch("time.sleep")
    def test_returns_none_correctly(self, mock_sleep):
        fn = MagicMock(return_value=None)
        # None is a valid return — must not trigger retry
        assert garmin_call(fn) is None
        assert fn.call_count == 1


# ── sync_all_users — error-tolerance ─────────────────────────────────────────


class TestSyncAllUsers:
    async def test_no_users_is_noop(self):
        repo = AsyncMock()
        repo.get_active_users.return_value = []
        await sync_all_users(repo, days=7, settings=MagicMock())
        repo.mark_sync_done.assert_not_called()

    async def test_calls_sync_user_for_each_active_user(self):
        repo = AsyncMock()
        repo.get_active_users.return_value = [
            {"id": 1, "garmin_email": "a@test.com"},
            {"id": 2, "garmin_email": "b@test.com"},
        ]
        with patch("sync_runner.sync_user", new_callable=AsyncMock) as mock_sync:
            await sync_all_users(repo, days=7, settings=MagicMock())
        assert mock_sync.call_count == 2

    async def test_continues_after_single_user_failure(self):
        repo = AsyncMock()
        repo.get_active_users.return_value = [
            {"id": 1, "garmin_email": "a@test.com"},
            {"id": 2, "garmin_email": "b@test.com"},
        ]
        synced_ids: list[int] = []

        async def fake_sync(user, repo, days, settings):
            if user["id"] == 1:
                raise RuntimeError("user 1 failed")
            synced_ids.append(user["id"])

        with patch("sync_runner.sync_user", side_effect=fake_sync):
            await sync_all_users(repo, days=7, settings=MagicMock())

        assert 2 in synced_ids, "user 2 must be synced even after user 1 fails"

    async def test_mark_sync_done_called_for_all_users(self):
        repo = AsyncMock()
        repo.get_active_users.return_value = [
            {"id": 10, "garmin_email": "x@test.com"},
            {"id": 20, "garmin_email": "y@test.com"},
        ]

        async def partial_failure(user, repo, days, settings):
            if user["id"] == 10:
                raise RuntimeError("fail")

        with patch("sync_runner.sync_user", side_effect=partial_failure):
            await sync_all_users(repo, days=7, settings=MagicMock())

        # mark_sync_done must be called for both users (finally block)
        called_ids = [c.args[0] for c in repo.mark_sync_done.call_args_list]
        assert 10 in called_ids
        assert 20 in called_ids


# ── process_sync_requests — ML flag + cleanup ─────────────────────────────────


class TestProcessSyncRequests:
    async def test_sets_ml_requested_and_marks_done_on_success(self):
        repo = AsyncMock()
        repo.get_sync_requested_users.return_value = [
            {"id": 42, "garmin_email": "x@test.com"}
        ]
        with patch("sync_runner.sync_user", new_callable=AsyncMock):
            await process_sync_requests(repo, daily_days=7, settings=MagicMock())
        repo.set_ml_requested.assert_called_once_with(42)
        repo.mark_sync_done.assert_called_once_with(42)

    async def test_sets_ml_requested_and_marks_done_even_on_failure(self):
        repo = AsyncMock()
        repo.get_sync_requested_users.return_value = [
            {"id": 99, "garmin_email": "x@test.com"}
        ]

        async def failing_sync(user, repo, days, settings):
            raise RuntimeError("sync exploded")

        with patch("sync_runner.sync_user", side_effect=failing_sync):
            await process_sync_requests(repo, daily_days=7, settings=MagicMock())

        # Both side-effects must fire from the finally block even on error
        repo.set_ml_requested.assert_called_once_with(99)
        repo.mark_sync_done.assert_called_once_with(99)

    async def test_no_requested_users_is_noop(self):
        repo = AsyncMock()
        repo.get_sync_requested_users.return_value = []
        with patch("sync_runner.sync_user", new_callable=AsyncMock) as mock_sync:
            await process_sync_requests(repo, daily_days=7, settings=MagicMock())
        mock_sync.assert_not_called()


# ── sync_all_libre — error classification ─────────────────────────────────────


class TestSyncAllLibre:
    async def test_no_users_is_noop(self):
        repo = AsyncMock()
        repo.get_libre_users.return_value = []
        await sync_all_libre(repo, MagicMock())  # must not raise

    async def test_auth_error_is_handled_without_raising(self):
        repo = AsyncMock()
        repo.get_libre_users.return_value = [{"id": 1}]

        async def auth_err(user, repo, settings):
            raise LibreAuthError("not linked")

        with patch("sync_runner.sync_libre_user", side_effect=auth_err):
            await sync_all_libre(repo, MagicMock())  # must not propagate

    async def test_generic_error_is_handled_without_raising(self):
        repo = AsyncMock()
        repo.get_libre_users.return_value = [{"id": 1}]

        async def network_err(user, repo, settings):
            raise ConnectionError("network unreachable")

        with patch("sync_runner.sync_libre_user", side_effect=network_err):
            await sync_all_libre(repo, MagicMock())  # must not propagate

    async def test_continues_after_one_user_fails(self):
        repo = AsyncMock()
        repo.get_libre_users.return_value = [{"id": 1}, {"id": 2}]
        synced: list[int] = []

        async def sometimes_fails(user, repo, settings):
            if user["id"] == 1:
                raise LibreAuthError("not linked")
            synced.append(user["id"])

        with patch("sync_runner.sync_libre_user", side_effect=sometimes_fails):
            await sync_all_libre(repo, MagicMock())

        assert 2 in synced, "user 2 must be synced even after user 1 fails"


# ── TestSyncDualLinkedUser — Garmin+Libre combination ────────────────────────


class TestSyncDualLinkedUser:
    """User linked to both Garmin and Libre — both sync jobs must run independently."""

    DUAL_USER = {"id": 1, "garmin_email": "dual@test.com"}

    async def test_dual_linked_user_synced_by_both_jobs(self):
        repo = AsyncMock()
        repo.get_active_users.return_value = [self.DUAL_USER]
        repo.get_libre_users.return_value = [self.DUAL_USER]
        with (
            patch("sync_runner.sync_user", new_callable=AsyncMock) as mock_garmin,
            patch("sync_runner.sync_libre_user", new_callable=AsyncMock) as mock_libre,
        ):
            await sync_all_users(repo, days=7, settings=MagicMock())
            await sync_all_libre(repo, MagicMock())
        assert mock_garmin.call_count == 1
        assert mock_libre.call_count == 1

    async def test_garmin_failure_does_not_prevent_libre_sync(self):
        repo = AsyncMock()
        repo.get_active_users.return_value = [self.DUAL_USER]
        repo.get_libre_users.return_value = [self.DUAL_USER]
        called: list[str] = []

        async def failing_garmin(user, repo, days, settings):
            raise RuntimeError("Garmin token missing")

        async def ok_libre(user, repo, settings):
            called.append("libre")

        with (
            patch("sync_runner.sync_user", side_effect=failing_garmin),
            patch("sync_runner.sync_libre_user", side_effect=ok_libre),
        ):
            await sync_all_users(repo, days=7, settings=MagicMock())
            await sync_all_libre(repo, MagicMock())

        assert "libre" in called, "Libre sync must proceed despite Garmin failure"


# ── _sync_activities ──────────────────────────────────────────────────────────


class TestSyncActivities:
    async def test_saves_activity_and_fetches_records_when_none_exist(self):
        client = MagicMock()
        client.get_activities.return_value = [{"activityId": 123}]
        client.get_activity_details.return_value = {}

        repo = AsyncMock()
        repo.save_activity.return_value = 42
        repo.records_exist.return_value = False

        activity_mock = MagicMock()
        activity_mock.records = []

        with (
            patch("sync_runner.garmin_call", side_effect=lambda fn: fn()),
            patch("sync_runner.map_activity", return_value=activity_mock),
            patch("sync_runner.map_records", return_value=[]),
        ):
            await _sync_activities(
                client,
                repo,
                user_id=1,
                start=date(2026, 1, 1),
                end=date(2026, 1, 7),
            )

        repo.save_activity.assert_awaited_once()

    async def test_skips_activity_without_garmin_id(self):
        client = MagicMock()
        client.get_activities.return_value = [{}]  # no activityId

        repo = AsyncMock()

        with patch("sync_runner.garmin_call", side_effect=lambda fn: fn()):
            await _sync_activities(
                client,
                repo,
                user_id=1,
                start=date(2026, 1, 1),
                end=date(2026, 1, 7),
            )

        repo.save_activity.assert_not_awaited()

    async def test_skips_record_fetch_when_records_exist(self):
        client = MagicMock()
        client.get_activities.return_value = [{"activityId": 99}]

        repo = AsyncMock()
        repo.save_activity.return_value = 10
        repo.records_exist.return_value = True  # already stored

        with (
            patch("sync_runner.garmin_call", side_effect=lambda fn: fn()),
            patch("sync_runner.map_activity", return_value=MagicMock(records=[])),
        ):
            await _sync_activities(
                client,
                repo,
                user_id=1,
                start=date(2026, 1, 1),
                end=date(2026, 1, 7),
            )

        client.get_activity_details.assert_not_called()

    async def test_bulk_inserts_records_when_present(self):
        client = MagicMock()
        client.get_activities.return_value = [{"activityId": 7}]
        client.get_activity_details.return_value = {}

        repo = AsyncMock()
        repo.save_activity.return_value = 5
        repo.records_exist.return_value = False

        record_mock = MagicMock()
        activity_mock = MagicMock()
        activity_mock.records = []  # will be set by _sync_activities

        with (
            patch("sync_runner.garmin_call", side_effect=lambda fn: fn()),
            patch("sync_runner.map_activity", return_value=activity_mock),
            patch("sync_runner.map_records", return_value=[record_mock]),
        ):
            await _sync_activities(
                client,
                repo,
                user_id=1,
                start=date(2026, 1, 1),
                end=date(2026, 1, 7),
            )

        repo.bulk_insert_records.assert_awaited_once_with(5, [record_mock])


# ── _sync_day ─────────────────────────────────────────────────────────────────


class TestSyncDay:
    async def test_calls_all_daily_repos(self):
        client = MagicMock()
        repo = AsyncMock()
        repo.sleep_exists.return_value = False

        sleep_mock = MagicMock()
        sleep_mock.garmin_sleep_id = 555

        with (
            patch("sync_runner.garmin_call", side_effect=lambda fn: fn()),
            patch("sync_runner.map_summary", return_value=MagicMock()),
            patch("sync_runner.map_sleep", return_value=sleep_mock),
            patch("sync_runner.map_hrv", return_value=MagicMock()),
            patch("sync_runner.map_body_battery", return_value=[]),
            patch("sync_runner.map_stress", return_value=[]),
            patch("sync_runner.map_training_status", return_value="PRODUCTIVE"),
        ):
            await _sync_day(client, repo, user_id=1, current=date(2026, 1, 1))

        repo.upsert_daily.assert_awaited_once()
        repo.save_sleep.assert_awaited_once()
        repo.upsert_hrv.assert_awaited_once()
        repo.upsert_training_status.assert_awaited_once()

    async def test_continues_after_individual_metric_failure(self):
        """One metric failing must not prevent subsequent metrics from being synced."""
        client = MagicMock()
        repo = AsyncMock()

        with (
            patch("sync_runner.garmin_call", side_effect=lambda fn: fn()),
            patch("sync_runner.map_summary", side_effect=RuntimeError("network error")),
            patch("sync_runner.map_sleep", return_value=None),
            patch("sync_runner.map_hrv", return_value=None),
            patch("sync_runner.map_body_battery", return_value=[]),
            patch("sync_runner.map_stress", return_value=[]),
            patch("sync_runner.map_training_status", return_value=None),
        ):
            await _sync_day(client, repo, user_id=1, current=date(2026, 1, 1))

        repo.upsert_daily.assert_not_awaited()  # failed
        # remaining sections still attempted (no exception propagated)

    async def test_all_garmin_api_failures_are_handled(self):
        """All six try/except blocks must absorb exceptions independently."""
        client = MagicMock()
        repo = AsyncMock()

        with patch("sync_runner.garmin_call", side_effect=RuntimeError("api down")):
            await _sync_day(client, repo, user_id=1, current=date(2026, 1, 1))

        repo.upsert_daily.assert_not_awaited()
        repo.save_sleep.assert_not_awaited()
        repo.upsert_hrv.assert_not_awaited()
        repo.upsert_training_status.assert_not_awaited()


# ── sync_libre_user ───────────────────────────────────────────────────────────


class TestSyncLibreUser:
    async def test_syncs_glucose_with_token_from_repo(self):
        user = {"id": 7}
        repo = AsyncMock()
        repo.get_user_token.return_value = b"encrypted_token"

        settings = MagicMock()
        settings.fernet_key = "key"
        settings.token_base_dir = Path("/tmp")

        glucose_row = MagicMock()

        with (
            patch("sync_runner.fernet_decrypt", return_value=b'{"token": "tok"}'),
            patch("sync_runner.connect_with_token", return_value=MagicMock()),
            patch("sync_runner.get_recent_glucose", return_value=[MagicMock()]),
            patch("sync_runner.map_glucose_reading", return_value=glucose_row),
        ):
            await sync_libre_user(user, repo, settings)

        repo.bulk_insert_glucose.assert_awaited_once_with(7, [glucose_row])

    async def test_raises_libre_auth_error_when_no_token(self):
        user = {"id": 5}
        repo = AsyncMock()
        repo.get_user_token.return_value = None

        settings = MagicMock()
        settings.token_base_dir = Path("/nonexistent/path")

        with pytest.raises(LibreAuthError):
            await sync_libre_user(user, repo, settings)

    async def test_migrates_libre_token_from_filesystem(self, tmp_path):
        """Libre token not in DB but present as JSON file → migrate to DB then sync."""
        import json as _json

        user = {"id": 6}
        repo = AsyncMock()
        repo.get_user_token.return_value = None

        libre_dir = tmp_path / "6" / "libre"
        libre_dir.mkdir(parents=True)
        (libre_dir / "libre_token.json").write_bytes(
            _json.dumps({"token": "test-tok"}).encode()
        )

        settings = MagicMock()
        settings.fernet_key = "key"
        settings.token_base_dir = tmp_path

        with (
            patch("sync_runner.fernet_encrypt", return_value=b"encrypted"),
            patch(
                "sync_runner.fernet_decrypt",
                return_value=_json.dumps({"token": "test-tok"}).encode(),
            ),
            patch("sync_runner.connect_with_token", return_value=MagicMock()),
            patch("sync_runner.get_recent_glucose", return_value=[]),
        ):
            await sync_libre_user(user, repo, settings)

        # token was saved to DB during migration
        repo.save_user_token.assert_awaited()


# ── sync_user ─────────────────────────────────────────────────────────────────


class TestSyncUser:
    async def test_skips_when_no_token_available(self):
        user = {"id": 3, "garmin_email": "x@garmin.com"}
        repo = AsyncMock()
        repo.get_user_token.return_value = None

        settings = MagicMock()
        settings.token_base_dir = Path("/nonexistent")
        settings.fernet_key = "key"

        await sync_user(user, repo, days=7, settings=settings)

        repo.save_activity.assert_not_called()

    async def test_full_sync_with_token_from_repo(self):
        user = {"id": 2, "garmin_email": "sync@garmin.com"}
        repo = AsyncMock()
        repo.get_user_token.return_value = b"encrypted_blob"

        settings = MagicMock()
        settings.fernet_key = "key"

        with (
            patch("sync_runner.fernet_decrypt", return_value=b"raw_token"),
            patch("sync_runner.fernet_encrypt", return_value=b"new_encrypted"),
            patch("sync_runner.restore_token_dir"),
            patch("sync_runner.serialize_token_dir", return_value=b"serialized"),
            patch("sync_runner.GarminClient") as MockClient,
            patch("sync_runner._sync_activities", new_callable=AsyncMock),
            patch("sync_runner._sync_day", new_callable=AsyncMock),
        ):
            MockClient.return_value.connect = MagicMock()
            await sync_user(user, repo, days=2, settings=settings)

        repo.save_user_token.assert_awaited_once()

    async def test_migrates_token_from_filesystem_when_not_in_db(self, tmp_path):
        """Token not in DB but present as directory → migrate to DB then sync."""
        user = {"id": 9, "garmin_email": "x@garmin.com"}
        repo = AsyncMock()
        repo.get_user_token.return_value = None

        token_dir = tmp_path / "9"
        token_dir.mkdir()

        settings = MagicMock()
        settings.fernet_key = "key"
        settings.token_base_dir = tmp_path

        with (
            patch("sync_runner.serialize_token_dir", return_value=b"serialized"),
            patch("sync_runner.fernet_encrypt", return_value=b"encrypted"),
            patch("sync_runner.fernet_decrypt", return_value=b"raw"),
            patch("sync_runner.restore_token_dir"),
            patch("sync_runner.GarminClient") as MockClient,
            patch("sync_runner._sync_activities", new_callable=AsyncMock),
            patch("sync_runner._sync_day", new_callable=AsyncMock),
        ):
            MockClient.return_value.connect = MagicMock()
            await sync_user(user, repo, days=1, settings=settings)

        assert repo.save_user_token.await_count >= 1
