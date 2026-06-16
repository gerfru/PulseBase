# Data Model: KI-Wochen-Insights (Schicht 1)

DB: PostgreSQL / TimescaleDB | Date: 2026-06-16
Grundlage: [ADR-0003](adr/0003-ai-weekly-insights.md) · Exploration: [ai-insights-exploration.md](ai-insights-exploration.md)

Designt die Datenstrukturen für Schicht 1: das **`WeeklyInsight`-Schema** (Pydantic),
die **`evidence_catalog.json`-Struktur** und die **Persistenz**. Gegen den realen Code
(`api/src/db/`, Pydantic v2, asyncpg, `ml_predictions`-Muster).

---

## Kernunterscheidung (zieht sich durch alles)

> **Insight-Objekt ≠ Persistenz-Zeile.**
> Das `WeeklyInsight`-Objekt ist der LLM-Payload und enthält **nie** einen Identifier.
> Die DB-Zeile, die es speichert, **muss** `user_id` als FK haben (Zugriffsschutz,
> DSGVO-Löschung). Das Objekt liegt identifier-frei als JSONB *in* der Zeile; das LLM
> bekommt nur das deserialisierte Objekt, nie die Zeile.

---

## Step 0 — Access Patterns

| Frage | Antwort |
|---|---|
| Primär-Queries | (1) „hole Insight für (user, Woche)", (2) „hole letzte N Wochen für user" |
| Read/Write-Ratio | Write **1×/user/Woche**; Reads selten (Seitenaufruf). Winzig. |
| Skalierung | ~52 Zeilen/user/Jahr. Tausende, nie Milliarden. |
| Konsistenz | Pro (user, Woche) atomar; einmal generiert, stabil. |
| Kardinalität | PK (user_id, iso_year, iso_week) hoch selektiv. |

**Konsequenz:** Kein Hypertable (TimescaleDB-Hypertables sind für High-Ingest-Timeseries;
hier wäre das Over-Engineering), kein RAG, keine Vektor-DB. Eine **normale Postgres-Tabelle**.

---

## Decisions

