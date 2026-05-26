# Eigenberechnete Metriken — Forschungsdokumentation

Ziel: Welche von Garmin gelieferten **berechneten Werte** können wir durch transparente,
wissenschaftlich publizierte Methoden selbst berechnen — unabhängig von Garmin's proprietären
Algorithmen (Firstbeat)?

---

## Übersicht: Alle berechneten Metriken in PulseBase

| Metrik | Tabelle / Spalte | Was Garmin macht | Machbarkeit |
|--------|-----------------|------------------|-------------|
| `sleep_score` | `sleep_sessions` | Gewichteter Score aus Schlafphasen | ✅ EASY |
| `hrv_status` | `hrv_daily` | BALANCED / UNBALANCED / LOW / POOR | ✅ EASY |
| `intensity_moderate` | `daily_summary` | WHO-Intensitätsminuten | ✅ EASY |
| `intensity_vigorous` | `daily_summary` | WHO-Intensitätsminuten | ✅ EASY |
| `aerobic_effect` | `activities` | EPOC-basierter Score 0–5 | 🟡 FEASIBLE (Banister TRIMP) |
| `training_status` | `daily_summary` | PRODUCTIVE / MAINTAINING / … | 🟡 FEASIBLE (CTL/ATL) |
| `body_battery_high/low` | `daily_summary` | Energie-Level 0–100 (Firstbeat) | 🟡 FEASIBLE (Kombination) |
| `anaerobic_effect` | `activities` | Anaerober Trainingseffekt 0–5 | 🔴 HARD (Power-Sensor nötig) |
| `hrv_last_night` | `hrv_daily` | RMSSD aus Nacht-RR-Intervallen | 🔴 HARD (keine RR-Rohdaten) |

---

## 1. Intensitätsminuten (moderate / vigorous)

**Methode:** WHO / CDC Herzfrequenz-Zonen — vollständig publiziert, kein proprietärer Algorithmus.

```
Moderat:  50–70 % HRmax  (alternativ: 64–76 % nach CDC)
Vigoros:  70–85 % HRmax  (alternativ: 77–93 % nach CDC)

Intensitätsminuten = Σ Sekunden_in_Zone / 60
```

**Benötigt:**
- Sekunden-HR aus `activity_records.heart_rate` ✅
- HRmax — aus `MAX(activities.max_hr)` pro User ableitbar ✅ (oder Formel: 220 − Alter)

**Fehlend:** `users.age` (für Formel-Fallback wenn kein max_hr vorhanden)

---

## 2. Schlaf-Score (0–100)

**Methode:** Gewichtete Schlafphasen-Formel (COROS-Ansatz, publiziert).

Optimale Schlafverteilung für Erwachsene (Lit.):
- Tiefschlaf: 15–25 % der Gesamtschlafzeit
- REM: 20–25 %
- Leichtschlaf: 50–60 %
- Wach-Anteil: < 5 %

```
deep_pct  = deep_sleep_seconds  / total_sleep_seconds
rem_pct   = rem_sleep_seconds   / total_sleep_seconds
wake_pct  = awake_seconds       / total_sleep_seconds
duration_h = total_sleep_seconds / 3600

# Komponenten (je 0–100)
deep_score     = min(100, deep_pct / 0.20 × 100)           # optimal bei 20%
rem_score      = min(100, rem_pct  / 0.22 × 100)           # optimal bei 22%
duration_score = min(100, duration_h / 7.0 × 100)          # optimal bei 7h (NSF-Empfehlung)
wake_penalty   = max(0, 100 − wake_pct × 500)              # -5 Punkte je 1% Wachanteil

score = deep_score × 0.35 + rem_score × 0.25 + duration_score × 0.25 + wake_penalty × 0.15
```

**Benötigt:** `deep_sleep_seconds`, `rem_sleep_seconds`, `awake_seconds`, `total_sleep_seconds` ✅

**Vorteil:** Transparent — der User sieht, warum der Score hoch oder niedrig ist.

---

## 3. HRV-Status (BALANCED / UNBALANCED / LOW / POOR)

**Methode:** Garmin's Logik ist publiziert — Vergleich aktueller RMSSD mit persönlicher
rollender Baseline (keine absoluten Cutoffs, sondern individuelle Standardabweichungen).

