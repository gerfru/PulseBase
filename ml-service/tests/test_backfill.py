"""Unit tests for ml-service backfill.py and inference_anomaly.py.

Mocks all DB and external dependencies — no database connection required.
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backfill import _compute_trimp, backfill_user
from inference_anomaly import _run_anomaly_for, _run_correlations


# ── _compute_trimp — pure function ────────────────────────────────────────────


class TestComputeTrimp:
    def test_returns_zero_when_no_activities(self):
        assert _compute_trimp([], 185.0, date(2026, 4, 27)) == 0.0

    def test_returns_zero_for_wrong_date(self):
        row = {
            "activity_date": date(2026, 4, 26),
            "avg_hr": 165,
            "duration_seconds": 3600,
            "resting_hr": 52,
        }
        assert _compute_trimp([row], 185.0, date(2026, 4, 27)) == 0.0

    def test_computes_positive_trimp(self):
        row = {
            "activity_date": date(2026, 4, 27),
            "avg_hr": 165,
            "duration_seconds": 3600,
            "resting_hr": 52,
        }
        result = _compute_trimp([row], 185.0, date(2026, 4, 27))
        assert result > 0.0

    def test_returns_zero_when_denominator_zero(self):
        row = {
            "activity_date": date(2026, 4, 27),
            "avg_hr": 165,
            "duration_seconds": 3600,
            "resting_hr": 185,
        }
        assert _compute_trimp([row], 185.0, date(2026, 4, 27)) == 0.0

    def test_returns_zero_when_avg_hr_missing(self):
        row = {"activity_date": date(2026, 4, 27), "duration_seconds": 3600}
        assert _compute_trimp([row], 185.0, date(2026, 4, 27)) == 0.0

    def test_returns_zero_when_duration_missing(self):
        row = {"activity_date": date(2026, 4, 27), "avg_hr": 165}
        assert _compute_trimp([row], 185.0, date(2026, 4, 27)) == 0.0


# ── backfill_user ─────────────────────────────────────────────────────────────

_EMPTY_ACT_HRV = {
    "hrmax": 185.0,
    "act_rows": [],
    "hrv_by_date": {},
    "hrv_dates_sorted": [],
}

_EMPTY_SLEEP_GAPS = {
    "gap_dates": [],
    "sleep_by_date": {},
    "daily_by_date": {},
}


async def test_backfill_user_returns_zero_when_no_gaps():
    with (
        patch(
            "backfill.get_backfill_activity_hrv_data",
            new_callable=AsyncMock,
            return_value=_EMPTY_ACT_HRV,
        ),
        patch(
            "backfill.get_backfill_sleep_daily_gaps",
            new_callable=AsyncMock,
            return_value=_EMPTY_SLEEP_GAPS,
        ),
    ):
        result = await backfill_user(user_id=1)
    assert result == 0


async def test_backfill_user_returns_count_of_gap_dates():
    target = date(2026, 4, 27)
    sleep_gaps = {
        **_EMPTY_SLEEP_GAPS,
        "gap_dates": [target, target - timedelta(days=1)],
    }
    with (
        patch(
            "backfill.get_backfill_activity_hrv_data",
            new_callable=AsyncMock,
            return_value=_EMPTY_ACT_HRV,
        ),
        patch(
            "backfill.get_backfill_sleep_daily_gaps",
            new_callable=AsyncMock,
            return_value=sleep_gaps,
        ),
        patch(
            "backfill.get_prediction_for_date",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("backfill.save_prediction", new_callable=AsyncMock),
    ):
        result = await backfill_user(user_id=1)
    assert result == 2


async def test_backfill_user_calls_save_prediction_per_gap():
    target = date(2026, 4, 27)
    sleep_gaps = {**_EMPTY_SLEEP_GAPS, "gap_dates": [target]}
    with (
        patch(
            "backfill.get_backfill_activity_hrv_data",
            new_callable=AsyncMock,
            return_value=_EMPTY_ACT_HRV,
        ),
        patch(
            "backfill.get_backfill_sleep_daily_gaps",
            new_callable=AsyncMock,
            return_value=sleep_gaps,
        ),
        patch(
            "backfill.get_prediction_for_date",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("backfill.save_prediction", new_callable=AsyncMock) as mock_save,
    ):
        await backfill_user(user_id=1)
    # energy_physical + energy_autonomic + energy_cognitive are the guaranteed saves
    assert mock_save.call_count >= 3


# ── inference_anomaly ─────────────────────────────────────────────────────────


async def test_run_anomaly_for_saves_prediction():
    history_fn = AsyncMock(return_value=[60.0, 61.0, 62.0])
    today_fn = AsyncMock(return_value=80.0)

    with patch(
        "inference_anomaly.save_prediction", new_callable=AsyncMock
    ) as mock_save:
        await _run_anomaly_for(
            user_id=1,
            today=date(2026, 4, 27),
            history_fn=history_fn,
            today_fn=today_fn,
            model_key="anomaly_hr",
            log_key="anomaly_hr",
        )
    mock_save.assert_called_once()
    args = mock_save.call_args.args
    assert args[0] == 1  # user_id
    assert args[2] == "anomaly_hr"  # model_key


async def test_run_anomaly_for_works_with_none_today_value():
    history_fn = AsyncMock(return_value=[60.0, 61.0, 62.0])
    today_fn = AsyncMock(return_value=None)

    with patch(
        "inference_anomaly.save_prediction", new_callable=AsyncMock
    ) as mock_save:
        await _run_anomaly_for(
            user_id=1,
            today=date(2026, 4, 27),
            history_fn=history_fn,
            today_fn=today_fn,
            model_key="anomaly_hr",
            log_key="anomaly_hr",
        )
    # Prediction must be saved even when today_val is None
    mock_save.assert_called_once()


async def test_run_correlations_skips_when_no_pairs():
    with (
        patch(
            "inference_anomaly.get_sleep_hrv_pairs",
            new_callable=AsyncMock,
            return_value=[],
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
        patch("inference_anomaly.save_prediction", new_callable=AsyncMock) as mock_save,
    ):
        await _run_correlations(user_id=1, today=date(2026, 4, 27))
    mock_save.assert_not_called()


async def test_run_correlations_saves_when_pairs_present():
    # Need at least 10 pairs for compute_sleep_hrv_correlation to return a result
    pairs = [
        (7.0, 50.0),
        (6.5, 48.0),
        (8.0, 55.0),
        (7.5, 52.0),
        (6.0, 45.0),
        (7.2, 51.0),
        (8.1, 56.0),
        (6.8, 49.0),
        (7.9, 54.0),
        (7.1, 50.5),
    ]
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
        patch("inference_anomaly.save_prediction", new_callable=AsyncMock) as mock_save,
    ):
        await _run_correlations(user_id=1, today=date(2026, 4, 27))
    mock_save.assert_called_once()
    assert mock_save.call_args.args[2] == "correlation_sleep_hrv"
