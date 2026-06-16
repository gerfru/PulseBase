# Implementierungsplan: KI-Wochen-Insights

Date: 2026-06-16 | Status: **Proposed** (Umsetzung von [ADR-0003](adr/0003-ai-weekly-insights.md))

Synthese aus den vier Design-Dokumenten — ein ausführbarer, phasierter Pfad:

- [Exploration](ai-insights-exploration.md) — Konzept, 3 Schichten, Eval-Strategie (8.4)
- [ADR-0003](adr/0003-ai-weekly-insights.md) — Pattern (Prompting-only), Architektur
- [Data-Design](design-data-ai-insights.md) — Schema, Katalog, Persistenz
- [Security-Design](design-secure-ai-insights.md) — Threat-Model, Controls C1–C8, Invarianten

> **Leitprinzip:** Zahlen aus Code, Worte aus dem LLM.
> **Baureihenfolge folgt dem Risiko:** der deterministische, testbare Kern + das
> Sicherheits-Gate zuerst; das LLM erst, wenn der Riegel steht.

---

## Leitplanken (gelten in jeder Phase)

Die 6 Security-Invarianten aus dem Security-Design sind **Definition of Done** für jede Phase, die sie berührt:

1. Kein ungeprüfter LLM-Text erreicht Nutzer **oder** DB (Post-Check, fail-secure).
2. Insight-Objekt im Prompt enthält **nie** einen Identifier.
3. Roher Health-Prompt/Response **nicht** in Standard-Logs.
4. Gesundheitsdaten verlassen das Homelab **nur** bei Cloud-Opt-in mit AVV.
5. Insight-Reads **immer** per Session-`user_id` gescopet.
6. KI-Text im UI **als KI-generiert gekennzeichnet** (AI-Act Art. 50).

---

## Vorschlag zur Code-Struktur (neu)

```
api/src/insights/
  __init__.py
  models.py          # WeeklyInsight, Metric, Enums (Phase 1)
  guard.py           # allowed_number_tokens, assert_no_identifier, Post-Check (Phase 1+3)
  evidence.py        # EvidenceCatalog-Loader + Validator (Phase 2)
  evidence_catalog.json
  collect.py         # Schicht-1-Builder gegen db/ (Phase 2)
  llm.py             # Provider-Abstraktion (lokal/Cloud) (Phase 4)
  templates.py       # Fallback- + Slot-Templates (Phase 3/4)
  generate.py        # Orchestrierung: collect→llm→guard→persist (Phase 5)
api/src/db/insights.py       # Persistenz-Queries (Phase 5)
api/src/routes/api_insights.py  # Endpoints, Scoping (Phase 6)
db/migrations/V32__weekly_insights.sql  # (Phase 5)
api/tests/insights/...       # Tests pro Phase
```

> Pfade sind Vorschlag — final an bestehende Konventionen angleichen.

---

## Phase 0 — ADR-Korrektur (Vorbedingung, ~15 min)

**Ziel:** Den dokumentierten Selbstwiderspruch schließen, bevor Code entsteht.

- [ ] ADR-0003 Observability-Todo: „Prompt, Response loggen" → **Metadaten** (Metrik-Keys,
      Post-Check-Ergebnis, Regenerations-Zahl, Latenz, Token) gemäß Security-Design C3.
- [ ] ADR-0003 `References` um [Security-Design](design-secure-ai-insights.md) + [Data-Design](design-data-ai-insights.md) ergänzen.
- [ ] ADR-Status ggf. auf **Accepted**, sobald der Plan freigegeben ist.

**DoD:** ADR enthält keine Aussage mehr, die Invariante 3 verletzt.

---

## Phase 1 — Schicht-1-Kern: Modelle + Identifier-Riegel

**Ziel:** Der voll testbare Trust-Vertrag. Kein LLM, keine DB. *Risikoärmster Einstieg.*
**Adressiert:** Invariante 2 · Daten-Design „Schema" · Security C1-Limitation (Schicht-1-Tests).