```
baseline_mean = Mittelwert der 90-Tage-History exkl. der letzten 7 Tage (Plews et al. 2013)
current_mean  = 7-Tage-Rolling-Mean der letzten 7 Tage (robuster als Einzeltag)
baseline_std  = Standardabweichung der Baseline

deviation = (hrv_last_night − baseline_mean) / baseline_std

BALANCED:    deviation ≥ −0.5   UND  hrv_last_night ≥ Perzentile 50 (Altersgruppe)
UNBALANCED:  −1.5 ≤ deviation < −0.5
LOW:         deviation < −1.5   ODER hrv_last_night sehr niedrig absolut
POOR:        anhaltend niedriger über mehrere Tage
```

**Benötigt:** `hrv_daily.hrv_last_night` (mindestens 21 Tage History) ✅

**Fehlend:** `users.age` + `users.sex` für Alters-/Geschlechts-Perzentilen (optional, verbessert Klassifikation)

---

## 4. Training Load — Banister TRIMP (aerober Trainingseffekt)

Garmin verwendet Firstbeat's proprietäres EPOC-Modell. Der publizierte
wissenschaftliche Goldstandard dafür ist **Banister TRIMP (1991)**:

```
HRr = (HR_exercise − HR_rest) / (HR_max − HR_rest)   # Heart Rate Reserve Fraktion

TRIMP = Dauer(min) × HRr × k × e^(b × HRr)

k (Skalierungsfaktor): 0.64 (männlich), 0.86 (weiblich)
b (Steigung):          1.92 (männlich), 1.67 (weiblich)
```

Kalibriert an Blutlaktat-Kurven — nicht willkürliche Zonen, sondern physiologisch begründet.
Validiert in hunderten Studien seit 1991.

**Benötigt:**
- `activities.avg_hr` ✅
- `activities.duration_seconds` ✅
- `daily_summary.resting_hr` ✅
- `activities.max_hr` (oder aus History ableiten) ✅
- `users.sex` ✅ (V12 migriert — `users.sex TEXT` mit Wert `'m'`/`'f'`/`'diverse'`)

---

## 5. Training Status (CTL / ATL / TSB) — Banister Fitness-Fatigue-Modell

Vollständig publiziertes Modell (Banister & Calvert, 1991; TrainingPeaks; Runalyze).

```
ATL (Acute Training Load / Fatigue):
  ATL_t = ATL_(t-1) × e^(−1/7) + TRIMP_t × (1 − e^(−1/7))
  → 7-Tage exponentiell gewichteter TRIMP-Durchschnitt

CTL (Chronic Training Load / Fitness):
  CTL_t = CTL_(t-1) × e^(−1/42) + TRIMP_t × (1 − e^(−1/42))
  → 42-Tage exponentiell gewichteter TRIMP-Durchschnitt

TSB (Training Stress Balance / Form):
  TSB = CTL − ATL
```

**Interpretation TSB:**

| TSB | Bedeutung |
|-----|-----------|
| > +10 | Sehr erholt, Topform |
| +5 bis +10 | Wettkampfform |
| 0 bis +5 | Optimales Gleichgewicht |
| −5 bis 0 | Normale Trainingsbelastung |
| < −10 | Deutliche Ermüdung, Erholung empfohlen |

**Benötigt:** TRIMP pro Aktivität (siehe oben) — kumuliert über 42+ Tage History.
Kalt-Start: Die ersten 6 Wochen baut sich CTL erst auf.

---

## 6. Energie / "Body Battery" — transparente Alternative

Garmin's Body Battery ist ein Firstbeat-Algorithmus ohne öffentliche Spezifikation.
Ziel ist ein einfacher, verständlicher Energiestatus nach dem Aufwachen und über den Tag.

> **Status:** ✅ Implementiert als `body_battery_custom` — Fresh-State-Modell v2 (Mai 2026).
> Das frühere Banister-Akkumulationsmodell wurde ersetzt (wissenschaftliche Grundlage
> und Plateau-Problem, siehe unten). Formel → `ml-service/src/models/body_battery.py`.

