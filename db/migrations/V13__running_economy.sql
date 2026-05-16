ALTER TABLE activities
    ADD COLUMN avg_ground_contact_time  INTEGER,
    ADD COLUMN avg_vertical_oscillation NUMERIC(4,1),
    ADD COLUMN avg_stride_length        NUMERIC(4,2),
    ADD COLUMN avg_vertical_ratio       NUMERIC(4,1),
    ADD COLUMN avg_running_power        INTEGER;
