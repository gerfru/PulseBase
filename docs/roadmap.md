# Roadmap

Geplante und mögliche Erweiterungen. Priorisiert nach Aufwand vs. Erkenntnisgewinn.

Status-Symbole: ✅ implementiert · 🟡 machbar mit aktuellen Daten · 🔵 neue Daten nötig · 🔴 komplex / Sensor nötig

---

## 1. Garmin-Blackboxes ersetzen

Garmin-Metriken die aktuell als undokumentierter Firstbeat-Output übernommen werden,
obwohl wissenschaftlich publizierte Alternativmethoden existieren.

### 1.1 Body Battery — eigenes Energie-Drain-Modell 🟡

**Aktuell:** `daily_summary.body_battery_high/low` — Garmin/Firstbeat, keine öffentliche Formel.

**Möglich:** Tagesenergie-Budget-Modell auf Basis bestehender Daten.

```
Basis-Energie    = 100 (Vollladung nach ausreichend Schlaf)
Drain Aktivität  = TRIMP_heute × Faktor (aus Trainingsintensität)
Drain Stress     = Σ stress_intraday über Tagesstunden
Recovery Nacht   = f(total_sleep_h, hrv_last_night) — analog Autonomic Energy

Body Battery = min(100, max(0, Vortag + Recovery_Nacht − Drain_Aktivität − Drain_Stress))
```

**Daten vorhanden:** `body_battery_intraday` (Garmin-Rohdaten als Trainings-Target),
`stress_intraday`, `sleep_sessions`, `hrv_daily`, `activities`

**Vorteil:** Explizite Drain-Quellen sichtbar (Stress vs. Training vs. Schlaf-Recovery).

**Aufwand:** Medium — ML-Service-Erweiterung, kein neues Schema.

---

### 1.2 Stress-Score — eigener HRV-basierter Tagesstress 🟡

**Aktuell:** `daily_summary.avg_stress` — Garmin/Firstbeat, HRV-basiert aber undokumentiert.

**Möglich:** Stress-Index aus verfügbaren täglichen HRV-Kennzahlen.

```
# Sympatico-vagale Balance: Abweichung von persönlicher HRV-Baseline unter Belastung
stress_index = (hrv_baseline_mean − hrv_last_night) / hrv_baseline_std

# Skalierung auf 0–100 (analog Autonomic Energy, invertiert)
stress_score = clip(50 − stress_index × 15)
```

**Limitation:** Kein intraday-HRV-Zugriff → Tagesgranularität statt stündlicher Auflösung.
Garmins Stress zeigt Stundenverläufe; unsere Methode nur einen Tageswert.

**Aufwand:** Niedrig — eine neue Berechnung in `energy_metrics.py`, kein Schema-Change.

---

### 1.3 Aerober Trainingseffekt — TRIMP-basiert 🟡 (bereits teilweise ✅)

**Aktuell:** `activities.aerobic_effect` — Garmin EPOC-Modell (Firstbeat).

**Implementiert:** Banister TRIMP im Physical-Energy-Score und Training-Effect-Metrik.
Noch nicht: Per-Aktivität-Skalierung auf 0–5 wie Garmin.

```
# EPOC-Proxy via Banister TRIMP (Morton et al. 1990)
TRIMP_session = Dauer × HRr × e^(b × HRr)   [b = 1.92 m / 1.67 f]

# Skalierung auf 0–5 (analog Garmin-Skala)
aerobic_effect = min(5, TRIMP_session / CTL × 0.8)
  — < 1 geringe Wirkung, 2–3 verbessernd, > 4 überbelastend
```

**Aufwand:** Niedrig — Schema vorhanden, Berechnung im Training-Effect-Modell ergänzen.

---

### 1.4 Anaerober Trainingseffekt 🔴

**Aktuell:** `activities.anaerobic_effect` — Garmin (Firstbeat, Power-Meter oder Speed-Proxy).

**Problem:** Anaerober Anteil erfordert Leistungsmessung (Watt) oder Laktat-Modell.
Ohne direkten Power-Sensor nur grob aus Speed + HR-Sprüngen schätzbar (unzuverlässig).

**Alternative:** Lactat Threshold Detection via kritische Herzfrequenz-Kurve (Bunc et al.).
Benötigt mehrere Maximalbelastungs-Sessions für Kalibrierung.

**Empfehlung:** Zurückstellen bis Leistungsmessdaten verfügbar (Cycling-Power-Meter oder
Stryd Running Power — bereits als `avg_running_power` in V13 gespeichert).

---

### 1.5 Schlafphasen-Klassifikation 🔴

**Aktuell:** Garmin-Schlafphasen aus Akzelerometer + optischem HRV.

**Problem:** EEG-Goldstandard nicht verfügbar. Garmin selbst gilt als unzuverlässig
(deshalb kein Qualitätsfaktor in unserem Kognitiv-Score).

