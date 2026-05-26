# ML Deep Dive — Technische Dokumentation

Vollständige technische Spezifikation aller ML-Modelle in PulseBase.
Implementierung: `ml-service/src/models/`, Scheduling: `ml-service/src/main.py`.

Für eine verständliche Erklärung ohne Mathekenntnisse: [eli5.md](eli5.md).

---

## Übersicht der Modelle

| Modell | Typ | Algorithmus | Ziel |
|--------|-----|-------------|------|
| `anomaly_hr` | Anomalieerkennung | Z-Score | Ruhepuls-Ausreißer identifizieren |
| `correlation_sleep_hrv` | Korrelationsanalyse | Pearson r | Schlaf → nächster-Tag-HRV |
| `correlation_sleep_rhr` | Korrelationsanalyse | Pearson r | Schlaf → nächster-Tag-Ruhepuls |
| `correlation_bb_rhr` | Korrelationsanalyse | Pearson r | Body Battery → nächster-Tag-Ruhepuls |
| `readiness_rf` | Regression | Random Forest | Readiness Score für morgen |
| `battery_pattern` | Clustering | k-Means | Energie-Tagesmuster |
| `model_meta_rf` | Metadaten | — | Feature Importances + Trainingsinfos des RF |
| `body_battery_custom` | Algorithmisch | Fresh-State-Modell | Tagesenergie (Schlafphasen + HRV) |

---

## 1. Anomalieerkennung: Z-Score auf Ruhepuls

**Datei:** `ml-service/src/models/anomaly.py`
**Trigger:** Täglich bei Inferenz-Lauf

### Datenbasis

```sql
SELECT resting_hr FROM daily_summary
WHERE user_id = $1
  AND date < CURRENT_DATE
  AND date >= CURRENT_DATE - INTERVAL '31 days'
ORDER BY date
```

Lookback: 31 Tage, exkl. heute. `None`-Werte werden gefiltert.
Minimum: 7 gültige Datenpunkte, sonst `status = "insufficient_data"`.

### Formel

```
μ = (1/n) · Σ xᵢ          (arithmetisches Mittel)
σ = sqrt[(1/n) · Σ(xᵢ − μ)²]  (Standardabweichung der Population)

z = (x_heute − μ) / σ
```

Sonderfall: Wenn `σ < 1.0` → `z = 0.0` (keine relevante Varianz, Division vermeiden).

### Schwellwert

```python
_THRESHOLD = 1.5
is_anomaly = z > _THRESHOLD
```

Begründung für 1.5 statt des üblichen 2.0: Bei n ≈ 30 Datenpunkten ist ein konservativerer
Threshold sinnvoll. Bei Normalverteilung werden damit ~13 % aller Tage als auffällig markiert —
bewusstes Design als "Frühwarnsystem". Nicht zur klinischen Diagnose geeignet.

### Ausgabe (gespeichert in `ml_predictions.metadata`)

```json
{
  "is_anomaly": false,
  "z_score": 1.29,
  "threshold": 1.5,
  "baseline_mean": 43.5,
  "baseline_std": 3.2
}
```

---

## 2. Pearson-Korrelation

**Datei:** `ml-service/src/models/correlation.py`
**Trigger:** Täglich bei Inferenz-Lauf

### Formel

```
r(X, Y) = Σ[(xᵢ − x̄)(yᵢ − ȳ)] / sqrt[Σ(xᵢ − x̄)² · Σ(yᵢ − ȳ)²]
```

Implementierung: `scipy.stats.pearsonr(x, y)` → gibt `(r, p_value)` zurück.
- `r` auf 3 Dezimalstellen gerundet
- `p_value` auf 4 Dezimalstellen gerundet
- Minimum: n ≥ 10 Paare, sonst `status = "insufficient_data"`

### Interpretationsschwellen

| |r|| Interpretation |
|-----|----------------|
| ≥ 0.7 | `stark` |
| ≥ 0.4 | `moderat` |
| ≥ 0.2 | `schwach` |
| < 0.2 | `kein Zusammenhang` |

### Berechnete Korrelationen

#### `correlation_sleep_hrv`

```sql
SELECT s.sleep_score, h_next.hrv_last_night
FROM sleep_sessions s
JOIN hrv_daily h_next ON h_next.date = DATE(s.start_time) + 1
                      AND h_next.user_id = s.user_id
WHERE s.user_id = $1
  AND s.start_time >= NOW() - INTERVAL '90 days'
  AND s.sleep_score IS NOT NULL
  AND h_next.hrv_last_night IS NOT NULL
```

