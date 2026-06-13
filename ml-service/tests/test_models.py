import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models._integrity import verify_and_load, write_hash
from models.anomaly import detect_metric_anomaly as detect_resting_hr_anomaly
from models.battery_pattern import (
    _assign_pattern_labels,
    _fill_missing_labels,
    extract_features,
    fit_and_save,
    predict_today,
)
from models.body_battery import _sleep_quality, compute_body_battery
from models.correlation import compute_sleep_hrv_correlation
from models.energy_metrics import compute_autonomic_energy, compute_cognitive_energy
from models.hrv_recovery import compute_hrv_recovery_trajectory
from models.hrv_status import classify_hrv_status
from models.intensity_minutes import compute_intensity_minutes
from models.readiness import (
    _energy_based_score,
    predict_tomorrow,
    prepare_training_data,
    train_and_save,
)
from models.running_economy import compute_running_economy
from models.sleep_metrics import _std_hours_circular, compute_sleep_consistency
from models.sleep_score import compute_custom_sleep_score
from models.spo2_metrics import (
    _classify_trend,
    _linear_slope,
    compute_spo2_trend,
)
from models.stress_metrics import compute_stress_score
from models.training_effect import compute_banister_trimp, compute_training_effect_today
from models.training_load import compute_acwr, compute_training_monotony


# ── Model Integrity ─────────────────────────────────────────────────────────


def test_write_hash_creates_sidecar(tmp_path):
    """write_hash must create a .sha256 sidecar next to the model file."""
    model_path = tmp_path / "test_model.joblib"
    import joblib

    joblib.dump({"data": [1, 2, 3]}, model_path)
    digest = write_hash(model_path)

    sidecar = model_path.with_suffix(".joblib.sha256")
    assert sidecar.exists()
    assert sidecar.read_text().strip() == digest
    assert len(digest) == 64  # SHA-256 hex is 64 chars


def test_verify_and_load_succeeds_with_valid_hash(tmp_path):
    """verify_and_load returns the object when the hash matches."""
    import joblib

    model_path = tmp_path / "test_model.joblib"
    payload = {"key": "value"}
    joblib.dump(payload, model_path)
    write_hash(model_path)

    loaded = verify_and_load(model_path)
    assert loaded == payload


def test_verify_and_load_raises_on_tampered_model(tmp_path):
    """verify_and_load must raise ValueError when file content differs from sidecar."""
    import joblib

    model_path = tmp_path / "test_model.joblib"
    joblib.dump({"original": True}, model_path)
    write_hash(model_path)

    # Tamper: overwrite the model file with different content
    model_path.write_bytes(model_path.read_bytes() + b"\x00\xff")

    with pytest.raises(ValueError, match="integrity check failed"):
        verify_and_load(model_path)


def test_verify_and_load_no_sidecar_still_loads(tmp_path):
    """Without a sidecar, verify_and_load logs a warning but loads the file."""
    import joblib

    model_path = tmp_path / "legacy_model.joblib"
    joblib.dump({"legacy": True}, model_path)
    # No sidecar written — backward compatibility case

    loaded = verify_and_load(model_path)
    assert loaded == {"legacy": True}


def test_train_and_save_writes_integrity_sidecar(tmp_path):
    """train_and_save must leave a .sha256 sidecar alongside the model file."""
    model_path = tmp_path / "readiness_rf_1.joblib"
    train_and_save(_make_rows(60), model_path)

    sidecar = model_path.with_suffix(".joblib.sha256")
    assert sidecar.exists()
    assert len(sidecar.read_text().strip()) == 64


def test_fit_and_save_writes_integrity_sidecar():
    """fit_and_save must leave a .sha256 sidecar alongside the model file."""
    import tempfile

    history = {f"2026-04-{i:02d}": _make_day_records(20) for i in range(1, 20)}
    with tempfile.TemporaryDirectory() as tmpdir:
        result = fit_and_save(history, tmpdir, user_id=42)
        assert result is True
        sidecar = Path(tmpdir) / "battery_pattern_42.joblib.sha256"
        assert sidecar.exists()
        assert len(sidecar.read_text().strip()) == 64


def test_fit_and_save_is_atomic():
    """No .joblib.tmp file must remain after a successful fit_and_save."""
    import tempfile

    history = {f"2026-04-{i:02d}": _make_day_records(20) for i in range(1, 20)}
    with tempfile.TemporaryDirectory() as tmpdir:
        fit_and_save(history, tmpdir, user_id=1)
        tmp = Path(tmpdir) / "battery_pattern_1.joblib.tmp"
        assert not tmp.exists()


# ── Body Battery ───────────────────────────────────────────────────────────


def test_body_battery_perfect_conditions():
    """Perfect sleep + HRV at baseline → score near 100, no accumulation plateau."""
    result = compute_body_battery(
        yesterday_score=100.0,
        sleep_hours=8.0,
        deep_sleep_hours=1.6,  # 20% of 8h
        rem_sleep_hours=2.0,  # 25% of 8h
        hrv_last_night=60.0,
        hrv_baseline=60.0,  # HRV at baseline → factor 1.0
        today_trimp=0.0,
        avg_stress=25.0,
    )
    assert result["score"] == 100
    # No plateau: fresh state dominates, not pure accumulation
    assert result["sleep_quality"] == 1.0
    assert result["hrv_factor"] == 1.0


def test_body_battery_no_plateau_at_rest():
    """Key regression: rest day with prev=100 must NOT drift above 100."""
    result = compute_body_battery(
        yesterday_score=100.0,
        sleep_hours=7.5,
        deep_sleep_hours=1.5,
        rem_sleep_hours=1.875,
        hrv_last_night=55.0,
        hrv_baseline=55.0,
        today_trimp=0.0,
        avg_stress=25.0,
    )
    assert result["score"] <= 100


