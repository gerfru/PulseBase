-- Garmin Dashboard — Initial Schema
-- TimescaleDB + PostgreSQL 16

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ── USERS ────────────────────────────────────────────────────────────────────

CREATE TABLE users (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── SUMMARY TABLES ───────────────────────────────────────────────────────────

CREATE TABLE activities (
    id                   SERIAL PRIMARY KEY,
    user_id              INTEGER NOT NULL REFERENCES users(id),
    garmin_activity_id   BIGINT  NOT NULL UNIQUE,
    started_at           TIMESTAMPTZ NOT NULL,
    duration_seconds     INTEGER,
    sport_type           TEXT NOT NULL,
    distance_meters      FLOAT,
    calories             INTEGER,
    avg_hr               SMALLINT,
    max_hr               SMALLINT,
    avg_pace_sec_per_km  FLOAT,
    avg_cadence          SMALLINT,
    avg_power            SMALLINT,
    elevation_gain       FLOAT,
    avg_speed_kmh        FLOAT,
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_activities_user_started ON activities (user_id, started_at DESC);

CREATE TABLE daily_summary (
    date              DATE    NOT NULL,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    steps             INTEGER,
    calories_total    INTEGER,
    avg_stress        SMALLINT,
    max_stress        SMALLINT,
    avg_spo2          SMALLINT,
    min_spo2          SMALLINT,
    body_battery_high SMALLINT,
    body_battery_low  SMALLINT,
    resting_hr        SMALLINT,
    PRIMARY KEY (date, user_id)
);

CREATE TABLE sleep_sessions (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    garmin_sleep_id     BIGINT  UNIQUE,
    start_time          TIMESTAMPTZ NOT NULL,
    end_time            TIMESTAMPTZ NOT NULL,
    total_sleep_seconds INTEGER,
    deep_sleep_seconds  INTEGER,
    light_sleep_seconds INTEGER,
    rem_sleep_seconds   INTEGER,
    awake_seconds       INTEGER,
    sleep_score         SMALLINT
);

CREATE INDEX idx_sleep_user_start ON sleep_sessions (user_id, start_time DESC);

CREATE TABLE hrv_daily (
    date           DATE    NOT NULL,
    user_id        INTEGER NOT NULL REFERENCES users(id),
    hrv_last_night SMALLINT,
    hrv_weekly_avg SMALLINT,
    hrv_status     TEXT,
    PRIMARY KEY (date, user_id)
);

-- ── TIMESERIES HYPERTABLES ───────────────────────────────────────────────────

CREATE TABLE activity_records (
    time             TIMESTAMPTZ NOT NULL,
    activity_id      INTEGER     NOT NULL REFERENCES activities(id),
    user_id          INTEGER     NOT NULL,
    heart_rate       SMALLINT,
    pace_sec_per_km  FLOAT,
    cadence          SMALLINT,
    power            SMALLINT,
    elevation        FLOAT,
    distance         FLOAT,
    lat              DOUBLE PRECISION,
    lng              DOUBLE PRECISION
);

SELECT create_hypertable('activity_records', 'time');

CREATE INDEX idx_activity_records_activity ON activity_records (activity_id, time DESC);

ALTER TABLE activity_records SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'activity_id'
);

SELECT add_compression_policy('activity_records', INTERVAL '7 days');


CREATE TABLE body_battery_intraday (
    time    TIMESTAMPTZ NOT NULL,
    user_id INTEGER     NOT NULL,
    value   SMALLINT    NOT NULL
);

SELECT create_hypertable('body_battery_intraday', 'time');

ALTER TABLE body_battery_intraday SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'user_id'
);

SELECT add_compression_policy('body_battery_intraday', INTERVAL '30 days');


CREATE TABLE stress_intraday (
    time    TIMESTAMPTZ NOT NULL,
    user_id INTEGER     NOT NULL,
    value   SMALLINT    NOT NULL
);

SELECT create_hypertable('stress_intraday', 'time');

ALTER TABLE stress_intraday SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'user_id'
);

SELECT add_compression_policy('stress_intraday', INTERVAL '30 days');


CREATE TABLE spo2_readings (
    time    TIMESTAMPTZ NOT NULL,
    user_id INTEGER     NOT NULL,
    value   SMALLINT    NOT NULL
);

SELECT create_hypertable('spo2_readings', 'time');


CREATE TABLE sleep_levels (
    time             TIMESTAMPTZ NOT NULL,
    sleep_session_id INTEGER     NOT NULL REFERENCES sleep_sessions(id),
    user_id          INTEGER     NOT NULL,
    level            TEXT        NOT NULL
);

SELECT create_hypertable('sleep_levels', 'time');