- [ ] `models.py`: `MetricKey`/`Unit`/`Trend`/`Metric`/`WeeklyInsight` (`extra="forbid"`, `frozen`).
- [ ] `Metric`-Validator: `trend` konsistent zum Vorzeichen von `change_pct`.
- [ ] `guard.py`: `allowed_number_tokens(insight)` — alle Render-Varianten inkl. **deutschem
      Komma** (`-4.1`, `4.1`, `−4,1`, `4,1`), mit/ohne Vorzeichen.
- [ ] `guard.py`: `assert_no_identifier(obj)` — rekursiver Key- + Wert-Scan (E-Mail-Regex).

**Tests (alle ohne I/O):**
- [ ] Identifier-Test: Feld-Denylist über `WeeklyInsight`/`Metric` (`user`, `user_id`, `id`, `name`, `email`, `ip`).
- [ ] `trend`-Validator akzeptiert/verwirft korrekt (inkl. `change_pct=None`).
- [ ] `allowed_number_tokens` deckt Komma/Punkt/Vorzeichen/Rundung ab.
- [ ] `assert_no_identifier` fängt eingeschmuggelte Keys **und** E-Mail-Werte.

**DoD:** 100 % der Tests grün; `assert_no_identifier` ist die Grundlage für Invariante 2.

---

## Phase 2 — Evidenz-Katalog + Schicht-1-Builder

**Ziel:** Das Insight-Objekt deterministisch aus echten Daten bauen.
**Adressiert:** ADR „Evidenz-Auflösung" · Security C6 (kuratierte/trusted Texte) · Regulatorik-Guard.

- [ ] `evidence_catalog.json`: Startumfang (wenige Einträge), namespaced Keys, `evidence_level`,
      `source`, `reviewed_by`. **Texte als Platzhalter markiert** bis fachliche Kuration.
- [ ] `evidence.py`: `EvidenceCatalog`-Pydantic-Modell, Laden+Validieren beim Start; exportiert
      gültige Key-Menge.
- [ ] `models.py`: `evidence`-Validator von `WeeklyInsight` gegen die Katalog-Keys (Grounding bei Konstruktion).
- [ ] `collect.py`: `build_weekly_insight(user_id, iso_year, iso_week)` gegen
      `get_glucose_stats` / `get_ml_insights` / `get_training_load_inputs`.
- [ ] Flag-Detektoren deterministisch (z.B. `training_load_spike`); vorerst `list[str]`.
- [ ] Empty-Week / `unavailable`-Logik (fehlende Metriken weglassen, Woche ohne Daten → leeres Objekt).

**Tests:**
- [ ] Katalog lädt; ungültiger Key wird abgelehnt.
- [ ] `build_weekly_insight` gegen **gemockte** db/-Returns → erwartete Objekte (inkl. Edge Cases:
      Spike, CGM-Lücke, alle stabil, widersprüchlich, leere Woche).
- [ ] CODEOWNERS-Regel auf `evidence_catalog.json`.

**DoD:** Schicht 1 erzeugt valide, identifier-freie Objekte für alle Edge Cases — voll deterministisch.

> ⚠️ **Blocker für Live, nicht für Bau:** Evidenz-Texte müssen fachlich kuratiert + belegt sein,
> bevor irgendetwas zu echten Nutzern geht ([Nicht verifiziert] medizinische Inhalte).

---

## Phase 3 — Post-Check-Gate + Fallback (das CRITICAL-Control)

