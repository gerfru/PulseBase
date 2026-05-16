from typing import Any


def compute_running_economy(activities: list[dict[str, Any]]) -> dict[str, Any]:
    """Running economy from ground contact time, vertical oscillation, vertical ratio.

    Optimums from Moore (2016), Cavanagh (1985), Fletcher (2009).
    GCT 200ms, VO 60mm, VR 6% ideal. Scoring heuristically calibrated.
    Running/trail running only.
    """
    valid = [a for a in activities if a.get("avg_ground_contact_time") is not None]

    if not valid:
        return {"score": None, "reason": "no_biomechanics_data"}

    recent = valid[:5]
    avg_gct = sum(a["avg_ground_contact_time"] for a in recent) / len(recent)
    avg_vo = sum(a.get("avg_vertical_oscillation") or 80 for a in recent) / len(recent)
    avg_vr = sum(a.get("avg_vertical_ratio") or 9 for a in recent) / len(recent)

    gct_score = max(0.0, min(100.0, 100.0 - (avg_gct - 200.0) * 0.5))
    vo_score = max(0.0, min(100.0, 100.0 - (avg_vo - 60.0) * 2.5))
    vr_score = max(0.0, min(100.0, 100.0 - (avg_vr - 6.0) * 8.0))

    score = gct_score * 0.4 + vo_score * 0.35 + vr_score * 0.25

    return {
        "score": round(score, 1),
        "gct_score": round(gct_score, 1),
        "vo_score": round(vo_score, 1),
        "vr_score": round(vr_score, 1),
        "avg_gct_ms": round(avg_gct),
        "avg_vo_mm": round(avg_vo, 1),
        "avg_vr_pct": round(avg_vr, 1),
        "n_activities": len(recent),
    }