Erwartete Richtung: **positiv** (besserer Schlaf → höherer HRV am Folgetag).

#### `correlation_sleep_rhr`

Wie oben, aber mit `d_next.resting_hr` aus `daily_summary`.
Erwartete Richtung: **negativ** (besserer Schlaf → niedrigerer Ruhepuls am Folgetag).

#### `correlation_bb_rhr`

```sql
SELECT d1.body_battery_high, d2.resting_hr
FROM daily_summary d1
JOIN daily_summary d2 ON d2.date = d1.date + 1
                      AND d2.user_id = d1.user_id
WHERE d1.user_id = $1
  AND d1.date >= CURRENT_DATE - INTERVAL '90 days'
  AND d1.body_battery_high IS NOT NULL
  AND d2.resting_hr IS NOT NULL
```

Erwartete Richtung: **negativ** (höhere Body Battery → niedrigerer Ruhepuls am Folgetag).

### Ausgabe

```json
{
  "r": 0.61,
  "p_value": 0.0031,
  "n": 42,
  "interpretation": "stark"
}
```

---

## 3. Random Forest Readiness Prediction

**Datei:** `ml-service/src/models/readiness.py`
**Inferenz:** Täglich | **Training:** Wöchentlich (Sonntag 03:00)

### Trainings-Target: Regelbasierter Score

Der Random Forest lernt nicht aus einem externen Label, sondern aus einem
regelbasierten Score, der zur Trainingszeit aus mehreren Signalen berechnet wird:

```
T = (w₁·v₁ + w₂·v₂ + w₃·v₃ + w₄·v₄) / Σwᵢ
```

| Signal | Gewicht | Transformation |
|--------|---------|----------------|
| HRV-Status | 30% | BALANCED=100, UNBALANCED=50, LOW=25, POOR=0 |
| Schlaf-Score | 30% | Garmin 0–100, direkt |
| Body Battery High | 20% | 0–100, direkt |
| Avg Stress (invertiert) | 20% | `max(0, 100 − avg_stress)` |

Fehlende Komponenten werden aus der Gewichtssumme herausgerechnet
(kein Imputation des Targets). Gibt `None` zurück wenn keine Komponente verfügbar.

### Feature Engineering

**Kandidaten-Features:**
```python
_CANDIDATE_FEATURES = ["hrv_last_night", "sleep_score", "resting_hr"]
```

**Dynamische Feature-Selektion:**
Features, bei denen der globale Median über alle Trainingsrows `None` ist
(d.h. alle Werte fehlen), werden ausgeschlossen. Dies verhindert Abstürze wenn
z.B. `hrv_last_night` nie befüllt wurde.

**Imputation:**
Fehlende Werte im aktiven Feature-Set werden mit dem globalen Median des jeweiligen
Features ersetzt (Median-Imputation, nicht Mean — robuster gegen Ausreißer).

**Trainingspaare:**
```
X (Tag N): [hrv_last_night?, sleep_score?, resting_hr?]
y (Tag N+1): regelbasierter Score
```

Datenbasis: 365-Tage-Lookback (`get_readiness_training_rows`), LEFT JOIN über
`daily_summary`, `hrv_daily`, `sleep_sessions`. Minimum: 30 gültige Paare.

### Modell

```python
RandomForestRegressor(n_estimators=100, random_state=42)
```

Output wird auf [0, 100] geclippt: `min(100.0, max(0.0, prediction))`.

**Persistenz:**
```python
joblib.dump({"model": model, "features": feature_names}, model_path)
# model_path: /app/models/readiness_rf_{user_id}.joblib
```

**Feature Importances** werden nach dem Training als `model_meta_rf` in
`ml_predictions` gespeichert:

```json
{
  "features": ["sleep_score", "resting_hr"],
  "importances": {"sleep_score": 0.562, "resting_hr": 0.438},
  "n_rows": 429
}
```

### Inferenz

```python
saved = joblib.load(model_path)
model = saved["model"]
feature_names = saved["features"]

# Für jedes aktive Feature: Wert holen (None → Fehler → return None)
X = [[features[f] for f in feature_names]]
score = float(model.predict(X)[0])
return round(min(100.0, max(0.0, score)), 1)
```

