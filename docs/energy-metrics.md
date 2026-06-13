# Eigenberechnete Metriken

PulseBase berechnet alle Fitness- und Gesundheitsmetriken transparent nach publizierten
wissenschaftlichen Methoden — unabhängig von Garmins proprietären Firstbeat-Algorithmen.

Dieses Dokument beschreibt **warum** (wissenschaftliche Herleitung) und **wie genau**
(Formeln, Implementierung) jede Metrik berechnet wird.

Alle Implementierungen liegen offen in `ml-service/src/models/`.

---

## Übersicht: Alle berechneten Metriken

| Metrik | Modell-Key | Implementiert in | Typ |
|--------|-----------|-----------------|-----|
| Intensitätsminuten (moderat / vigoros) | `intensity_minutes_custom` | `intensity_minutes.py` | Regel |
| Schlaf-Score | `sleep_score_custom` | `sleep_score.py` | Regel |
| HRV-Status | `hrv_status_custom` | `hrv_status.py` | Regel |
| Aerober Trainingseffekt (TRIMP) | `training_effect_custom` | `training_effect.py` | Regel |
| CTL / ATL / TSB | *(Teil von Physical Energy)* | `energy_metrics.py` | Regel |
| Physische Energie | `energy_physical` | `energy_metrics.py` | Regel |
| Autonome Energie | `energy_autonomic` | `energy_metrics.py` | Regel |
| Kognitive Energie | `energy_cognitive` | `energy_metrics.py` | Regel |
| Body Battery Custom | `body_battery_custom` | `body_battery.py` | Regel |
| ACWR (Workload-Ratio) | `acwr` | `training_load.py` | Regel |
| Training Monotony | `training_monotony` | `training_load.py` | Regel |
| Schlaf-Konsistenz | `sleep_consistency` | `sleep_metrics.py` | Regel |
| SpO2-Trend + Apnoe-Flag | `spo2_trend` | `spo2_metrics.py` | Regel |
| Stress-Score | `stress_score_custom` | `stress_metrics.py` | Regel |
| Running Economy | `running_economy` | `running_economy.py` | Regel |
| HRV-Erholungstrajektorie | `hrv_recovery` | `hrv_recovery.py` | Regel |
| Anomalie-Erkennung (5 Metriken) | `anomaly_hr` u.a. | `anomaly.py` | Regel (Z-Score) |
| Korrelationsanalyse (3 Paare) | `correlation_sleep_hrv` u.a. | `correlation.py` | Statistik |
| Readiness-Prediction | `readiness_rf` | `readiness.py` | ML (Random Forest) |
| Body-Battery-Muster | `battery_pattern` | `battery_pattern.py` | ML (K-Means) |

**Was Garmin liefert, was wir selbst berechnen:**

| Garmin-Wert | Was Garmin macht | Unsere Alternative |
|-------------|------------------|--------------------|
| Body Battery | Firstbeat-Algorithmus, proprietär | `body_battery_custom` (Fresh-State) |
| Training Status (PRODUCTIVE…) | Firstbeat EPOC-Modell | CTL/ATL/TSB + ACWR |
| HRV Status | proprietär (Baseline-Vergleich) | `hrv_status_custom` (σ-normiert) |
| Sleep Score | proprietär | `sleep_score_custom` (Phasen + Dauer) |
| Aerobic Effect | EPOC-basiert | `training_effect_custom` (Banister TRIMP) |