### Implementiertes Modell: Fresh-State (v2, Mai 2026)

Ersetzt das frühere lineare Akkumulationsmodell, das bei mehrtägiger Ruhe zu
Plateaus bei Score=100 geführt hat (fundamentale statistische Mängel des Banister-FFM,
Scientific Reports 2025, doi:10.1038/s41598-025-88153-7).

```
# Schlafqualität: Phasen 60% + Dauer 40%  (Walker 2017, Dijk & Czeisler 1995)
deep_score    = min(1.0, (deep_h / total_h) / 0.20)
rem_score     = min(1.0, (rem_h  / total_h) / 0.25)
sleep_quality = 0.40 × min(1.0, total_h / 7.5)
              + 0.60 × (0.55 × deep_score + 0.45 × rem_score)

# HRV-Faktor: letzte Nacht vs. 30-Tage-Baseline  (Plews et al. 2013)
hrv_factor = min(1.0, hrv_last_night / hrv_baseline)

# Tageszustand aus aktueller Physiologie (max 100 bei Idealwerten)
fresh = 40 + sleep_quality × 35 + hrv_factor × 25

# 70% Fresh + 30% Trägheit vom Vortag — verhindert Akkumulationsplateau
score = clamp(0.30 × prev + 0.70 × fresh − activity_drain − stress_drain, 5, 100)
```

**Wissenschaftlicher Status:** Einzelkomponenten validiert (HRV ✅, Schlafphasen ✅,
TRIMP-Drain ✅); Composite-Aggregation heuristisch — kein Hersteller (Oura, WHOOP,
Garmin) veröffentlicht klinisch validierte Formel (Wearable Composite Health Scores
Require Validation, biosourcesoftware.com 2025).

**Tages-Verlauf:** Intraday-Granularität nicht replizierbar (braucht kontinuierliches
HRV). Der Tages-Eröffnungswert nach Schlaf ist gut approximierbar.

### Früheres Modell (v1, ersetzt)

Das frühere Modell verwendete eine lineare Banister-Akkumulation
(`score = clamp(prev + recovery − drains, 5, 100)`), was bei mehrtägiger Ruhe
zu dauerhaften Plateaus bei 100 führte und Tageserholung nicht korrekt widerspiegelte.

---

## 7. Anaerober Trainingseffekt

Realistische Einschätzung: **Ohne Wattsensor schwer replizierbar.**

Das beste publizierte Modell ist **W' Balance (Skiba, 2012)**:
```
W'_balance(t) = W'₀ − Σ(max(0, Power(t) − CP))
Recovery:  W' × (1 − e^(−t_recovery / τ))   τ ≈ 400–600s
```

Benötigt: Critical Power CP (Watt) + W' (Joule) aus einem Rampentest.
Wir haben `avg_power` für Radfahren — für Laufen/Schwimmen fehlt der Wattmesser.

**Fallback ohne Wattsensor:** Zone 4/5 Minuten als Proxy für anaerobe Belastung.
Kein wissenschaftlich validiertes Äquivalent zu Training Effect 0–5.

---

## 8. RMSSD (HRV Last Night) — Neuberechnung

**Nicht sinnvoll mit vorhandenen Daten.**

- RMSSD benötigt RR-Intervalle (Beat-to-beat in Millisekunden)
- `activity_records.heart_rate` = 1 Hz (1 Messung/Sekunde) — zu grob für verlässliche RMSSD
- Garmin's Wert (`hrv_last_night`) basiert auf der optischen PPG-Nachtmessung — besser als Rekonstruktion
- Fazit: Garmin-Wert als Quelle behalten

---

## 9. Drei-Säulen-Energie-Modell: Physisch — Autonom — Kognitiv

Garmin's Body Battery ist eine Blackbox. Eine transparente Alternative kann aus drei
wissenschaftlich validierten Dimensionen aufgebaut werden, die unabhängig voneinander
beobachtbar und berechenbar sind.

---

### 9.1 Physische Energie — Fitness-Fatigue (aerob)

**Was es misst:** Wie viel aerobe Kapazität ist nach Trainingsbelastung der letzten Wochen
noch vorhanden? Kernmechanismus: Superkompensation — nach Stress folgt Erholung mit
kurzfristigem Kapazitätszuwachs.