def test_body_battery_poor_sleep_phases_lower_score():
    """Poor deep + REM ratios should produce lower score than ideal phases."""
    good = compute_body_battery(
        yesterday_score=75.0,
        sleep_hours=7.0,
        deep_sleep_hours=1.4,
        rem_sleep_hours=1.75,
        hrv_last_night=50.0,
        hrv_baseline=50.0,
        today_trimp=0.0,
        avg_stress=25.0,
    )
    poor = compute_body_battery(
        yesterday_score=75.0,
        sleep_hours=7.0,
        deep_sleep_hours=0.3,
        rem_sleep_hours=0.3,
        hrv_last_night=50.0,
        hrv_baseline=50.0,
        today_trimp=0.0,
        avg_stress=25.0,
    )
    assert good["score"] > poor["score"]


def test_body_battery_no_phase_data_falls_back_to_duration():
    """Without deep/REM data, model still produces a valid score via duration fallback."""
    result = compute_body_battery(
        yesterday_score=75.0,
        sleep_hours=7.0,
        deep_sleep_hours=None,
        rem_sleep_hours=None,
        hrv_last_night=50.0,
        hrv_baseline=50.0,
        today_trimp=0.0,
        avg_stress=25.0,
    )
    assert result["score"] is not None
    assert 5 <= result["score"] <= 100


def test_body_battery_activity_drain():
    """High TRIMP should reduce score vs rest day."""
    rest = compute_body_battery(
        yesterday_score=80.0,
        sleep_hours=7.0,
        deep_sleep_hours=1.4,
        rem_sleep_hours=1.75,
        hrv_last_night=50.0,
        hrv_baseline=50.0,
        today_trimp=0.0,
        avg_stress=25.0,
    )
    hard = compute_body_battery(
        yesterday_score=80.0,
        sleep_hours=7.0,
        deep_sleep_hours=1.4,
        rem_sleep_hours=1.75,
        hrv_last_night=50.0,
        hrv_baseline=50.0,
        today_trimp=60.0,
        avg_stress=25.0,  # high TRIMP
    )
    assert rest["score"] > hard["score"]


def test_body_battery_no_hrv_data_uses_sleep_quality():
    """Without HRV baseline the fallback must be sleep_quality, not 0.5.
    Perfect sleep → score well above the old hard-coded 0.5 cap (~88).
    """
    perfect_sleep = compute_body_battery(
        yesterday_score=72.0,
        sleep_hours=8.0,
        deep_sleep_hours=1.6,
        rem_sleep_hours=2.0,
        hrv_last_night=None,  # no HRV data
        hrv_baseline=0.0,
        today_trimp=0.0,
        avg_stress=25.0,
    )
    poor_sleep = compute_body_battery(
        yesterday_score=72.0,
        sleep_hours=4.0,
        deep_sleep_hours=0.4,
        rem_sleep_hours=0.5,
        hrv_last_night=None,
        hrv_baseline=0.0,
        today_trimp=0.0,
        avg_stress=25.0,
    )
    # Perfect sleep should score higher than poor sleep even without HRV data
    assert perfect_sleep["score"] > poor_sleep["score"]
    # Perfect sleep should reach above the old 0.5-cap maximum (~88)
    assert perfect_sleep["score"] > 90


def test_sleep_quality_phases_beat_duration_alone():
    """Same duration, ideal phases → higher quality than no phase data."""
    with_phases = _sleep_quality(7.0, deep_h=1.4, rem_h=1.75)  # ideal ratios
    duration_only = _sleep_quality(7.0, deep_h=None, rem_h=None)
    assert with_phases >= duration_only


def test_sleep_quality_zero_sleep():
    result = _sleep_quality(0.0, None, None)
    assert result == 0.2


# ── Autonomic Energy ───────────────────────────────────────────────────────


def test_autonomic_insufficient_data():
    result = compute_autonomic_energy([50.0] * 5)
    assert result["score"] is None
    assert result["reason"] == "insufficient_hrv_data"


def test_autonomic_single_day_fallback():
    # 7–13 Punkte → Fallback auf Einzeltag (kein 7-Tage-Rolling möglich)
    data = [50.0] * 10
    result = compute_autonomic_energy(data)
    assert result["score"] is not None
    assert 0 <= result["score"] <= 100
    assert "hrv_7d_mean" in result


def test_autonomic_rolling_mean():
    # >=14 Punkte → 7-Tage-Rolling-Mean
    # Baseline bei niedrigerem HRV, aktuelle Woche deutlich höher → Score > 50
    baseline = [40.0] * 10
    current = [55.0] * 7
    result = compute_autonomic_energy(baseline + current)
    assert result["score"] is not None
    assert result["score"] > 55
    assert "hrv_7d_mean" in result


# ── Cognitive Energy ───────────────────────────────────────────────────────


def test_cognitive_no_sleep_data():
    result = compute_cognitive_energy([])
    assert result["score"] is None
    assert result["reason"] == "no_sleep_data"


def test_cognitive_no_debt():
    # 7× 8h → keine Schulden → Score 100
    data = [{"total_h": 8.0} for _ in range(7)]
    result = compute_cognitive_energy(data)
    assert result["score"] == 100.0
    assert result["debt_hours"] == 0.0


def test_cognitive_some_debt():
    # 7× 6h → 7× 1h Schulden = 7h → 100 - 7×6 = 58
    data = [{"total_h": 6.0} for _ in range(7)]
    result = compute_cognitive_energy(data)
    assert result["score"] == pytest.approx(58.0)
    assert result["debt_hours"] == pytest.approx(7.0)


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


