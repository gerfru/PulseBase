# API Reference

All endpoints are served by the FastAPI container (`garmin-api`) behind Caddy (homelab-gateway).

Base URL: `https://garmin.home.lab`

---

## Authentication

Session-based via signed cookie (`SessionMiddleware`). Login at `POST /login` sets
`user_id` in the session. All protected routes check the session and redirect to `/login`
if missing.

The JSON API endpoints (`/api/*`) also require a valid session — they return a redirect
to `/login` if called without one (not a 401 JSON response).

---

## Public Routes

### `GET /login`

Renders the login form.

### `POST /login`

Rate-limited to 10 requests/minute per IP.

| Field | Type | Required |
|-------|------|----------|
| `email` | string | yes |
| `password` | string | yes |

On success: redirects to `/`.
On failure: re-renders login form with error message (HTTP 400).

### `GET /register`

Renders the registration form.

### `POST /register`

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `name` | string | yes | |
| `email` | string | yes | must be unique |
| `password` | string | yes | min 8 characters |
| `password_confirm` | string | yes | must match `password` |

On success: logs the user in and redirects to `/`.
On failure: re-renders form with error message (HTTP 400).

---

## Protected Pages (session required)

### `GET /`

Redirects to `/dashboard`.

### `POST /logout`

Clears the session. Redirects to `/login`.

### `GET /garmin/link`

Renders the Garmin account linking form.

### `POST /garmin/link`

| Field | Type | Notes |
|-------|------|-------|
| `garmin_email` | string | Garmin Connect email |
| `garmin_password` | string | Used once, then deleted from memory |

Authenticates against Garmin Connect, stores the session token in
`/app/tokens/{user_id}/`, marks user as `garmin_linked = true`.

On success: redirects to `/?linked=1`.
On failure: re-renders form with error (HTTP 400).

### `POST /garmin/unlink`

Sets `garmin_linked = false` and clears `garmin_email`. Redirects to `/`.
Tokens on disk are not deleted automatically.

### `GET /dashboard`

Renders `dashboard.html`. The page loads data asynchronously via the `/api/*` endpoints
below using `fetch()`.

### `GET /activity/{activity_id}`

Renders the activity detail page (`activity.html`) for a single activity.
Includes GPS track (Leaflet.js), HR/pace/elevation/cadence charts, stat grid, and
training effect bars. Redirects to `/dashboard` if the activity does not exist or
belongs to a different user.

### `GET /settings`

Renders the settings page. Shows account info (name, email), Garmin Connect
connection status, LibreLinkUp connection status, and the Epilepsie-Modus toggle —
each with inline connect/disconnect buttons.

### `GET /epilepsy`

Renders the seizure diary page (`epilepsy.html`). Redirects to `/settings` if
`epilepsy_mode` is not enabled for the user. Contains three sections:
daily risk indicator, log form, and event history.

### `GET /libre/link`

Renders the LibreLinkUp linking form. When already linked, shows the connected
email and a disconnect button instead of the form.

### `POST /libre/link`

| Field            | Type   | Notes                                                |
|------------------|--------|------------------------------------------------------|
| `libre_email`    | string | LibreLinkUp account email                            |
| `libre_password` | string | Used once for initial auth, then deleted from memory |

Authenticates against the LibreLinkUp EU endpoint, stores the session token
in `/app/tokens/{user_id}/libre/libre_token.json`, marks user as `libre_linked = true`.

Prerequisite: the sensor owner must have accepted the user as a follower in
their LibreLink app before linking will succeed.

On success: redirects to `/dashboard`.
On failure: re-renders form with error message (HTTP 400).

### `POST /libre/unlink`

Disconnects LibreLinkUp: sets `libre_linked = false`, clears `libre_email`,
deletes **all** `glucose_readings` rows for this user (irreversible), and
removes the token file. Redirects to `/libre/link`.

### `GET /ml/anomaly`

Renders the anomaly detection detail page. Shows z-score history (30 days),
stat tiles, and an explanation of z-score interpretation.

### `GET /ml/readiness`

Renders the readiness prediction detail page. Shows predicted score,
30-day history chart, feature importance bar chart, and model metadata.

### `GET /ml/correlations`

Renders the correlations detail page. Shows all three Pearson correlations
(sleep→HRV, sleep→resting HR, body battery→resting HR) with bar visualization.

### `GET /ml/battery`

Renders the body battery pattern detail page. Shows today's cluster assignment
with feature breakdown table.

---

## JSON API (session required)

