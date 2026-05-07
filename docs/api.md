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
| `days` | `14` | 1–365 | Number of sessions to return (LIMIT) |

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

## Health

### `GET /health`

Returns `{"status": "ok"}`. Not session-protected. Used by Docker healthcheck.
