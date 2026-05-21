ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ;
-- Existing users are considered verified (account was already active before this migration)
UPDATE users SET email_verified_at = NOW() WHERE email_verified_at IS NULL;
