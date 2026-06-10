from typing import Any

from src.db.health import get_energy_metrics


async def compute_readiness(user_id: int) -> dict[str, Any]:
    """Erholungs-Score (0–100) aus autonomer + kognitiver Energie — ohne TSB.

    Gewichtung: Autonom (HRV-Baseline) 60 % + Kognitiv (Schlafschuld) 40 %.
    TSB (physische Trainingsbelastung) ist bewusst NICHT enthalten — TSB misst
    akkumulierte Wochenlast, nicht die heutige Erholungsqualität. Vgl. WHOOP
    Recovery (rein overnight-physiologisch) vs. WHOOP Strain (Trainingskontext).
    TSB wird separat im Dashboard-Block "Heute möglich" dargestellt.
    """
    energy = await get_energy_metrics(user_id)
    auton = energy.get("energy_autonomic", {})
    cog = energy.get("energy_cognitive", {})

    components: list[tuple[float, float]] = []
    if auton.get("score") is not None:
        components.append((auton["score"], 0.60))
    if cog.get("score") is not None:
        components.append((cog["score"], 0.40))

    if not components:
        return {
            "score": None,
            "label": "Keine Daten",
            "cls": "badge-poor",
            "energy_autonomic": None,
            "energy_cognitive": None,
        }

    total_w = sum(w for _, w in components)
    score = round(max(0, min(100, sum(s * w / total_w for s, w in components))))

    if score >= 75:
        label, cls = "Gut erholt", "badge-balanced"
    elif score >= 55:
        label, cls = "In Ordnung", "badge-balanced"
    elif score >= 35:
        label, cls = "Erholen", "badge-unbalanced"
    else:
        label, cls = "Erschöpft", "badge-poor"

    return {
        "score": score,
        "label": label,
        "cls": cls,
        "energy_autonomic": auton.get("score"),
        "energy_cognitive": cog.get("score"),
    }