**Zukünftig:** Wenn Consumer-EEG (z.B. Muse, Dreem) integriert wird — dann sinnvoll.

---

## 2. Neue Kennzahlen — machbar mit aktuellen Daten

Metriken die wir noch nicht berechnen, aber mit vorhandenen Daten könnten.

### 2.1 ACWR — Acute:Chronic Workload Ratio (Verletzungsprävention) 🟡

**Basis:** Gabbett (2016) — ACWR > 1.5 erhöht Verletzungsrisiko signifikant.

```
ACWR = ATL (7d) / CTL (28d)

Grüner Bereich: 0.8 – 1.3
Amber:          1.3 – 1.5
Rot:            > 1.5 (Überbelastungsrisiko) oder < 0.8 (Detraining)
```

**Daten vorhanden:** ATL und CTL bereits in `ml_predictions.energy_physical`.

**Aufwand:** Sehr niedrig — zwei bestehende Werte dividieren, als eigene `model`-Row speichern.

**Quelle:** Gabbett TJ (2016). The training-injury prevention paradox. BJSM 50(5):273–280.

---

### 2.2 Training Monotony + Training Strain 🟡

**Basis:** Foster (1998) — zu wenig Variation im Training erhöht Krankheits- und Verletzungsrisiko.

```
Training Monotony = Ø TRIMP_7d / σ(TRIMP_7d)
  — hoch (> 2.0) = wenig Abwechslung im Training

Training Strain = Σ TRIMP_7d × Monotony
  — kombinierter Belastungsindikator
```

**Daten vorhanden:** TRIMP-History in `ml_predictions`.

**Aufwand:** Niedrig.

**Quelle:** Foster C (1998). Monitoring training in athletes. Med Sci Sports Exerc 30(7).

---

### 2.3 Laufökonomie-Score (Running Economy) 🟡

**Daten vorhanden (V13):**
- `avg_ground_contact_time` (ms) — optimal < 240ms
- `avg_vertical_oscillation` (cm) — optimal < 8cm
- `avg_vertical_ratio` (%) — optimal < 8%
- `avg_stride_length` (cm)

**Möglicher Score:**

```
# Jede Kennzahl gegen persönliche Baseline und Literatur-Optimum normieren
gct_score = clip(100 − (avg_gct − 200) × 0.5)    # 200ms ideal, −0.5 je ms darüber
vo_score  = clip(100 − (avg_vo  − 6)   × 5  )    # 6cm ideal
vr_score  = clip(100 − (avg_vr  − 6)   × 8  )    # 6% ideal

economy_score = gct_score × 0.4 + vo_score × 0.35 + vr_score × 0.25
```

**Quellen:**
- Cavanagh & Kram (1985): Ground contact time and running economy
- Moore (2016): Biomechanical factors associated with running economy

**Aufwand:** Medium — neue Berechnung im ML-Service, Schema vorhanden.

---

### 2.4 Sleep Consistency Score 🟡

**Basis:** Reguläre Schlaf-/Aufwachzeiten sind unabhängiger Prädiktor für Schlafqualität
(Phillips et al. 2017 — Social Jet Lag).

```
wake_times   = start_time + total_sleep_seconds [letzte 14 Nächte]
sleep_times  = start_time

consistency  = 100 − (σ(wake_times_h) × 15 + σ(sleep_times_h) × 10)
  — σ in Stunden; optimal < 30min Varianz = Score ~90+
```

**Daten vorhanden:** `sleep_sessions.start_time` + `total_sleep_seconds`

**Aufwand:** Niedrig.

---

### 2.5 SpO2-Trendanalyse 🟡

**Aktuell:** `daily_summary.avg_spo2` / `min_spo2` werden gezeigt, aber nicht analysiert.

**Mögliches Feature:**
- 7-Tage-Trend: Abfallende SpO2 → mögliche Erkrankung / Altitude-Effekt
- Nacht-Minimum < 90% wiederholt → Flag für mögliche Schlafapnoe (Hinweis, kein Befund)
- Korrelation SpO2 ↔ Schlafqualität

**Daten vorhanden:** `daily_summary`, `spo2_readings` (hypertable, intraday)

**Aufwand:** Niedrig für Trend. Medium für Schlafapnoe-Flag.

---

### 2.6 Glukose × Aktivität Korrelation 🟡 (nur für Libre-User)

**Daten vorhanden:** `glucose_readings` (mg/dL, ~1/min) + `activities` + `activity_records` (HR/sec)

**Mögliche Analysen:**
```
# Glukose-Response auf Training
pre_exercise_glucose   = Ø glucose 30min vor Aktivität
intra_exercise_drop    = pre − Ø glucose während Aktivität
recovery_glucose       = Ø glucose 60–120min nach Aktivität

# Korrelation Glukosevariabilität ↔ Schlafqualität
cv_glucose = σ(glucose_24h) / mean(glucose_24h) × 100   [Coefficient of Variation]
```

