import math
from typing import Any


def compute_sleep_consistency(session_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Phillips et al. (2017) Sci Rep 7:3216: Sleep consistency score.
    100 − (σ_wake×15 + σ_sleep×10), σ in hours.
    σ is a plain (linear) standard deviation of bedtime/wake-time hours;
    it does NOT handle midnight wrap-around (e.g. 23:30 vs 00:30 are treated
    as ~23h apart, not ~1h). Acceptable while sleep/wake times stay on one
    side of midnight; revisit with true circular statistics if that breaks.
    """
    if len(session_rows) < 5:
        return {"score": None, "reason": "insufficient_data"}

    sleeps = [r["start_h"] for r in session_rows if r.get("start_h") is not None]
    wakes = [r["end_h"] for r in session_rows if r.get("end_h") is not None]

    if len(sleeps) < 2 or len(wakes) < 2:
        return {"score": None, "reason": "insufficient_data"}

    def std_hours(hours: list[float]) -> float:
        """Linear std of hour values (no midnight wrap-around handling)."""
        if len(hours) < 2:  # pragma: no cover
            return 0.0
        m = sum(hours) / len(hours)
        return math.sqrt(sum((h - m) ** 2 for h in hours) / len(hours))

    std_sleep = std_hours(sleeps)
    std_wake = std_hours(wakes)
    score = max(0.0, min(100.0, 100.0 - std_wake * 15 - std_sleep * 10))
    return {
        "score": round(score, 1),
        "std_wake_h": round(std_wake, 2),
        "std_sleep_h": round(std_sleep, 2),
        "n_nights": len(sleeps),
    }
