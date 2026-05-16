from __future__ import annotations

from typing import Any


def compute_intensity_minutes(
    hr_records: list[int],
    resting_hr: float,
    hrmax: float,
) -> dict[str, Any]:
    # Karvonen HRR classification: moderate 50–70%, vigorous ≥70%
    # Karvonen (1957); validated for exercise intensity by ACSM guidelines
    denom = hrmax - resting_hr
    if denom <= 0 or not hr_records:
        return {"score": None, "reason": "insufficient_data"}

    moderate_sec = 0
    vigorous_sec = 0

    for hr in hr_records:
        hrr = (hr - resting_hr) / denom
        if hrr >= 0.70:
            vigorous_sec += 1
        elif hrr >= 0.50:
            moderate_sec += 1

    moderate_min = moderate_sec // 60
    vigorous_min = vigorous_sec // 60

    # WHO weekly targets: 150–300 min moderate OR 75–150 min vigorous (vigorous counts ×2)
    # Score per session, normalized against 30 min vigorous (≈ one strong workout)
    weekly_equivalent = moderate_min + vigorous_min * 2
    score = min(100.0, weekly_equivalent / 30.0 * 100.0)

    return {
        "score": round(score, 1),
        "moderate_minutes": moderate_min,
        "vigorous_minutes": vigorous_min,
        "hrmax_used": round(hrmax, 1),
        "resting_hr_used": round(resting_hr, 1),
    }
