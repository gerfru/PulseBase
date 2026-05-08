from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np
from sklearn.ensemble import RandomForestRegressor  # type: ignore[import-untyped]

_MIN_TRAINING_ROWS = 30
_HRV_MAP = {"BALANCED": 100, "UNBALANCED": 50, "LOW": 25, "POOR": 0}


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
) -> tuple[np.ndarray, np.ndarray] | None:
    """Build (X, y) where X=features on day N, y=readiness on day N+1.

    Missing feature values are imputed with the per-feature median so that rows
    where only HRV (or only sleep) is missing still contribute training signal.
    """
    hrv_med = _median(r.get("hrv_last_night") for r in rows)
    sleep_med = _median(r.get("sleep_score") for r in rows)
    hr_med = _median(r.get("resting_hr") for r in rows)

    X_rows, y_vals = [], []
    for i in range(len(rows) - 1):
        cur, nxt = rows[i], rows[i + 1]
        hrv = (
            cur.get("hrv_last_night")
            if cur.get("hrv_last_night") is not None
            else hrv_med
        )
        sleep = (
            cur.get("sleep_score") if cur.get("sleep_score") is not None else sleep_med
        )
        hr = cur.get("resting_hr") if cur.get("resting_hr") is not None else hr_med
        if hrv is None or sleep is None or hr is None:
            continue
        target = _rule_based_score(nxt)
        if target is None:
            continue
        X_rows.append([float(hrv), float(sleep), float(hr)])
        y_vals.append(float(target))

    if len(X_rows) < _MIN_TRAINING_ROWS:
        return None
    return np.array(X_rows), np.array(y_vals)


def train_and_save(rows: list[dict[str, Any]], model_path: Path) -> bool:
    result = prepare_training_data(rows)
    if result is None:
        return False
    X, y = result
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    return True


def predict_tomorrow(features: dict[str, Any], model_path: Path) -> float | None:
    if not model_path.exists():
        return None
    hrv = features.get("hrv_last_night")
    sleep = features.get("sleep_score")
    hr = features.get("resting_hr")
    if hrv is None or sleep is None or hr is None:
        return None
    model = joblib.load(model_path)
    X = np.array([[float(hrv), float(sleep), float(hr)]])
    score = float(model.predict(X)[0])
    return round(min(100.0, max(0.0, score)), 1)
