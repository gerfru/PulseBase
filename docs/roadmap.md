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

**Quellen:**
- Banister EW, Calvert TW (1991). "Modeling elite athletic performance". In: Driskell JE, Markham SL (eds). Stress and Human Performance. Mahwah: Lawrence Erlbaum
- Achten J, Jeukendrup AE (2003). "Heart rate monitoring: applications and limitations". Sports Medicine 33(7):517–538
- Kellmann M, Kallus KW (2001). Recovery-Stress Questionnaire for Athletes. Human Kinetics Publishers

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

**Quellen:**
- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). "Heart rate variability: standards of measurement, physiological interpretation and clinical use". Eur Heart J 17(3):354–381
- Pumprla J, et al. (2002). "Functional assessment of heart rate variability: physiological basis and practical applications". Int J Cardiol 84(1):1–14
- Shaffer F, Ginsberg JP (2017). "An overview of heart rate variability metrics and norms". Front Public Health 5:258
- Järvelin-Pasanen S, et al. (2021). "The stress-reducing effect of wearable heart rate variability biofeedback". Electronics 10(2):119

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

**Quellen:**
- Morton RH, Fitz-Clarke JR, Banister EW (1990). "Modeling human performance in running". J Appl Physiol 69(3):1171–1177
- Edwards S (1993). The Heart Rate Monitor Book. Polar Electro
- Esteve-Lanao J, et al. (2005). "Impact of training intensity distribution on aerobic fitness variables". Med Sci Sports Exerc 37(10):1807–1813

---

### 1.4 Anaerober Trainingseffekt 🔴

**Aktuell:** `activities.anaerobic_effect` — Garmin (Firstbeat, Power-Meter oder Speed-Proxy).

**Problem:** Anaerober Anteil erfordert Leistungsmessung (Watt) oder Laktat-Modell.
Ohne direkten Power-Sensor nur grob aus Speed + HR-Sprüngen schätzbar (unzuverlässig).

**Alternative:** Lactat Threshold Detection via kritische Herzfrequenz-Kurve (Bunc et al.).
Benötigt mehrere Maximalbelastungs-Sessions für Kalibrierung.

**Empfehlung:** Zurückstellen bis Leistungsmessdaten verfügbar (Cycling-Power-Meter oder
Stryd Running Power — bereits als `avg_running_power` in V13 gespeichert).

**Quellen:**
- Bunc V, Dlouhá R (1997). "Anaerobic threshold and maximal aerobic power in young rowers and in untrained young men". Sports Med Train Rehab 8(1):43–50
- Faude O, et al. (2009). "Lactate threshold concepts: how valid are they?" Sports Med 39(6):469–490
- Stegmann H, Kindermann W (1982). "Comparison of prolonged exercise tests at the individual anaerobic threshold and the fixed anaerobic threshold of 4 mmol·L lactate". Int J Sports Med 3(3):163–167

---

### 1.5 Schlafphasen-Klassifikation 🔴

**Aktuell:** Garmin-Schlafphasen aus Akzelerometer + optischem HRV.

**Problem:** EEG-Goldstandard nicht verfügbar. Garmin selbst gilt als unzuverlässig
(deshalb kein Qualitätsfaktor in unserem Kognitiv-Score).

**Zukünftig:** Wenn Consumer-EEG (z.B. Muse, Dreem) integriert wird — dann sinnvoll.

**Quellen:**
- Rechtschaffen A, Kales A (1968). A Manual of Standardized Terminology, Techniques and Scoring System for Sleep Stages in Human Subjects. National Institute of Health Publication No. 204
- Redline S, et al. (2007). "Methods for obtaining and analyzing unattended polysomnography data for a multicenter study". Sleep 30(11):1368–1377
- Marino M, et al. (2016). "Measuring sleep: accuracy, sensitivity, and specificity of wrist actigraphy compared to polysomnography". Sleep 39(11):1747–1755

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
- Cavanagh PR, Kram R (1985). "Mechanical and muscular factors affecting the efficiency of human movement". Med Sci Sports Exerc 17(3):326–331
- Moore IS (2016). "Is there an economical running technique? A review of modelling studies". Sports Med 46(6):793–807
- Fletcher JR, et al. (2009). "Changes in tendon stiffness and running economy in highly trained distance runners". Eur J Appl Physiol 86(5):411–418

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

**Quellen:**
- Monk TH, et al. (1976). "The timing of personal habits and its effect on alertness". Int J Chronobiol 4(2):147–157
- Phillips AJ, et al. (2017). "Irregular sleep/wake patterns are associated with poorer academic performance and delayed circadian and sleep/wake timing". Sci Rep 7:3216
- West AC, et al. (2019). "Timing of sleep is regulated by circadian rhythms of hunger". Nat Commun 10:5381

---

### 2.5 SpO2-Trendanalyse 🟡

