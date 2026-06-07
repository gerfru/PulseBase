-- UX Review Finding [D3-1] (PR4): Item-Level-Feedback fuer KI-Outputs.
--
-- Bislang gibt es keinen Weg, eine ML-Prognose (Readiness-RF, Anomalie) zu
-- bestaetigen oder als unzutreffend zu markieren (HAX G9/G15). Diese Tabelle
-- speichert ein binaeres 👍/👎 pro (User, Modell, Tag).
--
-- ml_predictions hat einen zusammengesetzten PK (date, user_id, model) ohne
-- Auto-ID; das Feedback referenziert deshalb (user_id, model, prediction_date).
-- prediction_date wird serverseitig auf CURRENT_DATE gestempelt. Das UNIQUE
-- macht das Feedback idempotent/umschaltbar (Upsert via ON CONFLICT).

CREATE TABLE IF NOT EXISTS ml_feedback (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    model           TEXT NOT NULL,
    prediction_date DATE NOT NULL,
    helpful         BOOLEAN NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, model, prediction_date)
);

CREATE INDEX IF NOT EXISTS ml_feedback_user_date
    ON ml_feedback (user_id, prediction_date DESC);

-- api (garmin_app) schreibt das Feedback aus dem Dashboard.
GRANT SELECT, INSERT, UPDATE, DELETE ON ml_feedback TO "${DB_APP_USER}";
-- ml-service (pulse_ml) liest read-only als spaeteres Retraining-/Kalibrierungssignal.
GRANT SELECT ON ml_feedback TO "${DB_ML_USER}";