Gibt `None` zurück wenn ein aktives Feature im aktuellen Datensatz fehlt.
Prediction date = morgen (`date.today() + timedelta(days=1)`).

---

## 4. Body Battery K-Means Clustering

**Datei:** `ml-service/src/models/battery.py` (inferenz in `main.py`)
**Inferenz:** Täglich | **Training:** Wöchentlich (Sonntag 03:00)

### Feature-Extraktion aus Intraday-Daten

Pro Tag werden aus den `body_battery_intraday`-Readings 5 Features berechnet:

| Feature | Berechnung |
|---------|-----------|
| `morning_avg` | Mittelwert der Readings 06:00–09:00 Uhr |
| `evening_avg` | Mittelwert der Readings 20:00–23:00 Uhr |
| `daily_range` | `max(value) − min(value)` des gesamten Tages |
| `auc` | Trapezregel über alle Readings, normiert auf Anzahl Intervalle |
| `n_dips` | Anzahl Abfälle > 10 Punkte zwischen aufeinanderfolgenden Readings |

```python
# AUC (trapezförmige Approximation):
auc = sum(
    (vals[i] + vals[i+1]) / 2 * (times[i+1] - times[i]).total_seconds() / 3600
    for i in range(len(vals) - 1)
) / max(1, total_hours)

# n_dips:
n_dips = sum(1 for i in range(1, len(vals)) if vals[i-1] - vals[i] > 10)
```

### Clustering

```python
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)  # 5 Features, n_samples = 90 Tage

kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
kmeans.fit(X_scaled)
```

Trainiert auf 90-Tage-History (`get_body_battery_history`).
Persistenz: `battery_kmeans_{user_id}.joblib` + `battery_scaler_{user_id}.joblib`.

**Cluster-Label-Zuweisung:**
Nach dem Training wird jedem Cluster anhand des Centroid-Profils ein Label zugewiesen:
- Hoher `morning_avg` + geringer `n_dips` → `stabil_hoch`
- Mittleres Profil → `erholung`
- Hoher `n_dips` + niedriger `evening_avg` → `erschoepft`

---

## 5. Scheduling & Datenpipeline

### Inferenz-Lauf (täglich, konfigurierbar über `ML_INFER_HOUR`)

```
für jeden aktiven User (garmin_linked=true, is_active=true):
  ┌─ anomaly.py
  │   get_resting_hr_history(31d) + get_today_resting_hr()
  │   → detect_resting_hr_anomaly()
  │   → save_prediction("anomaly_hr", value=z_score)
  │
  ├─ correlation.py
  │   get_sleep_hrv_pairs(90d) → compute_sleep_hrv_correlation()
  │   → save_prediction("correlation_sleep_hrv", value=r)
  │
  │   get_sleep_resting_hr_pairs(90d) → compute_sleep_hrv_correlation()
  │   → save_prediction("correlation_sleep_rhr", value=r)
  │
  │   get_bb_resting_hr_pairs(90d) → compute_sleep_hrv_correlation()
  │   → save_prediction("correlation_bb_rhr", value=r)
  │
  ├─ readiness.py
  │   get_latest_features() → predict_tomorrow(model_path)
  │   → save_prediction("readiness_rf", value=score, date=tomorrow)
  │
  └─ battery.py
      get_body_battery_today() → battery_predict_today(model_path)
      → save_prediction("battery_pattern", value=cluster_id)
```

### Trainings-Lauf (wöchentlich, Sonntag 03:00)

```
für jeden aktiven User:
  readiness.py:
    get_readiness_training_rows(365d) → train_and_save(model_path)
    → save_prediction("model_meta_rf", value=n_rows, metadata={features, importances})

  battery.py:
    get_body_battery_history(90d) → battery_fit_and_save(model_path)
```

### Startup-Verhalten

Beim Start des ML-Service wird einmalig synchron Training + Inferenz für alle User
durchgeführt, bevor der APScheduler die geplanten Jobs übernimmt.

---

## 6. Persistenz-Schema (`ml_predictions`)

Alle Ausgaben werden in der Tabelle `ml_predictions` gespeichert:

```sql
PRIMARY KEY (date, user_id, model)

-- Upsert-Logik:
INSERT INTO ml_predictions (date, user_id, model, value, metadata, created_at)
VALUES ($1, $2, $3, $4, $5, NOW())
ON CONFLICT (date, user_id, model) DO UPDATE
  SET value = EXCLUDED.value,
      metadata = EXCLUDED.metadata,
      created_at = NOW()
```

