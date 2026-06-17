-- KI-Wochen-Insights — Persistenz (ADR-0003, Schicht 1+2; Data-Design).
--
-- Zwei Tabellen pro (User, ISO-Woche): das identifier-freie Insight-Objekt als
-- JSONB (immer als Ganzes gelesen → bewusste Denormalisierung, kein 1NF-Verstoss)
-- und ein Text pro Praesentations-Segment mit eigener Provenance. Generiert wird
-- lazy in api (kein Hypertable — winziges Volumen, PK deckt beide Queries).
--
-- DSGVO: ON DELETE CASCADE von users(id) → Loeschung erbt automatisch (zusaetzlich
-- expliziter Delete in delete_user, konsistent mit der dortigen Konvention).

CREATE TABLE IF NOT EXISTS weekly_insights (
    user_id         INTEGER  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    iso_year        SMALLINT NOT NULL,
    iso_week        SMALLINT NOT NULL,
    insight_obj     JSONB    NOT NULL,
    catalog_version TEXT     NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, iso_year, iso_week)
);

CREATE TABLE IF NOT EXISTS weekly_insight_texts (
    user_id    INTEGER  NOT NULL,
    iso_year   SMALLINT NOT NULL,
    iso_week   SMALLINT NOT NULL,
    segment    TEXT     NOT NULL,
    body       TEXT     NOT NULL,
    generator  TEXT     NOT NULL,          -- 'llm' | 'fallback_template'
    model_id   TEXT,                       -- gepinnte Modellversion; NULL bei Fallback
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, iso_year, iso_week, segment),
    FOREIGN KEY (user_id, iso_year, iso_week)
        REFERENCES weekly_insights (user_id, iso_year, iso_week) ON DELETE CASCADE
);

-- api (garmin_app) generiert + liest die Insights (lazy on demand).
GRANT SELECT, INSERT, UPDATE, DELETE ON weekly_insights      TO "${DB_APP_USER}";
GRANT SELECT, INSERT, UPDATE, DELETE ON weekly_insight_texts TO "${DB_APP_USER}";