**Aufwand:** Medium — Cross-Join auf Zeitstempel (TimescaleDB time_bucket).

---

### 2.7 HRV Recovery Trajectory 🟡

Wie schnell erholt sich HRV nach Trainingsbelastung?

```
# Für jede Aktivität: TSB-Einbruch vs. HRV-Erholung in den Folgenächten
recovery_speed = ΔHRV_per_day nach TSB-Minimum

# Langfristiger Trend: verbessert sich Recovery-Speed über Trainingswochen?
```

**Aufwand:** Medium — neue Analysefunktion, Daten vorhanden.

---

## 3. ML-Erweiterungen

### 3.1 Epilepsie-Risiko V2 — datenbasiert statt regelbasiert 🔵

**Aktuell:** Regelbasierter Indikator (V15) — 6 Heuristiken, kein historischer Anfallsverlauf nötig.

**V2 (ab ~20 Ereignissen in `seizure_events`):**
- Feature Engineering: Biomarker 0–7 Tage vor bekannten Anfällen
- Modell: Logistische Regression oder Gradient Boosting auf Zeitfenstervektoren
- Ziel: Personalisierte Schwellenwerte statt generischer Heuristiken

**Voraussetzung:** Mindestens 20 Anfallsereignisse mit zeitlich zugeordneten Biomarkern.
`seizure_events`-Tabelle (V15) ist das Fundament dafür.

---

### 3.2 Readiness RF — erweiterte Features 🟡

**Aktuell:** Random Forest auf `[hrv_last_night, sleep_score, resting_hr, aerobic_effect, anaerobic_effect]`

**Erweiterung:**
- ACWR als Feature (Verletzungsrisiko-Signal)
- `avg_stress` aus daily_summary
- `body_battery_high/low`
- Konsistenz-Features: Varianz von HR/HRV über 7 Tage

---

### 3.3 Anomalie-Detektion auf weiteren Zeitreihen 🟡

**Aktuell:** Z-Score-Anomalie auf `resting_hr`.

**Erweiterbar auf:** SpO2, Schlafdauer, Stressindex, Schritte — gleicher Algorithmus,
neue `model`-Rows in `ml_predictions`.

---

## 4. Features / UX

### 4.1 Wochenrückblick 🟡

Automatisch generierte Wochenzusammenfassung: Trainingsvolumen, Readiness-Trend,
schlechteste und beste Nacht, Auffälligkeiten.

### 4.2 Ziele & Soll-Ist-Vergleich 🟡

- Wochen-Trainingsvolumen-Ziel (km/Stunden)
- Schlaf-Ziel (7h)
- Intensitätsminuten-Ziel (150min WHO)

### 4.3 Nahrungserfassung 🔵

Integration z.B. mit Open Food Facts API. Kalorien × Energiebedarf-Modell.
Relevant für Glukose-Analyse (Carb-Timing vor/nach Training).

---

## 5. Datenquellen

| Quelle | Neue Daten | Aufwand |
|--------|-----------|---------|
| **Withings Scale** | Gewicht, Körperfett, Muskelmasse | Medium |
| **Apple Health / Google Fit** | Zweiter Nutzer ohne Garmin | Medium |
| **Oura Ring** | Hochwertige Schlafphasen + HRV | Medium |
| **Stryd** (bereits: `avg_running_power`) | Laufleistung-Watt für anaeroben Effekt | Niedrig (Schema ✅) |
| **Consumer-EEG** (Muse, Dreem) | Schlafphasen-Goldstandard | Hoch |

---

## Priorisierung (Aufwand/Nutzen)

| Priorität | Feature | Aufwand | Nutzen |
|-----------|---------|---------|--------|
| 🥇 | ACWR (Verletzungsprävention) | Sehr niedrig | Hoch |
| 🥇 | Training Monotony + Strain | Niedrig | Mittel |
| 🥈 | Laufökonomie-Score (V13-Daten) | Medium | Hoch für Läufer |
| 🥈 | SpO2-Trendanalyse | Niedrig | Mittel |
| 🥈 | Sleep Consistency Score | Niedrig | Mittel |
| 🥉 | Body Battery Ersatz | Medium | Hoch |
| 🥉 | Stress-Score Ersatz | Niedrig | Mittel |
| 🥉 | Glukose × Training Korrelation | Medium | Hoch für Libre-User |
| ⏳ | Epilepsie-Risiko V2 (ML) | Hoch | Hoch (ab 20 Events) |
| ⏳ | Schlafphasen-Klassifikation | Sehr hoch | Fraglich (Sensor-Limitation) |