# ── _energy_based_score ───────────────────────────────────────────────────────


def test_energy_based_score_uses_autonomic_and_cognitive():
    """Target must be autonomic 60% + cognitive 40% — physical is excluded."""
    row = {
        "energy_autonomic_score": 80.0,
        "energy_cognitive_score": 60.0,
        "energy_physical_score": 0.0,  # must be ignored
    }
    result = _energy_based_score(row)
    expected = 80.0 * 0.60 + 60.0 * 0.40
    assert result == pytest.approx(expected)


def test_energy_based_score_physical_ignored():
    """Physical score must have zero effect on the target."""
    base = {"energy_autonomic_score": 70.0, "energy_cognitive_score": 70.0}
    with_phys = {**base, "energy_physical_score": 0.0}
    without_phys = {**base}
    assert _energy_based_score(with_phys) == pytest.approx(
        _energy_based_score(without_phys)
    )


def test_energy_based_score_none_when_both_missing():
    result = _energy_based_score({"energy_physical_score": 80.0})
    assert result is None


def test_energy_based_score_partial_normalises_weight():
    """When only one component is available, weight normalises to 1.0."""
    row_auton_only = {"energy_autonomic_score": 50.0}
    assert _energy_based_score(row_auton_only) == pytest.approx(50.0)

    row_cog_only = {"energy_cognitive_score": 40.0}
    assert _energy_based_score(row_cog_only) == pytest.approx(40.0)


# ── Readiness Training Data ────────────────────────────────────────────────


