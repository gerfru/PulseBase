ALTER TABLE users
    ADD COLUMN IF NOT EXISTS weight_kg FLOAT CHECK (weight_kg > 0 AND weight_kg <= 500);
