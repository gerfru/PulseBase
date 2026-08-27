-- The sync producer uses ON CONFLICT against the open-event partial index.
-- PostgreSQL requires SELECT on the referenced table for this statement.
GRANT SELECT ON service_events TO ${DB_SYNC_USER};
