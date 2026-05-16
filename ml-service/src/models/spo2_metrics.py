from typing import Any


def compute_spo2_trend(spo2_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """7-day SpO2 trend + apnea flag (min_spo2 < 90 on ≥2 nights).
    Kapur VK, et al. (2017) J Clin Sleep Med 13(3):479–504.
    """
    avgs = [r["avg_spo2"] for r in spo2_rows if r.get("avg_spo2") is not None]
    mins = [r["min_spo2"] for r in spo2_rows if r.get("min_spo2") is not None]
    if not avgs:
        return {"mean_spo2": None, "reason": "no_spo2_data"}

    mean_spo2 = sum(avgs) / len(avgs)
    # Linear slope: positive = rising, negative = falling
    n = len(avgs)
    slope = 0.0
    if n > 1:
        x_mean = (n - 1) / 2
        num = sum((i - x_mean) * (v - mean_spo2) for i, v in enumerate(avgs))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = round(num / den, 3) if den > 0 else 0.0

    apnea_nights = sum(1 for m in mins if m < 90)
    return {
        "mean_spo2": round(mean_spo2, 1),
        "min_spo2_7d": round(min(mins), 1) if mins else None,
        "slope": slope,
        "trend": "falling" if slope < -0.2 else "rising" if slope > 0.2 else "stable",
        "apnea_flag": apnea_nights >= 2,
        "apnea_nights": apnea_nights,
        "n_days": len(avgs),
    }