**Modell:** Banister Fitness-Fatigue (s. Abschnitt 5, CTL/ATL/TSB)

```
Physical_Energy = f(TSB)
                = 50 + TSB × 1.5    # TSB typisch ±30 → ergibt Bereich 5–95
                  geclippt auf [0, 100]
```

Alternativ direkter Ausgang: TRIMP-Akutlast / TRIMP-Chronischlast als Verhältnis
(Gabbett Acute:Chronic Workload Ratio):

```
ACWR = ATL / CTL
1.0–1.3 → optimales Trainingsfenster
> 1.5   → Verletzungsrisiko erhöht (Red Zone)
< 0.8   → Detraining, Formverlust
```

**Herzfrequenz-Erholung (HRR60)** als direkt messbarer physischer Regenerationsmarker:
```
HRR60 = HR_peak − HR_1min_nach_Ende
> 20 bpm → gute kardivaskuläre Fitness / ausreichend erholt
< 12 bpm → anhaltende Erschöpfung, unvollständige Erholung
```

Benötigt: `activity_records.heart_rate` in letzten Sekunden + 1 Minute nach Aktivitätsende
(Garmin liefert dies nicht direkt — bräuchte letzten `max_hr`-Zeitpunkt + Folgedaten)

**Datenstatus physische Energie:**

| Input | Verfügbar |
|-------|-----------|
| TRIMP (Edwards) | ✅ aus avg_hr + duration |
| CTL/ATL/TSB | ✅ berechenbar |
| ACWR | ✅ berechenbar |
| HRR60 | ❌ Rohdaten fehlen |
| VO2max-Schätzung | 🟡 aus Cooper-Test oder pace/HR-Regression |

---

### 9.2 Autonome Energie — Vagaler Tonus (ANS-Erholung)

**Was es misst:** Den Erholungsstatus des autonomen Nervensystems. Der Parasympathikus
(Ruhemodus) erhöht HRV — höhere RMSSD = besser erholtes System.

**Der einzelne verlässlichste Marker: RMSSD über Nacht**

Aus der Literatur (HRV4Training, Marco Altini; Ithlete; Kubios 2024):
- RMSSD ist robuster als LF/HF (LF/HF misst NICHT zuverlässig sympathisch/parasympathisch)
- Nur RMSSD aus > 5 Minuten stabilem Schlaf verlässlich
- Normierung auf persönliche Baseline eliminiert inter-individuelle Unterschiede

```
# Normierter HRV-Score (Ithlete / Elite HRV-Methode):
HRV_raw   = ln(hrv_last_night) × 20          # logarithmischer Skalierung wg. rechtsschiefer Verteilung
HRV_Score = (HRV_raw − Baseline_mean_90d) / Baseline_std_90d

# Auf 0–100 skalieren:
ANS_Energy = 50 + HRV_Score × 15   # ±2σ deckt Bereich 20–80 ab
             geclippt auf [0, 100]
```

**Empfehlung aus der Literatur (Marco Altini, HRV4Training):**
HRV sollte NICHT mit Schlaf-Scores oder Trainingslast in einem einzigen Composite-Score
kombiniert werden. Diese Metriken korrelieren unzuverlässig und ein Combined-Score verschleiert,
was tatsächlich die Ursache für schlechtes Wohlbefinden ist.
→ HRV als **eigenständige Dimension** anzeigen, nicht als Faktor in einer Formel.

**LF/HF-Ratio:** Nicht für die Praxis verwenden.
Garmin und andere nutzen sie, aber sie ist kein valider Marker für
sympathische Aktivität bei kurzem Zeitfenster (< 5 Minuten). Kubios selbst (führende
HRV-Software) hat 2024 die klinische Interpretation von LF/HF als problematisch bezeichnet.

**Praktischer PNS-Index (Kubios-ähnlich, ohne proprietäre Gewichte):**
```
PNS_approx = (RMSSD/mean_RR × 1000) + SD1   # SD1 = RMSSD / sqrt(2)
```
Für PulseBase: RMSSD allein (via Garmin `hrv_last_night`) ist ausreichend.

