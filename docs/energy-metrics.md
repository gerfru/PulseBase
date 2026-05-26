# Energie-Metriken

PulseBase berechnet drei eigene Energie-Dimensionen transparent nach publizierten
wissenschaftlichen Methoden — unabhängig von Garmins proprietären Firstbeat-Algorithmen.

Alle Berechnungen liegen offen in
[`ml-service/src/models/energy_metrics.py`](../ml-service/src/models/energy_metrics.py).

---

## Warum eigene Berechnung?

Garmin liefert Body Battery, Training Status und HRV-Status als Blackbox.
Die genauen Formeln sind nicht öffentlich. PulseBase ersetzt diese durch drei
separate, nachvollziehbare Dimensionen — mit zitierbaren Quellen für jede Formel.

---

## Für jeden verständlich

### Physische Energie — Wie viel habe ich nach meinem Training noch im Tank?

Stell dir ein Sparkonto vor: Jedes Training hebt Geld ab (Ermüdung), jeder Ruhetag zahlt
Zinsen ein (Erholung). Das Konto erholt sich langsam (6 Wochen um sich aufzubauen),
verbraucht sich aber schnell (1 Woche um zu sinken).

- **Score ≈ 50** → du trainierst und erholst dich im Gleichgewicht
- **Score > 70** → du bist ausgeruht, evtl. zu wenig Training
- **Score < 30** → anhaltende Ermüdung, Erholung empfohlen
- **Unter der Zahl** steht TSB (Training Stress Balance): positiv = erholt, negativ = ermüdet

### Autonome Energie — Wie gut hat sich mein Nervensystem erholt?

Dein Herz schlägt nicht gleichmäßig wie ein Metronom — die kleinen Schwankungen zwischen
den Schlägen zeigen, ob dein Körper im Erholungsmodus ist. Je mehr HRV, desto mehr
„Nerv zum Entspannen" hat dein System.

Wichtig: Wir vergleichen nicht mit fremden Werten, sondern nur mit **deiner eigenen Norm**.
Ein HRV-Wert von 35 ms kann für dich gut oder schlecht sein — entscheidend ist, ob er
höher oder tiefer ist als deine persönlichen letzten 90 Tage.

- **Score ≈ 50** → heute ist dein HRV auf deiner persönlichen Durchschnittslinie
- **Score > 70** → HRV über Norm, Nervensystem gut erholt
- **Score < 30** → HRV unter Norm, Körper im Stressmodus
- **Unter der Zahl** steht die Abweichung in σ (Standardabweichungen): +1σ = ungewöhnlich gut

### Kognitive Energie — Wie viel Schlafschuld trage ich mit mir?

Schlafmangel akkumuliert sich wie ein Rucksack. Jede Nacht mit zu wenig Schlaf kommt
obendrauf. Vollständiger Schlaf baut ihn wieder ab — aber nur wenn du wirklich genug schläfst.

- **Score 100** → keine Schlafschuld in den letzten 7 Nächten
- **Score 70** → etwa 5 Stunden kumulierter Schlafmangel (z.B. 5× 1h zu wenig)
- **Score 40** → rund 10 Stunden kumulierter Schlafmangel
- **Unter der Zahl** stehen die gesamten Stunden Schlafschuld der letzten 7 Nächte

---

## Technische Spezifikation

### Physisch: Edwards TRIMP + Banister Fitness-Fatigue-Modell

**Quellen:**
- Sally Edwards (1993): Heart Rate Monitor Training
- Banister EW & Calvert TW (1991): Planning for future performance. Can J Sport Sci 17(1):9
- TrainingPeaks: <https://www.trainingpeaks.com/learn/articles/applying-the-numbers/>

**Formel:**

```
# Schritt 1: Heart Rate Reserve Fraction (HRr)
HRr = (avg_hr_aktivität − resting_hr) / (hrmax − resting_hr)

# Schritt 2: Edwards TRIMP pro Aktivität (kein Geschlechtskoeffizient nötig)
TRIMP = duration_min × HRr × (HRr × 4 + 1)

# Schritt 3: Exponentiell gewichteter Mittelwert (Banister, 1991)
ATL_t = ATL_{t-1} × e^(−1/7)  + TRIMP_t × (1 − e^(−1/7))   # τ = 7 Tage
CTL_t = CTL_{t-1} × e^(−1/42) + TRIMP_t × (1 − e^(−1/42))  # τ = 42 Tage

# Schritt 4: TSB (Training Stress Balance / Form)
TSB = CTL − ATL

# Schritt 5: Score
score = clip(50 + TSB × 1.5, 0, 100)
```

