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
| `V6__sync_trigger.sql` | Adds `sync_requested`, `last_sync_at` to `users` |
| `V7__app_user.sql` | Creates least-privilege `garmin_app` DB user |
| `V8__ml_predictions.sql` | Creates `ml_predictions` table for ML model outputs |
| `V9__libre_glucose.sql` | Adds `libre_linked`/`libre_email` to `users`; creates `glucose_readings` hypertable |
| `V10__ml_trigger.sql` | Adds `ml_requested`, `last_ml_at` to `users` for on-demand ML trigger |
| `V11__activity_rpe.sql` | Adds `user_rpe SMALLINT` to `activities` (Foster RPE 1–10) |
| `V12__user_profile.sql` | Adds `date_of_birth DATE`, `sex TEXT` to `users` (required for Banister TRIMP) |
| `V13__running_economy.sql` | Adds running dynamics columns to `activities` (ground contact time, vertical oscillation, stride length, vertical ratio, running power) |
| `V14__fix_stride_length_precision.sql` | Widens `avg_stride_length` to `NUMERIC(6,1)` — Garmin returns cm, not meters |
| `V15__epilepsy.sql` | Adds `epilepsy_mode BOOLEAN` to `users`; creates `seizure_events` table |
| `V16__spo2_settings.sql` | Adds `spo2_enabled BOOLEAN` to `users` |
| `V17__account_lockout.sql` | Adds `failed_login_attempts SMALLINT`, `locked_until TIMESTAMPTZ` to `users` |
| `V18__email_verification.sql` | Adds `email_verified_at TIMESTAMPTZ` to `users`; backfills existing users |
| `V19__user_consents.sql` | Creates `user_consents` audit table for DSGVO Art. 5(2) accountability |
| `V20__user_tokens.sql` | Creates `user_tokens` table for Fernet-encrypted Garmin/LibreLink session tokens |
| `V21__consent_ip_hash.sql` | Replaces `ip_address INET` (PII) with `ip_address_hash TEXT` (SHA-256 prefix) in `user_consents` |
| `V22__password_reset_token.sql` | Adds `password_reset_token_hash TEXT`, `password_reset_expires_at TIMESTAMPTZ` to `users` |
| `V23__pending_deletion.sql` | Adds `pending_deletion_at TIMESTAMPTZ` to `users` (two-step account deletion with e-mail confirmation) |
| `V24__per_service_roles.sql` | Creates per-service least-privilege DB roles `pulse_sync` (ingest) and `pulse_ml` (read-only inference + `ml_predictions` write); column-level grants (ADR-0001) |
| `V25__ml_feedback.sql` | Creates `ml_feedback` table for 👍/👎 item-level feedback on ML predictions |
| `V26__single_use_tokens.sql` | Adds `verification_token_hash`, `verification_token_expires_at`, `deletion_token_hash`, `deletion_token_expires_at` to `users` — single-use, server-side-verified tokens (replaces replayable stateless itsdangerous payloads) |
| `V27__user_consent_events.sql` | Creates immutable `user_consent_events` audit table — append-only log of every consent change for GDPR Art. 5(2) accountability; `user_consents` remains the current-state table |
| `V34__service_events.sql` | Adds durable `service_events` for the sync/ML trigger migration; `LISTEN/NOTIFY` is only a wake-up signal while legacy flags remain active |
| `V35__service_events_sync_select.sql` | Grants `SELECT` on `service_events` to `pulse_sync`, required by the deduplicating `ON CONFLICT` insert |
| `V36__service_events_cutover.sql` | Completes ADR-0005: generation-based retrigger safety, update notifications, retention index, legacy-flag backfill, and row-level ownership policies |
| `V28__session_version.sql` | Adds `session_version INTEGER NOT NULL DEFAULT 0` to `users` — bumped on password reset to invalidate all existing signed session cookies |
| `V29__round_gps_precision.sql` | Rounds `activity_records.lat`/`lng` to 4 decimal places (~11 m) for GDPR Art. 5(1)(c) data minimisation |
| `V30__consent_audit_set_null.sql` | Changes `user_consents` and `user_consent_events` FK on `user_id` from `ON DELETE CASCADE` to `ON DELETE SET NULL` — pseudonymise instead of erase, preserving the consent audit trail (GDPR Art. 5(2)) |
| `V31__user_weight.sql` | Adds `weight_kg FLOAT CHECK (weight_kg > 0 AND weight_kg <= 500)` to `users` |

---

## Tables

### `service_events`

