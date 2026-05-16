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
- TrainingPeaks: https://www.trainingpeaks.com/learn/articles/applying-the-numbers/

**Formel:**

```
# Schritt 1: Heart Rate Reserve Fraction (HRr)
HRr = (avg_hr_aktivität − resting_hr) / (hrmax − resting_hr)

# Schritt 2: TRIMP pro Aktivität (Edwards, ohne Geschlechtskoeffizienten)
TRIMP = duration_min × HRr × (HRr × 4 + 1)

# Schritt 3: Exponentiell gewichteter Mittelwert (Banister, 1991)
ATL_t = ATL_{t-1} × e^(−1/7)  + TRIMP_t × (1 − e^(−1/7))   # τ = 7 Tage
CTL_t = CTL_{t-1} × e^(−1/42) + TRIMP_t × (1 − e^(−1/42))  # τ = 42 Tage

# Schritt 4: TSB (Training Stress Balance)
TSB = CTL − ATL

# Schritt 5: Score
score = clip(50 + TSB × 1.5, 0, 100)
```

**Parameter:**
- HRmax: `MAX(activities.max_hr)` der letzten 12 Monate; Fallback 190 bpm
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
- Banister TRIMP wäre präziser (geschlechtsspezifische Exponentialkurve), benötigt aber `users.sex`
- avg_hr statt Sekunden-HR; bei Ausdauer-Sport (konstante Intensität) gute Näherung

---

### Autonom: Ithlete / Elite HRV Score (normiert auf persönliche Baseline)

**Quellen:**
- Elite HRV (2021): The 1-10 Relative Balance Score.
  https://help.elitehrv.com/article/57-the-1-10-relative-balance-score
- Altini M (HRV4Training, 2021): On Heart Rate Variability and Readiness.
  https://medium.com/@altini_marco/on-heart-rate-variability-hrv-and-readiness-394a499ed05b

**Formel:**

```
# Schritt 1: Log-Normierung (RMSSD ist rechtsschief verteilt)
HRV_raw = ln(hrv_last_night) × 20

# Schritt 2: Persönliche 90-Tage-Baseline (exkl. heutiger Wert)
baseline_mean = Σ HRV_raw / n
baseline_std  = √(Σ(HRV_raw − mean)² / n), min. 1.0

# Schritt 3: σ-Normierung
deviation = (HRV_raw_heute − baseline_mean) / baseline_std

# Schritt 4: Score
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

## Was noch fehlt (Roadmap)

| Erweiterung | Status |
|-------------|--------|
| Banister TRIMP (präziser, geschlechtsspezifisch) | ✅ Implementiert als `training_effect_custom` — `users.sex` + `users.date_of_birth` in V12 migriert |
| HRmax via Altersformel (Fallback) | ✅ `users.date_of_birth` vorhanden; Alter aus Geburtsdatum berechenbar |
| Borbély Process C (Zirkadian) | Offen — Einschlaf-/Aufwachzeiten müssten explizit gespeichert werden |
| 7-Tage gleitendes Baseline-Fenster HRV | Offen — derzeit 90 Tage fix |
