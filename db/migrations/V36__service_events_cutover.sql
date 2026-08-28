-- ADR-0005: durable, coalescing inter-service work queue.
-- A producer increments generation when work is requested for an open job. If
-- that happens while the job is processing, acknowledgement returns it to
-- pending instead of losing the follow-up request.

ALTER TABLE service_events
    ADD COLUMN generation INTEGER NOT NULL DEFAULT 1 CHECK (generation > 0),
    ADD COLUMN claimed_generation INTEGER CHECK (claimed_generation > 0);

UPDATE service_events
SET claimed_generation = generation
WHERE status = 'processing';

ALTER TABLE service_events
    ADD CONSTRAINT service_events_claimed_generation_consistency CHECK (
        (status = 'processing' AND claimed_generation IS NOT NULL)
        OR (status <> 'processing' AND claimed_generation IS NULL)
    );

CREATE INDEX idx_service_events_completed_retention
    ON service_events (processed_at)
    WHERE status = 'completed';

DROP TRIGGER service_events_notify ON service_events;

CREATE OR REPLACE FUNCTION notify_service_event() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'pending' THEN
        PERFORM pg_notify('service_events', NEW.id::text);
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER service_events_notify
AFTER INSERT OR UPDATE OF status, generation ON service_events
FOR EACH ROW EXECUTE FUNCTION notify_service_event();

-- Preserve requests written by the legacy flag-only path before the cutover.
INSERT INTO service_events (event_type, user_id)
SELECT 'sync_requested', users.id
FROM users
WHERE users.sync_requested = true
ON CONFLICT (event_type, user_id)
WHERE status IN ('pending', 'processing') DO UPDATE
SET generation = service_events.generation + 1;

INSERT INTO service_events (event_type, user_id)
SELECT 'ml_requested', users.id
FROM users
WHERE users.ml_requested = true
ON CONFLICT (event_type, user_id)
WHERE status IN ('pending', 'processing') DO UPDATE
SET generation = service_events.generation + 1;

-- Producers may coalesce their own open commands; consumers may mutate and
-- retain only the command type they own.
GRANT UPDATE (generation, payload, available_at, attempts, last_error)
    ON service_events TO ${DB_APP_USER};
GRANT UPDATE (generation, payload, claimed_generation)
    ON service_events TO ${DB_SYNC_USER};
GRANT UPDATE (claimed_generation) ON service_events TO ${DB_ML_USER};
GRANT DELETE ON service_events TO ${DB_SYNC_USER}, ${DB_ML_USER};

ALTER TABLE service_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY service_events_app_select ON service_events
    FOR SELECT TO ${DB_APP_USER}
    USING (event_type IN ('sync_requested', 'ml_requested'));
CREATE POLICY service_events_app_insert ON service_events
    FOR INSERT TO ${DB_APP_USER}
    WITH CHECK (event_type = 'sync_requested');
CREATE POLICY service_events_app_update ON service_events
    FOR UPDATE TO ${DB_APP_USER}
    USING (event_type = 'sync_requested')
    WITH CHECK (event_type = 'sync_requested');

CREATE POLICY service_events_sync_select ON service_events
    FOR SELECT TO ${DB_SYNC_USER}
    USING (event_type IN ('sync_requested', 'ml_requested'));
CREATE POLICY service_events_sync_insert ON service_events
    FOR INSERT TO ${DB_SYNC_USER}
    WITH CHECK (event_type = 'ml_requested');
CREATE POLICY service_events_sync_update ON service_events
    FOR UPDATE TO ${DB_SYNC_USER}
    USING (event_type IN ('sync_requested', 'ml_requested'))
    WITH CHECK (event_type IN ('sync_requested', 'ml_requested'));
CREATE POLICY service_events_sync_delete ON service_events
    FOR DELETE TO ${DB_SYNC_USER}
    USING (event_type = 'sync_requested' AND status = 'completed');

-- INSERT remains temporarily available for startup reconciliation during the
-- rolling cutover. A later flag-removal migration can revoke it.
CREATE POLICY service_events_ml_select ON service_events
    FOR SELECT TO ${DB_ML_USER}
    USING (event_type = 'ml_requested');
CREATE POLICY service_events_ml_insert ON service_events
    FOR INSERT TO ${DB_ML_USER}
    WITH CHECK (event_type = 'ml_requested');
CREATE POLICY service_events_ml_update ON service_events
    FOR UPDATE TO ${DB_ML_USER}
    USING (event_type = 'ml_requested')
    WITH CHECK (event_type = 'ml_requested');
CREATE POLICY service_events_ml_delete ON service_events
    FOR DELETE TO ${DB_ML_USER}
    USING (event_type = 'ml_requested' AND status = 'completed');