**Ziel:** Der fail-secure Riegel — **bevor** das erste LLM dazukommt.
**Adressiert:** Security C1 (Risiko #1, Score 9) · Invariante 1 · Exploration 8.3.

- [ ] `guard.py`: `post_check(text, insight, segment) -> CheckResult` mit allen Riegeln:
      Number-Grounding (binär), Zahlwort-Blocklist, Evidence-Grounding, Trend-Richtung,
      Disclaimer-Präsenz, Identifier-Scan, Coverage.
- [ ] `templates.py`: deterministisches **Fallback-Template** (zahlen-treu, kein LLM).
- [ ] Gate-Logik: Fail → max. 2 Regenerationen → Fallback. Greift vor Auslieferung **und** Persistierung.

**Tests (mit synthetischen „LLM-Ausgaben", noch kein echtes LLM):**
- [ ] Jeder Riegel hat einen Positiv- + Negativ-Fall.
- [ ] Komma-Halluzination („knapp 60") wird gefangen.
- [ ] Trend-Widerspruch („verbessert" bei negativem `change_pct`) wird gefangen.
- [ ] Fallback erzeugt validen, post-check-konformen Text.

**DoD:** Das Gate ist als reine Funktion über Beispiel-Texte 100 % testbar — die wichtigste Versicherung steht.

---

## Phase 4 — Schicht 2: LLM-Provider + Generierung

**Ziel:** Der erste echte LLM-Aufruf, hinter dem Riegel aus Phase 3.
**Adressiert:** ADR „Modell" · Security C2/C7 · Invariante 4.

- [ ] `llm.py`: Provider-Abstraktion; **lokales Modell Default** (Ollama o.ä. auf Mac mini),
      Cloud nur per Opt-in-Flag. Modellversion **pinnen**.
- [ ] Prompt-Bau: nur das Insight-Objekt + Auftrag; `assert_no_identifier` **vor** dem Call (Invariante 2).
- [ ] `templates.py`: Slot-Template-Gerüst (Exploration 8.3 Stufe 3) für die spätere Härtung.
- [ ] **C7 — Inference-Härtung:** Endpoint nur localhost-Bind; Modell-Weights-Checksum; eigener Prozess.
- [ ] **C3 — Logging:** nur Metadaten; roher Prompt/Response nie in Standard-Logs.

**Tests:**
- [ ] Provider-Abstraktion gegen Fake-Provider (deterministische Antwort) — Orchestrierung ohne echtes Modell testbar.
- [ ] `assert_no_identifier` wird vor jedem Call ausgelöst (Test erzwingt es).
- [ ] Logging-Filter-Test: kein Health-Payload im Log-Output.

**DoD:** End-to-End-Generierung (collect→prompt→llm→guard→fallback) läuft lokal; Invarianten 2/3/4 testgedeckt.

---

## Phase 5 — Persistenz: Migration + Speicherung

**Ziel:** Stabile, auditierbare Insights mit Provenance.
**Adressiert:** Data-Design „Persistenz" · Security C8 · Invariante (DSGVO-Löschung).

- [ ] `V32__weekly_insights.sql`: `weekly_insights` + `weekly_insight_texts`, FK-CASCADE von `users(id)`.
- [ ] **Per-Service-Grants** für den schreibenden Service (ADR-0001-konform; nur Insight-Service schreibt).
- [ ] `db/insights.py`: Upsert Objekt + Texte (mit `catalog_version`, `model_id`, `generator`).
- [ ] `generate.py`: Orchestrierung inkl. Persistierung; Woche-ohne-Daten → Zeile + Fallback-Text.
- [ ] **C5:** Generierung als Batch/scheduled; Concurrency-Cap; Rate-Limit auf manuelle Regenerierung.
- [ ] Logs/Traces in den **DSGVO-Löschscope** aufnehmen.

**Tests:**
- [ ] Migration läuft via `make migrate` (nicht reset!) gegen Test-Stack.
- [ ] Upsert/Read-Roundtrip; `ON DELETE CASCADE` löscht Insights bei User-Löschung.
- [ ] Grant-Test: Insight-Service kann schreiben, andere Services nicht.

**DoD:** Insights werden reproduzierbar persistiert; Löschrecht erbt automatisch.

> Offene Frage (vor dieser Phase klären): **Welcher Service hostet Generierung/Inference?**
> Bestimmt Rolle, Isolation und Grant.

---

## Phase 6 — Schicht 3: Endpoints + Präsentation

**Ziel:** Insights sicher ausliefern, segment-spezifisch.
**Adressiert:** Security C4 (BOLA) · Invariante 5/6 · Regulatorik (Disclaimer).

- [ ] `api_insights.py`: `require_user` + Scoping **immer** per Session-`user_id` (nie Client-`user_id`).
- [ ] Präsentationsschicht: 3 Segmente (Hobby/Pro/Profi) — nur Tonlage/Tiefe, nicht Inhalt.
- [ ] **Disclaimer pro Segment** + **AI-Act-Art.-50-Kennzeichnung** „KI-generiert" im UI.
- [ ] CSP-konform: Insight-JS als statische Datei, kein Inline-Script.

**Tests:**
- [ ] **BOLA-Test:** User A kann Insight von User B **nicht** lesen (Security-Setup-Todo C4).
- [ ] Jedes Segment enthält Disclaimer + KI-Kennzeichnung (deterministisch prüfbar).

**DoD:** Endpoints scopen korrekt; Invarianten 5/6 testgedeckt.

---

## Phase 7 — Eval: Track A in CI (Safety-Gate)

**Ziel:** Regressionsschutz, bevor Prompt/Modell je wieder angefasst wird.
**Adressiert:** Exploration 8.4 · ADR „Evaluation" · Regression-Gate.

- [ ] Golden-Set: **≥ 30** kuratierte Insight-Objekte (Edge Cases), erwartete *Eigenschaften*.
- [ ] **Track A** (deterministisch, 100 %, CI-blockierend): Number-/Evidence-Grounding,
      Zahlwort-Blocklist, Trend-Richtung, Disclaimer, Kein-Identifier, Coverage.
- [ ] Regression-Gate verdrahten: Safety = 100 %; Metriken inkl. **Regenerations-Rate**.

**DoD:** CI bricht bei jeder Safety-Verletzung; Prompt-/Modell-Änderungen sind abgesichert.

---

## Phase 8 — Ausbaustufen (nach v1-Launch)

- [ ] **Track B** (LLM-as-Judge, Tonalität) + adversariale Schicht (Exploration 8.4).
- [ ] **Slot-Template** als stärkster Halluzinations-Riegel produktiv (8.3 Stufe 3).
- [ ] `flags` → `FlagKey`-Enum.
- [ ] **DPIA-Update + EU-AI-Act-Einstufung** rechtlich bestätigen (vor Public-Release).
- [ ] **v2: Profi-„frag-frei"-Agent** — eigener ADR + eigener Threat-Pass (Prompt-Injection/Excessive Agency werden CRITICAL).

---

## Abhängigkeiten

```text
P0 (ADR-Fix) ─┐
P1 (Modelle+Riegel) ──► P2 (Katalog+Builder) ──► P3 (Post-Check+Fallback) ──► P4 (LLM)
                                                                               │
                                                          P5 (Persistenz) ◄────┤
                                                                               ▼
                                                          P6 (Endpoints+UI) ──► P7 (Eval/CI)
                                                                               ▼
                                                                          P8 (Ausbau)
```

Kritischer Pfad: **P1 → P2 → P3 → P4**. P3 (CRITICAL-Control) liegt bewusst **vor** P4 (erstes LLM).

---

## Traceability — Risiko/Control → Phase

| Control / Risiko | Phase |
|---|---|
| C1 Output-Gate (Risiko #1, CRITICAL) | P3 |
| C2 Egress / Lokal-Default (#2) | P4 |
| C3 Log-Minimierung (#3) | P0 + P4 |
| C4 BOLA-Scoping (#4) | P6 |
| C5 Generierungs-Ratelimit (#5) | P5 |
| C6 Prompt-Injection (#6) | P2 + P4 |
| C7 Inference-Härtung (#7) | P4 |
| C8 Persistenz-Schutzniveau | P5 |
| Invariante 2 (kein Identifier) | P1 + P4 |
| Invariante 6 (AI-Act Art. 50) | P6 |

---

## Offene Punkte (vor bzw. während Umsetzung klären)

- **[Nicht verifiziert]** EU-AI-Act- & Art.-22-Einstufung — rechtlich bestätigen vor Public-Release (P8).
- **Welcher Service** hostet Generierung/Inference? (bestimmt P5-Rolle/Grant, P4-Isolation).
- **Evidenz-Kuration:** fachliche Texte + Belege — Blocker für Live, nicht für Bau (P2).
- **Glukose-Einheit** (mg/dL vs mmol/L) pro-User-Präferenz? (Umrechnung in Schicht 1, P2).
- **Cloud-Opt-in:** konkreter Anbieter + EU-Region + AVV — erst relevant, wenn Opt-in gebaut wird.