| Entscheidung | Wahl | Begründung | Referenz |
|---|---|---|---|
| `Metric.key` | **Enum/`Literal`, kein Freitext** | Post-Check & Präsentation keyen darauf; Freitext lädt Tippfehler ein | CMU 15-445 (kontrolliertes Vokabular) |
| `Metric.value` | **`Decimal`**, nicht float | asyncpg liefert Decimal; exakte Zahlen-Treue für Number-Grounding | ADR-0003 (binärer 100 %-Check) |
| `trend` | Enum, **deterministisch aus `change_pct` abgeleitet** + Validator | Trend-Richtungs-Guard braucht konsistente Quelle | ADR-0003 Guardrails |
| Fehlende Werte | Metrik **weglassen**, separat `unavailable: [key]` | Kein `None`-Rauschen im Trust-Objekt; LLM kann „keine Glukose-Daten" nur aus erlaubter Liste sagen | 1NF / Atomarität |
| Identifier-Verbot | `extra="forbid"` + Feld-Denylist-Test + Runtime-Scan | „Schema-Regel + Test" aus ADR, dreifach abgesichert | ADR-0003 Invariante |
| Evidenz-Keys | Enum/Validierung **gegen geladenen Katalog** | Evidence-Grounding schon bei Objekt-Konstruktion, nicht erst Post-Check | ADR-0003 |
| `evidence_catalog` | **In-Repo JSON**, typisiert geladen, nicht DB | Klein, kuratiert, per PR reviewt, mit App deployt | ADR-0003 („kein RAG") |
| Persistenz | **Ja** — generierten Text + Objekt speichern | Stabilität (gleicher Text bei jedem Aufruf), History, Audit-Trail, Reproduzierbarkeit | Reference: „document as a whole → JSONB" |
| Texte | **Child-Tabelle** pro Segment | Sauberes 1NF, einzelnes Segment regenerierbar, Provenance pro Text | Normalization-Ref |
| JSONB für `insight_obj` | Bewusste Denormalisierung | Objekt wird immer als Ganzes gelesen, nie hinein-gequeryt | Reference Punkt 4 |

---

## Schema — Pydantic (Schicht 1, der Trust-Vertrag)

```python
from decimal import Decimal
from enum import Enum
from datetime import date
from pydantic import BaseModel, ConfigDict, model_validator

class MetricKey(str, Enum):
    HRV = "hrv"
    GLUCOSE_CV = "glucose_cv"
    TIME_IN_RANGE = "time_in_range"
    TRAINING_LOAD = "training_load"
    # … erweiterbar, aber kontrolliert

class Unit(str, Enum):
    MS = "ms"; PERCENT = "%"; TSS = "TSS"; MGDL = "mg/dL"; MMOL = "mmol/L"

class Trend(str, Enum):
    UP = "up"; SLIGHTLY_UP = "slightly_up"; STABLE = "stable"
    SLIGHTLY_DOWN = "slightly_down"; DOWN = "down"

class Metric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: MetricKey
    value: Decimal                 # exakt; aus Schicht-1-Code, nie float-gerundet
    unit: Unit
    change_pct: Decimal | None     # None = kein Vorwochen-Vergleich (erste Woche)
    trend: Trend

    @model_validator(mode="after")
    def _trend_matches_change(self):
        # Trend muss konsistent zum Vorzeichen von change_pct sein (Defense in Depth).
        if self.change_pct is not None:
            up = self.change_pct > 0
            down = self.change_pct < 0
            if up and self.trend in (Trend.DOWN, Trend.SLIGHTLY_DOWN): raise ValueError(...)
            if down and self.trend in (Trend.UP, Trend.SLIGHTLY_UP): raise ValueError(...)
        return self

class WeeklyInsight(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    # Zeitraum ist KEIN Identifier (Zeitspanne, keine Person) → erlaubt & nötig:
    iso_year: int
    iso_week: int
    metrics: list[Metric]
    unavailable: list[MetricKey] = []      # deterministisch bekannt fehlend
    flags: list[str]                       # später FlagKey-Enum
    evidence: list[str]                    # gegen Katalog validiert (s.u.)
    catalog_version: str                   # mit welcher Katalog-Version erzeugt
    # KEIN user_id, KEIN name, KEIN email — harte Invariante.
```

### Identifier-Verbot — dreifach erzwungen

1. **`extra="forbid"`** auf allen Modellen → kein Feld kann sich „einschleichen".
2. **Test** (die „Schema-Regel + Test" aus der ADR): introspiziert `WeeklyInsight`/`Metric`
   und scheitert, wenn ein Feldname gegen eine Denylist matcht
   (`user`, `user_id`, `id`, `name`, `email`, `ip`, …).
3. **Runtime-Guard** `assert_no_identifier(obj)` vor jedem LLM-Aufruf: scannt das
   serialisierte Dict rekursiv auf verbotene Keys **und** Wertmuster (E-Mail-Regex etc.).
   = die Input-PII-Prüfung aus den ADR-Guardrails.

### Empty Week / Insufficient Data

- Einzelne Metrik ohne Daten → nicht in `metrics`, sondern in `unavailable`.
- Ganze Woche ohne Daten → `metrics=[]`, `flags=[]`, `evidence=[]`. Präsentation/Generator
  nutzt das **Fallback-Template** („Diese Woche liegen zu wenige Daten für eine Auswertung vor.").
  Trotzdem wird eine Zeile persistiert → History bleibt lückenlos, fehlende Woche sieht nicht
  wie ein Bug aus.

### Deutscher Dezimal-Trenner (für Number-Grounding)

Eine deterministische Funktion `allowed_number_tokens(insight) -> set[str]` erzeugt aus den
`Decimal`-Werten **alle** erlaubten Render-Varianten — mit/ohne Vorzeichen, Punkt **und**
Komma (`-4.1`, `4.1`, `−4,1`, `4,1`). Der Post-Check whitelistet gegen diese Menge. Nicht
die Render-Strings im Objekt speichern (DRY — aus `Decimal` ableiten).

---

## Schema — evidence_catalog.json

```json
{
  "schema_version": "1.0.0",
  "entries": {
    "training.acwr_injury_risk": {
      "title": "Acute:Chronic Workload Ratio",
      "applies_to": ["training_load"],
      "statement": "[Platzhalter — fachlich zu kuratieren] Einordnung des ACWR.",
      "recommendation": "[Platzhalter] Einzige erlaubte Quelle für Empfehlungstext.",
      "evidence_level": "observational",
      "source": { "citation": "…", "url": "https://…" },
      "added": "2026-06-16",
      "reviewed_by": "<owner>"
    }
  }
}
```

> Die `statement`/`recommendation`-Texte oben sind **Platzhalter**, keine medizinischen
> Aussagen — sie müssen fachlich kuratiert und belegt werden, bevor sie live gehen.

**Design-Regeln:**

- **Key-Schema:** stabil, namespaced (`training.`, `glucose.`, `hrv.`). Keys sind ein
  **append-only Vertrag** — umbenennen bricht persistierte Insights & Golden-Set.
  Veraltete Einträge **deprecaten** (`"deprecated": true`), nie umbenennen/löschen.
- **`recommendation` = einzige erlaubte Quelle** für jeden Empfehlungstext (Regulatorik-Guard
  aus ADR 8.2). Das LLM darf nur daraus zitieren, nichts frei empfehlen.
- **`evidence_level`:** kontrolliertes Vokabular (`guideline` | `rct` | `observational` |
  `expert_opinion`) — gibt der Health-Pro-Präsentation die „Evidenz-Stärke".
- **Versionierung:** `schema_version` (Struktur) + Git-History (Inhalt) + per-Eintrag
  `added`/`reviewed_by`. Persistierte Insights speichern `catalog_version` → Reproduzierbarkeit.
- **Laden:** beim Start einmal in ein `EvidenceCatalog`-Pydantic-Modell parsen & validieren.
  Die Key-Menge daraus speist den `evidence`-Validator von `WeeklyInsight` (Evidence-Grounding
  bei Konstruktion). Niemals das rohe JSON durchreichen.
- **Kuration:** `reviewed_by` Pflichtfeld; idealerweise CODEOWNERS-Regel auf der Datei.

---

## Schema — Persistenz (SQL)

```sql
-- Eltern: ein identifier-freies Objekt pro (user, ISO-Woche)
CREATE TABLE weekly_insights (
    user_id     INTEGER  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    iso_year    SMALLINT NOT NULL,
    iso_week    SMALLINT NOT NULL,
    insight_obj JSONB    NOT NULL,            -- das WeeklyInsight (ohne Identifier)
    catalog_version TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, iso_year, iso_week)
);

-- Kind: ein Text pro Segment, mit eigener Provenance
CREATE TABLE weekly_insight_texts (
    user_id    INTEGER  NOT NULL,
    iso_year   SMALLINT NOT NULL,
    iso_week   SMALLINT NOT NULL,
    segment    TEXT     NOT NULL,             -- 'hobby' | 'pro' | 'profi'
    body       TEXT     NOT NULL,
    generator  TEXT     NOT NULL,             -- 'llm' | 'fallback_template'
    model_id   TEXT,                          -- gepinnte Modellversion; NULL bei Fallback
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, iso_year, iso_week, segment),
    FOREIGN KEY (user_id, iso_year, iso_week)
        REFERENCES weekly_insights (user_id, iso_year, iso_week) ON DELETE CASCADE
);
```

**Warum so:**

- **JSONB für `insight_obj`** ist *bewusste* Denormalisierung, kein 1NF-Verstoß: das Objekt
  wird immer als Ganzes gelesen, nie hinein-gequeryt. (Reference: „complex nested structure
  always accessed as a whole → JSONB".) Sollten je Cross-User-Analytics nötig sein
  („alle mit HRV-Drop > 10 %"), dann **separates CQRS-Read-Model**, nicht dieses Write-Model
  denormalisieren.
- **Child-Tabelle für Texte** statt drei `text_*`-Spalten: sauberes 1NF, ein Segment einzeln
  regenerierbar, und Provenance **pro Text** (ein Segment kann Fallback sein, während ein
  anderes LLM ist).
- **`ON DELETE CASCADE`** von `users(id)` → DSGVO-Löschrecht erbt automatisch (gleiches Muster
  wie `ml_predictions`).
- **`user_id` hier ist korrekt** und widerspricht der Invariante nicht — sie gilt für das
  Objekt (`insight_obj`-Inhalt), nicht für die Speicher-Hülle.
- **Provenance** (`catalog_version`, `model_id`, `generator`) liefert den „begründbar"-Audit-Trail
  für Health-Pros und die Replay-Fähigkeit für die Eval/Regression aus ADR-0003.

---

## Index Strategy

| Index | Spalten | Begründung | Trade-off |
|---|---|---|---|
| PK `weekly_insights` | `(user_id, iso_year, iso_week)` | Deckt beide Primär-Queries: exakt eine Woche **und** Range „letzte N Wochen" (`WHERE user_id=? ORDER BY iso_year DESC, iso_week DESC`). Führende Spalte `user_id` = composite-Regel korrekt. | — |
| PK `weekly_insight_texts` | `(user_id, iso_year, iso_week, segment)` | Fetch by Woche+Segment; FK-Lookup gedeckt. | — |

**Keine Zusatz-Indizes für v1.** Tabelle klein + schreibarm; jeder weitere Index wäre
Overhead ohne Query, der ihn nutzt (Anti-Pattern aus der Reference).

---

## Assumptions & Open Questions

- **Welcher Service generiert/schreibt?** Schicht-1-`db/`-Funktionen liegen in `api`. Generierung
  ist ein Wochen-Job (scheduled oder bei erstem Zugriff). Nach [ADR-0001](adr/0001-per-service-db-roles.md)
  braucht der schreibende Service ein **gezieltes Grant** (`INSERT/SELECT` auf beide Tabellen),
  Leser nur `SELECT`. → in der Migration mitdenken.
- **`flags`** ist vorerst `list[str]`; sobald die deterministischen Detektoren stehen → `FlagKey`-Enum.
- **Glukose-Einheit** (mg/dL vs mmol/L): pro-User-Präferenz? Falls ja, gehört die Umrechnung
  in Schicht 1 (deterministisch), das Objekt trägt die *gewählte* Einheit.
- **[Nicht verifiziert]** Die Evidenz-Texte sind Platzhalter — fachliche Kuration + Beleg
  ausstehend, bevor irgendetwas live geht.

---

## ✅ Setup Todo

- [ ] Pydantic-Modelle `MetricKey`/`Unit`/`Trend`/`Metric`/`WeeklyInsight` (`extra="forbid"`, `frozen`)
- [ ] `trend`-Konsistenz-Validator + `allowed_number_tokens()` (inkl. Komma-Varianten)
- [ ] Identifier-Test (Feld-Denylist) + `assert_no_identifier()` Runtime-Guard
- [ ] `EvidenceCatalog`-Modell + `evidence_catalog.json` (Key-Schema, `evidence_level`, Quelle, `reviewed_by`)
- [ ] `evidence`-Validator von `WeeklyInsight` gegen geladene Katalog-Keys
- [ ] Migration `V32__weekly_insights.sql` (beide Tabellen, FK-CASCADE)
- [ ] Per-Service-Grants für den schreibenden Service (ADR-0001-konform)
- [ ] CODEOWNERS-Regel auf `evidence_catalog.json`

## 📋 Next Steps (priorisiert)

1. **Pydantic-Modelle + Identifier-Test** — reiner, voll testbarer Kern, kein LLM, keine DB.
2. **Deterministische Sammel-/Flag-Funktion** gegen `get_glucose_stats` / `get_ml_insights`
   / `get_training_load_inputs` → baut `WeeklyInsight`.
3. **`evidence_catalog.json` + Loader + Validator** — kleiner Startumfang, fachlich kuratiert.
4. **Migration V32** + Grants — erst wenn das Objekt steht und Persistenz gebraucht wird.
5. Danach zurück zu ADR-0003 Schritt 2 (Post-Check-Guard) und Schritt 3 (LLM-Schicht).
