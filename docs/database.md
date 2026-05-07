# Database

TimescaleDB (PostgreSQL 16) with the TimescaleDB extension enabled.

Migrations are managed by Flyway (`db/migrations/`). Never run manual SQL against the
production database — always add a new migration file.

---

## Migrations

| File | Contents |
|------|----------|
| `V1__initial_schema.sql` | Core tables, hypertables, compression policies |
| `V2__user_auth.sql` | Adds `garmin_email`, `garmin_linked`, `is_active`, `authelia_username` to `users` |
| `V3__user_password.sql` | Adds `password_hash` to `users` |
| `V4__intensity_training_status.sql` | Adds `intensity_moderate`, `intensity_vigorous`, `training_status` to `daily_summary` |
| `V5__activity_training_effect.sql` | Adds `aerobic_effect`, `anaerobic_effect` to `activities` |

---

## Tables

### `users`

| Column | Type | Notes |
|--------|------|-------|
| `id` | `SERIAL PK` | |
| `name` | `TEXT NOT NULL` | Display name |
| `email` | `TEXT NOT NULL UNIQUE` | Login identifier |
| `password_hash` | `TEXT` | bcrypt hash |
| `garmin_linked` | `BOOLEAN DEFAULT false` | Garmin account connected |
| `garmin_email` | `TEXT` | Garmin Connect email |
| `is_active` | `BOOLEAN DEFAULT true` | Soft-disable users |
| `authelia_username` | `TEXT UNIQUE` | Unused (Authelia removed) |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | |

---

### `activities`

| Column | Type | Notes |
|--------|------|-------|
| `id` | `SERIAL PK` | |
| `user_id` | `INTEGER → users(id)` | |
| `garmin_activity_id` | `BIGINT UNIQUE` | Deduplication key |
| `started_at` | `TIMESTAMPTZ NOT NULL` | Activity start (not `start_time`!) |
| `duration_seconds` | `INTEGER` | |
| `sport_type` | `TEXT NOT NULL` | e.g. `running`, `cycling`, `swimming` |
| `distance_meters` | `FLOAT` | |
| `calories` | `INTEGER` | (not `total_calories`!) |
| `avg_hr` | `SMALLINT` | (not `avg_heart_rate`!) |
| `max_hr` | `SMALLINT` | |
| `avg_pace_sec_per_km` | `FLOAT` | Seconds per km |
| `avg_cadence` | `SMALLINT` | Steps or RPM |
| `avg_power` | `SMALLINT` | Watts (cycling) |
| `elevation_gain` | `FLOAT` | Meters |
| `avg_speed_kmh` | `FLOAT` | |
| `aerobic_effect` | `FLOAT` | Garmin aerobic training effect 1–5 (V5) |
| `anaerobic_effect` | `FLOAT` | Garmin anaerobic training effect 1–5 (V5) |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | |

Index: `(user_id, started_at DESC)`

---

### `daily_summary`

Primary key: `(date, user_id)` — one row per user per day, upserted on sync.

| Column | Type | Notes |
|--------|------|-------|
| `date` | `DATE NOT NULL` | |
| `user_id` | `INTEGER → users(id)` | |
| `steps` | `INTEGER` | (not `total_steps`!) |
| `calories_total` | `INTEGER` | |
| `avg_stress` | `SMALLINT` | 0–100 |
| `max_stress` | `SMALLINT` | |
| `avg_spo2` | `SMALLINT` | % |
| `min_spo2` | `SMALLINT` | |
| `body_battery_high` | `SMALLINT` | 0–100 |
| `body_battery_low` | `SMALLINT` | |
| `resting_hr` | `SMALLINT` | bpm |
| `intensity_moderate` | `SMALLINT` | Minutes of moderate intensity (V4) |
| `intensity_vigorous` | `SMALLINT` | Minutes of vigorous intensity (V4) |
| `training_status` | `TEXT` | e.g. `PRODUCTIVE`, `MAINTAINING` (V4) |

---

### `sleep_sessions`

