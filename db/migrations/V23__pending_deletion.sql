-- L-04: Account deletion requires e-mail confirmation (pending_deletion_at + token).
-- Deletion is two-step: POST /account/delete sets pending_deletion_at and sends a
-- signed confirmation link; GET /account/delete/confirm/{token} executes the deletion.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS pending_deletion_at TIMESTAMPTZ;
