import math
from typing import Any


def _std_hours_circular(hours: list[float]) -> float:
    """Circular standard deviation for hour values in [0, 24).

    Maps hours onto the unit circle so that e.g. 23:30 and 00:30 are 1 h
    apart instead of 23 h apart (Mardia & Jupp 2000, directional statistics).
    R = mean resultant length (0 = maximally dispersed, 1 = perfectly constant).
    """
    if len(hours) < 2:
        return 0.0
    angles = [h / 24.0 * 2 * math.pi for h in hours]
    sin_mean = sum(math.sin(a) for a in angles) / len(angles)
    cos_mean = sum(math.cos(a) for a in angles) / len(angles)
    R = math.sqrt(sin_mean**2 + cos_mean**2)
    if R >= 1.0:
        return 0.0
    return math.sqrt(-2 * math.log(R)) / (2 * math.pi) * 24


def compute_sleep_consistency(session_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Phillips et al. (2017) Sci Rep 7:3216: Sleep consistency score.
    100 − (σ_wake×15 + σ_sleep×10), σ in hours (circular statistics).
    """
    if len(session_rows) < 5:
        return {"score": None, "reason": "insufficient_data"}

    sleeps = [r["start_h"] for r in session_rows if r.get("start_h") is not None]
    wakes = [r["end_h"] for r in session_rows if r.get("end_h") is not None]

    if len(sleeps) < 2 or len(wakes) < 2:
        return {"score": None, "reason": "insufficient_data"}

    std_sleep = _std_hours_circular(sleeps)
    std_wake = _std_hours_circular(wakes)
    score = max(0.0, min(100.0, 100.0 - std_wake * 15 - std_sleep * 10))
    return {
        "score": round(score, 1),
        "std_wake_h": round(std_wake, 2),
        "std_sleep_h": round(std_sleep, 2),
        "n_nights": len(sleeps),
    }
