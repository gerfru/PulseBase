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
duration_score = min(100, duration_h / 8.0 × 100)          # optimal bei 8h
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
baseline_mean = exponentiell gewichteter Mittelwert (90-Tage, Neueres zählt mehr)
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
- `users.sex` ❌ (fehlt — für Koeffizienten k und b)

**Alternative ohne Geschlecht:** Edwards TRIMP (Sally Edwards, 1993) — einfacher, zonenbasiert:

```
TRIMP = Σ(Minuten_in_Zone × Zonenkoeffizient)
Zone 1 (50–60% HRmax) × 1 ... Zone 5 (90–100%) × 5
```

Weniger physiologisch präzise (willkürliche Koeffizienten), aber kein Geschlecht nötig
und direkt aus Sekunden-HR in `activity_records` berechenbar.

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

### Wissenschaftlich fundiertes Ersatz-Modell

Drei publizierte Bausteine kombiniert:

```
Readiness = w₁ × HRV_Factor + w₂ × Sleep_Factor + w₃ × Recovery_Factor

Gewichte (Vorschlag, anpassbar):
  w₁ = 0.40  (HRV spiegelt autonome Erholung am direktesten wider)
  w₂ = 0.35  (Schlaf ist der primäre Erholungsmechanismus)
  w₃ = 0.25  (Trainingsbelastung als Kontext)
```

**HRV_Factor (0–100) nach Ithlete/Elite HRV:**
```
HRV_Score_raw = ln(hrv_last_night) × 20
HRV_Factor    = (HRV_Score_raw − Baseline_mean) / Baseline_std
              → normiert auf 0–100 relativ zur persönlichen Norm
```

**Sleep_Factor (0–100) — eigener Sleep Score (s. oben)**

**Recovery_Factor (0–100) aus TSB:**
```
Recovery_Factor = 50 + TSB × 1.5    # TSB ≈ ±30 typisch → ergibt 5–95
                  geclippt auf [0, 100]
```

**Tages-Verlauf:** Body Battery Intraday = nicht direkt replizierbar (braucht
kontinuierliches HRV), aber der **Tages-Eröffnungswert** (nach Schlaf) ist gut approximierbar.

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

**Einfache praktische Berechnung aus Schlafdaten:**
```python
# Schlafschuld (kumulierter Schlafmangel):
OPTIMAL_SLEEP = 8.0  # Stunden
sleep_debt_today = max(0, OPTIMAL_SLEEP − total_sleep_hours)
sleep_debt_7d    = Σ max(0, OPTIMAL_SLEEP − sleep_hours_i) for i in last 7 days

# Kognitiver Score nach dem Aufwachen (t=0):
cognitive_base = max(0, 100 − sleep_debt_7d × 6)   # 6 Punkte je Stunde kumulierter Schuld

# Sleep Inertia: 30 Minuten post-wake Einschränkung (~15% Degradierung, linear normalisierend)
# Nach 30 min vollständig abgeklungen — für Werte nach Aufwachen relevant
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

Beide wären **optionale** Felder — ohne sie können wir Edwards TRIMP (keine Koeffizienten nötig)
und einen sex-agnostischen HRV-Status berechnen, aber die Präzision steigt deutlich mit diesen Angaben.

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
| 5 | **TRIMP + CTL/ATL/TSB** | 2 Wochen | Aktivitäts-HR (✅ vorhanden) + `users.age/sex` (❌ fehlt) | Training Status + Readiness-Grundlage |
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
