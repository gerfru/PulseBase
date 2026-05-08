from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np
from sklearn.ensemble import RandomForestRegressor  # type: ignore[import-untyped]

_MIN_TRAINING_ROWS = 30
_HRV_MAP = {"BALANCED": 100, "UNBALANCED": 50, "LOW": 25, "POOR": 0}
_CANDIDATE_FEATURES = [
    "hrv_last_night",
    "sleep_score",
    "resting_hr",
    "aerobic_effect_daily",
    "anaerobic_effect_daily",
]


def _rule_based_score(row: dict[str, Any]) -> float | None:
    components: list[tuple[float, float]] = []
    status = (row.get("hrv_status") or "").upper()
    if status in _HRV_MAP:
        components.append((_HRV_MAP[status], 0.30))
    if row.get("sleep_score") is not None:
        components.append((float(row["sleep_score"]), 0.30))
    if row.get("body_battery_high") is not None:
        components.append((float(row["body_battery_high"]), 0.20))
    if row.get("avg_stress") is not None:
        components.append((max(0.0, 100.0 - float(row["avg_stress"])), 0.20))
    if not components:
        return None
    total_w = sum(w for _, w in components)
    return sum(v * w for v, w in components) / total_w


def _median(vals: Any) -> float | None:
    v = [float(x) for x in vals if x is not None]
    if not v:
        return None
    v.sort()
    return v[len(v) // 2]


def prepare_training_data(
    rows: list[dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray, list[str]] | None:
    """Build (X, y, feature_names) where X=features on day N, y=readiness on day N+1.

    Features with no data at all (median=None) are excluded so the model can train
    with whatever subset is actually available (e.g. sleep+resting_hr without HRV).
    Remaining missing values are imputed with the per-feature median.
    """
    medians = {f: _median(r.get(f) for r in rows) for f in _CANDIDATE_FEATURES}
    active = [f for f in _CANDIDATE_FEATURES if medians[f] is not None]
    if not active:
        return None

    X_rows, y_vals = [], []
    for i in range(len(rows) - 1):
        cur, nxt = rows[i], rows[i + 1]
        feat_vals = []
        skip = False
        for f in active:
            v = cur.get(f)
            v = v if v is not None else medians[f]
            if v is None:
                skip = True
                break
            feat_vals.append(float(v))
        if skip:
            continue
        target = _rule_based_score(nxt)
        if target is None:
            continue
        X_rows.append(feat_vals)
        y_vals.append(float(target))

    if len(X_rows) < _MIN_TRAINING_ROWS:
        return None
    return np.array(X_rows), np.array(y_vals), active


def train_and_save(
    rows: list[dict[str, Any]], model_path: Path
) -> dict[str, Any] | None:
    result = prepare_training_data(rows)
    if result is None:
        return None
    X, y, feature_names = result
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": feature_names}, model_path)
    importances = {
        f: round(float(v), 4) for f, v in zip(feature_names, model.feature_importances_)
    }
    return {"features": feature_names, "importances": importances, "n_rows": len(X)}


def predict_tomorrow(
    features: dict[str, Any], model_path: Path
) -> dict[str, Any] | None:
    if not model_path.exists():
        return None
    saved = joblib.load(model_path)
    if isinstance(saved, dict):
        model = saved["model"]
        feature_names: list[str] = saved["features"]
    else:
        model = saved
        feature_names = list(_CANDIDATE_FEATURES)
    vals = []
    for f in feature_names:
        v = features.get(f)
        if v is None:
            return None
        vals.append(float(v))
    X = np.array([vals])
    tree_preds = np.array([t.predict(X)[0] for t in model.estimators_])

    def _clamp(v: float) -> float:
        return round(min(100.0, max(0.0, v)), 1)

    return {
        "score": _clamp(float(np.mean(tree_preds))),
        "confidence_low": _clamp(float(np.percentile(tree_preds, 10))),
        "confidence_high": _clamp(float(np.percentile(tree_preds, 90))),
    }
