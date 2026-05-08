-- Libre CGM integration: user columns + glucose readings hypertable

ALTER TABLE users
  ADD COLUMN libre_linked BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN libre_email  TEXT;

CREATE TABLE glucose_readings (
  time        TIMESTAMPTZ NOT NULL,
  user_id     INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  value_mgdl  REAL        NOT NULL,
  trend       SMALLINT,   -- 1=FallingQuickly 2=Falling 3=Stable 4=Rising 5=RisingQuickly
  is_high     BOOLEAN,
  is_low      BOOLEAN
);

SELECT create_hypertable('glucose_readings', 'time');

ALTER TABLE glucose_readings SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'user_id'
);

SELECT add_compression_policy('glucose_readings', INTERVAL '7 days');

CREATE UNIQUE INDEX ON glucose_readings (user_id, time);
