"""Targeted tests closing the remaining coverage gaps in ml-service.

Covers small pure-function branches and a few orchestration/glue paths not
exercised by the broader suite (logging, health_server, run_training,
scheduler wiring, and several model branch toggles).
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── logging_config._sentry_error_processor ────────────────────────────────────


def test_sentry_processor_captures_exception_when_exc_info_true():
    import logging_config

    with patch.object(logging_config.sentry_sdk, "capture_exception") as cap:
        logging_config._sentry_error_processor(None, "error", {"exc_info": True})
        cap.assert_called_once_with()


def test_sentry_processor_captures_exc_info_tuple():
    import logging_config

    exc = (ValueError, ValueError("x"), None)
    with patch.object(logging_config.sentry_sdk, "capture_exception") as cap:
        logging_config._sentry_error_processor(None, "critical", {"exc_info": exc})
        cap.assert_called_once_with(exc)


# ── health_server._handle ─────────────────────────────────────────────────────


async def test_health_handle_writes_ok_and_closes():
    from health_server import _handle

    reader = MagicMock()
    reader.read = AsyncMock(return_value=b"GET / HTTP/1.1\r\n\r\n")
    writer = MagicMock()
    writer.drain = AsyncMock()

    await _handle(reader, writer)

    writer.write.assert_called_once()
    assert b"200 OK" in writer.write.call_args[0][0]
    writer.close.assert_called_once()


# ── main.run_training: model-trained vs insufficient-data branches ────────────


async def test_run_training_saves_meta_and_logs_when_trained(monkeypatch):
    import main

    monkeypatch.setattr(
        main, "get_readiness_training_rows", AsyncMock(return_value=[1])
    )
    monkeypatch.setattr(
        main,
        "train_and_save",
        MagicMock(return_value={"n_rows": 30, "importances": {}}),
    )
    save = AsyncMock()
    monkeypatch.setattr(main.prediction_repository, "save", save)
    monkeypatch.setattr(main, "get_body_battery_history", AsyncMock(return_value=[1]))
    monkeypatch.setattr(main, "battery_fit_and_save", MagicMock(return_value=True))

    settings = MagicMock()
    settings.model_dir = Path("/tmp")
    await main.run_training(1, settings)
    save.assert_awaited_once()


async def test_run_training_insufficient_data_skips_save(monkeypatch):
    import main

    monkeypatch.setattr(main, "get_readiness_training_rows", AsyncMock(return_value=[]))
    monkeypatch.setattr(main, "train_and_save", MagicMock(return_value=None))
    save = AsyncMock()
    monkeypatch.setattr(main.prediction_repository, "save", save)
    monkeypatch.setattr(main, "get_body_battery_history", AsyncMock(return_value=[]))
    monkeypatch.setattr(main, "battery_fit_and_save", MagicMock(return_value=False))

    settings = MagicMock()
    settings.model_dir = Path("/tmp")
    await main.run_training(1, settings)
    save.assert_not_awaited()


# ── main._write_alive_sentinel + _configure_ml_scheduler ──────────────────────


async def test_write_alive_sentinel_touches_file(monkeypatch):
    import main

    touched = {}
    monkeypatch.setattr(
        main.Path, "touch", lambda self: touched.__setitem__("done", True)
    )
    await main._write_alive_sentinel()
    assert touched["done"] is True


def test_configure_ml_scheduler_adds_jobs_and_starts(monkeypatch):
    import main

    fake = MagicMock()
    monkeypatch.setattr(main, "AsyncIOScheduler", lambda: fake)
    settings = MagicMock()
    settings.ml_infer_hour = 7
    settings.ml_train_weekday = "sun"

    result = main._configure_ml_scheduler(settings)
    assert result is fake
    assert fake.add_job.call_count == 4
    fake.start.assert_called_once()


def test_configure_ml_scheduler_replaces_legacy_poller_when_events_enabled(monkeypatch):
    import main

    fake = MagicMock()
    monkeypatch.setattr(main, "AsyncIOScheduler", lambda: fake)
    settings = MagicMock()
    settings.ml_infer_hour = 7
    settings.ml_train_weekday = "sun"
    settings.ml_event_consumer_enabled = True

    main._configure_ml_scheduler(settings)

    job_ids = [call.kwargs["id"] for call in fake.add_job.call_args_list]
    assert "service_events_retention" in job_ids
    assert "on_request" not in job_ids


# ── backfill_energy.main: backfill returning >0 skips up-to-date log ──────────


async def test_backfill_energy_main_with_pending_user(monkeypatch):
    import backfill_energy

    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[{"id": 1}])
    monkeypatch.setattr(backfill_energy, "Settings", lambda: MagicMock())
    monkeypatch.setattr(backfill_energy, "get_pool", lambda: pool)
    monkeypatch.setattr(backfill_energy, "init_pool", AsyncMock())
    monkeypatch.setattr(backfill_energy, "close_pool", AsyncMock())
    monkeypatch.setattr(backfill_energy, "backfill_user", AsyncMock(return_value=5))

    await backfill_energy.main()
    backfill_energy.backfill_user.assert_awaited_once_with(1)


# ── backfill: score-None guards skip save_prediction ──────────────────────────


async def test_save_body_battery_skips_when_no_score(monkeypatch):
    import backfill

    monkeypatch.setattr(backfill, "compute_body_battery", MagicMock(return_value={}))
    monkeypatch.setattr(backfill, "save_prediction", AsyncMock())

    data = {"sleep_by_date": {}, "act_rows": [], "hrmax": 190.0}
    await backfill._save_body_battery(1, date.today(), data, None, [], 50.0, None)
    backfill.save_prediction.assert_not_awaited()


async def test_save_running_economy_skips_when_no_score(monkeypatch):
    import backfill

    monkeypatch.setattr(
        backfill, "compute_running_economy", MagicMock(return_value={"score": None})
    )
    monkeypatch.setattr(backfill, "save_prediction", AsyncMock())

    target = date.today()
    data = {
        "act_rows": [
            {
                "activity_date": target,
                "sport_type": "running",
                "avg_ground_contact_time": 250,
            }
        ]
    }
    await backfill._save_running_economy(1, target, data)
    backfill.save_prediction.assert_not_awaited()


# ── inference_models: body-battery branches ───────────────────────────────────


async def test_run_body_battery_skips_when_no_score(monkeypatch):
    import inference_models as im

    monkeypatch.setattr(im, "compute_body_battery", MagicMock(return_value={}))
    monkeypatch.setattr(im, "save_prediction", AsyncMock())

    inputs = im.BodyBatteryInputs(
        yesterday_bb=50.0,
        last_night_h=7.0,
        last_night_deep=1.0,
        last_night_rem=1.5,
        hrv_last=42.0,
        hrv_baseline=40.0,
        act_rows=[],
        hrmax=190.0,
        daily_today=None,
    )
    await im._run_body_battery(1, date.today(), inputs)
    im.save_prediction.assert_not_awaited()


async def test_run_body_battery_and_stress_uses_existing_prediction(monkeypatch):
    import inference_models as im

    monkeypatch.setattr(im, "get_yesterday_prediction", AsyncMock(return_value=55.0))
    monkeypatch.setattr(im, "_run_body_battery", AsyncMock())
    monkeypatch.setattr(im, "_run_stress_score", AsyncMock())

    # yesterday_bb is not None → the daily_today fallback branch (278→279) is skipped
    await im._run_body_battery_and_stress(
        1, date.today(), [], 190.0, [42.0] * 14, [], {"body_battery_high": 70}
    )
    im._run_body_battery.assert_awaited_once()


# ── model pure-function branch toggles ────────────────────────────────────────


def test_day_trimp_for_row_returns_zero_when_denom_nonpositive():
    from models.training_load import _day_trimp_for_row

    row = {"avg_hr": 150, "duration_seconds": 3600, "resting_hr": 200}
    assert _day_trimp_for_row(row, hrmax=180.0) == 0.0


def test_intensity_minutes_ignores_low_intensity_seconds():
    from models.intensity_minutes import compute_intensity_minutes

    # hrr = (90-60)/(180-60) = 0.25 → below moderate threshold → neither bucket
    result = compute_intensity_minutes([90] * 120, resting_hr=60, hrmax=180)
    assert result["moderate_minutes"] == 0
    assert result["vigorous_minutes"] == 0


def test_spo2_trend_single_value_skips_slope():
    from models.spo2_metrics import compute_spo2_trend

    result = compute_spo2_trend([{"avg_spo2": 96.0, "min_spo2": 94.0}])
    assert result["slope"] == 0.0
    assert result["mean_spo2"] == 96.0


def test_collect_recovery_slopes_skips_window_with_too_few_valid():
    from models.hrv_recovery import _collect_recovery_slopes

    # trimps[0] over threshold, but the following window has < 3 valid HRV values
    trimps = [10.0] + [0.0] * 10
    hrv_vals = [40.0, None, None, None, None, None, None, None, 40.0, 40.0, 40.0]
    slopes = _collect_recovery_slopes(
        trimps, hrv_vals, trimp_threshold=5.0, baseline=40.0
    )
    assert slopes == []


def test_banister_trimp_handles_nonpositive_denom_and_past_days():
    from models.training_effect import compute_banister_trimp

    today = date.today()
    rows = [
        # i == 0, denom > 0 → trimp_today path
        {
            "activity_date": today,
            "avg_hr": 150,
            "duration_seconds": 3600,
            "resting_hr": 50,
        },
        # i == 1, denom <= 0 (resting_hr >= hrmax) → skip trimp (37→42)
        {
            "activity_date": today - timedelta(days=1),
            "avg_hr": 150,
            "duration_seconds": 3600,
            "resting_hr": 200,
        },
        # i == 2, denom > 0 but i != 0 → trimp computed, no trimp_today (40→42)
        {
            "activity_date": today - timedelta(days=2),
            "avg_hr": 150,
            "duration_seconds": 3600,
            "resting_hr": 50,
        },
    ]
    result = compute_banister_trimp(rows, sex="m", hrmax=190.0, window_days=5)
    assert "ctl" in result and "atl" in result
