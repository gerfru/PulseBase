from __future__ import annotations

from typing import Any


def compute_custom_sleep_score(sleep_row: dict[str, Any]) -> dict[str, Any]:
    # deep × 35% + rem × 25% + duration × 25% + wake_penalty × 15%
    # Weightings from Walker "Why We Sleep" (2017) + NSF phase recommendations
    total_s = sleep_row.get("total_sleep_seconds")
    if not total_s or total_s == 0:
        return {"score": None, "reason": "no_sleep_data"}

    total_h = total_s / 3600.0
    deep_s = sleep_row.get("deep_sleep_seconds")
    rem_s = sleep_row.get("rem_sleep_seconds")
    awake_s = sleep_row.get("awake_seconds")

    duration_score = min(100.0, total_h / 8.0 * 100.0)
    parts: list[tuple[float, float]] = [(duration_score, 0.25)]

    if deep_s is not None:
        deep_pct = deep_s / total_s
        parts.append((min(100.0, deep_pct / 0.20 * 100.0), 0.35))

    if rem_s is not None:
        rem_pct = rem_s / total_s
        parts.append((min(100.0, rem_pct / 0.22 * 100.0), 0.25))

    if awake_s is not None:
        wake_pct = awake_s / total_s
        wake_penalty = max(0.0, 100.0 - wake_pct * 500.0)
        parts.append((wake_penalty, 0.15))

    total_w = sum(w for _, w in parts)
    score = sum(s * w for s, w in parts) / total_w

    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "total_h": round(total_h, 2),
        "deep_pct": round(deep_s / total_s * 100, 1) if deep_s is not None else None,
        "rem_pct": round(rem_s / total_s * 100, 1) if rem_s is not None else None,
        "wake_pct": round(awake_s / total_s * 100, 1) if awake_s is not None else None,
    }
