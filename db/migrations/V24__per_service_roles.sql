-- ARCH Review Finding #1 (PR-1): Least-Privilege-DB-Rollen pro Service.
--
-- Bisher verbinden sich api, sync-service und ml-service alle mit der breiten
-- Rolle ${DB_APP_USER} (garmin_app, GRANT ALL aus V7). Ein kompromittierter
-- sync-/ml-Prozess haette DELETE auf users + Lesezugriff auf user_tokens.
--
-- Diese Migration laesst garmin_app als api-Rolle unveraendert (breit) und legt
-- zwei eng-granierte Rollen an:
--   pulse_sync : Ingest — schreibt Health/Activity, liest/schreibt user_tokens,
--                setzt Trigger-Flags. KEIN Zugriff auf password_hash / Reset-Token.
--   pulse_ml   : Inferenz — liest Health read-only, schreibt nur ml_predictions,
--                setzt ml-Flags. KEIN Schreibzugriff auf Health, kein user_tokens.
--
-- Spalten-genaue Grants statt Tabellen-ALL (ASVS V4.1, DSGVO Art. 32).
-- Siehe docs/adr/0001-per-service-db-roles.md.

-- ── Rollen anlegen (idempotent) ──────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_SYNC_USER}') THEN
        EXECUTE format('CREATE ROLE %I WITH LOGIN PASSWORD %L NOINHERIT',
                       '${DB_SYNC_USER}', '${DB_SYNC_PASSWORD}');
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_ML_USER}') THEN
        EXECUTE format('CREATE ROLE %I WITH LOGIN PASSWORD %L NOINHERIT',
                       '${DB_ML_USER}', '${DB_ML_PASSWORD}');
    END IF;
END
$$;

GRANT CONNECT ON DATABASE garmin TO "${DB_SYNC_USER}", "${DB_ML_USER}";
GRANT USAGE   ON SCHEMA public    TO "${DB_SYNC_USER}", "${DB_ML_USER}";

-- ── pulse_sync — Garmin/Libre-Ingest ────────────────────────────────────────
-- users: nur nicht-sensible Spalten lesen (kein password_hash / Reset-Token),
-- nur Trigger-Spalten schreiben. WHERE-referenzierte Spalten brauchen SELECT.
GRANT SELECT (id, name, garmin_email, garmin_linked, libre_linked,
              is_active, sync_requested)                ON users TO "${DB_SYNC_USER}";
GRANT UPDATE (sync_requested, last_sync_at, ml_requested) ON users TO "${DB_SYNC_USER}";

-- Health-/Activity-/Glucose-Ingest-Tabellen: Lesen + Schreiben.
GRANT SELECT, INSERT, UPDATE ON
      activities, activity_records, daily_summary, sleep_sessions, hrv_daily,
      body_battery_intraday, spo2_readings, stress_intraday, glucose_readings
      TO "${DB_SYNC_USER}";

-- Garmin/Libre-Token lesen + per Upsert schreiben (kein DELETE — Unlink ist api).
GRANT SELECT, INSERT, UPDATE ON user_tokens TO "${DB_SYNC_USER}";

-- ── pulse_ml — Inferenz ──────────────────────────────────────────────────────
-- users: Read-only nicht-sensible Profilspalten (Alter/Geschlecht fuer HRmax),
-- nur ml-Flags schreiben.
GRANT SELECT (id, name, garmin_linked, is_active, ml_requested,
              date_of_birth, sex)                  ON users TO "${DB_ML_USER}";
GRANT UPDATE (ml_requested, last_ml_at)            ON users TO "${DB_ML_USER}";

-- Health/Activity nur LESEN.
GRANT SELECT ON
      activities, activity_records, daily_summary, sleep_sessions, hrv_daily,
      body_battery_intraday
      TO "${DB_ML_USER}";

-- ml_predictions: voller Zugriff (schreibt Inferenz, Backfill loescht/ersetzt).
GRANT SELECT, INSERT, UPDATE, DELETE ON ml_predictions TO "${DB_ML_USER}";

-- ── Sequenzen ────────────────────────────────────────────────────────────────
-- SERIAL-PKs der beschriebenen Tabellen brauchen USAGE,SELECT auf die Sequenz.
-- Sequenzen enthalten keine PII; pauschaler Grant ist hier vertretbar und robust.
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "${DB_SYNC_USER}";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "${DB_ML_USER}";