**Datenstatus autonome Energie:**

| Input | Verfügbar |
|-------|-----------|
| `hrv_last_night` (RMSSD) | ✅ |
| 90-Tage Baseline | ✅ aus `hrv_daily` |
| RR-Intervall-Rohdaten (SD1, pNN50) | ❌ nicht in DB |

---

### 9.3 Kognitive Energie — Schlafschuld und zirkadianer Rhythmus

**Was es misst:** Die aktuelle kognitive Leistungsfähigkeit aus der Schlafgeschichte heraus.
Kernmechanismus: Je länger man wach ist, desto mehr Schlafschuld akkumuliert sich (Adenosin-
Anreicherung). Schlaf baut diese ab.

#### Modell: Borbély Two-Process Model (1982) — Goldstandard der Schlafforschung

```
Alertness(t) = Process_C(t) − Process_S(t)

Process S — Homöostatischer Schlafdruck:
  S_steigt  während Wachsein:  dS/dt = +µ    (µ ≈ 0.045/h bei vollem Schlaf)
  S_fällt   während Schlaf:    dS/dt = −µ/r  (r ≈ 5, Schlaf ist 5× effizienter)

  Vereinfacht:
  S_nach_Schlaf    = S_vor_Schlaf × e^(−sleep_hours / 5.0)
  S_nach_Wachsein  = S_wach_start × e^(wake_hours × 0.045)

Process C — Zirkadianer Rhythmus (24h-Oszillation):
  C(t) = A × cos(2π × (t − φ) / 24)
  A ≈ 0.97 (Amplitude), φ ≈ 14h (Peak bei ~14:00 Uhr, Tal bei ~02:00–04:00)
```

**Implementiert in PulseBase (`ml-service/src/models/energy_metrics.py`):**
```python
# Schlafschuld (kumulierter Schlafmangel):
# Ziel 7h: NSF-Empfehlung, untere Grenze für Erwachsene (vorher 8h)
# Qualitätsfaktor entfernt: Garmins Tiefschlaf-Messung (Akzelerometer+HRV) zu unzuverlässig
OPTIMAL_SLEEP = 7.0  # Stunden — NSF-Empfehlung 7–9h, 7h als Mindest-Ziel
sleep_debt_7d = Σ max(0, OPTIMAL_SLEEP − sleep_hours_i) for i in last 7 days

# Kognitiver Score:
cognitive_base = max(0, 100 − sleep_debt_7d × 6)   # 6 Punkte je Stunde kumulierter Schuld
# Beispiel: 7× 6h → 7h Schulden → Score 58

# Nicht implementiert: Sleep Inertia, Process C (Zirkadian) — braucht Einschlaf-/Aufwachzeiten
```

**SAFTE/FAST-Modell (US Army, 2004) als Erweiterung:**
Operationell validiert für kognitive Leistungsfähigkeit bei Schlafentzug/Schichtarbeit.
Berücksichtigt zusätzlich: zirkadianer Phasenlage, Schlafträgheit, kumulative Schuld.
Implementierung: open-source Python via `fastsafte`-Library.

```
Benötigt:
  - Schlafbegin / Schlafende je Nacht  (aus start_time / total_sleep_seconds) ✅
  - Alter (beeinflusst zirkadianen Amplitude)                                   ❌ fehlt
```

**Datenstatus kognitive Energie:**

| Input | Verfügbar |
|-------|-----------|
| `total_sleep_seconds` | ✅ |
| `deep_sleep_seconds`, `rem_sleep_seconds` | ✅ |
| `sleep_sessions.start_time` | ✅ |
| 7-Tage Schlafschuld-Berechnung | ✅ berechenbar |
| Zirkadianer Phasenlage | 🟡 Näherung über Einschlafzeit |
| Alter (Amplitude-Kalibrierung) | ❌ fehlt |

---

### 9.4 Composite-Score: "Energie nach dem Aufwachen"

Kombination der drei Dimensionen in einen einzigen Morgen-Energiewert:

