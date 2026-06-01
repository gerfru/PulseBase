from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from .trimp import compute_trimp

# ─────────────────────────────────────────────────────────────────────────────
# EWM-Konstanten für das Banister Fitness-Fatigue-Modell
# Quelle: Banister & Calvert (1991); popularisiert durch TrainingPeaks / Coggan
#   ATL  τ = 7 d  → kurzfristige Ermüdung (Acute Training Load)
#   CTL  τ = 42 d → langfristige Fitnessadaptation (Chronic Training Load)
# ─────────────────────────────────────────────────────────────────────────────
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
    """TSB-basierter Erholungsscore (0–100) aus ATL/CTL-EWM über `window_days` Tage.

    Liefert: score, atl, ctl, tsb, hrmax — oder {score: None, reason} bei fehlenden Daten.

    Algorithmus
    -----------
    Edwards TRIMP (Sally Edwards, 1993) + Banister Fitness-Fatigue-Modell (1991).
    TRIMP-Formel: Dauer_min × HRr × (HRr × 4 + 1)
      HRr = (avg_HR − resting_HR) / (HRmax − resting_HR)  [Heart Rate Reserve Fraction]
      Der quadratische Term gewichtet hohe Intensitäten stärker — physiologisch präziser
      als diskrete Edwards-Zonen, stetiges Polynom statt Stufenfunktion.

    Score-Formel: score = 72 + TSB × 1.5  (geclampt 0–100)
    -------------------------------------------------------
    Literatur-Ankerpunkte (nicht arbiträr):

      TSB = +10 → score ≈ 87  ("Bereit" / Wettkampf-Taper-Zone)
        Quelle: Busso (2003) J Appl Physiol — optimales Race-TSB +5 bis +15;
                Joe Friel, TrainingPeaks: "Fresh zone" beginnt bei +5

      TSB = −30 → score ≈ 27  (Overreaching-Schwelle, Grenze Amber/Rot)
        Quelle: Friel / TrainingPeaks: "Pushing TSB below −30 greatly increases
                risk of injury or illness"; Meeusen et al. (2013) EJSS Consensus
                Statement on Overreaching: anhaltend negatives TSB < −30 = Risiko

      TSB = −10 bis −30 → score 57–27  (gelbe Zone, produktiver Trainingsblock)
        Quelle: TrainingPeaks: "−10 to −30 is a very productive and healthy range"

      TSB = 0 → score = 72  (ausgeglichener Stand = guter, nicht mittelmäßiger Zustand)

    Rückrechnung der Konstanten aus den Anker-Punkten:
      a + 10·b = 87  und  a − 30·b = 27  →  40b = 60  →  b = 1.5,  a = 72

    Warum Linear und kein Sigmoid?
    --------------------------------
    (1) Die Nicht-Linearität sitzt bereits im Modell: ATL/CTL sind exponentielle
        Glättungsfilter (EWM) — TSB ist deren nicht-lineares Produkt.
    (2) Busso (2003) zeigt Nicht-Linearität vor allem an den Extremen; im
        Arbeitsbereich TSB ∈ [−30, +15] ist die lineare Näherung empirisch adäquat.
    (3) Extremwerte werden durch _clip(0, 100) gekappt — das ist die einzige Stelle
        wo Linearität versagt, und sie ist bereits behandelt.
    (4) Transparenz: "score = 72 + TSB × 1.5" ist für Nutzer erklärbar; Sigmoid-
        Parameter (Steigung, Mittelpunkt) erfordern Kalibrierung ohne greifbaren
        Mehrwert im normalen Betriebsbereich.
    """
    if not activity_rows:
        return {"score": None, "reason": "no_activity_data"}

    by_date = {r["activity_date"]: r for r in activity_rows}
    atl = ctl = 0.0

    for i in range(window_days, -1, -1):
        d = today - timedelta(days=i)
        row = by_date.get(d)
        trimp = compute_trimp(row or {}, hrmax)
        atl = atl * _EWM_TAU7 + trimp * _ALPHA7
        ctl = ctl * _EWM_TAU42 + trimp * _ALPHA42

    tsb = ctl - atl
    return {
        "score": round(_clip(72 + tsb * 1.5), 1),
        "atl": round(atl, 2),
        "ctl": round(ctl, 2),
        "tsb": round(tsb, 2),
        "hrmax": round(hrmax, 1),
    }


