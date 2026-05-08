from typing import Any

from scipy import stats  # type: ignore[import-untyped]

_MIN_SAMPLES = 10


def compute_sleep_hrv_correlation(
    sleep_scores: list[float],
    next_day_hrv: list[float],
) -> dict[str, Any]:
    n = len(sleep_scores)
    if n < _MIN_SAMPLES or n != len(next_day_hrv):
        return {
            "r": None,
            "p_value": None,
            "interpretation": "insufficient_data",
            "n": n,
        }

    r, p_value = stats.pearsonr(sleep_scores, next_day_hrv)
    r = round(float(r), 3)
    p_value = round(float(p_value), 4)

    abs_r = abs(r)
    if abs_r >= 0.7:
        interpretation = "stark"
    elif abs_r >= 0.4:
        interpretation = "moderat"
    elif abs_r >= 0.2:
        interpretation = "schwach"
    else:
        interpretation = "kein Zusammenhang"

    return {"r": r, "p_value": p_value, "interpretation": interpretation, "n": n}
