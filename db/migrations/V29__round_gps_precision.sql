-- GDPR Art. 5(1)(c) data minimisation: round GPS to 4 decimal places (~11 m).
-- Full-precision coordinates (7+ decimal places) can identify exact addresses.
UPDATE activity_records
    SET lat = ROUND(lat::numeric, 4)::double precision,
        lng = ROUND(lng::numeric, 4)::double precision
    WHERE lat IS NOT NULL AND lng IS NOT NULL;
