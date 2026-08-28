"""Unit tests for ml-service main.py orchestration functions.

Tests run_all_users, run_on_request, and run_inference. All DB calls and
inference sub-functions are mocked — no DB connection required.
"""

import asyncio
import signal
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import (
    _backfill_and_train,
    process_ml_events,
    run_ml_event_listener,
    run_all_users,
    run_inference,
    run_on_request,
)


def _make_settings() -> MagicMock:
    s = MagicMock()
    s.model_dir = Path("/tmp/ml_models")
    s.ml_event_sweep_seconds = 30
    return s


# ── _backfill_and_train ───────────────────────────────────────────────────────


class TestBackfillAndTrain:
    async def test_calls_run_training_always(self):
        settings = _make_settings()
        with (
            patch("main.count_energy_gaps", new_callable=AsyncMock, return_value=0),
            patch("main.run_training", new_callable=AsyncMock) as mock_train,
        ):
            await _backfill_and_train(42, settings)
        mock_train.assert_called_once_with(42, settings)

    async def test_backfills_when_gaps_exist(self):
        settings = _make_settings()
        with (
            patch("main.count_energy_gaps", new_callable=AsyncMock, return_value=3),
            patch("main.backfill_user", new_callable=AsyncMock) as mock_backfill,
            patch("main.run_training", new_callable=AsyncMock),
        ):
            await _backfill_and_train(42, settings)
        mock_backfill.assert_called_once_with(42)

    async def test_skips_backfill_when_no_gaps(self):
        settings = _make_settings()
        with (
            patch("main.count_energy_gaps", new_callable=AsyncMock, return_value=0),
            patch("main.backfill_user", new_callable=AsyncMock) as mock_backfill,
            patch("main.run_training", new_callable=AsyncMock),
        ):
            await _backfill_and_train(42, settings)
        mock_backfill.assert_not_called()


# ── run_all_users ─────────────────────────────────────────────────────────────


class TestRunAllUsers:
    async def test_no_users_is_noop(self):
        """Empty user list → run_inference never called."""
        settings = _make_settings()

        with (
            patch("main.get_active_users", new_callable=AsyncMock, return_value=[]),
            patch("main.run_inference", new_callable=AsyncMock) as mock_infer,
        ):
            await run_all_users(settings)

        mock_infer.assert_not_called()

    async def test_runs_inference_for_each_user(self):
        """Two active users → run_inference called twice."""
        settings = _make_settings()
        users = [{"id": 1}, {"id": 2}]

        with (
            patch("main.get_active_users", new_callable=AsyncMock, return_value=users),
            patch("main.run_inference", new_callable=AsyncMock) as mock_infer,
        ):
            await run_all_users(settings)

        assert mock_infer.call_count == 2
        called_ids = {c.args[0] for c in mock_infer.call_args_list}
        assert called_ids == {1, 2}

    async def test_continues_after_single_user_failure(self):
        """Exception for user 1 does not prevent user 2 from being processed."""
        settings = _make_settings()
        users = [{"id": 1}, {"id": 2}]
        processed: list[int] = []

        async def fake_infer(uid, s):
            if uid == 1:
                raise RuntimeError("user 1 failed")
            processed.append(uid)

        with (
            patch("main.get_active_users", new_callable=AsyncMock, return_value=users),
            patch("main.run_inference", side_effect=fake_infer),
        ):
            await run_all_users(settings)

        assert 2 in processed

    async def test_include_training_calls_run_training(self):
        """include_training=True → run_training called for each user before inference."""
        settings = _make_settings()
        users = [{"id": 10}]

        with (
            patch("main.get_active_users", new_callable=AsyncMock, return_value=users),
            patch("main.count_energy_gaps", new_callable=AsyncMock, return_value=0),
            patch("main.run_training", new_callable=AsyncMock) as mock_train,
            patch("main.run_inference", new_callable=AsyncMock),
        ):
            await run_all_users(settings, include_training=True)

        mock_train.assert_called_once_with(10, settings)

    async def test_include_training_backfills_when_gaps_exist(self):
        """When energy gaps > 0 and include_training=True, backfill_user is called."""
        settings = _make_settings()
        users = [{"id": 5}]

        with (
            patch("main.get_active_users", new_callable=AsyncMock, return_value=users),
            patch("main.count_energy_gaps", new_callable=AsyncMock, return_value=3),
            patch("main.backfill_user", new_callable=AsyncMock) as mock_backfill,
            patch("main.run_training", new_callable=AsyncMock),
            patch("main.run_inference", new_callable=AsyncMock),
        ):
            await run_all_users(settings, include_training=True)

        mock_backfill.assert_called_once_with(5)


