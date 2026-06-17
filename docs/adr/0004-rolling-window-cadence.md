# ADR-0004: Insights-Kadenz — rollierendes 7-Tage-Fenster statt fixer ISO-Woche

## Status

Accepted — 2026-06-17

**Supersedet die Wochen-Kadenz von [ADR-0003](0003-ai-weekly-insights.md).** Architektur,
Sicherheits-Invarianten 1–6, das 3-Schichten-Pattern und „Zahlen aus Code, Worte aus dem LLM"
aus ADR-0003 bleiben **unverändert** gültig — diese ADR ändert ausschließlich das
**Zeitfenster** und entfernt die kalender-basierte Navigation.

## Context

ADR-0003 hat die Insight an die **fixe ISO-Kalenderwoche** gekoppelt (browsbar via ◀▶).
Im Betrieb zeigte sich: der Nutzer will **Aktualität** („wie stehe ich gerade da?"), nicht
historisches Blättern durch abgeschlossene Kalenderwochen. Eine ISO-Woche ist zudem bis
Sonntagabend unvollständig — Montag-Insights über eine 1–2-Tage-Woche sind irreführend.

[Schlussfolgerung] Eine kalendarische Woche ist eine **Buchhaltungs-Einheit**, kein
physiologisch begründetes Auswertungsfenster.

## Decision Drivers

- **Aktualität** — der Wert liegt im „jetzt", nicht im Archiv.
- **Wissenschaftliche Haltbarkeit** — das Fenster soll einem etablierten Verfahren entsprechen,
  nicht dem Zufall des Wochentags.
- **KISS / wenig Churn** — bestehende Reads, das Gate, Async/Pending und die Persistenz-Form
  sollen möglichst unverändert bleiben.

## Recherche (Stand der Technik)

[Nicht verifiziert — Herstellerangaben/öffentliche Beschreibungen, keine Primärquelle geprüft]

- **Garmin Training Readiness:** tägliche Bewertung, u. a. über ein **rollierendes 7-Tage-HRV**.
- **Whoop / Oura:** tägliche Recovery/Readiness; HRV-Baselines über längere rollierende Fenster
  (~30 Tage).
- **ACWR (Acute:Chronic Workload Ratio)** aus der Sportwissenschaft: **Akut-Fenster 7 Tage**
  gegen chronische Baseline (28 Tage); „sweet spot" ~0.8–1.3, erhöhtes Risiko ≥ 1.5.

Gemeinsamer Nenner: **tägliche Auswertung über ein rollierendes Akut-Fenster von 7 Tagen**.
Die chronischen Baselines (28–42 Tage) stecken bereits in den fertigen ml-service-Tageswerten —
hier wird nichts neu berechnet (ADR-0003-Prinzip).

## Decision

1. **Rollierendes 7-Tage-Fenster, endend gestern.**
   `period_end = heute − 1` (letzter vollständiger Tag), `period_start = period_end − 6`.
   „Heute" ist unvollständig (Schlaf/HRV/Aktivität laufen noch) und wird ausgeschlossen.

2. **Outcome der Recherche:** `x = 7 Tage` (rollierender Rückblick).
   Ein `y = 7 Tage`-**Ausblick** ist erwogen, aber **bewusst zurückgestellt** (separate,
   regulatorisch abgesicherte PR) — eine Vorausschau ist präskriptiver und vergrößert die
   EU-AI-Act-/Art.-22-/MDR-Fläche.

3. **Keine kalender-basierte Navigation** mehr. Ein Insight pro `period_end`, täglich frisch;
   Cache greift pro Tag (regenerierbarer Cache, keine Quelldaten).

4. **Namen bleiben** (`weekly_insights`-Tabelle, `WeeklyInsight`-Klasse) — „weekly" = 7-Tage-
   Fenster. Nur die **Zeit-Felder** wechseln: `iso_year`/`iso_week` → `period_start`/`period_end`
   (DATE). Minimiert Churn.

5. **Datum gehört in die Präsentation, nicht in den LLM-Text.** Das Zeitfenster wird im UI-Header
   gezeigt („Letzte 7 Tage · dd.mm.–dd.mm."). Der LLM-Prompt nennt **keine** Datumsangaben, und
   das Number-Grounding-Gate führt Datums-Zahlen **nicht** als erlaubte Tokens — sonst würden
   Tag/Monat (z. B. „06", „14") echte Zahl-Halluzinationen maskieren. (Verschärfung von
   Invariante 1, nicht Abschwächung.)

## Consequences

**Positiv**

- Insight ist immer aktuell; kein „toter" Montag-Anfang.
- Fenster entspricht ACWR-Akutfenster + Garmin/Whoop/Oura-Praxis (rollierend, täglich).
- Glukose-Krücke entfällt: `get_glucose_stats` ist NOW-basiert (= letzte 7 Tage) und passt für
  das aktuelle Fenster ohne Sonderfall. Für ältere Fenster wird TIR bewusst weggelassen.

**Negativ / Kosten**

- **V33 = DROP + CREATE** beider Insight-Tabellen (PK wechselt zu `(user_id, period_end)`).
  Unkritisch, weil Insights ein **regenerierbarer Cache** sind (kein Quelldatenverlust).
- Historisches Blättern entfällt (bewusst — kein Nutzerbedarf).
- Trainingsvolumen kommt jetzt aus `get_recent_activities(days=7, end_date)` (Summe
  `duration_seconds`/3600) statt aus dem ISO-Wochen-Bucket `get_weekly_stats`.

**Unverändert**

- Sicherheits-Invarianten 1–6 (Post-Check fail-secure, kein Identifier im LLM-Payload,
  Metadaten-only-Logs, Session-Scoping/BOLA, AI-Act-Art.-50-Labeling).
- 3-Schichten-Pattern, Gate, Async/Pending/Poll, Disclaimer-Append, Evidenz-Katalog.

## Offen / danach

- **PR 2 — Ausblick (`y = 7 Tage`):** evidenzgegroundet + hedged, **keine** präskriptive
  Einzelanweisung; eigene Invariante + Eval-Regel; regulatorische Endabnahme vor Live.
- **P7 (Eval)** inkl. Ausblick-Regel; fachliche Endabnahme der Formulierungen.