| `model` | `value` | `metadata`-Felder |
|---------|---------|------------------|
| `anomaly_hr` | z_score | `is_anomaly`, `baseline_mean`, `baseline_std`, `threshold` |
| `correlation_sleep_hrv` | Pearson r | `p_value`, `n`, `interpretation` |
| `correlation_sleep_rhr` | Pearson r | `p_value`, `n`, `interpretation` |
| `correlation_bb_rhr` | Pearson r | `p_value`, `n`, `interpretation` |
| `readiness_rf` | Predicted score 0–100 | — |
| `battery_pattern` | Cluster-ID (int) | `pattern`, `features`, `cluster` |
| `model_meta_rf` | n_rows (float) | `features`, `importances`, `n_rows` |
| `sleep_score_custom` | Score 0–100 | `total_h`, `deep_pct`, `rem_pct`, `wake_pct` |
| `hrv_status_custom` | Score 0–100 | `status`, `deviation`, `baseline_mean`, `baseline_std`, `hrv_7d_mean` |
| `intensity_minutes_custom` | Score 0–100 | `moderate_minutes`, `vigorous_minutes`, `hrmax_used`, `resting_hr_used` |
| `training_effect_custom` | Score 0–100 | `effect`, `trimp_today`, `ctl`, `atl`, `tsb`, `vo2max`, `sex`, `b_coeff` |
| `body_battery_custom` | Score 5–100 | `sleep_quality`, `hrv_factor`, `activity_drain`, `stress_drain`, `sleep_h`, `deep_h`, `rem_h`, `prev_score` |

---

## 7. Custom Metric Models (Items 1–3 + 6)

Vier rein algorithmische Modelle ohne ML-Training — alle Formeln sind transparent.

### `sleep_score_custom` — Custom Schlaf-Score

**Datei:** `ml-service/src/models/sleep_score.py`

**Formel:** Gewichteter Durchschnitt der Schlafphasen-Qualität:

| Komponente | Gewicht | Formel |
|---|---|---|
| Tiefschlaf-Score | 35% | `min(100, deep% / 20% × 100)` |
| REM-Score | 25% | `min(100, rem% / 22% × 100)` |
| Dauer-Score | 25% | `min(100, stunden / 8 × 100)` |
| Wach-Penalty | 15% | `max(0, 100 − wake% × 500)` |

Fehlende Phasen: verbleibende Gewichte werden proportional normiert.

**Input:** `sleep_sessions` letzte Nacht (bis 2 Tage Lookback)
**Skip-Bedingung:** kein `total_sleep_seconds` vorhanden

---

### `hrv_status_custom` — Custom HRV Status

**Datei:** `ml-service/src/models/hrv_status.py`

Verwendet `compute_autonomic_energy()` intern (gleiche Log-Baseline) und mappt die σ-Deviation auf Labels:

| Status | Bedingung |
|---|---|
| `BALANCED` | deviation ≥ −0.5σ |
| `UNBALANCED` | −1.5σ ≤ deviation < −0.5σ |
| `LOW` | −2.0σ ≤ deviation < −1.5σ |
| `POOR` | deviation < −2.0σ |

**Input:** `hrv_daily.hrv_last_night` — 90 Tage Lookback
**Skip-Bedingung:** weniger als 7 HRV-Werte vorhanden

---

### `intensity_minutes_custom` — Karvonen Intensitätsminuten

**Datei:** `ml-service/src/models/intensity_minutes.py`

**Formel:** Karvonen Heart Rate Reserve:
```
HRr = (HR − Ruhepuls) / (HRmax − Ruhepuls)
Moderat: 0.50 ≤ HRr < 0.70
Intensiv: HRr ≥ 0.70
```

Score = `min(100, (moderate_min + vigorous_min × 2) / 30 × 100)`

**Input:** `activity_records.heart_rate` (Sekundenwerte) + `daily_summary.resting_hr` für heutige Aktivitäten
**Skip-Bedingung:** keine activity_records für heute oder kein resting_hr

---

### `body_battery_custom` — Fresh-State Energiemodell

**Datei:** `ml-service/src/models/body_battery.py`

Ersetzt Garmins proprietären Body-Battery-Score durch ein transparentes, physiologisch
begründetes Energiemodell. Löst das Akkumulationsplateau des früheren Banister-FFM-Ansatzes
(Scientific Reports, 2025: fundamentale statistische Mängel der Methode) ab.

