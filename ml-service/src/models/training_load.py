from datetime import date, timedelta
from typing import Any


def compute_acwr(atl: float, ctl: float) -> dict[str, Any]:
    """ACWR = ATL(7d) / CTL(42d). Gabbett (2016) BJSM 50(5):273–280."""
    if ctl <= 0:
        return {"acwr": None, "reason": "no_ctl"}
    acwr = atl / ctl
    level = "red" if (acwr > 1.5 or acwr < 0.8) else "amber" if acwr > 1.3 else "green"
    return {
        "acwr": round(acwr, 3),
        "level": level,
        "atl": round(atl, 2),
        "ctl": round(ctl, 2),
    }


def compute_training_monotony(
    activity_rows: list[dict[str, Any]],
    hrmax: float,
    today: date,
    window_days: int = 7,
) -> dict[str, Any]:
    """Foster (1998): Monotony = mean(TRIMP_7d) / σ(TRIMP_7d), Strain = Σ(TRIMP_7d) × Monotony.
    Same TRIMP formula as compute_physical_energy (HRr polynomial).
    """
    by_date = {r["activity_date"]: r for r in activity_rows}
    trimps = []
    for i in range(window_days - 1, -1, -1):
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

    if not any(t > 0 for t in trimps):
        return {"monotony": None, "reason": "no_training_data"}

    mean_t = sum(trimps) / len(trimps)
    variance = sum((t - mean_t) ** 2 for t in trimps) / len(trimps)
    std_t = max(0.01, variance**0.5)
    monotony = round(mean_t / std_t, 2)
    strain = round(sum(trimps) * monotony, 1)
    return {
        "monotony": monotony,
        "strain": strain,
        "trimp_7d_mean": round(mean_t, 1),
        "trimp_7d_std": round(std_t, 2),
        "trimp_values": [round(t, 1) for t in trimps],
    }
