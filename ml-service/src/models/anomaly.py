from typing import Any

import numpy as np

_THRESHOLD = 1.5
_MIN_HISTORY = 7


def detect_resting_hr_anomaly(
    history: list[float | None],
    today: float | None,
) -> dict[str, Any]:
    values = [float(v) for v in history if v is not None]
    if today is None or len(values) < _MIN_HISTORY:
        return {"is_anomaly": False, "z_score": None, "reason": "insufficient_data"}

    mean = float(np.mean(values))
    std = float(np.std(values))
    if std < 1.0:
        return {"is_anomaly": False, "z_score": 0.0, "baseline_mean": round(mean, 1)}

    z = (float(today) - mean) / std
    return {
        "is_anomaly": z > _THRESHOLD,
        "z_score": round(z, 2),
        "threshold": _THRESHOLD,
        "baseline_mean": round(mean, 1),
        "baseline_std": round(std, 1),
    }
