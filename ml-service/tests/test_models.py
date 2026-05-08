import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import datetime, timezone

from models.anomaly import detect_resting_hr_anomaly
from models.battery_pattern import extract_features
from models.correlation import compute_sleep_hrv_correlation
from models.readiness import predict_tomorrow, prepare_training_data, train_and_save


# ── Anomaly Detection ──────────────────────────────────────────────────────


def test_anomaly_insufficient_history():
    result = detect_resting_hr_anomaly([60, 62, 61], 63)
    assert not result["is_anomaly"]
    assert result["z_score"] is None
    assert result["reason"] == "insufficient_data"


def test_anomaly_no_today():
    history = [60.0] * 20
    result = detect_resting_hr_anomaly(history, None)
    assert not result["is_anomaly"]


def test_anomaly_normal_hr():
    history = [60, 62, 61, 63, 60, 59, 61, 62, 60, 61] * 3
    result = detect_resting_hr_anomaly(history, 62)
    assert not result["is_anomaly"]
    assert result["z_score"] is not None


def test_anomaly_spike():
    history = [60.0] * 30
    result = detect_resting_hr_anomaly(history, 75)
    # std is near 0 for perfectly constant data → low_variance case
    assert not result["is_anomaly"]
    assert result.get("baseline_mean") == 60.0


def test_anomaly_realistic_spike():
    np.random.seed(0)
    history = (np.random.normal(60, 3, 30)).tolist()
    result = detect_resting_hr_anomaly(history, 80)
    assert result["is_anomaly"]
    assert result["z_score"] > 1.5


# ── Correlation ────────────────────────────────────────────────────────────


def test_correlation_insufficient_data():
    result = compute_sleep_hrv_correlation([70, 80], [45, 50])
    assert result["r"] is None
    assert result["interpretation"] == "insufficient_data"


def test_correlation_positive():
    sleep = [50, 60, 70, 80, 90, 75, 65, 55, 85, 70, 80, 60]
    hrv = [40, 45, 50, 55, 60, 52, 48, 43, 58, 50, 54, 44]
    result = compute_sleep_hrv_correlation(sleep, hrv)
    assert result["r"] is not None
    assert result["r"] > 0
    assert result["n"] == 12


def test_correlation_strong():
    n = 20
    sleep = list(range(50, 50 + n))
    hrv = [s * 0.8 + 5 for s in sleep]
    result = compute_sleep_hrv_correlation(sleep, hrv)
    assert result["interpretation"] == "stark"
    assert result["r"] == pytest.approx(1.0, abs=0.01)


# ── Readiness Training Data ────────────────────────────────────────────────


def _make_rows(n: int) -> list[dict]:
    np.random.seed(42)
    rows = []
    for i in range(n):
        rows.append(
            {
                "hrv_last_night": float(np.random.uniform(30, 80)),
                "hrv_status": "BALANCED",
                "sleep_score": float(np.random.uniform(40, 90)),
                "resting_hr": float(np.random.uniform(45, 70)),
                "body_battery_high": float(np.random.uniform(30, 100)),
                "avg_stress": float(np.random.uniform(10, 60)),
            }
        )
    return rows


def test_prepare_training_data_too_few():
    rows = _make_rows(10)
    result = prepare_training_data(rows)
    assert result is None


def test_prepare_training_data_ok():
    rows = _make_rows(60)
    result = prepare_training_data(rows)
    assert result is not None
    X, y, feat_names = result
    assert X.shape[1] == 3
    assert feat_names == ["hrv_last_night", "sleep_score", "resting_hr"]
    assert len(X) == len(y)
    assert len(X) < 60  # last row has no next-day target


def test_prepare_training_data_skips_missing():
    rows = _make_rows(60)
    rows[5]["hrv_last_night"] = None  # imputed from median, not skipped
    result = prepare_training_data(rows)
    assert result is not None
    X, y, _ = result
    assert len(X) > 0