| Column | Type | Notes |
|--------|------|-------|
| `id` | `SERIAL PK` | |
| `user_id` | `INTEGER → users(id)` | |
| `garmin_sleep_id` | `BIGINT UNIQUE` | Deduplication key |
| `start_time` | `TIMESTAMPTZ NOT NULL` | |
| `end_time` | `TIMESTAMPTZ NOT NULL` | |
| `total_sleep_seconds` | `INTEGER` | (not `duration_seconds`!) |
| `deep_sleep_seconds` | `INTEGER` | |
| `light_sleep_seconds` | `INTEGER` | |
| `rem_sleep_seconds` | `INTEGER` | |
| `awake_seconds` | `INTEGER` | |
| `sleep_score` | `SMALLINT` | 0–100 Garmin score |

Index: `(user_id, start_time DESC)`

---

### `hrv_daily`

Primary key: `(date, user_id)` — upserted on sync.

| Column | Type | Notes |
|--------|------|-------|
| `date` | `DATE NOT NULL` | |
| `user_id` | `INTEGER → users(id)` | |
| `hrv_last_night` | `SMALLINT` | ms (not `hrv_last_night_avg`!) |
| `hrv_weekly_avg` | `SMALLINT` | ms (not `weekly_avg`!) |
| `hrv_status` | `TEXT` | `balanced` / `unbalanced` / `poor` (not `status`!) |

---

## Hypertables

Hypertables partition data by time. Used for high-frequency intraday data.

### `activity_records`

GPS + HR time-series per activity (~1 row/sec during activity).

| Column | Type |
|--------|------|
| `time` | `TIMESTAMPTZ NOT NULL` |
| `activity_id` | `INTEGER → activities(id)` |
| `user_id` | `INTEGER` |
| `heart_rate` | `SMALLINT` |
| `pace_sec_per_km` | `FLOAT` |
| `cadence` | `SMALLINT` |
| `power` | `SMALLINT` |
| `elevation` | `FLOAT` |
| `distance` | `FLOAT` |
| `lat` | `DOUBLE PRECISION` |
| `lng` | `DOUBLE PRECISION` |

Compression: after 7 days, segmented by `activity_id`.

### `body_battery_intraday`

| Column | Type | Notes |
|--------|------|-------|
| `time` | `TIMESTAMPTZ NOT NULL` | |
| `user_id` | `INTEGER` | |
| `value` | `SMALLINT NOT NULL` | 0–100 |

Compression: after 30 days.

### `stress_intraday`

Same structure as `body_battery_intraday`. Value 0–100.

Compression: after 30 days.

### `spo2_readings`

Same structure as `body_battery_intraday`. Value = SpO2 percentage.

### `sleep_levels`

| Column | Type | Notes |
|--------|------|-------|
| `time` | `TIMESTAMPTZ NOT NULL` | |
| `sleep_session_id` | `INTEGER → sleep_sessions(id)` | |
| `user_id` | `INTEGER` | |
| `level` | `TEXT NOT NULL` | `deep` / `light` / `rem` / `awake` |

---

## Useful Queries

```sql
-- Resting HR trend last 90 days
SELECT date, resting_hr
FROM daily_summary
WHERE user_id = 1 AND date >= NOW() - INTERVAL '90 days'
ORDER BY date;

-- Sleep score average per month
SELECT date_trunc('month', start_time) AS month, AVG(sleep_score)
FROM sleep_sessions
WHERE user_id = 1
GROUP BY 1 ORDER BY 1;

-- Body battery hourly average (TimescaleDB time_bucket)
SELECT time_bucket('1 hour', time) AS hour, AVG(value)
FROM body_battery_intraday
WHERE user_id = 1 AND time >= NOW() - INTERVAL '7 days'
GROUP BY 1 ORDER BY 1;

-- HRV last night vs resting HR correlation
SELECT h.date, h.hrv_last_night, d.resting_hr
FROM hrv_daily h
JOIN daily_summary d USING (date, user_id)
WHERE h.user_id = 1
ORDER BY h.date DESC;
```
