from typing import Any


def compute_body_battery(
    yesterday_score: float | None,
    sleep_hours: float,
    hrv_last_night: float | None,
    hrv_baseline: float,
    today_trimp: float,
    avg_stress: float | None,
) -> dict[str, Any]:
    """Energy budget model: Recovery − Activity Drain − Stress Drain.

    Concepts from Banister (1991) Impulse-Response and Kellmann (2001) Recovery.
    Parameters heuristically calibrated.
    """
    prev = yesterday_score if yesterday_score is not None else 75.0

    sleep_factor = min(1.0, sleep_hours / 7.0)
    hrv_factor = (
        min(1.0, hrv_last_night / hrv_baseline)
        if hrv_baseline > 0 and hrv_last_night
        else 0.5
    )
    recovery = round(30.0 * sleep_factor * hrv_factor, 1)

    activity_drain = round(min(40.0, today_trimp * 0.5), 1)

    stress_level = avg_stress or 25.0
    stress_drain = round(max(0.0, (stress_level - 25.0) * 0.2), 1)

    score = max(5.0, min(100.0, prev + recovery - activity_drain - stress_drain))

    return {
        "score": round(score),
        "recovery": recovery,
        "activity_drain": activity_drain,
        "stress_drain": stress_drain,
        "sleep_h": round(sleep_hours, 1),
        "prev_score": prev,
    }