Durable, coalescing work queue for `sync_requested` and `ml_requested` (ADR-0005).
`LISTEN/NOTIFY` is only a wake-up signal; consumers always claim durable rows with
`FOR UPDATE SKIP LOCKED`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `BIGSERIAL PK` | Stable job identifier |
| `event_type` | `TEXT` | `sync_requested` or `ml_requested` |
| `user_id` | `INTEGER → users(id)` | Work partition key |
| `payload` | `JSONB` | Version, correlation ID, and cause; no health values or secrets |
| `status` | `TEXT` | `pending`, `processing`, `completed`, or `failed` |
| `generation` | `INTEGER` | Incremented when an open job is retriggered |
| `claimed_generation` | `INTEGER` | Generation owned by the current processing lease |
| `available_at` | `TIMESTAMPTZ` | Retry/backoff eligibility |
| `attempts` | `INTEGER` | Current bounded retry count |
| `claimed_at` | `TIMESTAMPTZ` | Processing-lease start |
| `processed_at` | `TIMESTAMPTZ` | Completion or terminal-failure time |
| `last_error` | `TEXT` | Sanitized error summary, bounded to 2000 characters in code |
| `created_at` | `TIMESTAMPTZ` | Initial enqueue time |

One partial unique index permits at most one open row per `(event_type, user_id)`.
If `generation` advances during processing, acknowledgement returns that row to
`pending`; otherwise it becomes `completed`. Completed rows are retained for 30 days.
Row-level security enforces API → sync and sync → ML ownership.

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
| `libre_linked` | `BOOLEAN DEFAULT false` | LibreLinkUp account connected (V9) |
| `libre_email` | `TEXT` | LibreLinkUp email (V9) |
| `date_of_birth` | `DATE` | Used for age calculation + Banister TRIMP (V12) |
| `sex` | `TEXT CHECK (sex IN ('m','f','diverse'))` | Required for Banister TRIMP coefficients (V12) |
| `epilepsy_mode` | `BOOLEAN DEFAULT false` | Enables seizure diary + risk indicator (V15) |
| `spo2_enabled` | `BOOLEAN DEFAULT false` | SpO2 tracking opt-in (V16) |
| `failed_login_attempts` | `SMALLINT DEFAULT 0` | Brute-force counter; resets on success (V17) |
| `locked_until` | `TIMESTAMPTZ` | Account locked until this time after 5 failures (V17) |
| `email_verified_at` | `TIMESTAMPTZ` | Set on first email verification; NULL = unverified (V18) |
| `password_reset_token_hash` | `TEXT` | bcrypt hash of active reset token; NULL when no reset pending (V22) |
| `password_reset_expires_at` | `TIMESTAMPTZ` | Expiry of active reset token; token cleared after use (V22) |
| `pending_deletion_at` | `TIMESTAMPTZ` | Set when account deletion is requested; cleared/executed via signed confirmation link (V23) |
| `session_version` | `INTEGER NOT NULL DEFAULT 0` | Bumped on password reset to invalidate all existing signed session cookies (V28) |
| `weight_kg` | `FLOAT CHECK (>0 AND ≤500)` | Body weight in kg (V31) |
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
| `user_rpe` | `SMALLINT CHECK (1–10)` | User-entered RPE via Foster method (V11) |
| `avg_ground_contact_time` | `INTEGER` | Ground contact time in ms, running only (V13) |
| `avg_vertical_oscillation` | `NUMERIC(4,1)` | Vertical oscillation in cm, running only (V13) |
| `avg_stride_length` | `NUMERIC(6,1)` | Stride length in cm, running only — added in V13 as `NUMERIC(4,2)`, widened to `NUMERIC(6,1)` in V14 |
| `avg_vertical_ratio` | `NUMERIC(4,1)` | Vertical ratio %, running only (V13) |
| `avg_running_power` | `INTEGER` | Running power in W, requires sensor (V13) |
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

### `ml_predictions`

Primary key: `(date, user_id, model)` — one row per user per day per model, upserted on inference.

| Column | Type | Notes |
|--------|------|-------|
| `date` | `DATE NOT NULL` | Inference date |
| `user_id` | `INTEGER → users(id)` | |
| `model` | `TEXT NOT NULL` | Free TEXT model key. ~15+ values written by ml-service, e.g. `anomaly_hr`, `anomaly_sleep`, `anomaly_spo2`, `anomaly_steps`, `anomaly_stress`, `readiness_rf`, `correlation_sleep_hrv`, `correlation_sleep_rhr`, `correlation_bb_rhr`, `acwr`, `training_monotony`, `spo2_trend`, `body_battery_custom`, `stress_score_custom`, `running_economy`, `sleep_consistency`, `hrv_recovery`, `battery_pattern`, `energy_physical`, `energy_autonomic`, `energy_cognitive` |
| `value` | `FLOAT` | Primary output (z-score, predicted score, or Pearson r) |
| `metadata` | `JSONB` | Additional fields (e.g. `is_anomaly`, `p_value`, `n_samples`) |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | |

