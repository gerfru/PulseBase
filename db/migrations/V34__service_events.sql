-- Durable inter-service events; PostgreSQL NOTIFY is only a wake-up signal.
-- Existing users.* trigger flags remain active during the migration period.

CREATE TABLE service_events (
    id              BIGSERIAL PRIMARY KEY,
    event_type      TEXT NOT NULL CHECK (event_type IN ('sync_requested', 'ml_requested')),
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    available_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attempts        INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    claimed_at      TIMESTAMPTZ,
    processed_at    TIMESTAMPTZ,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT service_events_processing_consistency CHECK (
        (status = 'processing' AND claimed_at IS NOT NULL)
        OR status <> 'processing'
    )
);

CREATE INDEX idx_service_events_pending
    ON service_events (event_type, available_at, id)
    WHERE status IN ('pending', 'processing');

CREATE UNIQUE INDEX uq_service_events_open_user_type
    ON service_events (event_type, user_id)
    WHERE status IN ('pending', 'processing');

CREATE OR REPLACE FUNCTION notify_service_event() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify('service_events', NEW.id::text);
    RETURN NEW;
END;
$$;

CREATE TRIGGER service_events_notify
AFTER INSERT ON service_events
FOR EACH ROW EXECUTE FUNCTION notify_service_event();

GRANT SELECT, INSERT ON service_events TO ${db_app_user};
GRANT INSERT, UPDATE (status, available_at, attempts, claimed_at, processed_at, last_error)
    ON service_events TO ${DB_SYNC_USER};
GRANT SELECT, INSERT, UPDATE (status, available_at, attempts, claimed_at, processed_at, last_error)
    ON service_events TO ${DB_ML_USER};
GRANT USAGE, SELECT ON SEQUENCE service_events_id_seq TO ${DB_APP_USER};
GRANT USAGE, SELECT ON SEQUENCE service_events_id_seq TO ${DB_SYNC_USER};
GRANT USAGE, SELECT ON SEQUENCE service_events_id_seq TO ${DB_ML_USER};
