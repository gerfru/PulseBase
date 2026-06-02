"""Unit tests for ml-service main.py orchestration.

Tests run_inference, run_training, run_on_request, run_all_users.
All DB and external dependencies are mocked.
"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from contextlib import ExitStack

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import run_all_users, run_inference, run_on_request, run_training


_TODAY = date(2026, 4, 27)
_SETTINGS = MagicMock()
_SETTINGS.model_dir = Path("/tmp/models")


def _all_run_patches():
    return [
        patch(
            "main.get_activity_trimp_inputs", new_callable=AsyncMock, return_value=[]
        ),
        patch("main.get_hrmax", new_callable=AsyncMock, return_value=185.0),
        patch(
            "main.get_hrv_history_for_energy", new_callable=AsyncMock, return_value=[]
        ),
        patch("main.get_sleep_data_7d", new_callable=AsyncMock, return_value=[]),
        patch("main.get_today_daily_summary", new_callable=AsyncMock, return_value={}),
        patch(
            "main.get_todays_activity_hr_records",
            new_callable=AsyncMock,
            return_value=([], None),
        ),
        patch("main._run_anomaly", new_callable=AsyncMock),
        patch("main._run_anomaly_spo2", new_callable=AsyncMock),
        patch("main._run_anomaly_sleep", new_callable=AsyncMock),
        patch("main._run_anomaly_steps", new_callable=AsyncMock),
        patch("main._run_anomaly_stress", new_callable=AsyncMock),
        patch("main._run_correlations", new_callable=AsyncMock),
        patch("main._run_readiness", new_callable=AsyncMock),
        patch("main._run_battery_pattern", new_callable=AsyncMock),
        patch("main._run_energy_metrics", new_callable=AsyncMock),
        patch("main._run_training_effect", new_callable=AsyncMock),
        patch("main._run_sleep_and_spo2", new_callable=AsyncMock),
        patch("main._run_hrv_and_recovery", new_callable=AsyncMock),
        patch("main._run_body_battery_and_stress", new_callable=AsyncMock),
        patch("main._run_running_and_intensity", new_callable=AsyncMock),
    ]


# ── run_inference ─────────────────────────────────────────────────────────────


class TestRunInference:
    async def test_calls_all_run_functions(self):
        with ExitStack() as stack:
            mocks = {p.attribute: stack.enter_context(p) for p in _all_run_patches()}
            await run_inference(user_id=1, settings=_SETTINGS)
        assert mocks["_run_anomaly"].await_count == 1

    async def test_completes_without_error(self):
        with ExitStack() as stack:
            for p in _all_run_patches():
                stack.enter_context(p)
            await run_inference(user_id=42, settings=_SETTINGS)


# ── run_training ──────────────────────────────────────────────────────────────


class TestRunTraining:
    async def test_saves_model_meta_when_training_succeeds(self):
        meta = {
            "n_rows": 50,
            "features": ["f1"],
            "importances": {"f1": 0.9},
            "trained_at": "2026-04-27",
        }
        with (
            patch(
                "main.get_readiness_training_rows",
                new_callable=AsyncMock,
                return_value=[{}] * 50,
            ),
            patch("main.train_and_save", return_value=meta),
            patch("main.save_prediction", new_callable=AsyncMock) as mock_save,
            patch(
                "main.get_body_battery_history", new_callable=AsyncMock, return_value={}
            ),
            patch("main.battery_fit_and_save", return_value=True),
        ):
            await run_training(user_id=1, settings=_SETTINGS)
        called_models = [c.args[2] for c in mock_save.call_args_list]
        assert "model_meta_rf" in called_models

    async def test_logs_insufficient_data_when_training_fails(self):
        with (
            patch(
                "main.get_readiness_training_rows",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("main.train_and_save", return_value=None),
            patch("main.save_prediction", new_callable=AsyncMock) as mock_save,
            patch(
                "main.get_body_battery_history", new_callable=AsyncMock, return_value={}
            ),
            patch("main.battery_fit_and_save", return_value=False),
        ):
            await run_training(user_id=1, settings=_SETTINGS)
        mock_save.assert_not_called()


# ── run_on_request ────────────────────────────────────────────────────────────


class TestRunOnRequest:
    async def test_runs_training_and_inference_for_each_user(self):
        with (
            patch(
                "main.get_ml_requested_users",
                new_callable=AsyncMock,
                return_value=[{"id": 5}],
            ),
            patch("main.count_energy_gaps", new_callable=AsyncMock, return_value=0),
            patch("main.run_training", new_callable=AsyncMock),
            patch("main.run_inference", new_callable=AsyncMock) as mock_infer,
            patch("main.mark_ml_done", new_callable=AsyncMock) as mock_done,
        ):
            await run_on_request(_SETTINGS)
        mock_infer.assert_awaited_once()
        mock_done.assert_awaited_once_with(5)

    async def test_triggers_backfill_when_gaps_exist(self):
        with (
            patch(
                "main.get_ml_requested_users",
                new_callable=AsyncMock,
                return_value=[{"id": 7}],
            ),
            patch("main.count_energy_gaps", new_callable=AsyncMock, return_value=3),
            patch("main.backfill_user", new_callable=AsyncMock) as mock_backfill,
            patch("main.run_training", new_callable=AsyncMock),
            patch("main.run_inference", new_callable=AsyncMock),
            patch("main.mark_ml_done", new_callable=AsyncMock),
        ):
            await run_on_request(_SETTINGS)
        mock_backfill.assert_awaited_once_with(7)

    async def test_mark_ml_done_called_even_on_failure(self):
        async def failing_run(*a, **kw):
            raise RuntimeError("inference failed")

        with (
            patch(
                "main.get_ml_requested_users",
                new_callable=AsyncMock,
                return_value=[{"id": 9}],
            ),
            patch("main.count_energy_gaps", new_callable=AsyncMock, return_value=0),
            patch("main.run_training", new_callable=AsyncMock),
            patch("main.run_inference", side_effect=failing_run),
            patch("main.mark_ml_done", new_callable=AsyncMock) as mock_done,
        ):
            await run_on_request(_SETTINGS)
        mock_done.assert_awaited_once_with(9)

    async def test_no_users_is_noop(self):
        with (
            patch(
                "main.get_ml_requested_users", new_callable=AsyncMock, return_value=[]
            ),
            patch("main.run_training", new_callable=AsyncMock) as mock_train,
        ):
            await run_on_request(_SETTINGS)
        mock_train.assert_not_called()


# ── run_all_users ─────────────────────────────────────────────────────────────


class TestRunAllUsers:
    async def test_no_users_is_noop(self):
        with (
            patch("main.get_active_users", new_callable=AsyncMock, return_value=[]),
            patch("main.run_inference", new_callable=AsyncMock) as mock_infer,
        ):
            await run_all_users(_SETTINGS)
        mock_infer.assert_not_called()

    async def test_runs_inference_for_each_user(self):
        with (
            patch(
                "main.get_active_users",
                new_callable=AsyncMock,
                return_value=[{"id": 1}, {"id": 2}],
            ),
            patch("main.run_inference", new_callable=AsyncMock) as mock_infer,
        ):
            await run_all_users(_SETTINGS, include_training=False)
        assert mock_infer.await_count == 2

    async def test_with_training_triggers_backfill_and_training(self):
        with (
            patch(
                "main.get_active_users",
                new_callable=AsyncMock,
                return_value=[{"id": 3}],
            ),
            patch("main.count_energy_gaps", new_callable=AsyncMock, return_value=2),
            patch("main.backfill_user", new_callable=AsyncMock) as mock_backfill,
            patch("main.run_training", new_callable=AsyncMock) as mock_train,
            patch("main.run_inference", new_callable=AsyncMock),
        ):
            await run_all_users(_SETTINGS, include_training=True)
        mock_backfill.assert_awaited_once_with(3)
        mock_train.assert_awaited_once()

    async def test_continues_after_single_user_failure(self):
        async def fail_on_1(uid, settings):
            if uid == 1:
                raise RuntimeError("user 1 broke")

        with (
            patch(
                "main.get_active_users",
                new_callable=AsyncMock,
                return_value=[{"id": 1}, {"id": 2}],
            ),
            patch("main.run_inference", side_effect=fail_on_1),
        ):
            await run_all_users(_SETTINGS)  # must not raise