def compute_autonomic_energy(
    hrv_history: list[float | None],
) -> dict[str, Any]:
    """Z-Score des aktuellen 7-Tage-HRV-Mittels gegen persönliche Baseline, skaliert 0–100.

    Liefert: score, deviation (σ), baseline_mean/std, hrv_7d_mean — oder {score: None, reason}.

    Algorithmus
    -----------
    ln(RMSSD)-Normierung nach Elite HRV / ithlete-Methodik:
      Quelle: https://help.elitehrv.com/article/57-the-1-10-relative-balance-score
      Begründung log: RMSSD ist rechtsschief verteilt → log-Transformation normalisiert
      auf annähernde Normalverteilung → σ-Vergleich erst danach valide.

    7-Tage-Rolling-Mean statt Einzeltag (Plews et al. 2013, Int J Sports Physiol Perform):
      RMSSD variiert täglich um 20–30 % durch Messartefakte → Wochenmittel robuster.
      hrv_history muss ORDER BY date ASC übergeben werden; letzte 7 Werte = aktuelle Woche.

    Score-Formel: score = 70 + deviation × 15  (geclampt 0–100)
    -------------------------------------------------------------
    Literatur-Ankerpunkte:

      deviation = 0  → score = 70  ("In Ordnung", grüne Zone)
        Quelle: Altini & Plews (2021) Frontiers Physiol: "At baseline HRV, the athlete
                is in a normal recovery state — not compromised."
                Elite HRV KB: "Normal values contextualize: below normal = higher stress."
                → Baseline ist der Normalzustand, nicht die Untergrenze.

      deviation = ±1σ → score = 85 / 55  (SWC-Schwelle)
        Quelle: Buchheit (2014): "Smallest Worthwhile Change ≈ 1 × CV des Athleten"
                (typisch ~1σ in ln-RMSSD-Einheiten); Plews et al. (2013):
                Reaktion auf Training erst bei anhaltender Baseline-Abweichung > SWC.
                → ±1σ markiert die Grenze zwischen "normal" und "bedeutsam verändert".

      deviation = −2σ → score = 40  (klinisch relevante Suppression)
      deviation = +2σ → score = 100 (geclampt)

    Rückrechnung: a + 0·15 = 70 → a = 70 (direkt aus Altini-Anker).

    Warum Linear nach der log-Transformation?
    ------------------------------------------
    (1) ln(RMSSD) korrigiert die stärkste Nicht-Linearität (rechte HRV-Schiefe).
        Nach der Transformation ist der σ-Raum annähernd gaußisch → lineares Mapping
        ist statistisch korrekt.
    (2) Die nachgelagerte lineare Skalierung bewegt sich im Raum der Standardnormalverteilung
        — Abweichungen von ±3σ sind physiologisch extrem selten und werden durch _clip
        abgefangen.
    (3) Kubios HRV Readiness Score und HRV4Training nutzen ebenfalls lineare z-Score-
        Mappings nach log-Transformation (keine Sigmoids in peer-reviewed Systemen).
    """
    _WINDOW = 7
    raw = [math.log(v) * 20 for v in hrv_history if v is not None and v > 0]
    if len(raw) < 7:
        return {"score": None, "reason": "insufficient_hrv_data"}

    if len(raw) >= 14:
        current_window = raw[-_WINDOW:]
        baseline = raw[:-_WINDOW]
        current_mean = sum(current_window) / len(current_window)
    else:
        # Fallback für neue User (<14 Datenpunkte): Einzeltag statt 7-Tage-Mean
        current_mean = raw[-1]
        baseline = raw[:-1]

    n = len(baseline)
    mean = sum(baseline) / n
    std = max(1.0, math.sqrt(sum((x - mean) ** 2 for x in baseline) / n))
    dev = (current_mean - mean) / std

    return {
        "score": round(_clip(70 + dev * 15), 1),
        "deviation": round(dev, 2),
        "baseline_mean": round(mean, 2),
        "baseline_std": round(std, 2),
        "hrv_7d_mean": round(current_mean, 2),
    }


def compute_cognitive_energy(
    sleep_data_7d: list[dict[str, float | None]],
) -> dict[str, Any]:
    """Kumulierte Schlafschuld-Score über 7 Nächte, skaliert 0–100 (100 = keine Schuld).

    Liefert: score, debt_hours (Summe der Defizite gegen 7h-Ziel), days_used — oder {score: None}.

    Algorithmus
    -----------
    Borbély Two-Process Model — Process S (homöostatischer Schlafdruck):
      Quelle: Borbély AA (1982) A two process model of sleep regulation.
              Hum Neurobiol 1(3):195–204
    Schlafdruck akkumuliert linear über Wachtage und dissipiert während des Schlafs.
    7-Nächte-Fenster nach Banks & Dinges (2007): kumulative Schuld > 5h → kognitive
    Beeinträchtigungen vergleichbar mit 24h Schlafentzug.

    Score-Formel: score = 100 − debt_hours × 6  (geclampt 0–100)
      Schlüsselankerpunkt: debt = 5h → score = 70 (Grenze klinisch relevante Beeinträchtigung
      nach Banks & Dinges); debt = 0 → 100; debt ≥ 16.7h → 0.
      Ziel 7h/Nacht: NSF-Empfehlung 7–9h, 7h als untere Grenze für Erwachsene.

    Hinweis: Schlafqualitätsfaktor entfernt — Garmins Tiefschlaf-Erkennung basiert auf
    Akzelerometer + HRV, nicht auf PSG-Goldstandard, und ist zu unzuverlässig für
    quantitative Gewichtung.
    """
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
