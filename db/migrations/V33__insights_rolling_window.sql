-- KI-Insights: Cadence-Pivot von fixer ISO-Woche -> rollierendes 7-Tage-Fenster
-- (ADR-0004, supersedet die Wochen-Cadence von ADR-0003).
--
-- Die Insight-Tabellen sind ein REGENERIERBARER Cache (kein Quelldatum) — daher
-- DROP + CREATE statt PK-ALTER mit FK-Juggling. Beim naechsten Aufruf werden die
-- Insights neu generiert. Key jetzt (user_id, period_end); das Fenster ist immer
-- [period_end-6 .. period_end].

DROP TABLE IF EXISTS weekly_insight_texts;
DROP TABLE IF EXISTS weekly_insights;

CREATE TABLE weekly_insights (
    user_id         INTEGER  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    period_start    DATE     NOT NULL,
    period_end      DATE     NOT NULL,
    insight_obj     JSONB    NOT NULL,
    catalog_version TEXT     NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, period_end)
);

CREATE TABLE weekly_insight_texts (
    user_id    INTEGER  NOT NULL,
    period_end DATE     NOT NULL,
    segment    TEXT     NOT NULL,
    body       TEXT     NOT NULL,
    generator  TEXT     NOT NULL,          -- 'llm' | 'fallback_template'
    model_id   TEXT,                       -- gepinnte Modellversion; NULL bei Fallback
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, period_end, segment),
    FOREIGN KEY (user_id, period_end)
        REFERENCES weekly_insights (user_id, period_end) ON DELETE CASCADE
);

-- api (garmin_app) generiert + liest die Insights (lazy on demand).
GRANT SELECT, INSERT, UPDATE, DELETE ON weekly_insights      TO "${DB_APP_USER}";
GRANT SELECT, INSERT, UPDATE, DELETE ON weekly_insight_texts TO "${DB_APP_USER}";