**Was nicht replizierbar ist:**
- **Anaerober Trainingseffekt**: braucht Wattsensor (W'-Balance-Modell); `avg_power` nur für Radfahren
- **Intraday-HRV** (RMSSD): Garmin liefert keine RR-Rohdaten; `hrv_last_night` als Quelle beibehalten
- **Body Battery Intraday-Verlauf**: braucht kontinuierliches HRV; Tages-Eröffnungswert approximierbar

---

## 1. Intensitätsminuten

**Methode:** WHO/CDC Herzfrequenz-Zonen — vollständig publiziert.

**Formel:**
```
HRr = (HR_exercise − HR_rest) / (HR_max − HR_rest)   # Karvonen Heart Rate Reserve

Moderat:  0.50 ≤ HRr < 0.70
Vigoros:  HRr ≥ 0.70

Intensitätsminuten = Σ Sekunden_in_Zone / 60
```

**Inputs:**
- `activity_records.heart_rate` (Sekunden-HR) ✅
- HRmax: `MAX(activities.max_hr)` über alle Aktivitäten; besser als Formel 220−Alter
- Resting HR: `daily_summary.resting_hr`; Fallback 60 bpm

**Implementiert in:** `ml-service/src/models/intensity_minutes.py`

---

## 2. Schlaf-Score (0–100)

**Methode:** Gewichtete Schlafphasen-Formel (COROS-Ansatz, publiziert).

Optimale Schlafverteilung (Literatur): Tiefschlaf ~20%, REM ~22%, Leichtschlaf ~50%, Wach < 5%.

**Formel:**
```
deep_pct       = deep_sleep_seconds  / total_sleep_seconds
rem_pct        = rem_sleep_seconds   / total_sleep_seconds
wake_pct       = awake_seconds       / total_sleep_seconds
duration_h     = total_sleep_seconds / 3600

deep_score     = min(100, deep_pct / 0.20 × 100)     # optimal bei 20% Tiefschlaf
rem_score      = min(100, rem_pct  / 0.22 × 100)     # optimal bei 22% REM
duration_score = min(100, duration_h / 8.0 × 100)    # optimal bei 8h (Walker 2017)
wake_penalty   = max(0, 100 − wake_pct × 500)        # −5 Punkte je 1% Wachanteil

score = deep_score×0.35 + rem_score×0.25 + duration_score×0.25 + wake_penalty×0.15
```

**Inputs:** `sleep_sessions.{deep_sleep_seconds, rem_sleep_seconds, awake_seconds, total_sleep_seconds}` ✅

**Implementiert in:** `ml-service/src/models/sleep_score.py`

---

## 3. HRV-Status (BALANCED / UNBALANCED / LOW / POOR)

**Methode:** Vergleich aktueller RMSSD mit persönlicher rollender Baseline (Plews et al. 2013).
Keine absoluten Cutoffs — individuelle Standardabweichungen.

**Formel:**
```
baseline_mean = Mittelwert der 90-Tage-History exkl. der letzten 7 Tage
current_mean  = 7-Tage-Rolling-Mean der letzten 7 Tage (robuster als Einzeltag)
baseline_std  = Standardabweichung der Baseline

deviation = (current_mean − baseline_mean) / baseline_std

BALANCED:    deviation ≥ −0.5
UNBALANCED:  −1.5 ≤ deviation < −0.5
LOW:         −2.0 ≤ deviation < −1.5
POOR:        deviation < −2.0
```

**Inputs:** `hrv_daily.hrv_last_night` (mindestens 21 Tage History empfohlen) ✅

**Implementiert in:** `ml-service/src/models/hrv_status.py`

---

## 4. Training Load — TRIMP + Banister Fitness-Fatigue-Modell

### 4.1 Edwards TRIMP (Einzelaktivität)

**Formel:**
```
HRr = (avg_hr − resting_hr) / (hrmax − resting_hr)

TRIMP_Edwards = duration_min × HRr × (HRr × 4 + 1)
```

**Banister TRIMP** (geschlechtsspezifisch, präziser bei Ausdauersport):
```
TRIMP_Banister = duration_min × HRr × e^(b × HRr)

b (Steigung):   1.92 (männlich), 1.67 (weiblich)
```
Kalibriert an Blutlaktat-Kurven. `users.sex` aus V12 vorhanden ✅.

**Implementiert in:** Edwards TRIMP in `ml-service/src/models/trimp.py`;
Banister TRIMP in `ml-service/src/models/training_effect.py` (und `api/src/training_load.py`)

### 4.2 CTL / ATL / TSB (Banister Fitness-Fatigue, 1991)

```
ATL_t = ATL_{t-1} × e^(−1/7)  + TRIMP_t × (1 − e^(−1/7))   # τ = 7 Tage  (Ermüdung)
CTL_t = CTL_{t-1} × e^(−1/42) + TRIMP_t × (1 − e^(−1/42))  # τ = 42 Tage (Fitness)

TSB = CTL − ATL   # Training Stress Balance / Form
```

**TSB-Interpretation:**

| TSB | Bedeutung |
|-----|-----------|
| > +10 | Sehr erholt / Wettkampfform |
| +5 bis +10 | Gut erholt |
| 0 bis +5 | Gleichgewicht |
| −5 bis 0 | Normale Trainingsbelastung |
| < −10 | Deutliche Ermüdung |

**Kalt-Start:** Die ersten 6 Wochen baut sich CTL erst auf. Fenster: 50+ Tage dense-date-Walk.

**Inputs:** `activities.{avg_hr, duration_seconds, max_hr}`, `daily_summary.resting_hr` ✅

### 4.3 ACWR (Acute:Chronic Workload Ratio)

```
ACWR = ATL / CTL

< 0.8   → Detraining-Risiko (rote Zone)
0.8–1.3 → optimales Trainingsfenster (grüne Zone)
1.3–1.5 → erhöhtes Verletzungsrisiko (gelbe Zone)
> 1.5   → hohes Verletzungsrisiko (rote Zone)
```

**Quelle:** Gabbett (2015+), *British Journal of Sports Medicine*

**Implementiert in:** `ml-service/src/models/training_load.py`

---

## 5. Drei-Säulen-Energie-Modell

PulseBase berechnet drei separate, nachvollziehbare Energie-Dimensionen — unabhängig
von Garmins proprietären Firstbeat-Algorithmen.

### 5.1 Physische Energie — Fitness-Fatigue (aerob)

**Was es misst:** Wie viel aerobe Kapazität ist nach Trainingsbelastung der letzten Wochen
noch vorhanden? Mechanismus: Superkompensation — nach Belastung folgt Erholung.

**Formel:**
```
score = clip(72 + TSB × 1.5, 0, 100)
```

**Hinweis:** TSB stammt aus dem ATL/CTL-Modell, das hier mit **Edwards TRIMP**
(`compute_trimp`, quadratische Zonengewichtung) gespeist wird — *nicht* mit Banister TRIMP.
Banister TRIMP kommt nur im Aerobic-Effect-Modell (`training_effect.py`) zum Einsatz.

**Ankerpunkte (aus Code energy_metrics.py):**

| TSB | Score | Bedeutung |
|-----|-------|-----------|
| +10 | 87 | Sehr erholt / Wettkampfform |
| +5 | 80 | Gut erholt |
| 0 | 72 | Gleichgewicht (Ruhezustand) |
| −5 | 65 | Normale Trainingsbelastung |
| −20 | 42 | Deutliche Ermüdung |
| −30 | 27 | Starke Erschöpfung |

**Für den User:**
- **Score > 80** → ausgeruht, intensive Einheiten möglich
- **Score 60–80** → im Training, normaler Bereich
- **Score < 50** → Ermüdung, Erholung empfohlen

**Quellen:**
- Sally Edwards (1993): *Heart Rate Monitor Training*
- Banister EW & Calvert TW (1991): *Can J Sport Sci* 17(1):9
- Statistical flaws of the fitness-fatigue model. *Sci Rep* (2025) doi:10.1038/s41598-025-88153-7

**Implementiert in:** `ml-service/src/models/energy_metrics.py`

---

### 5.2 Autonome Energie — Vagaler Tonus (ANS-Erholung)

**Was es misst:** Erholungsstatus des autonomen Nervensystems via RMSSD.
Der einzelne verlässlichste Marker laut Literatur (HRV4Training, Kubios 2024).

**Wichtig:** Kein Vergleich mit fremden Werten — nur mit **deiner eigenen 90-Tage-Baseline**.
LF/HF-Ratio wird bewusst nicht verwendet (kein valider Marker für < 5-Minuten-Fenster).

**Formel:**
```
# Schritt 1: Log-Normierung (RMSSD ist rechtsschief verteilt)
HRV_raw = ln(hrv_last_night) × 20

# Schritt 2: 7-Tage-Rolling-Mean (Plews et al. 2013, robuster als Einzeltag)
# Fallback für neue User (<14 Punkte): nur letzter Wert
current_mean = Σ HRV_raw[-7:] / 7

# Schritt 3: Persönliche 90-Tage-Baseline (exkl. der letzten 7 Tage)
baseline_mean = Σ HRV_raw[:-7] / n
baseline_std  = std(HRV_raw[:-7]),  min. 1.0

# Schritt 4: σ-Normierung
deviation = (current_mean − baseline_mean) / baseline_std

# Schritt 5: Score
score = clip(70 + deviation × 15, 0, 100)
```

**Interpretation deviation:**

| deviation | Score | Bedeutung |
|-----------|-------|-----------|
| +2σ | 100 | Deutlich über Norm — exzellente Erholung |
| +1σ | 85 | Über Norm — gut erholt |
| 0σ | 70 | Persönliche Norm |
| −1σ | 55 | Unter Norm — Körper im Stressmodus |
| −2σ | 40 | Deutlich unter Norm — Erholung empfohlen |

**Quellen:**
- Elite HRV (2021): *The 1-10 Relative Balance Score*
- Altini M, HRV4Training (2021): *On HRV and Readiness*
- Plews DJ et al. (2013): *Sports Med* 43(9):773–781

**Implementiert in:** `ml-service/src/models/energy_metrics.py`

---

### 5.3 Kognitive Energie — Schlafschuld (Process S)

**Was es misst:** Kumulierten Schlafmangel der letzten 7 Nächte.
Basiert auf Borbélys Two-Process-Model (1982) — Goldstandard der Schlafforschung.

**PulseBase implementiert nur Process S** (homöostatischer Schlafdruck) als kumulierte
Schlafschuld. Process C (zirkadianer Rhythmus) erfordert Einschlaf-/Aufwachzeiten, die
aktuell nicht für die Berechnung herangezogen werden.

**Formel:**
```
# Schlafschuld pro Nacht (Ziel 7h — NSF-Empfehlung, untere Grenze für Erwachsene)
debt_n = max(0, 7.0 − total_sleep_hours_n)

# Kumulierte 7-Tage-Schuld
total_debt = Σ debt_n  für n in [letzte 7 Nächte]

# Score
score = clip(100 − total_debt × 6, 0, 100)
# Kalibrierung: 6 Punkte / Stunde Schulden
```

**Beispielwerte:**

| Schlafmuster | Schuld | Score |
|-------------|--------|-------|
| 7× 8h | 0h | 100 |
| 7× 7h | 0h | 100 |
| 7× 6h | 7h | 58 |
| 7× 5h | 14h | 16 |
| 3× 8h + 4× 6h | 4h | 76 |

**Quellen:**
- Borbély AA (1982): *Human Neurobiology* 1(3):195–204
- National Sleep Foundation (2015): *Sleep Duration Recommendations*

**Implementiert in:** `ml-service/src/models/energy_metrics.py`

---

## 6. Body Battery Custom — Fresh-State-Modell

**Modell-Key:** `body_battery_custom`
**Implementiert in:** `ml-service/src/models/body_battery.py`

Ersetzt Garmins proprietären Body-Battery-Score (Firstbeat) durch ein transparentes Modell.
Das frühere Banister-Akkumulationsmodell (v1) führte bei mehrtägiger Ruhe zu Plateaus
bei Score=100 und spiegelte Tageserholung nicht korrekt wider.

### Schlafqualitätsfaktor

```
# Phasen-Zielwerte: Tiefschlaf 20%, REM 25% der Schlafdauer (Walker 2017)
deep_score    = min(1.0, (deep_h / total_h) / 0.20)
rem_score     = min(1.0, (rem_h  / total_h) / 0.25)

sleep_quality = 0.40 × min(1.0, total_h / 7.5)              # Dauer 40%
              + 0.60 × (0.55 × deep_score + 0.45 × rem_score) # Phasen 60%

# Fallback: wenn keine Phasendaten → reine Dauer
```

### Tageszustand (Fresh-State)

```
# HRV-Faktor: letzte Nacht vs. persönliche 30-Tage-Baseline
hrv_factor = min(1.0, hrv_last_night / hrv_baseline)   # Fallback 0.5

# Tageszustand aus aktueller Physiologie (max 100 bei Idealwerten)
fresh = 40 + sleep_quality × 35 + hrv_factor × 25

# 70% Fresh + 30% Trägheit vom Vortag — verhindert Akkumulationsplateau
# activity_drain = TRIMP × 0.5 (max 40); stress_drain = (avg_stress−25) × 0.2
score = clamp(0.30 × prev + 0.70 × fresh − activity_drain − stress_drain, 5, 100)
```

**Wissenschaftlicher Status:** Einzelkomponenten validiert (HRV ✅, Schlafphasen ✅,
TRIMP-Drain ✅). Composite-Aggregation heuristisch — kein Hersteller (Oura, WHOOP, Garmin)
veröffentlicht klinisch validierte Formel (Wearable Composite Health Scores Require
Validation, biosourcesoftware.com 2025).

**Intraday-Verlauf:** Nicht replizierbar (braucht kontinuierliches HRV). Tages-Eröffnungswert
nach Schlaf gut approximierbar.

**Backfill nach Modellwechsel:** `make backfill-battery`

**Quellen:**
- Walker M (2017). *Why We Sleep* — sleep stage targets
- Dijk DJ, Czeisler CA (1995). *J Neurosci* 15(5):3526 — SWS/REM physiology
- Plews DJ et al. (2013). *Sports Med* 43(9):773 — HRV vs. baseline
- Scientific Reports (2025): doi:10.1038/s41598-025-88153-7 — FFM statistical flaws

---

## 7. Weitere Algorithmen

Kurzdokumentation der restlichen Modelle:

| Modell | Kern-Logik | Lookback |
|--------|-----------|----------|
| **ACWR** | ATL/CTL-Ratio; Zonen <0.8/0.8–1.3/1.3–1.5/>1.5 | 50 Tage |
| **Training Monotony** | Foster (1998): mean(TRIMP)/σ(TRIMP); Strain = Σ×Monotony | 7 Tage |
| **Sleep Consistency** | Zirkuläre σ (Rayleigh R) auf Einschlaf-/Aufwachzeit — behandelt Mitternachts-Wraparound korrekt; score=100−σ_wake×15−σ_sleep×10 | 14 Tage |
| **SpO2 Trend** | Lineare Regression auf SpO2-History; Apnoe-Flag wenn min_spo2 < 90% in ≥2 Nächten | 7 Tage |
| **Autonomer Stressindex** | HRV σ-Score invertiert + Garmin avg_stress (75/25 blend — Garmin-Stress ist HRV-abgeleitet, daher gering gewichtet) | 90 Tage |
| **Running Economy** | Z-Score auf Bodenkon­takt­zeit, vertikale Oszillation, vertikales Verhältnis | kein festes Zeitfenster; jüngste Aktivitäten, Top 5 verwendet |
| **HRV Recovery** | TRIMP-Peak-Detection (>1.5×mean); ΔHRV/Tag in 7-Tage-Fenster post-Peak | 60 Tage |
| **Anomalie-Erkennung** | Z-Score: z=(x−μ)/σ; threshold 2.0σ; min. 7 Punkte; 31 Tage History | 31 Tage |
| **Pearson-Korrelation** | 3 Paare: Schlaf→HRV, Schlaf→RHR, Body-Battery→RHR; min. 10 Paare; r≥0.7 stark | 90 Tage |

---

## 8. Datenverfügbarkeit

| Input | Verfügbar |
|-------|-----------|
| `activities.{avg_hr, duration_seconds, max_hr}` | ✅ |
| `daily_summary.{resting_hr, steps, avg_stress, spo2_avg}` | ✅ |
| `sleep_sessions.{total_sleep_seconds, deep_sleep_seconds, rem_sleep_seconds, awake_seconds, start_time}` | ✅ |
| `hrv_daily.{hrv_last_night, hrv_weekly_avg}` | ✅ |
| `activity_records.heart_rate` (1 Hz) | ✅ |
| `users.{sex, date_of_birth}` | ✅ (V12) |
| RR-Intervall-Rohdaten (RMSSD selbst berechnen) | ❌ |
| Kontinuierliches HRV intraday | ❌ |
| Wattsensor-Daten (Radfahren) | 🟡 `avg_power` vorhanden |

---

## Quellen

| Methode | Quelle |
|---------|--------|
| Edwards TRIMP | Sally Edwards (1993) |
| Banister TRIMP | Banister & Calvert (1991); *Can J Sport Sci* 17(1):9 |
| CTL/ATL/TSB | TrainingPeaks; Busso (2003), *Med Sci Sports Exerc* |
| ACWR | Gabbett (2015+); *Br J Sports Med* |
| Training Monotony | Foster et al. (1996); *Eur J Appl Physiol* |
| Ithlete HRV Score | Elite HRV; Altini (HRV4Training) |
| HRV Baseline | Plews DJ et al. (2013); *Sports Med* 43(9):773 |
| Sleep Score | COROS Sleep Quality; *NSF Sleep Duration* (2015) |
| Body Battery | Walker M (2017); Dijk & Czeisler (1995); Plews (2013) |
| FFM-Kritik | *Sci Rep* (2025) doi:10.1038/s41598-025-88153-7 |
| Sleep Consistency | Phillips AJK et al. (2017); *Sci Adv* 3:e1601666 |
| Borbély Process S | Borbély AA (1982); *Hum Neurobiol* 1(3):195 |
| Running Economy | Anderson T (1996); *Sports Med* 22(2):76 |
| HRV Recovery | Plews et al. (2013); *Sports Med* |
| W' Balance (anaerob, nicht implementiert) | Skiba et al. (2012) |
