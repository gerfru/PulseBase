from __future__ import annotations

from typing import Any

from models.energy_metrics import compute_autonomic_energy


def classify_hrv_status(hrv_history: list[float | None]) -> dict[str, Any]:
    # Reuses compute_autonomic_energy log-baseline; maps σ-deviation to 4 status labels.
    # BALANCED: deviation ≥ −0.5 (within 0.5 σ below personal mean)
    # UNBALANCED: −1.5 ≤ deviation < −0.5
    # LOW: −2.0 ≤ deviation < −1.5
    # POOR: deviation < −2.0 (sustained suppression)
    result = compute_autonomic_energy(hrv_history)
    if result.get("score") is None:
        return {
            "status": None,
            "score": None,
            "reason": result.get("reason", "insufficient_hrv_data"),
        }

    dev = result["deviation"]

    if dev >= -0.5:
        status = "BALANCED"
    elif dev >= -1.5:
        status = "UNBALANCED"
    elif dev >= -2.0:
        status = "LOW"
    else:
        status = "POOR"

    return {
        "status": status,
        "score": result["score"],
        "deviation": result["deviation"],
        "baseline_mean": result["baseline_mean"],
        "baseline_std": result["baseline_std"],
        "hrv_7d_mean": result["hrv_7d_mean"],
    }
