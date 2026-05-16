from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

# Banister TRIMP sex-specific coefficients (Banister 1991, Morton 1990)
_K = {"m": 0.64, "f": 0.86}
_B = {"m": 1.92, "f": 1.67}

_EWM_TAU7 = math.exp(-1 / 7)
_ALPHA7 = 1 - _EWM_TAU7
_EWM_TAU42 = math.exp(-1 / 42)
_ALPHA42 = 1 - _EWM_TAU42


def compute_banister_trimp(
    activity_rows: list[dict[str, Any]],
    sex: str,
    hrmax: float,
    window_days: int = 50,
) -> dict[str, Any]:
    # Same EWM structure as compute_physical_energy but uses Banister formula
    # instead of Edwards — accounts for exponential HR-intensity relationship
    b = _B.get(sex, _B["m"])
    today = date.today()
    by_date = {r["activity_date"]: r for r in activity_rows}
    atl = ctl = trimp_today = 0.0

    for i in range(window_days, -1, -1):
        d = today - timedelta(days=i)
        row = by_date.get(d)
        trimp = 0.0
        if row and row.get("avg_hr") and row.get("duration_seconds"):
            rhr = row.get("resting_hr") or 60.0
            denom = hrmax - rhr
            if denom > 0:
                hrr = max(0.0, (row["avg_hr"] - rhr) / denom)
                trimp = (row["duration_seconds"] / 60.0) * hrr * math.exp(b * hrr)
                if i == 0:
                    trimp_today = trimp
        atl = atl * _EWM_TAU7 + trimp * _ALPHA7
        ctl = ctl * _EWM_TAU42 + trimp * _ALPHA42

    return {
        "atl": round(atl, 2),
        "ctl": round(ctl, 2),
        "tsb": round(ctl - atl, 2),
        "trimp_today": round(trimp_today, 2),
        "sex": sex,
        "b_coeff": b,
    }


def compute_training_effect_today(
    trimp_today: float,
    ctl: float,
    resting_hr: float,
    hrmax: float,
) -> dict[str, Any]:
    # Training effect 0–5 via atan scaled against personal CTL baseline
    # VO2max estimate: Uth et al. (2004) VO2max = 15 × (HRmax / HRrest)
    ctl_ref = max(ctl, 10.0)
    effect = math.atan(trimp_today / (ctl_ref * 0.5)) * (10.0 / math.pi)
    effect = max(0.0, min(5.0, effect))

    vo2max = round(15.0 * hrmax / resting_hr, 1) if resting_hr > 0 else None

    return {
        "score": round(effect * 20.0, 1),
        "effect": round(effect, 2),
        "trimp_today": round(trimp_today, 2),
        "ctl": round(ctl, 2),
        "vo2max": vo2max,
    }
