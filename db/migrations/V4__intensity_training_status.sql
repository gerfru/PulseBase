ALTER TABLE daily_summary
    ADD COLUMN IF NOT EXISTS intensity_moderate  smallint,
    ADD COLUMN IF NOT EXISTS intensity_vigorous  smallint,
    ADD COLUMN IF NOT EXISTS training_status     text;
