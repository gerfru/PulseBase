# API Reference

All endpoints are served by the FastAPI container (`garmin-api`) behind Traefik HTTPS.

Base URL: `https://garmin.local`

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

Home page. Shows Garmin link status for the logged-in user.

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

---

## JSON API (session required)

All endpoints return `application/json`. User data is always scoped to the
authenticated user — cross-user access is not possible.

---

### `GET /api/activities`

Returns the 10 most recent activities.

**Response** — array of objects:

```json
[
  {
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
| `sport_type` | string | e.g. `running`, `cycling`, `swimming`, `other` |
| `started_at` | ISO 8601 datetime | UTC |
| `duration_seconds` | integer | null if unknown |
| `distance_meters` | float | null if unknown |
| `avg_hr` | integer | null if no HR data |
| `calories` | integer | null if unknown |

---

### `GET /api/daily`

Returns daily summaries.

**Query parameters:**

| Parameter | Default | Notes |
|-----------|---------|-------|
| `days` | `30` | How many days back to return |

**Response** — array of objects ordered by date ascending:

```json
[
  {
    "date": "2026-04-27",
    "steps": 8423,
    "resting_hr": 52,
    "body_battery_high": 87,
    "body_battery_low": 14
  }
]
```

---

### `GET /api/sleep`

Returns recent sleep sessions.

**Query parameters:**

| Parameter | Default | Notes |
|-----------|---------|-------|
| `days` | `14` | Number of sessions to return (used as LIMIT) |

**Response** — array ordered by `start_time DESC`:

```json
[
  {
    "date": "2026-04-27",
    "sleep_score": 78,
    "total_sleep_seconds": 27540
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