```
Energy_Score = w₁ × Physical_Energy + w₂ × ANS_Energy + w₃ × Cognitive_Energy

Empfohlene Gewichte:
  w₁ = 0.30  (Trainingslast — relevant nach hartem Training, weniger im Ruhezustand)
  w₂ = 0.40  (ANS-Erholung — stärkster direkter Erholungsmarker)
  w₃ = 0.30  (Schlafschuld — verlässlicher Tagesprediktor)
```

**Wichtiger Vorbehalt (nach Marco Altini / HRV4Training):**
Die drei Dimensionen sollten separat angezeigt werden — ein Combined-Score ist für den
User verständlicher als eine einzelne Blackbox-Zahl. Implementierungsempfehlung:
drei Einzelbalken (Physisch / Autonom / Kognitiv) + optionaler Gesamt-Score.

---

## Was fehlt in der Datenbasis

Für eine vollständige eigene Berechnung fehlen zwei Felder in der `users`-Tabelle:

| Feld | Typ | Wofür nötig | Priorität |
|------|-----|-------------|-----------|
| `age` | INTEGER | HRmax-Formel (220−Alter), HRV-Perzentilen | Hoch |
| `sex` | TEXT (`m`/`f`/`diverse`) | Banister TRIMP (Koeffizienten), HRV-Normwerte | Hoch |

`users.sex` ist in V12 als Pflichtfeld migriert — Banister TRIMP mit geschlechtsspezifischen
Koeffizienten (b=1.92/1.67) ist implementiert. `users.age` kann aus `users.date_of_birth` berechnet werden.

HRmax ohne Altersformel: aus `MAX(activities.max_hr)` der letzten 12 Monate ableitbar —
das ist sogar besser als die generische Formel.

---

## Priorisierte Roadmap

| Prio | Metrik | Aufwand | Benötigt | Mehrwert |
|------|--------|---------|----------|----------|
| 1 | **Intensity Minutes** | 1–2 Tage | `activity_records.heart_rate` (✅ vorhanden) | Direkter Vergleich mit Garmin-Wert |
| 2 | **Sleep Score (custom)** | 2–3 Tage | Schlafdauern (✅ vorhanden) | Transparent, kein Garmin-Blackbox |
| 3 | **HRV Status** | 3–5 Tage | `hrv_last_night` + 90d History (✅ vorhanden) | Persönliche Baseline statt absoluter Cutoff |
| 4 | **Readiness / Energie-Score** | 1 Woche | HRV + Sleep Score + TSB | Body-Battery-Ersatz, vollständig transparent |
| 5 | **TRIMP + CTL/ATL/TSB** | ✅ Implementiert | Banister TRIMP + `users.sex` (V12) — `/api/training-load` | Training Status + Readiness-Grundlage |
| 6 | **Aerober Training Effect** | 3–4 Wochen | TRIMP-Grundlage (Prio 5) + VO2max-Schätzung | Ersatz für Garmin Training Effect |

---

## Quellen

| Methode | Quelle |
|---------|--------|
| Banister TRIMP | Banister & Calvert (1991); https://www.trainingimpulse.com/banisters-trimp-0 |
| Edwards TRIMP | Sally Edwards (1993); https://www.trainingimpulse.com/edwards-trimp |
| CTL/ATL/TSB | TrainingPeaks; https://www.trainingpeaks.com/learn/articles/applying-the-numbers-part-3-training-stress-balance/ |
| W' Balance | Skiba et al. (2012); https://pubmed.ncbi.nlm.nih.gov/22382171/ |
| Ithlete HRV Score | https://help.elitehrv.com/article/57-the-1-10-relative-balance-score-morning-readiness |
| HRV4Training | Marco Altini; https://medium.com/@altini_marco/on-heart-rate-variability-hrv-and-readiness-394a499ed05b |
| Session-RPE | Foster et al. (2001); https://pmc.ncbi.nlm.nih.gov/articles/PMC5673663/ |
| WHO Intensity Minutes | https://www.heart.org/en/healthy-living/fitness/fitness-basics/target-heart-rates |
| Sleep Score (COROS) | https://support.coros.com/hc/en-us/articles/30206181626900-Sleep-Quality |
| Acute:Chronic Ratio | Gabbett (2015+); https://www.scienceforsport.com/acutechronic-workload-ratio/ |
