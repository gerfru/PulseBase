"""Unit tests for sync-service main.py orchestration.

Tests the independently testable parts: _garmin_call retry logic,
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
from main import (
    _garmin_call,
    process_sync_requests,
    sync_all_libre,
    sync_all_users,
)


# ── _garmin_call — Tenacity retry logic ──────────────────────────────────────


class TestGarminCall:
    @patch("time.sleep")
    def test_succeeds_on_first_try(self, mock_sleep):
        fn = MagicMock(return_value="ok")
        assert _garmin_call(fn) == "ok"
        assert fn.call_count == 1
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_retries_on_exception_and_succeeds(self, mock_sleep):
        fn = MagicMock(side_effect=[RuntimeError("fail"), RuntimeError("fail"), "ok"])
        result = _garmin_call(fn)
        assert result == "ok"
        assert fn.call_count == 3

    @patch("time.sleep")
    def test_raises_after_max_retries(self, mock_sleep):
        fn = MagicMock(side_effect=ValueError("always fails"))
        with pytest.raises(ValueError, match="always fails"):
            _garmin_call(fn)
        assert fn.call_count == 3

    @patch("time.sleep")
    def test_returns_none_correctly(self, mock_sleep):
        fn = MagicMock(return_value=None)
        # None is a valid return — must not trigger retry
        assert _garmin_call(fn) is None
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
        with patch("main.sync_user", new_callable=AsyncMock) as mock_sync:
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

        with patch("main.sync_user", side_effect=fake_sync):
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

        with patch("main.sync_user", side_effect=partial_failure):
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
        with patch("main.sync_user", new_callable=AsyncMock):
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

        with patch("main.sync_user", side_effect=failing_sync):
            await process_sync_requests(repo, daily_days=7, settings=MagicMock())

        # Both side-effects must fire from the finally block even on error
        repo.set_ml_requested.assert_called_once_with(99)
        repo.mark_sync_done.assert_called_once_with(99)

    async def test_no_requested_users_is_noop(self):
        repo = AsyncMock()
        repo.get_sync_requested_users.return_value = []
        with patch("main.sync_user", new_callable=AsyncMock) as mock_sync:
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

        with patch("main.sync_libre_user", side_effect=auth_err):
            await sync_all_libre(repo, MagicMock())  # must not propagate

    async def test_generic_error_is_handled_without_raising(self):
        repo = AsyncMock()
        repo.get_libre_users.return_value = [{"id": 1}]

        async def network_err(user, repo, settings):
            raise ConnectionError("network unreachable")

        with patch("main.sync_libre_user", side_effect=network_err):
            await sync_all_libre(repo, MagicMock())  # must not propagate

    async def test_continues_after_one_user_fails(self):
        repo = AsyncMock()
        repo.get_libre_users.return_value = [{"id": 1}, {"id": 2}]
        synced: list[int] = []

        async def sometimes_fails(user, repo, settings):
            if user["id"] == 1:
                raise LibreAuthError("not linked")
            synced.append(user["id"])

        with patch("main.sync_libre_user", side_effect=sometimes_fails):
            await sync_all_libre(repo, MagicMock())

        assert 2 in synced, "user 2 must be synced even after user 1 fails"
