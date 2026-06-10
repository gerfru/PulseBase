-- GDPR Art. 5(2) Accountability: immutable audit log of all consent events.
-- user_consents remains the current-state table (ON CONFLICT UPSERT).
-- Every consent change now also inserts a row here — never updated, never deleted.
CREATE TABLE user_consent_events (
    id               BIGSERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    consent_type     TEXT NOT NULL,
    accepted         BOOLEAN NOT NULL,
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address_hash  TEXT,
    privacy_policy_version TEXT
);

CREATE INDEX idx_consent_events_user ON user_consent_events(user_id, recorded_at DESC);

GRANT SELECT, INSERT ON user_consent_events TO ${db_app_user};
GRANT USAGE, SELECT ON SEQUENCE user_consent_events_id_seq TO ${db_app_user};
