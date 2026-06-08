from typing import Any

_APNEA_MIN_SPO2 = 90  # min_spo2 below this counts as a desaturation night
_APNEA_NIGHT_THRESHOLD = 2  # ≥ this many such nights raises the apnea flag
_TREND_SLOPE_EPS = 0.2  # |slope| below this is "stable"


def _linear_slope(values: list[float], mean: float) -> float:
    """Least-squares slope of values over their index (0..n-1)."""
    n = len(values)
    if n <= 1:
        return 0.0
    x_mean = (n - 1) / 2
    num = sum((i - x_mean) * (v - mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return round(num / den, 3) if den > 0 else 0.0


def _classify_trend(slope: float) -> str:
    if slope < -_TREND_SLOPE_EPS:
        return "falling"
    if slope > _TREND_SLOPE_EPS:
        return "rising"
    return "stable"


def compute_spo2_trend(spo2_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """7-day SpO2 trend + apnea flag (min_spo2 < 90 on ≥2 nights).
    Kapur VK, et al. (2017) J Clin Sleep Med 13(3):479–504.
    """
    avgs = [r["avg_spo2"] for r in spo2_rows if r.get("avg_spo2") is not None]
    mins = [r["min_spo2"] for r in spo2_rows if r.get("min_spo2") is not None]
    if not avgs:
        return {"mean_spo2": None, "reason": "no_spo2_data"}

    mean_spo2 = sum(avgs) / len(avgs)
    slope = _linear_slope(avgs, mean_spo2)
    apnea_nights = sum(1 for m in mins if m < _APNEA_MIN_SPO2)
    return {
        "mean_spo2": round(mean_spo2, 1),
        "min_spo2_7d": round(min(mins), 1) if mins else None,
        "slope": slope,
        "trend": _classify_trend(slope),
        "apnea_flag": apnea_nights >= _APNEA_NIGHT_THRESHOLD,
        "apnea_nights": apnea_nights,
        "n_days": len(avgs),
    }
