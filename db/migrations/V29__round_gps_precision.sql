-- GDPR Art. 5(1)(c) data minimisation: round GPS to 4 decimal places (~11 m).
-- Full-precision coordinates (7+ decimal places) can identify exact addresses.
-- Disable TimescaleDB decompression limit for this bulk update (activity_records
-- is a compressed hypertable; default limit of 100k would block the backfill).
SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0;
UPDATE activity_records
    SET lat = ROUND(lat::numeric, 4)::double precision,
        lng = ROUND(lng::numeric, 4)::double precision
    WHERE lat IS NOT NULL AND lng IS NOT NULL;
RESET timescaledb.max_tuples_decompressed_per_dml_transaction;