# ── run_on_request ────────────────────────────────────────────────────────────


class TestRunOnRequest:
    async def test_no_requested_users_is_noop(self):
        """Empty ml_requested list → training and inference never called."""
        settings = _make_settings()

        with (
            patch(
                "main.get_ml_requested_users",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("main.run_inference", new_callable=AsyncMock) as mock_infer,
        ):
            await run_on_request(settings)

        mock_infer.assert_not_called()

    async def test_runs_training_and_inference_for_requested_user(self):
        """Requested user gets training → inference in sequence."""
        settings = _make_settings()
        users = [{"id": 42}]

        with (
            patch(
                "main.get_ml_requested_users",
                new_callable=AsyncMock,
                return_value=users,
            ),
            patch("main.count_energy_gaps", new_callable=AsyncMock, return_value=0),
            patch("main.run_training", new_callable=AsyncMock) as mock_train,
            patch("main.run_inference", new_callable=AsyncMock) as mock_infer,
            patch("main.mark_ml_done", new_callable=AsyncMock),
        ):
            await run_on_request(settings)

        mock_train.assert_called_once_with(42, settings)
        mock_infer.assert_called_once_with(42, settings)

    async def test_failure_remains_requested_for_retry(self):
        settings = _make_settings()
        users = [{"id": 99}]

        async def failing_train(uid, s):
            raise RuntimeError("training failed")

        with (
            patch(
                "main.get_ml_requested_users",
                new_callable=AsyncMock,
                return_value=users,
            ),
            patch("main.count_energy_gaps", new_callable=AsyncMock, return_value=0),
            patch("main.run_training", side_effect=failing_train),
            patch("main.mark_ml_done", new_callable=AsyncMock) as mock_done,
        ):
            await run_on_request(settings)

        mock_done.assert_not_called()

    async def test_backfills_when_energy_gaps_exist(self):
        """When energy gaps > 0, backfill_user is called before training."""
        settings = _make_settings()
        users = [{"id": 7}]

        with (
            patch(
                "main.get_ml_requested_users",
                new_callable=AsyncMock,
                return_value=users,
            ),
            patch("main.count_energy_gaps", new_callable=AsyncMock, return_value=5),
            patch("main.backfill_user", new_callable=AsyncMock) as mock_backfill,
            patch("main.run_training", new_callable=AsyncMock),
            patch("main.run_inference", new_callable=AsyncMock),
            patch("main.mark_ml_done", new_callable=AsyncMock),
        ):
            await run_on_request(settings)

        mock_backfill.assert_called_once_with(7)


class TestProcessMlEvents:
    async def test_completes_event_and_clears_legacy_flag(self):
        settings = _make_settings()
        event = {"id": 8, "user_id": 42, "attempts": 1}

        with (
            patch("main.requeue_stale_ml_events", new_callable=AsyncMock),
            patch("main.reconcile_ml_events", new_callable=AsyncMock),
            patch(
                "main.claim_ml_events",
                new_callable=AsyncMock,
                side_effect=[[event], []],
            ),
            patch("main._backfill_and_train", new_callable=AsyncMock),
            patch("main.run_inference", new_callable=AsyncMock),
            patch(
                "main.complete_event",
                new_callable=AsyncMock,
                return_value="completed",
            ) as mock_complete,
            patch("main.mark_ml_done", new_callable=AsyncMock) as mock_done,
            patch(
                "main.get_ml_queue_metrics",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            await process_ml_events(settings)

        mock_complete.assert_awaited_once_with(8)
        mock_done.assert_awaited_once_with(42)

    async def test_retries_failed_event_without_clearing_flag(self):
        settings = _make_settings()
        event = {"id": 9, "user_id": 43, "attempts": 1}

        with (
            patch("main.requeue_stale_ml_events", new_callable=AsyncMock),
            patch("main.reconcile_ml_events", new_callable=AsyncMock),
            patch(
                "main.claim_ml_events",
                new_callable=AsyncMock,
                side_effect=[[event], []],
            ),
            patch(
                "main._backfill_and_train",
                new_callable=AsyncMock,
                side_effect=RuntimeError("temporary"),
            ),
            patch(
                "main.fail_event",
                new_callable=AsyncMock,
                return_value="pending",
            ) as mock_fail,
            patch("main.mark_ml_done", new_callable=AsyncMock) as mock_done,
            patch(
                "main.get_ml_queue_metrics",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            await process_ml_events(settings)

        mock_fail.assert_awaited_once_with(9, "temporary", 1)
        mock_done.assert_not_awaited()


class TestMlEventListener:
    async def test_notification_wakes_consumer_and_closes_connection(self):
        settings = _make_settings()
        settings.db_url = "postgresql://test"
        stop_event = asyncio.Event()
        connection = MagicMock()
        connection.add_listener = AsyncMock(
            side_effect=lambda _channel, callback: callback(
                None, 0, "service_events", "1"
            )
        )
        connection.close = AsyncMock()

        async def process(_settings):
            stop_event.set()

        with patch(
            "main.asyncpg.connect", new_callable=AsyncMock, return_value=connection
        ):
            await run_ml_event_listener(settings, stop_event, process)

        connection.add_listener.assert_awaited_once()
        connection.close.assert_awaited_once()

    async def test_reconnects_after_connection_failure(self):
        settings = _make_settings()
        settings.db_url = "postgresql://test"
        stop_event = asyncio.Event()
        first = MagicMock()
        first.add_listener = AsyncMock(side_effect=ConnectionError("gone"))
        first.close = AsyncMock()
        second = MagicMock()
        second.add_listener = AsyncMock(
            side_effect=lambda _channel, callback: callback(
                None, 0, "service_events", "1"
            )
        )
        second.close = AsyncMock()
        connect = AsyncMock(side_effect=[first, second])

        async def process(_settings):
            stop_event.set()

        with patch("main.asyncpg.connect", connect):
            await run_ml_event_listener(settings, stop_event, process)

        assert connect.await_count == 2
        first.close.assert_awaited_once()
        second.close.assert_awaited_once()


# ── run_inference ─────────────────────────────────────────────────────────────


class TestRunInference:
    async def test_completes_without_error_for_valid_user(self):
        """run_inference orchestrates all sub-functions without raising."""
        settings = _make_settings()
        noop = AsyncMock(return_value=None)
        noop_list = AsyncMock(return_value=[])
        noop_tuple = AsyncMock(return_value=([], 0.0))

        with (
            patch("main.get_activity_trimp_inputs", noop_list),
            patch("main.get_hrmax", AsyncMock(return_value=180)),
            patch("main.get_hrv_history_for_energy", noop_list),
            patch("main.get_sleep_data_7d", noop_list),
            patch("main.get_today_daily_summary", AsyncMock(return_value={})),
            patch("main.get_todays_activity_hr_records", noop_tuple),
            patch("main._run_anomaly", noop),
            patch("main._run_anomaly_spo2", noop),
            patch("main._run_anomaly_sleep", noop),
            patch("main._run_anomaly_steps", noop),
            patch("main._run_anomaly_stress", noop),
            patch("main._run_correlations", noop),
            patch("main._run_readiness", noop),
            patch("main._run_battery_pattern", noop),
            patch("main._run_energy_metrics", noop),
            patch("main._run_training_effect", noop),
            patch("main._run_sleep_and_spo2", noop),
            patch("main._run_hrv_and_recovery", noop),
            patch("main._run_body_battery_and_stress", noop),
            patch("main._run_running_and_intensity", noop),
        ):
            await run_inference(1, settings)  # must not raise

    async def test_calls_all_inference_sub_functions(self):
        """All 14 inference sub-functions are invoked exactly once per run."""
        settings = _make_settings()

        with (
            patch(
                "main.get_activity_trimp_inputs",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("main.get_hrmax", new_callable=AsyncMock, return_value=180),
            patch(
                "main.get_hrv_history_for_energy",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("main.get_sleep_data_7d", new_callable=AsyncMock, return_value=[]),
            patch(
                "main.get_today_daily_summary", new_callable=AsyncMock, return_value={}
            ),
            patch(
                "main.get_todays_activity_hr_records",
                new_callable=AsyncMock,
                return_value=([], 0.0),
            ),
            patch("main._run_anomaly", new_callable=AsyncMock) as m_anomaly,
            patch("main._run_anomaly_spo2", new_callable=AsyncMock) as m_spo2,
            patch("main._run_anomaly_sleep", new_callable=AsyncMock) as m_sleep_an,
            patch("main._run_anomaly_steps", new_callable=AsyncMock) as m_steps,
            patch("main._run_anomaly_stress", new_callable=AsyncMock) as m_stress_an,
            patch("main._run_correlations", new_callable=AsyncMock) as m_corr,
            patch("main._run_readiness", new_callable=AsyncMock) as m_ready,
            patch("main._run_battery_pattern", new_callable=AsyncMock) as m_bp,
            patch("main._run_energy_metrics", new_callable=AsyncMock) as m_energy,
            patch("main._run_training_effect", new_callable=AsyncMock) as m_te,
            patch("main._run_sleep_and_spo2", new_callable=AsyncMock) as m_sleep,
            patch("main._run_hrv_and_recovery", new_callable=AsyncMock) as m_hrv,
            patch("main._run_body_battery_and_stress", new_callable=AsyncMock) as m_bb,
            patch("main._run_running_and_intensity", new_callable=AsyncMock) as m_run,
        ):
            await run_inference(1, settings)

        for mock in (
            m_anomaly,
            m_spo2,
            m_sleep_an,
            m_steps,
            m_stress_an,
            m_corr,
            m_ready,
            m_bp,
            m_energy,
            m_te,
            m_sleep,
            m_hrv,
            m_bb,
            m_run,
        ):
            assert mock.call_count == 1, (
                f"{mock._mock_name} was not called exactly once"
            )


# ── Shutdown / SIGTERM ────────────────────────────────────────────────────────


class TestShutdown:
    async def test_sigterm_handler_is_non_blocking(self):
        """M-83: SIGTERM handler must only set an asyncio.Event, never call scheduler.shutdown."""
        from main import main

        captured_sigterm_handler = None

        def _capture_handler(sig, handler):
            nonlocal captured_sigterm_handler
            if sig == signal.SIGTERM:
                captured_sigterm_handler = handler

        mock_loop = MagicMock()
        mock_loop.add_signal_handler.side_effect = _capture_handler

        shutdown_event = asyncio.Event()

        async def finish_initial_run(*_args, **_kwargs):
            shutdown_event.set()

        mock_scheduler = MagicMock()

        mock_settings = MagicMock()
        mock_settings.sentry_dsn = ""
        mock_settings.ml_event_consumer_enabled = False

        mock_pool = AsyncMock()
        with (
            patch("main.init_pool", new_callable=AsyncMock),
            patch("main.get_pool", new_callable=AsyncMock, return_value=mock_pool),
            patch("main.close_pool", new_callable=AsyncMock),
            patch("main.start_health_server", new_callable=AsyncMock),
            patch("main.run_all_users", side_effect=finish_initial_run),
            patch("main._configure_ml_scheduler", return_value=mock_scheduler),
            patch("main.asyncio.get_running_loop", return_value=mock_loop),
            patch("main.asyncio.Event", return_value=shutdown_event),
            patch("main.Settings", return_value=mock_settings),
        ):
            await main()

        assert captured_sigterm_handler is not None, (
            "SIGTERM handler was not registered"
        )

        # scheduler.shutdown was called once in the finally block (correct: graceful shutdown)
        shutdown_calls_before = mock_scheduler.shutdown.call_count

        # Call the captured SIGTERM handler — it must NOT add another scheduler.shutdown call
        captured_sigterm_handler()

        assert shutdown_event.is_set()
        assert mock_scheduler.shutdown.call_count == shutdown_calls_before, (
            "SIGTERM handler must not call scheduler.shutdown directly (blocking)"
        )
