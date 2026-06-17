# ADR-0003: KI-Wochen-Insights — Integration-Pattern & Architektur

## Status

Accepted — 2026-06-16

> **Teilweise superseded durch [ADR-0004](0004-rolling-window-cadence.md) (2026-06-17):**
> Die **Kadenz** wechselt von der fixen ISO-Woche auf ein **rollierendes 7-Tage-Fenster**
> (endend gestern), ohne Kalender-Navigation. Architektur, Sicherheits-Invarianten 1–6,
> das 3-Schichten-Pattern und „Zahlen aus Code, Worte aus dem LLM" bleiben unverändert.

Verdichtet die Exploration [`docs/ai-insights-exploration.md`](../ai-insights-exploration.md)
zu einer entscheidungsfesten Spec. Umsetzung phasiert gemäß
[`docs/ai-insights-implementation-plan.md`](../ai-insights-implementation-plan.md).

## Context

PulseBase soll ein **KI-gestütztes Wochen-Insight-Feature** bekommen: ein kurzer,
verständlicher Text, der die wöchentlichen Trainings-, Glukose- und HRV-Kennzahlen
einordnet — differenziert für drei Segmente (Hobby-Sportler, Health-Pro/Trainer,
Profi-Sportler).

**Auslösender Kontext & Randbedingungen:**

- **Gesundheitsdaten (DSGVO Art. 9):** HRV, Glukose, Trainingslast sind besonders
  schützenswert. PulseBase ist self-hosted (Mac mini = Prod) und für einen
  öffentlichen, multi-mandantenfähigen Release vorgesehen (vgl. [ADR-0001](0001-per-service-db-roles.md),
  [`docs/dpia.md`](../dpia.md)).
- **Haftung = höchstes Risiko:** Eine erfundene Gesundheitszahl ist bei Hobby-Nutzern
  ärgerlich, bei Health-Pros & Profis geschäftsschädigend. Die Fehlertoleranz der
  zahlungskräftigen Segmente ist *sehr niedrig bis null*.
- **Bestehender deterministischer Kern:** `get_glucose_stats`, `get_ml_insights`,
  `training_load` etc. liefern bereits verlässliche Zahlen. Der LLM-Bedarf ist
  *Formulierung*, nicht *Berechnung*.

**Leitprinzip (aus der Exploration):**

> **Zahlen kommen aus Code, Worte kommen aus dem LLM.**

## Decision Drivers

- **Vertrauen / keine Halluzination zuerst** — höchste Priorität wegen Haftung.
- **DSGVO Art. 9 / Offline-Fähigkeit** — Gesundheitsdaten sollen das Homelab nach
  Möglichkeit nicht verlassen (Stand der Technik, OWASP ASVS, vgl. ADR-0001).
- **KISS / Reversibilität** — LLM-Pattern-Entscheidungen (Embeddings, Fine-tune-Runs,
  Agent-Loops) sind in Produktion schwer umkehrbar. CMU 11-667: *„Always start with
  the simplest pattern: Prompt → RAG → Fine-tune → Agent."*
- **Eine Engine für drei Segmente** — gemeinsamer deterministischer Kern, nur die
  Präsentation variiert. Nicht dreimal bauen.

## Considered Options

- **A — Prompting-only mit strukturiertem Input** (kontrollierter Code-Orchestrierungs-
  Pfad; Evidenz als deterministischer Lookup im Prompt-Kontext).
- **B — RAG** über einen Health-/Evidenz-Korpus (Vektor-DB, Embeddings).
- **C — Agent/Tool-Loop** sofort (LLM entscheidet selbst, welche Daten-Tools es zieht).
- **D — Fine-tune** auf einen Health-Insight-Stil.

## Decision Outcome

