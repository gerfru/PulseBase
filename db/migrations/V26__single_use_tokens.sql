-- Wave 15: DB-backed single-use tokens for e-mail verification + account deletion.
-- Mirrors the password-reset pattern (V22): a SHA-256 token hash + expiry stored per
-- user, verified server-side (expires_at > NOW()) and cleared on consumption → the
-- token is strictly single-use and revocable (vs. the previous stateless itsdangerous
-- payloads that were replayable until expiry).
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email_verify_token_hash TEXT,
    ADD COLUMN IF NOT EXISTS email_verify_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS account_deletion_token_hash TEXT,
    ADD COLUMN IF NOT EXISTS account_deletion_expires_at TIMESTAMPTZ;
