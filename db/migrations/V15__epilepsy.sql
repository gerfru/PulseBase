ALTER TABLE users
    ADD COLUMN IF NOT EXISTS epilepsy_mode BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS seizure_events (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    occurred_at      TIMESTAMPTZ NOT NULL,
    duration_seconds INTEGER,
    type             TEXT CHECK (type IN ('focal', 'generalized', 'unknown')) DEFAULT 'unknown',
    severity         SMALLINT CHECK (severity >= 1 AND severity <= 5),
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS seizure_events_user_date
    ON seizure_events (user_id, occurred_at DESC);
