from typing import Any


def _sleep_quality(
    total_h: float,
    deep_h: float | None,
    rem_h: float | None,
) -> float:
    """Sleep quality factor 0–1 from phase architecture + duration.

    Targets based on Walker (2017) and Dijk & Czeisler (1995):
      - Deep sleep (SWS): ~20% of total → tissue repair, GH release
      - REM sleep:        ~25% of total → cognitive restoration

    Weights: phase quality 60%, duration 40%.
    Falls back to duration-only when phase data is unavailable.
    """
    if not total_h or total_h < 0.5:
        return 0.2  # essentially no sleep

    # Duration component (40%) — 7.5h as full-recovery target
    duration = min(1.0, total_h / 7.5)

    # Phase quality component (60%)
    if deep_h is not None and rem_h is not None and total_h > 0:
        deep_ratio = deep_h / total_h
        rem_ratio = rem_h / total_h
        deep_score = min(1.0, deep_ratio / 0.20)
        rem_score = min(1.0, rem_ratio / 0.25)
        quality = 0.55 * deep_score + 0.45 * rem_score
    elif deep_h is not None and total_h > 0:
        quality = min(1.0, (deep_h / total_h) / 0.20)
    else:
        quality = duration  # no phase data → fall back to duration only

    return round(0.40 * duration + 0.60 * quality, 3)


def compute_body_battery(
    yesterday_score: float | None,
    sleep_hours: float,
    deep_sleep_hours: float | None,
    rem_sleep_hours: float | None,
    hrv_last_night: float | None,
    hrv_baseline: float,
    today_trimp: float,
    avg_stress: float | None,
) -> dict[str, Any]:
    """Fresh-state energy model: sleep quality + HRV + activity drain.

    Computes today's energy as a fresh physiological snapshot (70% weight)
    blended with yesterday's score as inertia (30% weight).  This avoids the
    accumulation-plateau artefact of pure budget models while preserving
    multi-day trend continuity.

    Validated inputs:
      - HRV factor: Plews et al. (2013) — last-night HRV vs 30-day baseline
      - Sleep quality: deep sleep + REM phases as primary signal,
        duration as secondary (Walker 2017, Dijk & Czeisler 1995)
      - Activity drain: TRIMP-based (Banister-inspired, independent component)
      - Stress drain: parasympathetic suppression proxy (Kellmann 2001)

    No claim is made that the composite formula is validated against clinical
    outcomes — no manufacturer discloses such a formula (Wearable Composite
    Health Scores Require Validation, 2025).
    """
    prev = yesterday_score if yesterday_score is not None else 72.0

    # Sleep quality: phases (60%) + duration (40%)
    sleep_quality = _sleep_quality(sleep_hours, deep_sleep_hours, rem_sleep_hours)

    # HRV recovery indicator: last night vs personal 30-day baseline
    hrv_factor = (
        min(1.0, hrv_last_night / hrv_baseline)
        if hrv_baseline > 0 and hrv_last_night
        else 0.5
    )

    # Fresh daily score from today's physiology
    # At perfect conditions: 40 + 35 + 25 = 100
    fresh = 40.0 + sleep_quality * 35.0 + hrv_factor * 25.0

    # Activity drain: TRIMP-based fatigue (capped at 40)
    activity_drain = round(min(40.0, today_trimp * 0.5), 1)

    # Stress drain: sympathetic activation above resting baseline
    stress_level = avg_stress or 25.0
    stress_drain = round(max(0.0, (stress_level - 25.0) * 0.2), 1)

    # Fresh state 70% + inertia 30% — no accumulation plateau
    score = max(
        5.0, min(100.0, 0.30 * prev + 0.70 * fresh - activity_drain - stress_drain)
    )

    return {
        "score": round(score),
        "sleep_quality": round(sleep_quality, 2),
        "hrv_factor": round(hrv_factor, 2),
        "activity_drain": activity_drain,
        "stress_drain": stress_drain,
        "sleep_h": round(sleep_hours, 1),
        "deep_h": round(deep_sleep_hours, 1) if deep_sleep_hours is not None else None,
        "rem_h": round(rem_sleep_hours, 1) if rem_sleep_hours is not None else None,
        "prev_score": round(prev, 1),
    }
