ALTER TABLE users
    ADD COLUMN IF NOT EXISTS date_of_birth DATE,
    ADD COLUMN IF NOT EXISTS sex           TEXT CHECK (sex IN ('m', 'f', 'diverse'));
