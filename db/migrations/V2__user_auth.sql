ALTER TABLE users
    ADD COLUMN authelia_username TEXT UNIQUE,
    ADD COLUMN garmin_email      TEXT,
    ADD COLUMN garmin_linked     BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN is_active         BOOLEAN NOT NULL DEFAULT true;
