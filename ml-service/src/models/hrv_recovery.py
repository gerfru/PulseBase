from datetime import date, timedelta
from typing import Any


def compute_hrv_recovery_trajectory(
    hrv_history: list[float | None],
    act_rows: list[dict[str, Any]],
    hrmax: float,
    today: date,
    lookback: int = 60,
) -> dict[str, Any]:
    """Recovery speed: Δ HRV/day after training load (Plews et al. 2013, Stanley et al. 2015).

    Detects TRIMP peaks (>1.5× mean) and measures HRV recovery slope in following 7 days.
    """
    by_date = {r["activity_date"]: r for r in act_rows}
    trimps = []
    hrv_vals = []

    for i in range(lookback - 1, -1, -1):
        d = today - timedelta(days=i)
        row = by_date.get(d)
        trimp = 0.0

        if row and row.get("avg_hr") and row.get("duration_seconds"):
            rhr = row.get("resting_hr") or 60.0
            denom = hrmax - rhr
            if denom > 0:
                hfr = max(0.0, (row["avg_hr"] - rhr) / denom)
                trimp = (row["duration_seconds"] / 60.0) * hfr * (hfr * 4 + 1)

        trimps.append(trimp)

    hrv_slice = hrv_history[-(lookback):]
    hrv_vals = [v for v in hrv_slice]

    valid_hrv = [v for v in hrv_vals if v is not None]
    if len(valid_hrv) < 14:
        return {"score": None, "reason": "insufficient_hrv_data"}

    baseline = sum(valid_hrv) / len(valid_hrv)

    trimp_mean = sum(trimps) / len(trimps) if trimps else 0.0
    trimp_threshold = trimp_mean * 1.5 if trimp_mean > 0 else 1e9

    recovery_slopes = []
    i = 0
    while i < len(trimps) - 5:
        if trimps[i] >= trimp_threshold:
            window = hrv_vals[i + 1 : i + 8]
            valid_w = [(j, v) for j, v in enumerate(window) if v is not None]
            if len(valid_w) >= 3:
                slope = sum((v - baseline) for _, v in valid_w) / len(valid_w)
                recovery_slopes.append(slope)
            i += 7
        else:
            i += 1

    if not recovery_slopes:
        return {"score": None, "reason": "no_recovery_events"}

    recovery_speed = sum(recovery_slopes) / len(recovery_slopes)

    return {
        "recovery_speed": round(recovery_speed, 2),
        "n_events": len(recovery_slopes),
        "hrv_baseline": round(baseline, 1),
        "trimp_threshold": round(trimp_threshold, 1),
    }
