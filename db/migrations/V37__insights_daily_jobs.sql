CREATE TABLE insights_daily_jobs (
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    period_end   DATE NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    attempts     INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    last_error   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, period_end),
    CONSTRAINT insights_daily_jobs_processing_check CHECK (
        (status = 'processing' AND claimed_at IS NOT NULL)
        OR (status <> 'processing' AND claimed_at IS NULL)
    )
);

CREATE INDEX idx_insights_daily_jobs_pending
    ON insights_daily_jobs (available_at, period_end, user_id)
    WHERE status = 'pending';

GRANT SELECT, INSERT, UPDATE ON insights_daily_jobs TO "${DB_APP_USER}";
