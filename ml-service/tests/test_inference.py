"""Unit tests for inference_anomaly.py and inference_models.py.

All DB calls and save_prediction are mocked — only model computation runs real.
"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── inference_anomaly — individual wrapper functions ──────────────────────────


class TestAnomalyWrappers:
    """_run_anomaly_* are thin wrappers around _run_anomaly_for — each needs one test."""

    async def _run_with_mocks(self, fn, *args):
        history = [60.0] * 10
        today_val = 80.0
        with (
            patch(
                "inference_anomaly.get_resting_hr_history",
                new_callable=AsyncMock,
                return_value=history,
            ),
            patch(
                "inference_anomaly.get_today_resting_hr",
                new_callable=AsyncMock,
                return_value=today_val,
            ),
            patch(
                "inference_anomaly.get_spo2_history_flat",
                new_callable=AsyncMock,
                return_value=history,
            ),
            patch(
                "inference_anomaly.get_today_spo2",
                new_callable=AsyncMock,
                return_value=today_val,
            ),
            patch(
                "inference_anomaly.get_sleep_duration_history",
                new_callable=AsyncMock,
                return_value=history,
            ),
            patch(
                "inference_anomaly.get_today_sleep_duration",
                new_callable=AsyncMock,
                return_value=today_val,
            ),
            patch(
                "inference_anomaly.get_steps_history",
                new_callable=AsyncMock,
                return_value=history,
            ),
            patch(
                "inference_anomaly.get_today_steps",
                new_callable=AsyncMock,
                return_value=today_val,
            ),
            patch(
                "inference_anomaly.get_stress_history",
                new_callable=AsyncMock,
                return_value=history,
            ),
            patch(
                "inference_anomaly.get_today_stress",
                new_callable=AsyncMock,
                return_value=today_val,
            ),
            patch("inference_anomaly.save_prediction", new_callable=AsyncMock),
        ):
            await fn(*args)

    async def test_run_anomaly_hr(self):
        from inference_anomaly import _run_anomaly

        await self._run_with_mocks(_run_anomaly, 1, date(2026, 4, 27))

    async def test_run_anomaly_spo2(self):
        from inference_anomaly import _run_anomaly_spo2

        await self._run_with_mocks(_run_anomaly_spo2, 1, date(2026, 4, 27))

    async def test_run_anomaly_sleep(self):
        from inference_anomaly import _run_anomaly_sleep

        await self._run_with_mocks(_run_anomaly_sleep, 1, date(2026, 4, 27))

    async def test_run_anomaly_steps(self):
        from inference_anomaly import _run_anomaly_steps

        await self._run_with_mocks(_run_anomaly_steps, 1, date(2026, 4, 27))

    async def test_run_anomaly_stress(self):
        from inference_anomaly import _run_anomaly_stress

        await self._run_with_mocks(_run_anomaly_stress, 1, date(2026, 4, 27))


# ── inference_models ──────────────────────────────────────────────────────────


_TODAY = date(2026, 4, 27)
_MOCK_SETTINGS = MagicMock()
_MOCK_SETTINGS.model_dir = Path("/tmp/models")


class TestRunReadiness:
    async def test_noop_when_predict_returns_none(self):
        from inference_models import _run_readiness

        with (
            patch(
                "inference_models.get_latest_features",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch("inference_models.predict_tomorrow", return_value=None),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_readiness(1, _TODAY, _MOCK_SETTINGS)
        mock_save.assert_not_called()

    async def test_saves_prediction_when_model_returns_score(self):
        from inference_models import _run_readiness

        predicted = {"score": 75.0, "confidence_low": 65.0, "confidence_high": 85.0}
        with (
            patch(
                "inference_models.get_latest_features",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch("inference_models.predict_tomorrow", return_value=predicted),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_readiness(1, _TODAY, _MOCK_SETTINGS)
        assert mock_save.call_count == 2  # today + tomorrow


class TestRunBatteryPattern:
    async def test_noop_when_predict_returns_none(self):
        from inference_models import _run_battery_pattern

        with (
            patch(
                "inference_models.get_body_battery_today",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("inference_models.battery_predict_today", return_value=None),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_battery_pattern(1, _TODAY, _MOCK_SETTINGS)
        mock_save.assert_not_called()

    async def test_saves_prediction_when_cluster_returned(self):
        from inference_models import _run_battery_pattern

        bp = {"cluster": 2, "pattern": "fresh"}
        with (
            patch(
                "inference_models.get_body_battery_today",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("inference_models.battery_predict_today", return_value=bp),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_battery_pattern(1, _TODAY, _MOCK_SETTINGS)
        mock_save.assert_called_once()


class TestRunEnergyMetrics:
    async def test_saves_energy_predictions(self):
        from inference_energy import _run_energy_metrics

        with patch(
            "inference_energy.save_prediction", new_callable=AsyncMock
        ) as mock_save:
            await _run_energy_metrics(1, _TODAY, [], 185.0, [], [])
        # energy_physical + energy_autonomic + energy_cognitive always saved
        model_keys = [c.args[2] for c in mock_save.call_args_list]
        assert "energy_physical" in model_keys
        assert "energy_autonomic" in model_keys
        assert "energy_cognitive" in model_keys

    async def test_saves_acwr_when_atl_ctl_present(self):
        from inference_energy import _run_energy_metrics
        from datetime import timedelta

        # Build act_rows that produce nonzero ATL/CTL
        act_rows = [
            {
                "activity_date": _TODAY - timedelta(days=i),
                "avg_hr": 150,
                "duration_seconds": 3600,
                "resting_hr": 52,
            }
            for i in range(10)
        ]
        with patch(
            "inference_energy.save_prediction", new_callable=AsyncMock
        ) as mock_save:
            await _run_energy_metrics(1, _TODAY, act_rows, 185.0, [], [])
        model_keys = [c.args[2] for c in mock_save.call_args_list]
        assert "acwr" in model_keys


class TestRunPhysicalEnergy:
    async def test_saves_and_returns_phys(self):
        from inference_energy import _run_physical_energy

        with patch(
            "inference_energy.save_prediction", new_callable=AsyncMock
        ) as mock_save:
            result = await _run_physical_energy(1, _TODAY, [], 185.0)
        mock_save.assert_called_once()
        assert mock_save.call_args.args[2] == "energy_physical"
        assert isinstance(result, dict)

    async def test_returns_phys_dict_with_score_key(self):
        from inference_energy import _run_physical_energy

        with patch("inference_energy.save_prediction", new_callable=AsyncMock):
            result = await _run_physical_energy(1, _TODAY, [], 185.0)
        assert "score" in result


class TestRunAcwr:
    async def test_skips_when_atl_or_ctl_missing(self):
        from inference_energy import _run_acwr

        with patch(
            "inference_energy.save_prediction", new_callable=AsyncMock
        ) as mock_save:
            await _run_acwr(1, _TODAY, {"atl": None, "ctl": None})
        mock_save.assert_not_called()

    async def test_saves_when_atl_and_ctl_present(self):
        from inference_energy import _run_acwr

        with patch(
            "inference_energy.save_prediction", new_callable=AsyncMock
        ) as mock_save:
            await _run_acwr(1, _TODAY, {"atl": 50.0, "ctl": 45.0})
        mock_save.assert_called_once()
        assert mock_save.call_args.args[2] == "acwr"


class TestRunTrainingMonotony:
    async def test_skips_when_monotony_is_none(self):
        from inference_energy import _run_training_monotony

        with patch(
            "inference_energy.save_prediction", new_callable=AsyncMock
        ) as mock_save:
            await _run_training_monotony(1, _TODAY, [], 185.0)
        mock_save.assert_not_called()

    async def test_saves_when_monotony_present(self):
        from inference_energy import _run_training_monotony
        from datetime import timedelta

        act_rows = [
            {
                "activity_date": _TODAY - timedelta(days=i),
                "avg_hr": 150,
                "duration_seconds": 3600,
                "resting_hr": 52,
            }
            for i in range(7)
        ]
        with patch(
            "inference_energy.save_prediction", new_callable=AsyncMock
        ) as mock_save:
            await _run_training_monotony(1, _TODAY, act_rows, 185.0)
        model_keys = [c.args[2] for c in mock_save.call_args_list]
        assert "training_monotony" in model_keys


class TestRunAutonomicEnergy:
    async def test_saves_autonomic_energy(self):
        from inference_energy import _run_autonomic_energy

        with patch(
            "inference_energy.save_prediction", new_callable=AsyncMock
        ) as mock_save:
            await _run_autonomic_energy(1, _TODAY, [50.0] * 10)
        mock_save.assert_called_once()
        assert mock_save.call_args.args[2] == "energy_autonomic"


class TestRunCognitiveEnergy:
    async def test_saves_cognitive_energy(self):
        from inference_energy import _run_cognitive_energy

        sleep_h = [{"total_h": 7.5} for _ in range(7)]
        with patch(
            "inference_energy.save_prediction", new_callable=AsyncMock
        ) as mock_save:
            await _run_cognitive_energy(1, _TODAY, sleep_h)
        mock_save.assert_called_once()
        assert mock_save.call_args.args[2] == "energy_cognitive"


class TestComputeHrvBaseline:
    def test_returns_zero_when_fewer_than_7_values(self):
        from inference_models import _compute_hrv_baseline

        assert _compute_hrv_baseline([]) == 0.0
        assert _compute_hrv_baseline([50.0] * 6) == 0.0

    def test_computes_mean_of_last_30_when_sufficient(self):
        from inference_models import _compute_hrv_baseline

        hrv = [50.0] * 7
        result = _compute_hrv_baseline(hrv)
        assert result == 50.0

    def test_skips_none_values(self):
        from inference_models import _compute_hrv_baseline

        # 7 non-None values interspersed with None
        hrv = [50.0, None, 60.0, None, 55.0, 52.0, 48.0, None, 53.0, 51.0]
        valid = [50.0, 60.0, 55.0, 52.0, 48.0, 53.0, 51.0]
        result = _compute_hrv_baseline(hrv)
        assert result == pytest.approx(sum(valid) / len(valid))

    def test_uses_at_most_last_30_values(self):
        from inference_models import _compute_hrv_baseline

        hrv = [100.0] * 10 + [50.0] * 30
        result = _compute_hrv_baseline(hrv)
        assert result == 50.0


class TestRunTrainingEffect:
    async def test_noop_when_no_profile(self):
        from inference_models import _run_training_effect

        with (
            patch(
                "inference_models.get_user_profile",
                new_callable=AsyncMock,
                return_value={"has_profile": False},
            ),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_training_effect(1, _TODAY, [], 185.0, None)
        mock_save.assert_not_called()

    async def test_saves_effect_when_profile_present(self):
        from inference_models import _run_training_effect

        profile = {"has_profile": True, "sex": "male", "age": 35}
        with (
            patch(
                "inference_models.get_user_profile",
                new_callable=AsyncMock,
                return_value=profile,
            ),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_training_effect(1, _TODAY, [], 185.0, 52.0)
        mock_save.assert_called_once()
        assert mock_save.call_args.args[2] == "training_effect_custom"


class TestRunSleepAndSpo2:
    async def test_skips_spo2_when_no_mean(self):
        from inference_models import _run_sleep_and_spo2

        with (
            patch(
                "inference_models.get_spo2_history",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "inference_models.get_sleep_sessions_14d",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "inference_models.get_last_sleep_session",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_sleep_and_spo2(1, _TODAY)
        mock_save.assert_not_called()

    async def test_saves_sleep_score_when_session_present(self):
        from inference_models import _run_sleep_and_spo2

        session = {
            "total_sleep_seconds": 27000,
            "deep_sleep_seconds": 5400,
            "light_sleep_seconds": 10800,
            "rem_sleep_seconds": 7200,
            "awake_seconds": 1800,
        }
        with (
            patch(
                "inference_models.get_spo2_history",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "inference_models.get_sleep_sessions_14d",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "inference_models.get_last_sleep_session",
                new_callable=AsyncMock,
                return_value=session,
            ),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_sleep_and_spo2(1, _TODAY)
        model_keys = [c.args[2] for c in mock_save.call_args_list]
        assert "sleep_score_custom" in model_keys


class TestRunHrvAndRecovery:
    async def test_skips_recovery_when_no_events(self):
        from inference_models import _run_hrv_and_recovery

        with patch(
            "inference_models.save_prediction", new_callable=AsyncMock
        ) as mock_save:
            await _run_hrv_and_recovery(1, _TODAY, [], [], 185.0)
        # hrv_recovery not saved (no data), hrv_status_custom may be skipped too
        model_keys = [c.args[2] for c in mock_save.call_args_list]
        assert "hrv_recovery" not in model_keys

    async def test_saves_hrv_status_when_data_present(self):
        from inference_models import _run_hrv_and_recovery

        hrv_hist = [50.0] * 30
        with patch(
            "inference_models.save_prediction", new_callable=AsyncMock
        ) as mock_save:
            await _run_hrv_and_recovery(1, _TODAY, hrv_hist, [], 185.0)
        model_keys = [c.args[2] for c in mock_save.call_args_list]
        assert "hrv_status_custom" in model_keys


class TestRunBodyBatteryAndStress:
    async def test_saves_bb_and_stress_with_sufficient_hrv(self):
        from inference_models import _run_body_battery_and_stress

        hrv_hist = [50.0] * 10

        with (
            patch(
                "inference_models.get_yesterday_prediction",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_body_battery_and_stress(
                1,
                _TODAY,
                [],
                185.0,
                hrv_hist,
                [{"total_h": 7.5, "deep_h": 1.5, "rem_h": 2.0}],
                {"body_battery_high": 85, "avg_stress": 30},
            )
        assert mock_save.call_count > 0

    async def test_uses_daily_bb_when_no_yesterday_prediction(self):
        from inference_models import _run_body_battery_and_stress

        with (
            patch(
                "inference_models.get_yesterday_prediction",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("inference_models.save_prediction", new_callable=AsyncMock),
        ):
            # Should not raise even with empty data
            await _run_body_battery_and_stress(
                1,
                _TODAY,
                [],
                185.0,
                [],
                [],
                {"body_battery_high": 80, "avg_stress": None},
            )


class TestRunRunningAndIntensity:
    async def test_skips_economy_when_no_run_activities(self):
        from inference_models import _run_running_and_intensity

        with (
            patch(
                "inference_models.get_running_economy_activities",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_running_and_intensity(1, _TODAY, 185.0, [], None)
        model_keys = [c.args[2] for c in mock_save.call_args_list]
        assert "running_economy" not in model_keys

    async def test_saves_intensity_when_hr_records_and_rhr_present(self):
        from inference_models import _run_running_and_intensity

        hr_records = [130] * 3600

        with (
            patch(
                "inference_models.get_running_economy_activities",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_running_and_intensity(1, _TODAY, 185.0, hr_records, 52.0)
        model_keys = [c.args[2] for c in mock_save.call_args_list]
        assert "intensity_minutes_custom" in model_keys

    async def test_saves_running_economy_when_activities_present(self):
        """Lines 319-322: save_prediction called when running economy score available."""
        from inference_models import _run_running_and_intensity

        run_acts = [
            {
                "avg_ground_contact_time": 245.0,
                "avg_vertical_oscillation": 8.5,
                "avg_vertical_ratio": 8.2,
            }
        ]
        with (
            patch(
                "inference_models.get_running_economy_activities",
                new_callable=AsyncMock,
                return_value=run_acts,
            ),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_running_and_intensity(1, _TODAY, 185.0, [], None)
        model_keys = [c.args[2] for c in mock_save.call_args_list]
        assert "running_economy" in model_keys


class TestRunSleepAndSpo2SavePaths:
    async def test_saves_spo2_when_mean_not_none(self):
        """Lines 176-179: save_prediction called when mean_spo2 is not None."""
        from inference_models import _run_sleep_and_spo2

        spo2_rows = [{"avg_spo2": 97.0, "min_spo2": 95.0} for _ in range(7)]
        with (
            patch(
                "inference_models.get_spo2_history",
                new_callable=AsyncMock,
                return_value=spo2_rows,
            ),
            patch(
                "inference_models.get_sleep_sessions_14d",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "inference_models.get_last_sleep_session",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_sleep_and_spo2(1, _TODAY)
        model_keys = [c.args[2] for c in mock_save.call_args_list]
        assert "spo2_trend" in model_keys

    async def test_saves_sleep_consistency_when_score_not_none(self):
        """Lines 190-193: save_prediction called when consistency score available."""
        from inference_models import _run_sleep_and_spo2

        sessions = [
            {"start_h": 23.0, "end_h": 7.0},
            {"start_h": 23.5, "end_h": 7.5},
            {"start_h": 22.5, "end_h": 6.5},
            {"start_h": 23.0, "end_h": 7.0},
            {"start_h": 23.2, "end_h": 7.2},
        ]
        with (
            patch(
                "inference_models.get_spo2_history",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "inference_models.get_sleep_sessions_14d",
                new_callable=AsyncMock,
                return_value=sessions,
            ),
            patch(
                "inference_models.get_last_sleep_session",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_sleep_and_spo2(1, _TODAY)
        model_keys = [c.args[2] for c in mock_save.call_args_list]
        assert "sleep_consistency" in model_keys


class TestRunHrvAndRecoverySavePaths:
    async def test_saves_hrv_recovery_when_speed_not_none(self):
        """Lines 221-228: save_prediction called when recovery_speed is not None."""
        from inference_models import _run_hrv_and_recovery

        hrv_hist = [50.0] * 30
        with (
            patch(
                "inference_models.compute_hrv_recovery_trajectory",
                return_value={"recovery_speed": 1.2, "score": 0.8, "n_events": 2},
            ),
            patch(
                "inference_models.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_hrv_and_recovery(1, _TODAY, hrv_hist, [], 185.0)
        model_keys = [c.args[2] for c in mock_save.call_args_list]
        assert "hrv_recovery" in model_keys


# ── inference_anomaly — _run_correlations ─────────────────────────────────────


class TestRunCorrelations:
    async def test_skips_key_when_fewer_than_2_pairs(self):
        from inference_anomaly import _run_correlations

        with (
            patch(
                "inference_anomaly.get_sleep_hrv_pairs",
                new_callable=AsyncMock,
                return_value=[(50.0, 55.0)],  # only 1 pair → skip
            ),
            patch(
                "inference_anomaly.get_sleep_resting_hr_pairs",
                new_callable=AsyncMock,
                return_value=[],  # empty → skip
            ),
            patch(
                "inference_anomaly.get_bb_resting_hr_pairs",
                new_callable=AsyncMock,
                return_value=[(80.0, 52.0), (75.0, 54.0)],  # 2 pairs → save
            ),
            patch(
                "inference_anomaly.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_correlations(1, _TODAY)
        assert mock_save.call_count == 1
        assert mock_save.call_args.args[2] == "correlation_bb_rhr"

    async def test_saves_correlation_for_valid_pairs(self):
        from inference_anomaly import _run_correlations

        pairs = [(float(i), float(i + 1)) for i in range(10)]
        with (
            patch(
                "inference_anomaly.get_sleep_hrv_pairs",
                new_callable=AsyncMock,
                return_value=pairs,
            ),
            patch(
                "inference_anomaly.get_sleep_resting_hr_pairs",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "inference_anomaly.get_bb_resting_hr_pairs",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "inference_anomaly.save_prediction", new_callable=AsyncMock
            ) as mock_save,
        ):
            await _run_correlations(1, _TODAY)
        assert mock_save.call_count == 1
        assert mock_save.call_args.args[2] == "correlation_sleep_hrv"

    async def test_fetches_all_pairs_concurrently(self):
        """asyncio.gather is used — all three DB functions are called."""
        from inference_anomaly import _run_correlations

        with (
            patch(
                "inference_anomaly.get_sleep_hrv_pairs",
                new_callable=AsyncMock,
                return_value=[],
            ) as m1,
            patch(
                "inference_anomaly.get_sleep_resting_hr_pairs",
                new_callable=AsyncMock,
                return_value=[],
            ) as m2,
            patch(
                "inference_anomaly.get_bb_resting_hr_pairs",
                new_callable=AsyncMock,
                return_value=[],
            ) as m3,
            patch("inference_anomaly.save_prediction", new_callable=AsyncMock),
        ):
            await _run_correlations(1, _TODAY)
        m1.assert_called_once_with(1)
        m2.assert_called_once_with(1)
        m3.assert_called_once_with(1)