**Parameter:**
- HRmax: `MAX(activities.max_hr)` aus der Aktivitäts-History; Fallback 190 bpm
- Resting HR Fallback: 60 bpm wenn kein Wert vorhanden
- Fenster: 50 Tage täglich dekayend (dense-date-Walk)

**TSB-Interpretation:**

| TSB | Bedeutung |
|-----|-----------|
| > +10 | Sehr erholt / Wettkampfform |
| +5 bis +10 | Gut erholt |
| 0 bis +5 | Gleichgewicht |
| −5 bis 0 | Normale Trainingsbelastung |
| < −10 | Deutliche Ermüdung |

**Bekannte Vereinfachungen:**
- avg_hr statt Sekunden-HR; bei Ausdauer-Sport (konstante Intensität) gute Näherung
- Genauere Variante mit Banister TRIMP (geschlechtsspezifisch) verfügbar über `/api/training-load`

---

### Autonom: Ithlete / Elite HRV Score (normiert auf persönliche Baseline)

**Quellen:**
- Elite HRV (2021): The 1-10 Relative Balance Score.
  <https://help.elitehrv.com/article/57-the-1-10-relative-balance-score>
- Altini M (HRV4Training, 2021): On Heart Rate Variability and Readiness.
  <https://medium.com/@altini_marco/on-heart-rate-variability-hrv-and-readiness-394a499ed05b>

**Formel:**

```
# Schritt 1: Log-Normierung (RMSSD ist rechtsschief verteilt)
HRV_raw = ln(hrv_last_night) × 20

# Schritt 2: 7-Tage-Rolling-Mean als "aktueller" Wert (Plews et al. 2013)
# Ab 14 Datenpunkten: Mittelwert der letzten 7 Tage statt Einzeltag
# Fallback für neue User (<14 Punkte): nur letzter Wert
current_mean = Σ HRV_raw[-7:] / 7

# Schritt 3: Persönliche Baseline (Rest der 90-Tage-History, exkl. der letzten 7 Tage)
baseline_mean = Σ HRV_raw[:-7] / n
baseline_std  = √(Σ(HRV_raw − mean)² / n), min. 1.0

# Schritt 4: σ-Normierung
deviation = (current_mean − baseline_mean) / baseline_std

# Schritt 5: Score
score = clip(50 + deviation × 15, 0, 100)
```

**Interpretation deviation:**
- +2σ → score ≈ 80 (sehr gut)
- 0σ → score = 50 (Norm)
- −2σ → score ≈ 20 (deutlich unter Norm)

**Warum NICHT LF/HF-Ratio:**
LF/HF ist kein valider Marker für sympathische Aktivität bei kurzen Zeitfenstern
(< 5 Minuten). Kubios (führende HRV-Software) hat dies 2024 explizit als problematisch
bezeichnet. Wir verwenden ausschließlich RMSSD (`hrv_daily.hrv_last_night`).

---

### Kognitiv: Borbély Two-Process Model (vereinfacht — Process S)

**Quellen:**
- Borbély AA (1982): A two process model of sleep regulation.
  Human Neurobiology 1(3):195-204
- National Sleep Foundation: Sleep Duration Recommendations (2015)

**Modell:**

Das vollständige Borbély-Modell beschreibt Schläfrigkeit durch zwei Prozesse:
- **Process S** (homöostatischer Schlafdruck): steigt während Wachsein an
  (Adenosin-Akkumulation), fällt während Schlaf ab
- **Process C** (zirkadianer Rhythmus): 24h-Oszillation, Peak ~14 Uhr, Tal ~3 Uhr

PulseBase implementiert **nur Process S** als kumulierte Schlafschuld, da Process C
die Einschlaf- und Aufwachzeit erfordert, die aktuell nicht in der DB gespeichert ist.

Process S wird wissenschaftlich korrekt primär durch **SWS (Tiefschlaf)** entladen, nicht
durch reine Schlafdauer. Daher wird ein Qualitätsfaktor aus `sleep_sessions.deep_sleep_seconds`
berechnet — kein proprietärer Garmin-Score, sondern die Rohmessung aus der DB.

**Formel:**