**Schlafqualitätsfaktor** (Phases 60% + Dauer 40%):
```
deep_score    = min(1.0, (deep_h / total_h) / 0.20)   # Ziel: 20% Tiefschlaf (Walker 2017)
rem_score     = min(1.0, (rem_h  / total_h) / 0.25)   # Ziel: 25% REM (Dijk & Czeisler 1995)
quality       = 0.55 × deep_score + 0.45 × rem_score  # Phasen-Qualität
sleep_quality = 0.40 × (total_h / 7.5) + 0.60 × quality
```

**Tagesscore** (Fresh-State-Formel):
```
hrv_factor     = min(1.0, hrv_last_night / hrv_baseline)  # Plews et al. 2013
fresh          = 40 + sleep_quality × 35 + hrv_factor × 25  # max 100 bei Idealwerten
activity_drain = min(40, today_trimp × 0.5)
stress_drain   = max(0, (avg_stress − 25) × 0.2)
score          = clamp(0.30 × prev + 0.70 × fresh − activity_drain − stress_drain, 5, 100)
```

Verhindert Akkumulationsplateau: Fresh-State (70%) dominiert, Trägheit (30%) verhindert
tägliche Überschwingungen. Bei guten Werten: `fresh ≈ 100`, `score ≈ 100` unabhängig von
gestern.

**Input:** `sleep_sessions` (letzte Nacht), `hrv_daily` (letzte Nacht + 30-Tage-Baseline),
`activities` (heutige TRIMP), `daily_summary.avg_stress`
**Fallback:** kein `hrv_last_night` → `hrv_factor = 0.5`; keine Schlafphasen → Duration-only
**Backfill:** `make backfill-battery` — löscht alte `body_battery_custom`-Predictions und rechnet neu

**Wissenschaftlicher Status:** Einzelkomponenten validiert (HRV ✅, Schlafphasen ✅, TRIMP ✅);
Composite-Aggregation heuristisch — kein Hersteller publiziert klinisch validierte Formel.

---

### `training_effect_custom` — Banister TRIMP + Training Effect

**Datei:** `ml-service/src/models/training_effect.py`

**Banister TRIMP** (geschlechtsspezifisch):
```
TRIMP = Dauer(min) × HRr × e^(b × HRr)
b = 1.92 (männlich) | b = 1.67 (weiblich)
```

**CTL/ATL** via EWM (gleiche Zeitkonstanten wie `energy_physical`: τ=42/7):

**Training Effect (0–5):**
```
effect = atan(TRIMP_heute / (CTL × 0.5)) × (10/π)
```

**VO₂max** (Uth et al. 2004): `15 × (HRmax / HRrest)`

**Input:** `activities` (50d Lookback), `users.sex` + `users.date_of_birth`
**Skip-Bedingung:** `has_profile = False` (sex nicht gesetzt in Einstellungen → Profil)

---

## 8. Lookback-Windows im Überblick

| Modell | Lookback | Minimum |
|--------|----------|---------|
| Anomalie Z-Score (Baseline) | 31 Tage | 7 Datenpunkte |
| Pearson-Korrelation | 90 Tage | 10 Paare |
| RF Training | 365 Tage | 30 Trainingspaare |
| K-Means Training | 90 Tage | k.A. |
| Inferenz (Features) | 2 Tage | alle aktiven Features müssen vorhanden sein |
| `sleep_score_custom` | 2 Tage | letzte Schlafsession |
| `hrv_status_custom` | 90 Tage | 7 HRV-Werte |
| `intensity_minutes_custom` | heute | min. 1 activity_record |
| `training_effect_custom` | 50 Tage | Profil (sex) gesetzt |
| `body_battery_custom` | 2 Tage Schlaf + 30 Tage HRV-Baseline | kein Minimum (Fallbacks greifen) |

---

## 9. Abhängigkeiten

| Library | Version | Verwendung |
|---------|---------|------------|
| `scikit-learn` | ≥1.4 | RandomForestRegressor, KMeans, StandardScaler |
| `scipy` | ≥1.12 | `pearsonr()` |
| `numpy` | ≥1.26 | Array-Operationen |
| `joblib` | (via sklearn) | Modell-Serialisierung |
| `asyncpg` | ≥0.29 | Datenbankzugriff |
| `APScheduler` | ≥3.10 | Job-Scheduling |