def test_prepare_training_data_imputes_missing():
    rows = _make_rows(60)
    # Every 3rd row has no HRV — without imputation this would drop below 30 valid pairs
    for i in range(0, 60, 3):
        rows[i]["hrv_last_night"] = None
    result = prepare_training_data(rows)
    assert result is not None  # imputation keeps enough rows to train
    X, y, feat_names = result
    assert len(X) >= 50  # ~59 pairs, most retained via imputation
    assert X.shape[1] == 3  # hrv median still non-None → all 3 active


def test_prepare_training_data_dynamic_features():
    rows = _make_rows(60)
    # Simulate hrv_last_night always NULL (like real DB where hrv_last_night never synced)
    for r in rows:
        r["hrv_last_night"] = None
    result = prepare_training_data(rows)
    assert result is not None  # should train with [sleep_score, resting_hr] only
    X, y, feat_names = result
    assert feat_names == ["sleep_score", "resting_hr"]
    assert X.shape[1] == 2
    assert len(X) >= 50


# ── predict_tomorrow (confidence interval) ────────────────────────────────────


def test_predict_tomorrow_returns_confidence_interval(tmp_path):
    model_path = tmp_path / "readiness_rf_1.joblib"
    rows = _make_rows(60)
    train_and_save(rows, model_path)

    features = {
        "hrv_last_night": 55.0,
        "sleep_score": 72.0,
        "resting_hr": 52.0,
    }
    result = predict_tomorrow(features, model_path)

    assert result is not None
    assert "score" in result
    assert "confidence_low" in result
    assert "confidence_high" in result
    assert (
        0.0
        <= result["confidence_low"]
        <= result["score"]
        <= result["confidence_high"]
        <= 100.0
    )


def test_predict_tomorrow_no_model(tmp_path):
    result = predict_tomorrow({"hrv_last_night": 55.0}, tmp_path / "missing.joblib")
    assert result is None


def test_predict_tomorrow_missing_feature(tmp_path):
    model_path = tmp_path / "readiness_rf_1.joblib"
    train_and_save(_make_rows(60), model_path)
    result = predict_tomorrow({}, model_path)
    assert result is None


def test_training_effects_used_when_present():
    rows = _make_rows(60)
    for r in rows:
        r["aerobic_effect_daily"] = float(np.random.uniform(0, 4))
        r["anaerobic_effect_daily"] = float(np.random.uniform(0, 2))
    result = prepare_training_data(rows)
    assert result is not None
    X, y, feat_names = result
    assert "aerobic_effect_daily" in feat_names
    assert "anaerobic_effect_daily" in feat_names
    assert X.shape[1] == 5  # all 5 candidate features active


def test_training_effects_absent_falls_back_to_core_features():
    rows = _make_rows(60)
    result = prepare_training_data(rows)
    assert result is not None
    X, y, feat_names = result
    assert feat_names == ["hrv_last_night", "sleep_score", "resting_hr"]
    assert X.shape[1] == 3


# ── Battery Pattern ────────────────────────────────────────────────────────


def _make_bb_records(n: int, base_hour: int = 0) -> list[dict]:
    records = []
    for i in range(n):
        hour = (base_hour + i * (24 // max(n, 1))) % 24
        records.append(
            {
                "time": datetime(2026, 5, 8, hour, 0, tzinfo=timezone.utc),
                "value": 60 + (i % 10),
            }
        )
    return records


def test_extract_features_empty():
    assert extract_features([]) is None


def test_extract_features_few_points():
    assert extract_features(_make_bb_records(3)) is None


def test_extract_features_ok():
    records = _make_bb_records(50, base_hour=0)
    feat = extract_features(records)
    assert feat is not None
    assert set(feat.keys()) == {
        "morning_avg",
        "evening_avg",
        "daily_range",
        "auc",
        "n_dips",
    }
    assert feat["daily_range"] >= 0
    assert 0 <= feat["auc"] <= 100