```
# Schlafschuld pro Nacht (Ziel 7h — NSF-Empfehlung, untere Grenze für Erwachsene)
# Qualitätsfaktor entfernt: Garmins Tiefschlaf-Messung (Akzelerometer+HRV) zu unzuverlässig
debt_n = max(0, 7.0 − total_sleep_hours_n)

# Kumulierte 7-Tage-Schuld
total_debt = Σ debt_n  für n in [letzte 7 Nächte]

# Score
score = clip(100 − total_debt × 6, 0, 100)
# Kalibrierung: 6 Punkte / Stunde Schulden → bei ~16.7h Schulden = Score 0
```

**Beispielwerte:**

| Schlafmuster | Schlafschuld | Score |
|-------------|-------------|-------|
| 7× 8h | 0h | 100 |
| 7× 7h | 0h | 100 |
| 7× 6h | 7h | 58 |
| 7× 5h | 14h | 16 |
| 3× 8h + 4× 6h | 4h | 76 |

---

---

## Body Battery Custom: Fresh-State-Modell mit Schlafphasen

**Modell-Key:** `body_battery_custom`
**Datei:** [`ml-service/src/models/body_battery.py`](../ml-service/src/models/body_battery.py)

Ersetzt Garmins proprietären Body-Battery-Score durch ein transparentes Energiemodell.

### Schlafqualitätsfaktor (neu)

```
# Phasen-Zielwerte: Tiefschlaf 20%, REM 25% der Schlafdauer
# (Walker 2017, Dijk & Czeisler 1995)
deep_score    = min(1.0, (deep_h / total_h) / 0.20)
rem_score     = min(1.0, (rem_h  / total_h) / 0.25)

sleep_quality = 0.40 × min(1.0, total_h / 7.5)          # Dauer 40%
              + 0.60 × (0.55 × deep_score + 0.45 × rem_score)  # Phasen 60%

# Fallback: wenn keine Phasendaten → reine Dauer
```

### Fresh-State-Modell (kein Akkumulationsplateau)

```
# HRV-Faktor: letzte Nacht vs. persönliche 30-Tage-Baseline (Plews 2013)
hrv_factor = min(1.0, hrv_last_night / hrv_baseline)   # Fallback 0.5

# Tageszustand aus heutiger Physiologie (max 100 bei Idealwerten)
fresh = 40 + sleep_quality × 35 + hrv_factor × 25

# Fresh 70% + Trägheit vom Vortag 30% — verhindert Akkumulations-Plateau
score = clamp(0.30 × prev + 0.70 × fresh − activity_drain − stress_drain, 5, 100)
```

### Wissenschaftlicher Status (Stand 2025/2026)

Kein Hersteller (Oura, WHOOP, Garmin) veröffentlicht eine klinisch validierte
Composite-Score-Formel — der Algorithmus bleibt immer proprietär. PulseBase verwendet
**validierte Einzelkomponenten** (HRV als Recovery-Indikator ✅, Schlafphasen als
Qualitätsproxy ✅) in einer heuristischen Aggregation. Das frühere Banister-Akkumulationsmodell
hat fundamentale statistische Mängel (Scientific Reports, 2025) und wurde bewusst ersetzt.

**Backfill nach Modellwechsel:** `make backfill-battery`

**Quellen:**
- Walker M (2017). Why We Sleep — sleep stage targets (Deep ~20%, REM ~25%)
- Dijk DJ, Czeisler CA (1995). J Neurosci 15(5):3526–3538 — SWS/REM physiology
- Plews DJ et al. (2013). Sports Med 43(9):773–781 — HRV vs. baseline
- Kellmann M, Kallus KW (2001). Recovery-Stress Questionnaire for Athletes
- Statistical flaws of the fitness-fatigue model. Sci Rep (2025) doi:10.1038/s41598-025-88153-7
- Wearable Composite Health Scores Require Validation. biosourcesoftware.com (2025)

---

## Was noch fehlt (Roadmap)

| Erweiterung | Status |
|-------------|--------|
| Banister TRIMP (präziser, geschlechtsspezifisch) | ✅ Implementiert als `training_effect_custom` — `users.sex` + `users.date_of_birth` in V12 migriert |
| HRmax via Altersformel (Fallback) | ✅ `users.date_of_birth` vorhanden; Alter aus Geburtsdatum berechenbar |
| Borbély Process C (Zirkadian) | Offen — Einschlaf-/Aufwachzeiten müssten explizit gespeichert werden |
| 7-Tage gleitendes Baseline-Fenster HRV | ✅ Implementiert — 7-Tage-Rolling-Mean vs. Rest-Baseline |
| Body Battery Custom — Schlafphasen + Fresh-State | ✅ Implementiert — `body_battery.py` v2 mit deep_h + rem_h |