**Gewählt: Option A — Prompting-only mit strukturiertem Input — für v1.**
Der Agent-Pfad (Option C) wird **bewusst auf v2** verschoben (Profi-Feature „frag
deine Daten frei") und greift dort auf **dieselbe** Fakten-Schicht zu.

Begründung: Das Wissen (die Zahlen) entsteht deterministisch im Code — es gibt also
*keinen Wissens-Bottleneck*, den RAG (B) lösen würde. Das Verhalten (3 Tonlagen)
ist über Prompting + Präsentationsmodi abbildbar bei geringem Volumen (1 Insight /
Nutzer / Woche) — also *kein Verhaltens-Bottleneck*, der Fine-tune (D) rechtfertigt.
Ein Agent (C) löst „mehrere Schritte / externe Aktionen" — die Wochen-Insight ist
ein einzelner, kontrollierter Aufruf. Damit ist Prompting-only nach CMU 11-667 die
korrekte und am leichtesten umkehrbare Wahl.

> **Wichtig:** Der Evidenz-Katalog ist **kein RAG**. Er ist ein kleiner, kuratierter
> Key-Lookup (`evidence_catalog.json`), der in Schicht 1 *deterministisch* aufgelöst
> und als fertiger Kontext in den Prompt gelegt wird — keine Embeddings, keine
> Vektor-DB, keine Retrieval-Latenz.

### Decisions (Übersicht)

| Entscheidung | Wahl | Begründung | Referenz |
|---|---|---|---|
| Integration-Pattern v1 | Prompting-only, strukturierter Input | Kein Wissens-/Verhaltens-Bottleneck; einfachste & reversibelste Wahl | CMU 11-667 Lec 4/11; integration-patterns.md |
| Evidenz-Auflösung | Deterministischer Key-Lookup (kein RAG) | Katalog klein & kuratiert; Retrieval würde nur Latenz + Fehlerquelle addieren | CMU 11-667 Lec 5–7 |
| Modell | Lokales Instruct-Modell (Default), hinter Abstraktion austauschbar | DSGVO Art. 9 → offline; geringes Volumen → lokale Kosten ~0 | Chip Huyen, ML Systems Ch. 6; SKILL Step 2 |
| Cloud-API | Nur Opt-in, mit Pseudonymisierung vor dem Prompt | Default soll Homelab nicht verlassen | DPIA, ADR-0001 |
| Halluzinations-Gate | Number-Grounding als **binärer 100 %-Check** | Strukturierter Input erlaubt exakte Prüfung statt 0–1-Faithfulness-Score | evaluation-framework.md (RAGAS-Analog) |
| Fehler-Fallback | Deterministisches Template (kein LLM) | Bei wiederholtem Post-Check-Fail muss ein sicherer, zahlen-treuer Text bleiben | Chip Huyen, Guardrails |
| Agent-Pattern | Auf v2 verschoben | „Mehrere Schritte" trifft erst auf das Profi-„frag-frei"-Feature zu | CMU 11-667 Lec 11/14 |

## Architecture Overview

Drei Schichten (Detail in der Exploration, Abschnitt 6). Datenfluss:

```text
Schicht 1  FAKTEN (deterministisch, Code)
  db/-Funktionen + Flag-Erkennung + evidence_catalog-Lookup
  → WeeklyInsight-Objekt (strikt, ohne Identifier)
        │  nur geprüfte Zahlen + Evidenz-Keys
        ▼
Schicht 2  ERKLÄR (LLM, 1 kontrollierter Aufruf)
  verbalisiert · ordnet ein · nennt Evidenz · rechnet NIE
        │  Roh-Text
        ▼
  POST-CHECK (Code-Guard)
  Number-Grounding · Zahlwort-Blocklist · Evidence-Grounding ·
  Trend-Richtung · Disclaimer · Kein-Identifier
        │  bestanden? ── nein ──► Regenerate (max. 2) ──► Fallback-Template
        ▼ ja
Schicht 3  PRÄSENTATION (pro Segment: Tonlage/Tiefe, NICHT Inhalt)
  Hobby kurz · Pro + Zahlen/Evidenz/Export · Profi + Rohdaten
```

**Insight-Objekt** = Vertrauens-Vertrag (Schema in Exploration 6). Zusatz-Invariante
dieser ADR: **enthält nie einen Identifier** (Name/User-ID) — als Schema-Regel **plus
Test** (siehe Setup-Todo).

**Modellwahl:** Default ist ein **lokales Instruct-Modell** auf dem Mac mini
(Referenzklasse Llama 3.1 8B–70B / Mistral 7B gemäß SKILL Step 2), gekapselt hinter
einer schmalen Provider-Abstraktion, damit ein Wechsel (oder Cloud-Opt-in) keine
Schicht-2-Änderung erzwingt.

> [Nicht verifiziert] Ob ein konkretes kleines lokales Modell die **deutsche**
> Formulierungsqualität für Health-Texte ausreichend trifft, ist nicht gemessen — das
> wird zum Eval-Kriterium (Track B), nicht zur Annahme. Modellversion **pinnen**.

## Evaluation Strategy

Zwei getrennte Tracks (Detail in Exploration 8.4). Reihenfolge: erst Track A + Golden-Set,
dann Track B.

- **Golden-Set:** kuratierte `Insight-Objekte` mit erwarteten *Eigenschaften* (nicht
  exakte Strings). Edge Cases: Spike, fehlende Werte, alle Trends stabil, widersprüchliche
  Signale, Extremwerte, leere Woche. **Start ≥ 30, Ausbau ≥ 50.**
  *(Hinweis: das SKILL/CMU-Minimum nennt 50+; v1 startet bei ≥ 30 und wächst über
  echte Produktionsfälle.)*
- **Track A — Safety (deterministisch, muss 100 % bestehen, CI-blockierend):**
  Number-Grounding, Zahlwort-Blocklist, Evidence-Grounding, Trend-Richtung,
  Disclaimer-Präsenz, Kein-Identifier-Leak, Coverage.
  → Das Number-Grounding ist hier das **Faithfulness-Äquivalent zu RAGAS**, aber als
  **binärer 100 %-Gate** statt 0–1-Score — möglich, weil der Input strukturiert ist.
- **Track B — Quality (LLM-as-Judge, Schwellwert):** Ton passt zum Segment, Klarheit,
  kein Widerspruch. Judge mit stärkerem Modell, gegen ein human-gelabeltes Set
  validiert (Bias-Risiken: Position-/Length-Bias).
- **Regression-Gate:** läuft bei jedem Prompt-/Modell-Wechsel. Pass: **Safety = 100 %**,
  Quality ≥ Baseline − 3 %.
- **Metriken:** Halluzinations-Rate, Evidence-Grounding-Rate, Judge-Pass-Rate und
  **Regenerations-Rate** (Frühwarnsignal für schlechten Prompt).

## Guardrails

- **Input:** v1 hat **keinen freien User-Text** → Prompt-Injection-Fläche minimal.
  Restrisiko: Inhalt aus Daten-/Evidenz-Feldern darf nicht als Instruktion wirken →
  Feld-Inhalte als Daten markieren/escapen.
- **Output:** der Post-Check (Track A) als harter Riegel **vor** der Auslieferung.
- **Fallback:** bei wiederholtem Post-Check-Fail → deterministisch erzeugter,
  zahlen-treuer Standardtext (kein LLM). Niemals einen ungeprüften LLM-Text ausliefern.
- **Topic-Guard:** v1 nicht nötig (kein freier Dialog); wird in v2 (Agent) relevant.
- **Regulatorik:** keine individualisierten Handlungsanweisungen; Empfehlungen nur aus
  `evidence_catalog`. Disclaimer pro Segment in Schicht 3 (Exploration 8.2).

## Cost & Latency Budget

- **Volumen:** ~1 Insight / Nutzer / Woche → niedrig; nicht interaktiv (Batch-tauglich).
- **Latenz:** unkritisch (Sekunden bis zweistellige Sekunden akzeptabel).
- **Kosten:** lokales Modell → marginale Kosten ~0; nur Rechenzeit auf dem Mac mini.
  Cloud-Opt-in würde Token-Kosten einführen — bewusst nicht der Default.

## Positive Consequences

- Halluzinationsrisiko strukturell minimiert (geprüft, nicht gehofft) — adressiert
  das Haftungs-Kernrisiko.
- DSGVO Art. 9 über Architektur gelöst (lokal + Objekt ohne Identifier) statt nur
  vertraglich.
- Reversibel: kein Embedding-/Fine-tune-/Agent-Lock-in; v1 kann verworfen werden,
  ohne Datenpipelines zurückzubauen.
- Schicht 1 ist framework-unabhängig, voll testbar und der eigentliche Wert.

## Negative Consequences (akzeptierte Trade-offs)

- Schicht 2 braucht eine **eigene Eval** (echte Zusatzarbeit) — billigste Versicherung
  gegen stille Regressionen, aber Aufwand.
- Lokales Modell kann in deutscher Formulierungsqualität schwächer sein als ein
  Cloud-Frontier-Modell — bewusst über Eval abgesichert, ggf. Cloud-Opt-in.
- Slot-Template (stärkster Post-Check-Riegel) begrenzt die sprachliche Freiheit der
  Ausgabe — akzeptiert zugunsten der Zahlen-Treue.

## Pros and Cons of the Options

### Option A — Prompting-only, strukturierter Input (gewählt)
- **Pro:** einfachste & reversibelste Wahl; exakte Faithfulness-Prüfung möglich;
  niedrige Kosten/Latenz; offline-fähig.
- **Contra:** sprachlich gebunden an das Insight-Objekt; eigene Eval nötig.

### Option B — RAG über Evidenz-/Health-Korpus
- **Pro:** skaliert, wenn der Evidenz-Korpus groß/dynamisch würde.
- **Contra:** löst einen Bottleneck, den es hier nicht gibt; addiert Embeddings,
  Vektor-DB, Retrieval-Latenz und eine neue Halluzinations-Quelle. Over-Engineering
  für einen kleinen kuratierten Katalog.

### Option C — Agent/Tool-Loop sofort
- **Pro:** maximale Flexibilität; nötig für freies Nachfragen (Profi).
- **Contra:** mehrere LLM-Aufrufe → höhere Kosten/Latenz/Fehlerfläche; mehr Autonomie =
  schwerer gegen Halluzination abzusichern. Für eine Einzel-Insight unnötig. → v2.

### Option D — Fine-tune auf Insight-Stil
- **Pro:** konsistenter Ton ohne lange Prompts.
- **Contra:** Verhaltens-Bottleneck ist nicht das Problem; < 500 Beispiele; Retraining-
  Aufwand; verlagert nichts am Zahlen-Risiko. Verfrüht.

## Setup Todo

- [ ] `WeeklyInsight`-Schema (Pydantic) + harte Regel „kein Identifier" **+ Test**
- [ ] Deterministische Sammel-/Flag-Funktion gegen bestehende `db/`-Funktionen (kein LLM)
- [ ] `evidence_catalog.json` — Struktur, Quellenangabe, Versionierung, Kurations-Owner
- [ ] Provider-Abstraktion + lokales Instruct-Modell auf dem Mac mini aufsetzen (Version pinnen)
- [ ] Post-Check-Guard: Number-Grounding + Zahlwort-Blocklist + Evidence/Trend/Disclaimer/Identifier
- [ ] Fallback-Template (deterministisch) bei wiederholtem Post-Check-Fail
- [ ] Schicht 2: 1 kontrollierter LLM-Aufruf + 3 Präsentationsmodi (Schicht 3)
- [ ] Golden-Set (≥ 30) + Track-A-Checks in CI; Regression-Gate verdrahten
- [ ] Observability: pro LLM-Call **nur Metadaten** loggen (Metrik-*Keys* statt Werte,
      Latenz, Tokens, Modell, Post-Check-Ergebnis, Regenerations-Zahl). **Roher
      Prompt/Response gehört NICHT in Standard-Logs** — der Prompt enthält Art.-9-Daten
      (vgl. Security-Design C3). Voll-Trace nur opt-in + im Art.-9-Schutzniveau.

## Next Steps (priorisiert)

1. **Schicht 1 + Schema + Test** — reines, voll testbares Coding, kein LLM.
2. **Post-Check-Guard + Fallback** — der Sicherheits-Riegel, vor jedem LLM-Einsatz.
3. **Schicht 2 + Präsentationsmodi** — der erste LLM-Aufruf.
4. **Golden-Set + Track-A-Eval in CI** — Regression-Schutz.
5. **Track B (Judge) + Adversariales** — Ausbaustufe.
6. **v2: Profi-„frag-frei"-Agent** — eigener ADR, greift auf dieselbe Fakten-Schicht zu.

## Supersession trigger

Diese ADR wird abgelöst/ergänzt, wenn:

- der Evidenz-Katalog so groß/dynamisch wird, dass ein deterministischer Lookup nicht
  mehr trägt (→ RAG-Re-Evaluation, Option B), **oder**
- das Profi-„frag-frei"-Feature gebaut wird (→ eigener Agent-ADR, Option C), **oder**
- die Eval zeigt, dass kein lokales Modell die Qualitäts-/Sicherheitsschwellen erreicht
  (→ Cloud-Opt-in als Default neu bewerten, DPIA aktualisieren).

## References

- Exploration: [`docs/ai-insights-exploration.md`](../ai-insights-exploration.md)
- Datenmodell: [`docs/design-data-ai-insights.md`](../design-data-ai-insights.md)
- Security-Design: [`docs/design-secure-ai-insights.md`](../design-secure-ai-insights.md)
- Implementierungsplan: [`docs/ai-insights-implementation-plan.md`](../ai-insights-implementation-plan.md)
- [ADR-0001 — Per-Service-DB-Rollen](0001-per-service-db-roles.md) (DSGVO Art. 9 Kontext)
- [`docs/dpia.md`](../dpia.md) — Datenschutz-Folgenabschätzung
- CMU 11-667 — Integration-Pattern-Reihenfolge (Lec 4/5–7/11/14)
- Stanford CS224N — Benchmarking & Evaluation
- Chip Huyen, „Designing ML Systems" Ch. 6 — Evaluation & Guardrails
- OWASP LLM Top 10 — Output-Handling, Excessive Agency (für v2-Agent)
