import math
from typing import Any


def compute_stress_score(
    hrv_history: list[float | None],
    avg_stress: float | None,
) -> dict[str, Any]:
    """HRV-baseline deviation + Garmin avg_stress (60/40 blend).

    Uses log(HRV) z-score methodology (Task Force ESC/NASPE 1996, Shaffer 2017).
    High HRV → low stress. Blending weight heuristically calibrated.
    """
    valid = [x for x in hrv_history if x is not None]

    if len(valid) < 7:
        return {"score": None, "reason": "insufficient_hrv_data"}

    log_vals = [math.log(v) for v in valid]
    mu = sum(log_vals) / len(log_vals)
    sigma = max(0.01, math.sqrt(sum((x - mu) ** 2 for x in log_vals) / len(log_vals)))

    deviation = (math.log(valid[-1]) - mu) / sigma
    hrv_stress = max(0.0, min(100.0, 50.0 - deviation * 20.0))

    if avg_stress is not None:
        score = hrv_stress * 0.6 + avg_stress * 0.4
    else:
        score = hrv_stress

    return {
        "score": round(score, 1),
        "hrv_component": round(hrv_stress, 1),
        "garmin_stress": avg_stress,
        "hrv_deviation": round(deviation, 2),
        "n_hrv": len(valid),
    }