All endpoints return `application/json`. User data is always scoped to the
authenticated user — cross-user access is not possible.

---

### `GET /api/activities`

Returns activities within the requested time range.

**Query parameters:**

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| `days` | `7` | 1–365 | How many days back to query |
| `limit` | `500` | 1–500 | Maximum number of results |
| `end_date` | `today` | ISO date | Last day of the window (for time navigation) |

**Response** — array of objects ordered by `started_at DESC`:

```json
[
  {
    "id": 42,
    "sport_type": "running",
    "started_at": "2026-04-27T06:32:00+00:00",
    "duration_seconds": 3420,
    "distance_meters": 10250.5,
    "avg_hr": 148,
    "calories": 512
  }
]
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | integer | DB primary key — use for `/api/activities/{id}` |
| `sport_type` | string | e.g. `running`, `cycling`, `swimming`, `strength_training` |
| `started_at` | ISO 8601 datetime | UTC |
| `duration_seconds` | integer | null if unknown |
| `distance_meters` | float | null if unknown |
| `avg_hr` | integer | null if no HR data |
| `calories` | integer | null if unknown |

---

### `GET /api/activities/{activity_id}`

Returns full detail for a single activity including per-second records.

**Response:**

```json
{
  "id": 42,
  "sport_type": "running",
  "started_at": "2026-04-27T06:32:00+00:00",
  "duration_seconds": 3420,
  "distance_meters": 10250.5,
  "calories": 512,
  "avg_hr": 148,
  "max_hr": 178,
  "avg_pace_sec_per_km": 334.5,
  "avg_speed_kmh": null,
  "avg_cadence": 172,
  "avg_power": null,
  "elevation_gain": 42.0,
  "aerobic_effect": 3.8,
  "anaerobic_effect": 1.2,
  "training_status": "PRODUCTIVE",
  "records": [
    {
      "time": "2026-04-27T06:32:01+00:00",
      "heart_rate": 142,
      "pace_sec_per_km": 340.0,
      "cadence": 170,
      "power": null,
      "elevation": 245.2,
      "distance": 5.1,
      "lat": 47.0707,
      "lng": 15.4395
    }
  ]
}
```

| Field | Notes |
|-------|-------|
| `aerobic_effect` | Garmin aerobic training effect 1.0–5.0, null if not available |
| `anaerobic_effect` | Garmin anaerobic training effect 1.0–5.0, null if not available |
| `training_status` | From `daily_summary` for the activity date (LEFT JOIN) |
| `records` | Per-second data points, empty array if no GPS/HR data stored |

Returns HTTP 404 with `{"error": {"code": "NOT_FOUND", ...}}` if activity does not exist
or belongs to a different user.

---

### `GET /api/daily`

Returns daily summaries.

**Query parameters:**

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| `days` | `30` | 1–365 | How many days back to return |
| `end_date` | `today` | ISO date | Last day of the window (for time navigation) |

**Response** — array of objects ordered by date ascending:

```json
[
  {
    "date": "2026-04-27",
    "steps": 8423,
    "resting_hr": 52,
    "avg_stress": 28,
    "calories_total": 2180,
    "intensity_moderate": 22,
    "intensity_vigorous": 8,
    "body_battery_high": 87,
    "body_battery_low": 14
  }
]
```

---

### `GET /api/sleep`

Returns recent sleep sessions.

**Query parameters:**

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| `days` | `14` | 1–365 | How many days back to return |
| `end_date` | `today` | ISO date | Last day of the window (for time navigation) |

**Response** — array ordered by `start_time DESC`:

```json
[
  {
    "date": "2026-04-27",
    "sleep_score": 78,
    "total_sleep_seconds": 27540,
    "deep_sleep_seconds": 5400,
    "light_sleep_seconds": 14400,
    "rem_sleep_seconds": 6300,
    "awake_seconds": 1440
  }
]
```

---

### `GET /api/hrv`

Returns the most recent HRV entry.

**Response** — single object or `null` if no data:

```json
{
  "hrv_last_night": 48,
  "hrv_weekly_avg": 52,
  "hrv_status": "balanced"
}
```

| Field | Notes |
|-------|-------|
| `hrv_last_night` | ms, last night measurement |
| `hrv_weekly_avg` | ms, 7-day rolling average |
| `hrv_status` | `balanced` / `unbalanced` / `poor` |

---

### `GET /api/hrv/trend`

Returns HRV data points for a date range.

**Query parameters:**

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| `days` | `30` | 1–365 | How many days back |
| `end_date` | `today` | ISO date | Last day of the window (for time navigation) |

**Response** — array ordered by date ascending:

```json
[
  {
    "date": "2026-04-27",
    "hrv_last_night": 48,
    "hrv_weekly_avg": 52,
    "hrv_status": "balanced"
  }
]
```

---

### `GET /api/weekly`

Returns weekly training volume aggregates.

**Query parameters:**

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| `weeks` | `12` | 1–52 | How many weeks back |
| `end_date` | `today` | ISO date | Last day of the window (for time navigation) |

**Response** — array ordered by week ascending:

```json
[
  {
    "week": "2026-04-27",
    "activity_count": 4,
    "total_km": 42.3,
    "total_hours": 4.2,
    "run_km": 35.1,
    "ride_km": 7.2,
    "other_hours": 1.0
  }
]
```

| Field | Notes |
|-------|-------|
| `week` | Monday of the week (ISO date) |
| `run_km` | Distance for `running`, `trail_running`, `hiking`, `walking` |
| `ride_km` | Distance for `cycling`, `indoor_cycling` |
| `other_hours` | Duration for all other sport types (strength, yoga, …) |

---

### `GET /api/readiness`

Returns a rule-based readiness score for the most recent day with data (within last 2 days).

**Response:**

```json
{
  "score": 74,
  "label": "In Ordnung",
  "cls": "badge-balanced",
  "energy_physical": 62,
  "energy_autonomic": 78,
  "energy_cognitive": 85
}
```

| Field | Notes |
|-------|-------|
| `score` | 0–100, weighted average of the three energy dimensions |
| `label` | `Bereit` (≥75) / `In Ordnung` (≥55) / `Erholen` (≥35) / `Pause` (<35) |
| `cls` | CSS badge class for color coding |
| `energy_physical` | Physical energy score or `null` if not yet computed |
| `energy_autonomic` | Autonomic (HRV) energy score or `null` |
| `energy_cognitive` | Cognitive (sleep debt) energy score or `null` |
| `score: null` | Returned when none of the three energy dimensions have data yet |

**Score formula** (missing dimensions are excluded and weights renormalized):

| Dimension | Weight |
|-----------|--------|
| Physical energy (CTL/TSB) | 35% |
| Autonomic energy (HRV σ-baseline) | 40% |
| Cognitive energy (sleep debt) | 25% |

---

### `GET /api/training-status`

Returns the most recent training status entry.

**Response** — single object or `null` if no data:

```json
{
  "date": "2026-04-27",
  "training_status": "PRODUCTIVE"
}
```

| `training_status` value | Meaning |
|-------------------------|---------|
| `PRODUCTIVE` | Load is building fitness |
| `MAINTAINING` | Fitness is being maintained |
| `RECOVERY` | Body is recovering |
| `UNPRODUCTIVE` | Load not resulting in adaptation |
| `OVERREACHING` | Training load too high |
| `DETRAINING` | Fitness declining |

---

### `GET /api/glucose`

Returns recent glucose readings from LibreLinkUp. Only available when `libre_linked = true`.

**Query parameters:**

| Parameter | Default | Notes                         |
|-----------|---------|-------------------------------|
| `hours`   | `24`    | How many hours back to return |

**Response** — array ordered by `time DESC`:

```json
[
  {
    "time": "2026-05-08T14:32:00+00:00",
    "value_mgdl": 98.0,
    "trend": 3,
    "is_high": false,
    "is_low": false
  }
]
```

| `trend` value | Meaning       |
|---------------|---------------|
| `1`           | Falling quickly (↓↓) |
| `2`           | Falling (↓)   |
| `3`           | Stable (→)    |
| `4`           | Rising (↑)    |
| `5`           | Rising quickly (↑↑) |

---

### `GET /api/glucose/stats`

Returns aggregated glucose statistics. Only available when `libre_linked = true`.

**Query parameters:**

| Parameter | Default | Notes                    |
|-----------|---------|--------------------------|
| `days`    | `14`    | How many days to include |

**Response:**

```json
{
  "avg_mgdl": 103.4,
  "min_mgdl": 72.0,
  "max_mgdl": 168.0,
  "tir_pct": 87.2,
  "count_high": 12,
  "count_low": 1
}
```

| Field       | Notes                                              |
|-------------|-----------------------------------------------------|
| `tir_pct`   | Time-in-Range percentage (70–180 mg/dL)            |
| `count_high`| Readings flagged as high by the sensor             |
| `count_low` | Readings flagged as low (hypoglycemia) by the sensor |

---

### `GET /api/ml-history`

Returns historical ML prediction values grouped by model.

**Query parameters:**

| Parameter | Default | Notes                    |
|-----------|---------|--------------------------|
| `days`    | `30`    | How many days back       |
| `end_date` | `today` | Last day of the window (ISO date, for time navigation) |

**Response** — object with one array per model:

```json
{
  "anomaly_hr": [
    { "date": "2026-05-08", "value": 1.29, "is_anomaly": false, "z_score": 1.29 }
  ],
  "readiness_rf": [
    { "date": "2026-05-08", "value": 74.0 }
  ],
  "correlation_sleep_hrv": [
    { "date": "2026-05-08", "value": 0.61, "r": 0.61, "n": 42 }
  ]
}
```

---

### `GET /api/ml-insights`

Returns the latest ML model outputs for the authenticated user. All models write daily
to `ml_predictions`; this endpoint returns the most recent row per model (within 1 day).

**Response** — object with one key per available model (absent if no data):

```json
{
  "anomaly_hr": {
    "value": 1.29,
    "is_anomaly": false,
    "baseline_mean": 43.5,
    "baseline_std": 3.2,
    "threshold": 1.5
  },
  "readiness_rf": {
    "value": 71.0
  },
  "correlation_sleep_hrv": {
    "value": 0.61,
    "r": 0.61,
    "p_value": 0.003,
    "n_samples": 42,
    "interpretation": "mittel"
  }
}
```

| Model key | `value` | Notes |
|-----------|---------|-------|
| `anomaly_hr` | Z-score of today's resting HR | `is_anomaly: true` when z > 1.5 |
| `readiness_rf` | Predicted readiness score 0–100 | null when < 30 valid training rows |
| `correlation_sleep_hrv` | Pearson r (−1 to 1) | Requires ≥ 10 sleep→HRV pairs |

Returns `{}` if no ML data has been computed yet.

---

### `GET /api/energy`

Returns today's three energy dimension scores computed by the ML service.

**Response** — object with one key per computed dimension (absent if no data yet):

```json
{
  "energy_physical": {
    "score": 54.0,
    "atl": 28.3,
    "ctl": 31.1,
    "tsb": 2.8,
    "hrmax": 185.0
  },
  "energy_autonomic": {
    "score": 62.0,
    "deviation": 0.8,
    "baseline_mean": 3.81,
    "baseline_std": 0.22,
    "hrv_7d_mean": 3.99
  },
  "energy_cognitive": {
    "score": 78.0,
    "debt_hours": 3.7,
    "days_used": 7
  }
}
```

| Field | Notes |
|-------|-------|
| `energy_physical.tsb` | Training Stress Balance (positive = recovered, negative = fatigued) |
| `energy_autonomic.deviation` | HRV deviation in σ units from 90-day baseline |
| `energy_cognitive.debt_hours` | Cumulative 7-day sleep deficit vs 7h target |

Returns `{}` if ML inference has not run yet.

---

### `PATCH /api/profile`

Saves the user's date of birth, biological sex, and optional epilepsy mode flag. Used for Banister TRIMP computation in the ML service. Session-protected.

**Request body (JSON):**

```json
{ "date_of_birth": "1990-05-15", "sex": "m", "epilepsy_mode": true }
```

| Field | Type | Constraint |
|-------|------|------------|
| `date_of_birth` | `date \| null` | ISO 8601, must be in the past |
| `sex` | `string \| null` | `"m"`, `"f"`, or `"diverse"` |
| `epilepsy_mode` | `boolean \| null` | Enables seizure diary; omit to leave unchanged |

**Response on success:**

```json
{ "ok": true }
```

**Error responses:**
- `422` — `date_of_birth` not in the past, or `sex` not in allowed values

---

### `PATCH /api/activities/{activity_id}/rpe`

Sets the subjective RPE (Rate of Perceived Exertion) for an activity. Session-protected.

**Path parameter:** `activity_id` — integer

**Request body (JSON):**

```json
{ "rpe": 7 }
```

| Field | Type | Constraint |
|-------|------|------------|
| `rpe` | integer | 1–10 (Foster CR-10 scale) |

**Response on success:**

```json
{ "ok": true, "rpe": 7 }
```

**Error responses:**
- `404` — activity not found or belongs to another user
- `422` — `rpe` out of range

---

### `POST /api/sync`

Requests an immediate Garmin sync for the authenticated user. The sync-service polls for
this flag and processes it within 2 minutes.

**Request body:** none

**Response:**

```json
{ "status": "requested" }
```

**Error:** `400` with `code: NOT_LINKED` if Garmin account is not connected.

---

### `GET /api/sync-status`

Returns the sync state for the authenticated user.

**Response:**

```json
{
  "pending": false,
  "last_sync_at": "2026-05-15T06:12:44.123456+00:00"
}
```

| Field | Notes |
|-------|-------|
| `pending` | `true` while sync is queued but not yet processed |
| `last_sync_at` | ISO 8601 timestamp or `null` if never synced |

---

### `GET /api/ml-status`

Returns the ML inference state for the authenticated user.

**Response:**

```json
{
  "pending": false,
  "last_ml_at": "2026-05-15T07:02:11.445312+00:00"
}
```

| Field | Notes |
|-------|-------|
| `pending` | `true` while ML run is queued (set by sync-service after Garmin sync) |
| `last_ml_at` | ISO 8601 timestamp or `null` if never run |

---

## Protected Pages (additional)

### `GET /metrics/{name}`

Renders the metric detail page for a named metric. Redirects to `/dashboard` if `name` is
not in the allowed set.

**Valid `name` values:**

`steps`, `sleep`, `hrv`, `body-battery`, `physical`, `autonomic`, `cognitive`,
`hr-zscore`, `readiness-rf`, `hrv-status`, `hrv-status-custom`, `training-status`,
`readiness`, `sleep-score-custom`, `intensity-minutes`, `training-effect`

**Response:** HTML page (`metrics.html` template). Data is loaded client-side via
`/api/activities`, `/api/daily`, `/api/sleep`, `/api/hrv/trend`, and `/api/energy`.

---

### `POST /api/seizures`

Logs a new seizure event. Session-protected. Only meaningful when `epilepsy_mode = true`.

**Request body (JSON):**

```json
{
  "occurred_at": "2026-05-16T08:30:00Z",
  "type": "focal",
  "duration_seconds": 90,
  "severity": 3,
  "notes": "Nach Schlafentzug, mit Aura"
}
```

| Field | Type | Constraint |
|-------|------|------------|
| `occurred_at` | ISO 8601 datetime | required |
| `type` | string | `"focal"`, `"generalized"`, or `"unknown"` (default) |
| `duration_seconds` | integer \| null | optional |
| `severity` | integer \| null | 1–5; optional |
| `notes` | string \| null | free text; optional |

**Response:**

```json
{ "ok": true, "id": 1 }
```

---

### `GET /api/seizures`

Returns logged seizure events for the authenticated user.

**Query parameters:**

| Parameter | Default | Notes |
|-----------|---------|-------|
| `days` | `365` | Look-back window |

**Response** — array ordered by `occurred_at DESC`:

```json
[
  {
    "id": 1,
    "occurred_at": "2026-05-16T08:30:00+00:00",
    "duration_seconds": 90,
    "type": "focal",
    "severity": 3,
    "notes": "Nach Schlafentzug, mit Aura"
  }
]
```

---

### `GET /api/seizures/risk`

Returns a rule-based daily risk indicator computed from existing biomarkers.
No seizure history required — useful from day 1.

**Response:**

```json
{
  "level": "amber",
  "flags": [
    { "label": "Schlafschuld", "detail": "3.2h in 7 Nächten", "color": "amber" }
  ],
  "sleep_debt_h": 3.2
}
```

| Field | Values | Notes |
|-------|--------|-------|
| `level` | `"ok"` / `"amber"` / `"red"` | Highest severity across all flags |
| `flags` | array | Each active risk factor with label, detail, color |
| `sleep_debt_h` | float | Cumulative sleep deficit vs 7h/night over last 7 nights |

**Risk rules (current):**

| Condition | Level | Data source |
|-----------|-------|-------------|
| Sleep debt > 5h (last 7 nights vs 7h target) | red | `sleep_sessions` |
| Sleep debt 2–5h | amber | `sleep_sessions` |
| avg_stress (yesterday) > 70 | amber | `daily_summary` |
| HRV last night < 80 % of weekly average | amber | `hrv_daily` |
| Body battery daily low < 20 (yesterday) | amber | `daily_summary` |
| Vigorous intensity > 60 min (yesterday) | amber | `daily_summary` |
| Resting HR > 110 % of 30-day baseline | amber | `daily_summary` |

---

## Health

### `GET /health`

Returns `{"status": "ok"}`. Not session-protected. Used by Docker healthcheck.
