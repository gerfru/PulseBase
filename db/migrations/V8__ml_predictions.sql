CREATE TABLE IF NOT EXISTS ml_predictions (
    date        DATE    NOT NULL,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    model       TEXT    NOT NULL,
    value       FLOAT,
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (date, user_id, model)
);

CREATE INDEX IF NOT EXISTS ml_predictions_user_date
    ON ml_predictions (user_id, date DESC);
