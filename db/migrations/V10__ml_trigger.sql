-- On-demand ML trigger: flag set by sync-service after sync, polled by ml-service

ALTER TABLE users
  ADD COLUMN ml_requested BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN last_ml_at   TIMESTAMPTZ;
