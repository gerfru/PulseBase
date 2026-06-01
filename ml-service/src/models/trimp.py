from typing import Any

_DEFAULT_RHR = 60.0


def compute_trimp(
    row: dict[str, Any], hrmax: float, default_rhr: float = _DEFAULT_RHR
) -> float:
    """Edwards TRIMP (1993): duration_min × HRr × (HRr × 4 + 1).

    HRr = (avg_HR − resting_HR) / (HRmax − resting_HR)
    The quadratic term weights high-intensity efforts more than a linear zone model.
    Returns 0.0 when required fields are absent or the denominator is non-positive.
    """
    if not row.get("avg_hr") or not row.get("duration_seconds"):
        return 0.0
    rhr = row.get("resting_hr") or default_rhr
    denom = hrmax - rhr
    if denom <= 0:
        return 0.0
    hfr = max(0.0, (row["avg_hr"] - rhr) / denom)
    return (row["duration_seconds"] / 60.0) * hfr * (hfr * 4 + 1)
