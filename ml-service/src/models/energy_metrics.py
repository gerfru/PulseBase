from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

# Edwards TRIMP EWM-Konstanten: Banister & Calvert (1991), popularisiert via TrainingPeaks
# ATL τ=7d (kurzfristige Ermüdung), CTL τ=42d (langfristige Fitness)
_EWM_TAU7 = math.exp(-1 / 7)
_ALPHA7 = 1 - _EWM_TAU7
_EWM_TAU42 = math.exp(-1 / 42)
_ALPHA42 = 1 - _EWM_TAU42


def _clip(v: float) -> float:
    return max(0.0, min(100.0, v))


def compute_physical_energy(
    activity_rows: list[dict[str, Any]],
    hrmax: float,
    today: date,
    window_days: int = 50,
) -> dict[str, Any]:
    # Algorithmus: Edwards TRIMP (Sally Edwards, 1993) + Banister Fitness-Fatigue-Modell (1991)
    # Quelle: https://www.trainingimpulse.com/edwards-trimp
    # HRr (Heart Rate Reserve Fraction) statt absoluter HR-Zonen — physiologisch präziser
    # TSB = CTL − ATL: positiv = erholt (Konto im Plus), negativ = ermüdet
    # Score-Formel: 50 + TSB × 1.5 → 50 bei Gleichgewicht, 0–100 bei ±33 TSB
    if not activity_rows:
        return {"score": None, "reason": "no_activity_data"}

    by_date = {r["activity_date"]: r for r in activity_rows}
    atl = ctl = 0.0

    for i in range(window_days, -1, -1):
        d = today - timedelta(days=i)
        row = by_date.get(d)
        trimp = 0.0
        if row and row.get("avg_hr") and row.get("duration_seconds"):
            rhr = row.get("resting_hr") or 60.0
            denom = hrmax - rhr
            if denom > 0:
                hfr = max(0.0, (row["avg_hr"] - rhr) / denom)
                trimp = (row["duration_seconds"] / 60.0) * hfr * (hfr * 4 + 1)
        atl = atl * _EWM_TAU7 + trimp * _ALPHA7
        ctl = ctl * _EWM_TAU42 + trimp * _ALPHA42

    tsb = ctl - atl
    return {
        "score": round(_clip(50 + tsb * 1.5), 1),
        "atl": round(atl, 2),
        "ctl": round(ctl, 2),
        "tsb": round(tsb, 2),
        "hrmax": round(hrmax, 1),
    }


def compute_autonomic_energy(
    hrv_history: list[float | None],
) -> dict[str, Any]:
    # Algorithmus: Ithlete / Elite HRV Score — ln(RMSSD) × 20 Normierung
    # Quelle: https://help.elitehrv.com/article/57-the-1-10-relative-balance-score
    # Begründung log: RMSSD ist rechtsschief verteilt → log-Transformation normalisiert
    # Individuelle σ-Baseline statt Absolutwert (Marco Altini, HRV4Training)
    # hrv_history muss ORDER BY date ASC kommen; letzter Wert = heute
    raw = [math.log(v) * 20 for v in hrv_history if v is not None and v > 0]
    if len(raw) < 7:
        return {"score": None, "reason": "insufficient_hrv_data"}

    today_raw = raw[-1]
    baseline = raw[:-1]
    n = len(baseline)
    mean = sum(baseline) / n
    std = max(1.0, math.sqrt(sum((x - mean) ** 2 for x in baseline) / n))
    dev = (today_raw - mean) / std

    return {
        "score": round(_clip(50 + dev * 15), 1),
        "deviation": round(dev, 2),
        "baseline_mean": round(mean, 2),
        "baseline_std": round(std, 2),
        "hrv_raw_today": round(today_raw, 2),
    }


def compute_cognitive_energy(
    sleep_data_7d: list[dict[str, float | None]],
) -> dict[str, Any]:
    # Algorithmus: Borbély Two-Process Model (Process S — homöostatischer Schlafdruck)
    # Quelle: Borbély AA (1982) A two process model of sleep regulation. Hum Neurobiol 1(3):195-204
    # Qualitätsfaktor entfernt: Garmins Tiefschlaf-Messung (Akzelerometer+HRV) zu unzuverlässig
    # Ziel 7h: NSF-Empfehlung 7–9h, 7h als untere Grenze für Erwachsene (vorher 8h)
    debt = 0.0
    days_used = 0
    for d in sleep_data_7d:
        total = d.get("total_h")
        if total is None:
            continue
        days_used += 1
        debt += max(0.0, 7.0 - total)

    if days_used == 0:
        return {"score": None, "reason": "no_sleep_data"}

    return {
        "score": round(_clip(100 - debt * 6), 1),
        "debt_hours": round(debt, 2),
        "days_used": days_used,
    }