Index: `(user_id, date DESC)`

---

### `ml_feedback`

Binary 👍/👎 feedback on ML predictions — one row per user per model per day. Added in V25.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `SERIAL PK` | |
| `user_id` | `INTEGER → users(id) ON DELETE CASCADE` | |
| `model` | `TEXT NOT NULL` | Model key matching `ml_predictions.model` |
| `prediction_date` | `DATE NOT NULL` | Stamped server-side to `CURRENT_DATE` |
| `helpful` | `BOOLEAN NOT NULL` | `true` = 👍, `false` = 👎 |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | |

UNIQUE on `(user_id, model, prediction_date)` — makes feedback idempotent/toggleable via `ON CONFLICT` upsert.
Index: `(user_id, prediction_date DESC)`

---

### `glucose_readings`

Hypertable for continuous glucose monitor (CGM) readings via LibreLinkUp (Libre 3).
~1 reading per minute = ~1,440 rows/day/user. Added in V9.

| Column | Type | Notes |
|--------|------|-------|
| `time` | `TIMESTAMPTZ NOT NULL` | Reading timestamp (partition key) |
| `user_id` | `INTEGER → users(id)` | |
| `value_mgdl` | `REAL NOT NULL` | Glucose in mg/dL |
| `trend` | `SMALLINT` | 1=FallingQuickly, 2=Falling, 3=Stable, 4=Rising, 5=RisingQuickly |
| `is_high` | `BOOLEAN` | Sensor-flagged high value |
| `is_low` | `BOOLEAN` | Sensor-flagged low value (hypoglycemia) |

UNIQUE INDEX on `(user_id, time)` — upserted with `ON CONFLICT DO NOTHING`.
Compression: after 7 days, segmented by `user_id`.

---

### `seizure_events`

Manual seizure diary entries. Added in V15.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `SERIAL PK` | |
| `user_id` | `INTEGER → users(id)` | Cascade delete |
| `occurred_at` | `TIMESTAMPTZ NOT NULL` | When the seizure happened |
| `duration_seconds` | `INTEGER` | Optional |
| `type` | `TEXT CHECK ('focal','generalized','unknown')` | Default `unknown` |
| `severity` | `SMALLINT CHECK (1–5)` | 1=very mild, 5=very severe; optional |
| `notes` | `TEXT` | Free text; optional |
| `created_at` | `TIMESTAMPTZ DEFAULT NOW()` | |

Index: `(user_id, occurred_at DESC)`

Entries are editable and deletable from the diary UI via `PATCH`/`DELETE
/api/seizures/{id}`; both DB helpers (`update_seizure`, `delete_seizure`) filter on
`id AND user_id` so a user can only mutate their own rows.

---

### `user_consents`

Audit log for user consent (DSGVO Art. 5(2) — Rechenschaftspflicht). Added in V19.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `SERIAL PK` | |
| `user_id` | `INTEGER → users(id) ON DELETE SET NULL` | Pseudonymised (not erased) on user delete to preserve the audit trail (V30; was `ON DELETE CASCADE` in V19) |
| `consent_type` | `TEXT NOT NULL` | e.g. `health_data` (Art. 9 explicit consent) |
| `accepted` | `BOOLEAN NOT NULL` | `true` = consent given |
| `timestamp` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | When consent was recorded |
| `ip_address_hash` | `TEXT` | SHA-256 prefix hash of request IP (DSGVO Art. 5(1)(c) data minimisation, V21) |
| `privacy_policy_version` | `TEXT NOT NULL DEFAULT 'v1.0'` | Policy version the user consented to |

UNIQUE on `(user_id, consent_type)` — upserted on re-registration via `ON CONFLICT DO UPDATE`.

---

### `user_tokens`

Fernet-encrypted session tokens for third-party service accounts. Added in V20.

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | `INT → users(id) ON DELETE CASCADE` | Token deleted automatically when user account is deleted |
| `service` | `TEXT CHECK (service IN ('garmin', 'libre'))` | |
| `token_data` | `BYTEA NOT NULL` | Fernet-encrypted JSON blob (filename-agnostic serialization of garth token dir) |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | Set on every upsert |

PRIMARY KEY on `(user_id, service)` — upserted on every successful connect/sync via `ON CONFLICT DO UPDATE`.

Tokens are encrypted with `FERNET_KEY` (AES-128-CBC + HMAC-SHA256). If `FERNET_KEY` is not set, tokens are stored unencrypted with a startup warning. The same key must be set in both `env/.env.api` and `env/.env.sync`.

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

Same column structure as `body_battery_intraday` (`time`, `user_id`, `value`); value = SpO2 percentage.

No compression policy — this hypertable is not compressed (unlike `body_battery_intraday` and `stress_intraday`).

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
