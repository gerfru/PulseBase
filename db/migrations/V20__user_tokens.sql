CREATE TABLE IF NOT EXISTS user_tokens (
    user_id    INT  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service    TEXT NOT NULL CHECK (service IN ('garmin', 'libre')),
    token_data BYTEA NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, service)
);
