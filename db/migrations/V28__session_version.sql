-- Cross-session invalidation: bump session_version on password reset
-- so all existing signed cookies are rejected by require_user().
ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0;