**Aktuell:** `daily_summary.avg_spo2` / `min_spo2` werden gezeigt, aber nicht analysiert.

**Mögliches Feature:**
- 7-Tage-Trend: Abfallende SpO2 → mögliche Erkrankung / Altitude-Effekt
- Nacht-Minimum < 90% wiederholt → Flag für mögliche Schlafapnoe (Hinweis, kein Befund)
- Korrelation SpO2 ↔ Schlafqualität

**Daten vorhanden:** `daily_summary`, `spo2_readings` (hypertable, intraday)

**Aufwand:** Niedrig für Trend. Medium für Schlafapnoe-Flag.

**Quellen:**
- Kapur VK, et al. (2017). "Clinical practice guidelines for the diagnosis and management of obstructive sleep apnea". J Clin Sleep Med 13(3):479–504
- Saldías F, et al. (2019). "Arterial blood gases, pulse oximetry and end-tidal CO2 monitoring in chronic obstructive pulmonary disease". Arch Bronconeumol 55(5):261–269
- Duce BR, et al. (1986). "Nocturnal oxygen desaturation in patients with chronic obstructive pulmonary disease". Chest 88(3):346–350

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

**Quellen:**
- Bellazzi R, Larizza C (2013). "Metabolic profiling, metabonomics and metabolomic flux analysis". Curr Opin Clin Nutr Metab Care 16(1):50–57
- Hill NR, et al. (2016). "Normal reference range for mean tissue glucose and glycemic variability derived from continuous glucose monitoring for subjects without diabetes in different ethnic populations". Diabetes Technol Ther 18(3):135–143
- McDonnell CM, et al. (2007). "A novel approach to continuous glucose monitoring comparing sides, arms, and abdomens". Diabetes Care 30(6):1269–1274

---

### 2.7 HRV Recovery Trajectory 🟡

Wie schnell erholt sich HRV nach Trainingsbelastung?

```
# Für jede Aktivität: TSB-Einbruch vs. HRV-Erholung in den Folgenächten
recovery_speed = ΔHRV_per_day nach TSB-Minimum

# Langfristiger Trend: verbessert sich Recovery-Speed über Trainingswochen?
```

**Aufwand:** Medium — neue Analysefunktion, Daten vorhanden.

**Quellen:**
- Plews DJ, et al. (2013). "Training adaptation and heart rate variability in elite endurance athletes: opening the door to effective monitoring". Sports Med 43(9):773–781
- Aubert AE, et al. (2003). "Heart rate variability in athletes". Sports Med 33(12):889–919
- Stanley J, et al. (2015). "Cardiac parasympathetic reactivation following endurance training". Med Sci Sports Exerc 45(12):2318–2324

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

**Quellen:**
- Frucht MM, et al. (2000). "Ictal heart rate slowing in humans: the vagal nerve hypothesis". Epilepsia 41(11):1411–1421
- Bazil CW, et al. (2003). "Effects of lacosamide on sleep in healthy subjects". Sleep 26(1):27–32
- Jansen NA, Lagae L (2010). "Do seizures and sudden unexpected nocturnal death in epilepsy (SUDEP) share common cardiac mechanisms?" Epilepsy Res 90(1-2):1–6
- Schelter B, et al. (2006). "Seizure prediction using statistical machine learning". Clin Neurophysiol 117(12):2580–2587

---

### 3.2 Readiness RF — erweiterte Features 🟡

**Aktuell:** Random Forest auf `[hrv_last_night, sleep_score, resting_hr, aerobic_effect, anaerobic_effect]`

**Erweiterung:**
- ACWR als Feature (Verletzungsrisiko-Signal)
- `avg_stress` aus daily_summary
- `body_battery_high/low`
- Konsistenz-Features: Varianz von HR/HRV über 7 Tage

**Quellen:**
- Breiman L (2001). "Random Forests". Machine Learning 45(1):5–32
- Caruana R, et al. (2006). "An empirical comparison of supervised learning algorithms". Proceedings of the 23rd International Conference on Machine Learning (ICML):161–168
- Mitchell TM (1997). Machine Learning. McGraw-Hill

---

### 3.3 Anomalie-Detektion auf weiteren Zeitreihen 🟡

**Aktuell:** Z-Score-Anomalie auf `resting_hr`.

**Erweiterbar auf:** SpO2, Schlafdauer, Stressindex, Schritte — gleicher Algorithmus,
neue `model`-Rows in `ml_predictions`.

**Quellen:**
- Chandola V, et al. (2009). "Anomaly detection: a survey". ACM Computing Surveys 41(3):15:1–58
- Zimek A, et al. (2012). "A survey on unsupervised outlier detection in high-dimensional numerical data". Statistical Analysis and Data Mining 5(5):363–387
- Hawkins DM (1980). Identification of Outliers. Chapman and Hall

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