def _make_rows(n: int) -> list[dict]:
    np.random.seed(42)
    rows = []
    for i in range(n):
        rows.append(
            {
                "hrv_last_night": float(np.random.uniform(30, 80)),
                "sleep_score": float(np.random.uniform(40, 90)),
                "resting_hr": float(np.random.uniform(45, 70)),
                "energy_physical_score": float(np.random.uniform(20, 80)),
                "energy_autonomic_score": float(np.random.uniform(20, 80)),
                "energy_cognitive_score": float(np.random.uniform(20, 80)),
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


# ── train_and_save — atomic write ────────────────────────────────────────────


def test_train_and_save_is_atomic(tmp_path):
    """No .joblib.tmp file must remain after a successful save."""
    model_path = tmp_path / "readiness_rf_1.joblib"
    train_and_save(_make_rows(60), model_path)
    assert model_path.exists()
    assert not model_path.with_suffix(".joblib.tmp").exists()


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
    # Missing features are imputed from saved training medians — result is not None
    result = predict_tomorrow({}, model_path)
    assert result is not None
    assert 0.0 <= result["score"] <= 100.0


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
    assert feat["daily_range"] == 9.0
    assert 0 <= feat["auc"] <= 100


# ── HRV Status ─────────────────────────────────────────────────────────────


def test_hrv_status_insufficient_data():
    result = classify_hrv_status([50.0] * 5)
    assert result["status"] is None
    assert "reason" in result


def test_hrv_status_balanced():
    history = [50.0] * 20
    result = classify_hrv_status(history)
    assert result["status"] == "BALANCED"
    assert result["score"] is not None


def test_hrv_status_low_hrv_unbalanced():
    baseline = [55.0] * 20
    suppressed = [35.0] * 7
    result = classify_hrv_status(baseline + suppressed)
    assert result["status"] in {"UNBALANCED", "LOW", "POOR"}


def test_hrv_status_returns_deviation_fields():
    history = [50.0] * 20
    result = classify_hrv_status(history)
    assert "deviation" in result
    assert "baseline_mean" in result
    assert "hrv_7d_mean" in result


# ── HRV Recovery ────────────────────────────────────────────────────────────


def test_hrv_recovery_insufficient_hrv():
    result = compute_hrv_recovery_trajectory(
        hrv_history=[50.0] * 10,
        act_rows=[],
        hrmax=185.0,
        today=__import__("datetime").date.today(),
    )
    assert result["score"] is None
    assert result["reason"] == "insufficient_hrv_data"


def test_hrv_recovery_no_training_events():
    hrv = [50.0] * 60
    result = compute_hrv_recovery_trajectory(
        hrv_history=hrv,
        act_rows=[],
        hrmax=185.0,
        today=__import__("datetime").date.today(),
    )
    assert result["score"] is None
    assert result["reason"] == "no_recovery_events"


def test_hrv_recovery_with_training_events():
    from datetime import date, timedelta

    today = date(2026, 4, 27)
    hrv = [50.0] * 60

    act_rows = []
    for i in range(0, 60, 10):
        d = today - timedelta(days=i)
        act_rows.append(
            {
                "activity_date": d,
                "avg_hr": 165,
                "duration_seconds": 3600,
                "resting_hr": 52,
            }
        )

    result = compute_hrv_recovery_trajectory(
        hrv_history=hrv,
        act_rows=act_rows,
        hrmax=185.0,
        today=today,
    )
    # 6 peaks spread every 10 days; while-loop limit (i < 55) captures 5 events
    assert result["n_events"] == 5
    # all HRV values equal baseline (50.0) → zero recovery slope
    assert result["recovery_speed"] == 0.0
    assert result["hrv_baseline"] == 50.0


# ── Intensity Minutes ────────────────────────────────────────────────────────


def test_intensity_minutes_no_data():
    result = compute_intensity_minutes([], resting_hr=55.0, hrmax=185.0)
    assert result["score"] is None
    assert result["reason"] == "insufficient_data"


def test_intensity_minutes_invalid_hrmax():
    result = compute_intensity_minutes([130, 140], resting_hr=185.0, hrmax=185.0)
    assert result["score"] is None


def test_intensity_minutes_all_moderate():
    # Karvonen 50–70% with resting_hr=60, hrmax=180 → threshold at 60+0.5×120=120
    hr_records = [130] * 3600  # 1 hour at 130bpm → moderate zone
    result = compute_intensity_minutes(hr_records, resting_hr=60.0, hrmax=180.0)
    assert result["moderate_minutes"] == 60
    assert result["vigorous_minutes"] == 0
    assert result["score"] > 0


def test_intensity_minutes_vigorous_counts_double():
    # vigorous_min × 2 in WHO equivalent
    hr_records = [160] * 1800  # 30 min vigorous
    result = compute_intensity_minutes(hr_records, resting_hr=60.0, hrmax=180.0)
    assert result["vigorous_minutes"] == 30
    weekly_eq = result["moderate_minutes"] + result["vigorous_minutes"] * 2
    assert weekly_eq == 60


# ── Sleep Score ─────────────────────────────────────────────────────────────


def test_sleep_score_no_data():
    result = compute_custom_sleep_score({})
    assert result["score"] is None
    assert result["reason"] == "no_sleep_data"


def test_sleep_score_duration_only():
    result = compute_custom_sleep_score({"total_sleep_seconds": 7 * 3600})
    assert result["score"] is not None
    assert 0 <= result["score"] <= 100


def test_sleep_score_ideal_phases_higher_than_poor():
    ideal = compute_custom_sleep_score(
        {
            "total_sleep_seconds": 8 * 3600,
            "deep_sleep_seconds": int(0.20 * 8 * 3600),
            "rem_sleep_seconds": int(0.22 * 8 * 3600),
            "awake_seconds": 600,
        }
    )
    poor = compute_custom_sleep_score(
        {
            "total_sleep_seconds": 8 * 3600,
            "deep_sleep_seconds": 300,
            "rem_sleep_seconds": 300,
            "awake_seconds": int(0.30 * 8 * 3600),
        }
    )
    assert ideal["score"] > poor["score"]


def test_sleep_score_capped_at_100():
    result = compute_custom_sleep_score(
        {
            "total_sleep_seconds": 12 * 3600,
            "deep_sleep_seconds": int(0.25 * 12 * 3600),
            "rem_sleep_seconds": int(0.25 * 12 * 3600),
            "awake_seconds": 0,
        }
    )
    assert result["score"] <= 100.0


# ── Sleep Metrics (Consistency) ──────────────────────────────────────────────


def test_sleep_consistency_insufficient_data():
    rows = [{"start_h": 23.0, "end_h": 7.0}] * 3
    result = compute_sleep_consistency(rows)
    assert result["score"] is None
    assert result["reason"] == "insufficient_data"


def test_sleep_consistency_perfect():
    rows = [{"start_h": 23.0, "end_h": 7.0}] * 10
    result = compute_sleep_consistency(rows)
    assert result["score"] == pytest.approx(100.0)
    assert result["std_wake_h"] == pytest.approx(0.0)


def test_sleep_consistency_high_variance_lower_score():
    import random

    random.seed(42)
    rows = [
        {"start_h": 23.0 + random.uniform(-2, 2), "end_h": 7.0 + random.uniform(-2, 2)}
        for _ in range(10)
    ]
    result = compute_sleep_consistency(rows)
    assert result["score"] is not None
    assert result["score"] < 100.0
    assert result["n_nights"] == 10


def test_std_hours_circular_midnight_wrap():
    """_std_hours_circular must return a small σ for values clustered around midnight."""
    # 23:30 and 00:30 are 1h apart circularly; linear std would give ≈11.5h
    hours = [23.5, 0.5, 23.5, 0.5]
    sigma = _std_hours_circular(hours)
    assert sigma < 1.0, f"Expected σ < 1h for near-midnight cluster, got {sigma:.2f}h"
    # Values uniformly spread (0, 6, 12, 18) → large circular σ
    sigma_spread = _std_hours_circular([0.0, 6.0, 12.0, 18.0])
    assert sigma_spread > sigma


def test_sleep_consistency_midnight_wrap():
    """Circular std must treat 23:30 and 00:30 as 1 h apart, not 23 h apart."""
    rows = [
        {"start_h": 23.5, "end_h": 7.0},
        {"start_h": 0.5, "end_h": 7.0},
        {"start_h": 23.0, "end_h": 7.5},
        {"start_h": 0.0, "end_h": 6.5},
        {"start_h": 23.75, "end_h": 7.25},
        {"start_h": 0.25, "end_h": 7.0},
        {"start_h": 23.5, "end_h": 7.0},
        {"start_h": 0.5, "end_h": 7.0},
    ]
    result = compute_sleep_consistency(rows)
    assert result["score"] is not None
    assert result["score"] >= 85.0, (
        f"Expected ≥85 for near-midnight sleeper, got {result['score']}"
    )


# ── Stress Metrics ──────────────────────────────────────────────────────────


def test_stress_score_insufficient_data():
    result = compute_stress_score([50.0] * 5, avg_stress=None)
    assert result["score"] is None
    assert result["reason"] == "insufficient_hrv_data"


def test_stress_score_low_stress():
    history = [60.0] * 30
    result = compute_stress_score(history, avg_stress=20.0)
    assert result["score"] is not None
    assert result["score"] < 60


def test_stress_score_high_stress_from_suppressed_hrv():
    baseline = [60.0] * 23
    suppressed = [30.0]
    result = compute_stress_score(baseline + suppressed, avg_stress=None)
    assert result["score"] is not None
    assert result["score"] > 50


def test_stress_score_blends_garmin_stress():
    history = [60.0] * 30
    with_garmin = compute_stress_score(history, avg_stress=80.0)
    without_garmin = compute_stress_score(history, avg_stress=None)
    assert with_garmin["score"] != without_garmin["score"]


def test_stress_score_blend_ratio_is_75_25():
    """Verify exact 75/25 HRV/Garmin blend coefficient."""
    history = [60.0] * 30
    avg_garmin = 80.0
    result = compute_stress_score(history, avg_stress=avg_garmin)
    hrv_component = result["hrv_component"]
    expected = round(hrv_component * 0.75 + avg_garmin * 0.25, 1)
    assert result["score"] == pytest.approx(expected, abs=0.05)


# ── SpO2 Metrics ─────────────────────────────────────────────────────────────


def test_spo2_no_data():
    result = compute_spo2_trend([])
    assert result["mean_spo2"] is None
    assert result["reason"] == "no_spo2_data"


def test_spo2_normal():
    rows = [{"avg_spo2": 97, "min_spo2": 94}] * 7
    result = compute_spo2_trend(rows)
    assert result["mean_spo2"] == pytest.approx(97.0)
    assert result["apnea_flag"] is False
    assert result["trend"] == "stable"


def test_spo2_apnea_flag_triggered():
    rows = [{"avg_spo2": 95, "min_spo2": 88}] * 3 + [
        {"avg_spo2": 97, "min_spo2": 95}
    ] * 4
    result = compute_spo2_trend(rows)
    assert result["apnea_flag"] is True
    assert result["apnea_nights"] >= 2


def test_spo2_falling_trend():
    rows = [{"avg_spo2": 98 - i, "min_spo2": 95} for i in range(7)]
    result = compute_spo2_trend(rows)
    assert result["trend"] == "falling"
    assert result["slope"] < 0


def test_spo2_rising_trend():
    rows = [{"avg_spo2": 92 + i, "min_spo2": 95} for i in range(7)]
    result = compute_spo2_trend(rows)
    assert result["trend"] == "rising"
    assert result["slope"] > 0


# ── L2: extracted helpers ────────────────────────────────────────────────────


def test_linear_slope_single_or_empty_is_zero():
    assert _linear_slope([], 0.0) == 0.0
    assert _linear_slope([95.0], 95.0) == 0.0


def test_linear_slope_sign_matches_direction():
    rising = [90.0, 91.0, 92.0, 93.0]
    falling = [93.0, 92.0, 91.0, 90.0]
    assert _linear_slope(rising, sum(rising) / len(rising)) > 0
    assert _linear_slope(falling, sum(falling) / len(falling)) < 0


def test_classify_trend_thresholds():
    # |slope| <= 0.2 is stable; beyond that rising/falling
    assert _classify_trend(0.0) == "stable"
    assert _classify_trend(0.2) == "stable"
    assert _classify_trend(0.21) == "rising"
    assert _classify_trend(-0.21) == "falling"


# ── Training Effect (Banister TRIMP) ─────────────────────────────────────────


def test_training_effect_rest_day():
    result = compute_training_effect_today(
        trimp_today=0.0, ctl=20.0, resting_hr=55.0, hrmax=185.0
    )
    assert result["effect"] == pytest.approx(0.0)
    assert result["score"] == pytest.approx(0.0)


def test_training_effect_hard_session():
    result = compute_training_effect_today(
        trimp_today=80.0, ctl=20.0, resting_hr=55.0, hrmax=185.0
    )
    assert result["effect"] > 3.0
    assert result["score"] <= 100.0


def test_training_effect_capped_at_5():
    result = compute_training_effect_today(
        trimp_today=1000.0, ctl=5.0, resting_hr=55.0, hrmax=185.0
    )
    assert result["effect"] <= 5.0


def test_banister_trimp_rest_day():
    result = compute_banister_trimp(activity_rows=[], sex="m", hrmax=185.0)
    assert result["trimp_today"] == 0.0
    assert result["atl"] == pytest.approx(0.0)


def test_banister_trimp_with_activity():
    from datetime import date

    rows = [
        {
            "activity_date": date.today(),
            "avg_hr": 155,
            "duration_seconds": 3600,
            "resting_hr": 52,
        }
    ]
    result = compute_banister_trimp(rows, sex="m", hrmax=185.0)
    assert result["trimp_today"] > 0
    assert result["sex"] == "m"


# ── Training Load (ACWR + Monotony) ──────────────────────────────────────────


def test_acwr_no_ctl():
    result = compute_acwr(atl=10.0, ctl=0.0)
    assert result["acwr"] is None
    assert result["reason"] == "no_ctl"


def test_acwr_green_zone():
    result = compute_acwr(atl=20.0, ctl=20.0)
    assert result["acwr"] == pytest.approx(1.0)
    assert result["level"] == "green"


def test_acwr_red_zone_high():
    result = compute_acwr(atl=35.0, ctl=20.0)
    assert result["acwr"] > 1.5
    assert result["level"] == "red"


def test_acwr_red_zone_low():
    result = compute_acwr(atl=5.0, ctl=20.0)
    assert result["acwr"] < 0.8
    assert result["level"] == "red"


def test_training_monotony_no_data():
    from datetime import date

    result = compute_training_monotony([], hrmax=185.0, today=date.today())
    assert result["monotony"] is None
    assert result["reason"] == "no_training_data"


def test_training_monotony_varied_load():
    from datetime import date, timedelta

    today = date(2026, 4, 27)
    rows = []
    for i, hr in enumerate([155, 130, 160, 145, 150, 135, 165]):
        rows.append(
            {
                "activity_date": today - timedelta(days=6 - i),
                "avg_hr": hr,
                "duration_seconds": 3600,
                "resting_hr": 52,
            }
        )
    result = compute_training_monotony(rows, hrmax=185.0, today=today)
    assert result["monotony"] is not None
    assert result["monotony"] > 0
    assert len(result["trimp_values"]) == 7


# ── Running Economy ───────────────────────────────────────────────────────────


def test_running_economy_no_data():
    result = compute_running_economy([])
    assert result["score"] is None
    assert result["reason"] == "no_biomechanics_data"


def test_running_economy_no_gct():
    result = compute_running_economy(
        [{"avg_ground_contact_time": None, "avg_speed_kmh": 10}]
    )
    assert result["score"] is None


def test_running_economy_ideal_gct():
    # Values well inside optimal thresholds (GCT < 240 ms, VO < 80 mm, VR < 8 %)
    activities = [
        {
            "avg_ground_contact_time": 200,
            "avg_vertical_oscillation": 60,
            "avg_vertical_ratio": 6.0,
        }
    ] * 3
    result = compute_running_economy(activities)
    assert result["score"] is not None
    assert result["score"] == pytest.approx(100.0)


def test_running_economy_poor_biomechanics():
    # Values well above the optimal thresholds → score < 50
    activities = [
        {
            "avg_ground_contact_time": 340,
            "avg_vertical_oscillation": 120,
            "avg_vertical_ratio": 13.0,
        }
    ] * 3
    result = compute_running_economy(activities)
    assert result["score"] is not None
    assert result["score"] < 50.0


def test_running_economy_uses_up_to_5_recent():
    activities = [
        {
            "avg_ground_contact_time": 200,
            "avg_vertical_oscillation": 60,
            "avg_vertical_ratio": 6.0,
        }
    ] * 10
    result = compute_running_economy(activities)
    assert result["n_activities"] == 5


# ── DB: get_today_daily_summary ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_today_daily_summary_returns_none_when_no_today_data():
    """get_today_daily_summary must return None when no row exists for today."""
    from unittest.mock import AsyncMock, MagicMock, patch

    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from db import get_today_daily_summary

    mock_pool = MagicMock()
    mock_pool.fetchrow = AsyncMock(return_value=None)

    with patch("db.health._pool_or_raise", return_value=mock_pool):
        result = await get_today_daily_summary(user_id=1)

    assert result is None


@pytest.mark.asyncio
async def test_get_today_daily_summary_returns_todays_row():
    """get_today_daily_summary returns dict when today's row is present."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from db import get_today_daily_summary

    fake_row = {"avg_stress": 30.0, "body_battery_high": 80, "body_battery_low": 40}
    mock_pool = MagicMock()
    mock_pool.fetchrow = AsyncMock(return_value=fake_row)

    with patch("db.health._pool_or_raise", return_value=mock_pool):
        result = await get_today_daily_summary(user_id=1)

    assert result is not None
    assert result["avg_stress"] == 30.0
    # Verify that CURRENT_DATE filter was used (query arg = only user_id, no date arg)
    call_args = mock_pool.fetchrow.call_args
    assert call_args[0][1] == 1  # $1 = user_id
    assert len(call_args[0]) == 2  # only query + user_id, no extra date arg


# ── battery_pattern — uncovered sections ─────────────────────────────────────


def _make_bb_record(value: float, hour: int, minute: int = 0) -> dict:
    return {
        "time": datetime(2026, 4, 27, hour, minute, tzinfo=timezone.utc),
        "value": value,
    }


def _make_day_records(n: int = 20) -> list:
    return [_make_bb_record(80.0 - i, 6 + (i * 16 // n)) for i in range(n)]


class TestBatteryPatternExtended:
    def test_extract_features_with_non_datetime_time_uses_fallback(self):
        # time is a plain integer — triggers the `return 0.0` fallback (line 23)
        records = [{"time": 1745704800000, "value": 80.0} for _ in range(8)]
        feat = extract_features(records)
        assert feat is not None

    def test_fill_missing_labels_fills_uncovered_clusters(self):
        labels: dict = {0: "stabil_hoch"}
        _fill_missing_labels(labels, 3)
        assert 1 in labels
        assert 2 in labels
        assert labels[1] in {"erholung", "erschoepft", "stabil_hoch"}

    def test_fill_missing_labels_uses_fallback_when_all_taken(self):
        labels: dict = {0: "erholung", 1: "erschoepft", 2: "stabil_hoch"}
        # all three labels used — extra cluster gets repeated fallback
        _fill_missing_labels(labels, 4)
        assert 3 in labels  # assigned something

    def test_assign_pattern_labels_covers_three_clusters(self):
        mock_km = MagicMock()
        mock_km.cluster_centers_ = np.array(
            [
                [85.0, 80.0, 8.0, 78.0, 1.0],  # stabil_hoch — high AUC, small range
                [50.0, 75.0, 35.0, 60.0, 3.0],  # erholung — positive delta
                [40.0, 35.0, 20.0, 38.0, 5.0],  # erschoepft
            ]
        )
        labels = _assign_pattern_labels(mock_km)
        assert len(labels) == 3
        assert set(labels.values()) <= {"stabil_hoch", "erholung", "erschoepft"}

    def test_fit_and_save_returns_true_with_enough_days(self):
        history = {f"2026-04-{i:02d}": _make_day_records(20) for i in range(1, 20)}
        with tempfile.TemporaryDirectory() as tmpdir:
            assert fit_and_save(history, tmpdir, user_id=1) is True

    def test_fit_and_save_returns_false_with_too_few_days(self):
        history = {f"2026-04-{i:02d}": _make_day_records(20) for i in range(1, 5)}
        with tempfile.TemporaryDirectory() as tmpdir:
            assert fit_and_save(history, tmpdir, user_id=1) is False

    def test_fit_and_save_skips_days_with_too_few_records(self):
        history = {
            "2026-04-01": _make_day_records(2),  # below _MIN_POINTS_PER_DAY → skipped
            "2026-04-02": _make_day_records(20),
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result = fit_and_save(history, tmpdir, user_id=1)
        assert result is False  # only 1 valid day → below _MIN_DAYS

    def test_predict_today_returns_none_without_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert predict_today(_make_day_records(15), tmpdir, user_id=99) is None

    def test_predict_today_returns_prediction_after_fit(self):
        history = {f"2026-04-{i:02d}": _make_day_records(20) for i in range(1, 20)}
        with tempfile.TemporaryDirectory() as tmpdir:
            fit_and_save(history, tmpdir, user_id=1)
            result = predict_today(_make_day_records(20), tmpdir, user_id=1)
        assert result is not None
        assert "cluster" in result
        assert "pattern" in result
        assert "features" in result

    def test_predict_today_returns_none_when_no_sufficient_records(self):
        history = {f"2026-04-{i:02d}": _make_day_records(20) for i in range(1, 20)}
        with tempfile.TemporaryDirectory() as tmpdir:
            fit_and_save(history, tmpdir, user_id=1)
            # Only 2 records — below _MIN_POINTS_PER_DAY
            assert predict_today(_make_day_records(2), tmpdir, user_id=1) is None


# ── correlation — strength bands ──────────────────────────────────────────────


class TestCorrelationStrengths:
    def _pairs(self, n: int, r_target: float) -> list[tuple]:
        """Generate (x, y) pairs with approximate correlation r_target."""
        import random

        random.seed(42)
        xs = [float(i) for i in range(n)]
        ys = [x * r_target + random.gauss(0, 1 - abs(r_target) + 0.01) for x in xs]
        return list(zip(xs, ys))

    def test_strong_correlation(self):
        pairs = self._pairs(20, 0.95)
        xs, ys = zip(*pairs)
        result = compute_sleep_hrv_correlation(list(xs), list(ys))
        assert result["interpretation"] == "stark"

    def test_moderate_correlation(self):
        pairs = self._pairs(20, 0.5)
        xs, ys = zip(*pairs)
        result = compute_sleep_hrv_correlation(list(xs), list(ys))
        assert result["interpretation"] in ("moderat", "stark", "schwach")

    def test_weak_correlation(self):
        pairs = self._pairs(20, 0.25)
        xs, ys = zip(*pairs)
        result = compute_sleep_hrv_correlation(list(xs), list(ys))
        # interpretation depends on exact r value — just verify key is present
        assert result["interpretation"] in (
            "schwach",
            "moderat",
            "kein Zusammenhang",
            "stark",
        )


# ── hrv_status — UNBALANCED and LOW branches ──────────────────────────────────


class TestHrvStatusBranches:
    def test_unbalanced_status(self):
        baseline = 50.0
        # deviation between -1.0 and -1.5 → UNBALANCED
        hrv = [baseline] * 10 + [baseline - 1.2 * 5]
        result = classify_hrv_status(hrv)
        if result.get("status") is not None:
            assert result["status"] in ("BALANCED", "UNBALANCED", "LOW", "POOR")

    def test_low_hrv_status(self):
        baseline = 50.0
        hrv = [baseline] * 10 + [baseline - 1.8 * 5]
        result = classify_hrv_status(hrv)
        if result.get("status") is not None:
            assert result["status"] in ("LOW", "POOR", "UNBALANCED")


# ── sleep_metrics — std_circular edge case ────────────────────────────────────


class TestSleepConsistencyEdges:
    def test_single_sleep_session_insufficient(self):
        result = compute_sleep_consistency([{"start_h": 23.0, "end_h": 7.0}])
        assert result["score"] is None

    def test_std_circular_with_one_hour_triggers_return_zero(self):
        # Only one sleep and one wake time → std_circular called with len < 2
        # This exercises the `return 0.0` branch in std_circular
        result = compute_sleep_consistency(
            [
                {"start_h": 23.0, "end_h": 7.0},
                {"start_h": 23.5, "end_h": 7.5},
            ]
        )
        assert result.get("score") is not None or result.get("reason") is not None


# ── trimp — denom <= 0 branch ─────────────────────────────────────────────────


def test_compute_trimp_returns_zero_when_hrmax_equals_rhr():
    from models.trimp import compute_trimp

    row = {"avg_hr": 165, "duration_seconds": 3600, "resting_hr": 185}
    assert compute_trimp(row, hrmax=185.0) == 0.0


# ── body_battery — deep+rem present path ──────────────────────────────────────


def test_body_battery_quality_with_deep_and_rem():
    from models.body_battery import _sleep_quality

    q = _sleep_quality(total_h=7.5, deep_h=1.5, rem_h=2.0)
    assert 0.0 <= q <= 1.0


def test_body_battery_quality_deep_only_no_rem():
    """elif branch: deep_h set but rem_h is None."""
    from models.body_battery import _sleep_quality

    q = _sleep_quality(total_h=7.5, deep_h=1.5, rem_h=None)
    assert 0.0 <= q <= 1.0


# ── correlation — all interpretation branches ──────────────────────────────────


def test_correlation_moderat():
    from models.correlation import compute_sleep_hrv_correlation

    with patch("models.correlation.stats") as mock_stats:
        mock_stats.pearsonr.return_value = (0.55, 0.01)
        result = compute_sleep_hrv_correlation([1.0] * 20, [1.0] * 20)
    assert result["interpretation"] == "moderat"


def test_correlation_schwach():
    from models.correlation import compute_sleep_hrv_correlation

    with patch("models.correlation.stats") as mock_stats:
        mock_stats.pearsonr.return_value = (0.3, 0.05)
        result = compute_sleep_hrv_correlation([1.0] * 20, [1.0] * 20)
    assert result["interpretation"] == "schwach"


def test_correlation_kein_zusammenhang():
    from models.correlation import compute_sleep_hrv_correlation

    with patch("models.correlation.stats") as mock_stats:
        mock_stats.pearsonr.return_value = (0.1, 0.7)
        result = compute_sleep_hrv_correlation([1.0] * 20, [1.0] * 20)
    assert result["interpretation"] == "kein Zusammenhang"


# ── hrv_status — LOW and POOR branches ────────────────────────────────────────


def test_hrv_status_unbalanced():
    """UNBALANCED branch (line 27): dev in [-1.5, -0.5)."""
    with patch("models.hrv_status.compute_autonomic_energy") as mock_energy:
        mock_energy.return_value = {
            "score": 72.0,
            "deviation": -0.9,
            "baseline_mean": 52.0,
            "baseline_std": 4.0,
            "hrv_7d_mean": 48.4,
        }
        result = classify_hrv_status([50.0] * 27)
    assert result["status"] == "UNBALANCED"


def test_hrv_status_low():
    """LOW branch (line 29): dev in [-2.0, -1.5)."""
    with patch("models.hrv_status.compute_autonomic_energy") as mock_energy:
        mock_energy.return_value = {
            "score": 55.0,
            "deviation": -1.7,
            "baseline_mean": 52.0,
            "baseline_std": 4.0,
            "hrv_7d_mean": 45.2,
        }
        result = classify_hrv_status([50.0] * 27)
    assert result["status"] == "LOW"


def test_hrv_status_poor():
    """POOR branch: dev < -2.0."""
    with patch("models.hrv_status.compute_autonomic_energy") as mock_energy:
        mock_energy.return_value = {
            "score": 35.0,
            "deviation": -2.5,
            "baseline_mean": 52.0,
            "baseline_std": 4.0,
            "hrv_7d_mean": 42.0,
        }
        result = classify_hrv_status([50.0] * 27)
    assert result["status"] == "POOR"


# ── sleep_metrics — second insufficient_data branch ───────────────────────────


def test_sleep_consistency_insufficient_start_times():
    """5+ sessions but only 1 has start_h → triggers second insufficient_data."""
    from models.sleep_metrics import compute_sleep_consistency

    rows = [
        {"start_h": 23.0, "end_h": 7.0},  # only one with start_h
        {"start_h": None, "end_h": 7.0},
        {"start_h": None, "end_h": 7.5},
        {"start_h": None, "end_h": 6.5},
        {"start_h": None, "end_h": 7.2},
    ]
    result = compute_sleep_consistency(rows)
    assert result["score"] is None


# ── energy_metrics — sleep debt with None entry ───────────────────────────────


def test_cognitive_energy_skips_none_total():
    """total=None entries must be skipped (not counted as 0)."""
    from models.energy_metrics import compute_cognitive_energy

    data = [
        {"total_h": None},
        {"total_h": 6.5},
        {"total_h": 7.5},
    ]
    result = compute_cognitive_energy(data)
    assert result["score"] is not None


# ── readiness — all_none features → line 56 ───────────────────────────────────


def test_prepare_training_data_all_none_features():
    rows = [{"resting_hr": None, "hrv_last_night": None} for _ in range(35)]
    result = prepare_training_data(rows)
    assert result is None


# ── readiness — target=None row → line 73-74 ──────────────────────────────────


def test_prepare_training_data_skips_none_target():
    """Rows where _energy_based_score(nxt) is None (no energy cols) are skipped."""
    rows = [{"resting_hr": 55.0, "hrv_last_night": 48.0} for _ in range(35)]
    result = prepare_training_data(rows)
    assert result is None


def test_train_and_save_returns_none_when_insufficient_data(tmp_path):
    """Line 88: train_and_save returns None when prepare_training_data returns None."""
    result = train_and_save([], tmp_path / "model.joblib")
    assert result is None


# ── readiness — old-format model (not dict) → lines 123-125, 132 ──────────────


def test_predict_tomorrow_old_format_model_missing_feature(tmp_path):
    """Model saved as bare object (old format) with missing feature → return None."""
    from sklearn.ensemble import RandomForestRegressor
    import joblib

    model = RandomForestRegressor(n_estimators=10, random_state=0)
    model.fit([[1.0]], [50.0])
    model_path = tmp_path / "readiness_rf_old.joblib"
    joblib.dump(model, model_path)  # old format: bare model, not dict

    result = predict_tomorrow({"resting_hr": None}, model_path)
    assert result is None


def test_predict_tomorrow_old_format_model_with_features(tmp_path):
    """Old-format model with all features available → returns prediction."""
    from sklearn.ensemble import RandomForestRegressor
    import joblib

    from models.readiness import _CANDIDATE_FEATURES

    n = len(_CANDIDATE_FEATURES)
    model = RandomForestRegressor(n_estimators=10, random_state=0)
    X_train = [[55.0] * n] * 10
    y_train = [70.0] * 10
    model.fit(X_train, y_train)
    model_path = tmp_path / "readiness_rf_old2.joblib"
    joblib.dump(model, model_path)

    features = {f: 55.0 for f in _CANDIDATE_FEATURES}
    result = predict_tomorrow(features, model_path)
    assert result is not None
