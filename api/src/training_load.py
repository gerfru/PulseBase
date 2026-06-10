from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

_ATL_TAU = 7.0
_CTL_TAU = 42.0
_K_ATL = math.exp(-1.0 / _ATL_TAU)
_K_CTL = math.exp(-1.0 / _CTL_TAU)
_ALPHA_ATL = 1.0 - _K_ATL  # EWM weight for new TRIMP (ATL)
_ALPHA_CTL = 1.0 - _K_CTL  # EWM weight for new TRIMP (CTL)

# Enough history so CTL (τ=42d) is ≥95% converged at display start
_WARMUP_DAYS = 180


def _trimp(
    duration_seconds: float, avg_hr: float, resting_hr: float, hrmax: float, sex: str
) -> float:
    if hrmax <= resting_hr or avg_hr <= resting_hr:
        return 0.0
    hrr = max(0.0, min(1.0, (avg_hr - resting_hr) / (hrmax - resting_hr)))
    b = 1.67 if sex == "female" else 1.92  # Edwards 1993 sex-specific TRIMP exponents
    return (duration_seconds / 60.0) * hrr * math.exp(b * hrr)


def build_training_load(
    activity_rows: list[dict[str, Any]],
    hrmax: float,
    sex: str,
    lookback_days: int,
    forecast_days: int,
) -> dict[str, Any]:
    """Compute Banister training load (ATL/CTL/TSB) from activity history.

    Uses exponentially weighted TRIMP (Edwards 1993, τ_ATL=7d, τ_CTL=42d). Warms up
    over 180 days so CTL is ≥95% converged at the display start. Returns history,
    zero-load forecast, and today's ATL/CTL/TSB snapshot.
    """
    today = date.today()
    warmup_start = today - timedelta(days=_WARMUP_DAYS)

    trimp_by_day: dict[date, float] = {}
    for row in activity_rows:
        d: date = row["activity_date"]
        if d < warmup_start:
            continue
        rhr = float(row.get("resting_hr") or 55.0)
        t = _trimp(
            float(row.get("duration_seconds") or 0),
            float(row.get("avg_hr") or 0),
            rhr,
            hrmax,
            sex,
        )
        trimp_by_day[d] = trimp_by_day.get(d, 0.0) + t

    atl = 0.0
    ctl = 0.0
    display_from = today - timedelta(days=lookback_days - 1)

    d = warmup_start
    history: list[dict[str, Any]] = []
    while d <= today:
        t = trimp_by_day.get(d, 0.0)
        atl = atl * _K_ATL + t * _ALPHA_ATL
        ctl = ctl * _K_CTL + t * _ALPHA_CTL
        if d >= display_from:
            history.append(
                {
                    "date": d.isoformat(),
                    "trimp": round(t, 1),
                    "atl": round(atl, 1),
                    "ctl": round(ctl, 1),
                    "tsb": round(ctl - atl, 1),
                }
            )
        d += timedelta(days=1)

    forecast: list[dict[str, Any]] = []
    for i in range(1, forecast_days + 1):
        atl *= _K_ATL
        ctl *= _K_CTL
        forecast.append(
            {
                "date": (today + timedelta(days=i)).isoformat(),
                "trimp": 0.0,
                "atl": round(atl, 1),
                "ctl": round(ctl, 1),
                "tsb": round(ctl - atl, 1),
                "forecast": True,
            }
        )

    today_snap = history[-1] if history else {}
    return {
        "history": history,
        "forecast": forecast,
        "today": {
            "atl": today_snap.get("atl"),
            "ctl": today_snap.get("ctl"),
            "tsb": today_snap.get("tsb"),
        },
    }
