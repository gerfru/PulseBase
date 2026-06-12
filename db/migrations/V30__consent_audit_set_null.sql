-- GDPR Art. 5(2) accountability: preserve consent audit trail after user deletion.
-- Replaces ON DELETE CASCADE with SET NULL to pseudonymise rather than erase.

-- user_consent_events (immutable audit log — must never be deleted on user delete)
ALTER TABLE user_consent_events
    DROP CONSTRAINT user_consent_events_user_id_fkey;
ALTER TABLE user_consent_events
    ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE user_consent_events
    ADD CONSTRAINT user_consent_events_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;

-- user_consents (current consent state — pseudonymise on user delete)
ALTER TABLE user_consents
    DROP CONSTRAINT user_consents_user_id_fkey;
ALTER TABLE user_consents
    ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE user_consents
    ADD CONSTRAINT user_consents_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
