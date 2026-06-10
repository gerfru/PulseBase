# Dashboard ↔ Metriken: Drilldown & klickbare Charts — Arbeits-Briefing

> Feature-Erweiterung + Design/Layout-Change für PulseBase.
> Branch: `claude/dashboard-metrics-charts-c7tuno`
> Ziel: Dashboard-Charts klickbar machen (→ Detailseite), eigene (berechnete) Metriken am Dashboard sichtbarer machen, Detailseiten vernetzen.

---

## 1. Ausgangs-Anliegen (User)

1. **„Nicht alle Metriken werden am Dashboard verwendet"** — gemeint sind die *eigenen, berechneten* Metriken. Die sollen am Dashboard auftauchen.
   - Präzisierung: Wo es eine eigene Version *und* eine Garmin-Rohversion gibt, soll das Dashboard die **eigene** Version zeigen (Garmin bleibt unter `/metrics` verfügbar).
2. **„Jedes Diagramm ist nur ein Diagramm"** — beim Klick auf ein Diagramm soll sich eine **eigene Subpage** öffnen, mit passenden/verwandten Metriken dazu.

Leitplanken: **KISS**, **sicher** (CSP-konform, kein `innerHTML` mit Fremddaten), **barrierefrei** (BFSG/WCAG 2.1 AA).

---

## 2. Verifizierte Faktenlage (Code-Recherche)

### 2.1 Dashboard zeigt 13 Charts, großteils Garmin-Rohwerte
`api/src/templates/dashboard.html`, gerendert via `api/src/static/dashboard-loaders.js` + `dashboard-utils.js:makeChart()`.

| Tab | Chart (Canvas-ID) | Datenquelle |
|---|---|---|
| Training | `weekly-chart`, `training-load-chart`, `intensity-chart`, Aktivitäten-Tabelle | `/api/activities`, `/api/training-load`, `/api/ml-history` |
| Verlauf | `battery-chart`, `hr-chart`, `steps-chart`, `stress-chart`, `calories-chart` | `/api/daily` |
| Erholung | `sleep-chart`, `hrv-trend-chart`, `sleep-stages-chart` | `/api/sleep`, `/api/hrv/trend` |

### 2.2 Die eigenen Metriken leben unter `/metrics` (22 Kacheln), nicht am Dashboard
`api/src/static/metrics-overview.js` → `METRIC_GROUPS`. Detailseiten: Route `/metrics/{name}` (`api/src/routes/pages.py:87`), Template `metrics.html`, Renderer `metrics.js` + `metrics-*.js`-Module.
**→ User-Aussage 1 bestätigt.** Custom-Metriken (Energie-Trio, `training-monotony`, `spo2-trend`, `hrv-status-custom`, `stress-score-custom`, `sleep-consistency`, `running-economy`, `hrv-recovery` …) sind nur unter `/metrics`, nicht am Dashboard.

### 2.3 Canvas-Accessibility ist BEREITS gelöst
`dashboard-utils.js:120-128` (`makeChart`) setzt pro Canvas `role="img"` + `aria-label` + versteckte Datentabelle (`buildChartDataTable`). `metrics.js` macht dasselbe für Detail-Charts. **→ Keine zusätzliche Canvas-a11y-Arbeit nötig.**

### 2.4 Charts waren bisher NICHT klickbar
Nur Aktivitäten-Tabellenzeilen (`dashboard.js:63`) und Evidence-Badges (Hero, Formel-Modal) waren interaktiv. **→ User-Aussage 2 bestätigt** (Infrastruktur `/metrics/{name}` existiert aber schon → Drilldown ist v. a. Verdrahtung).

### 2.5 KORREKTUR — es gibt KEINE toten Routen
Erste Analyse behauptete `recovery` / `battery-pattern` / `correlations` seien tot. **Falsch.** Alle drei sind voll funktionsfähige Detailseiten:
- `battery-pattern` → `metrics-ml.js:388` (ML-Modell, Evidence `battery_pattern`, `/api/ml-insights`)
- `correlations` → `metrics-ml.js:442` (Pearson r, Evidence `correlation_sleep_hrv`)
- `recovery` → `metrics-readiness.js:255` („Erholung — Schlaf & HRV", fetch+render+KPIs+Charts)

Sie sind nur **nicht in der `/metrics`-Übersichtsgrid** gelistet. **→ Aktion ist Aufnehmen, NICHT Löschen.**
`recovery` ist inhaltlich redundant zur bestehenden „Erholung"-Kachel → bleibt erreichbar, wird aber nicht zusätzlich promotet.

---

## 3. Best-Practice-Recherche (2024–2026), kurz

- **Shneiderman-Mantra** „Overview first → details-on-demand": Dashboard = kuratierte Übersicht, Detail beim Klick. Genau was Garmin/Whoop/Oura/Apple Health machen (Tile → Detail-Screen). ✅ Genau der geplante Ansatz.
- **Eigene Seite vs. Modal/Drawer**: Für inhaltsreiche Detail-Views (Charts + KPIs + Text) ist die **eigene Seite** state of the art (deep-linkbar, Back-Button, kein Focus-Trap). Modal nur fürs kleine Formel-/Methodik-Popover. ✅
- **Dichte (Few/Tufte)**: **NICHT alle Metriken aufs Dashboard** — kuratierte, entscheidungsrelevante Auswahl + Drilldown für den Rest. Reduziert Cognitive Load. ✅ (wichtige Nuance zu Aussage 1)
- **Klickbare Card/Chart, a11y**:
  - Keine ganze Card als ein `<a>` (Screenreader liest den ganzen Card-Text als Linkname).
  - Echten Link auf den **Titel** (`<h2><a>`), optional ganze Card per JS-Maus-Klick als Komfort-Hitbox.
  - Canvas: `role="img"` + `aria-label` + versteckte Datentabelle (hier schon vorhanden).
  - Sichtbarer Fokus-Indikator (global in `style.css:744` vorhanden), Navigation = `<a href>` (Mittelklick/neuer Tab/History).
- **KISS-Stack**: Server-rendered Jinja2 + Vanilla JS + Chart.js reicht; kein Framework, kein Client-Router.

Quellen u. a.: Shneiderman (InfoVis-Wiki), Smashing „Modal vs Separate Page", Chart.js Accessibility Docs, Nomensa/Kitty Giraudel/Heydon Pickering „Accessible Cards / Block Links", Stephen Few „Information Dashboard Design", Tufte „Data-Ink Ratio".

---

## 4. Plan (3 Phasen, je 1 Commit, KISS)

### Phase 1 — Charts klickbar → Subpage  ✅ CODE FERTIG (noch nicht committet)
Block-Link-Pattern: Card-Titel als echter `<a class="card-title-link">` + ganze Card per JS-Maus-Klick (`.card[data-href]`). **Bewusst kein `::after`-Overlay über dem Canvas**, damit Chart.js-Hover-Tooltips erhalten bleiben. Mapping bevorzugt die **eigene** Metrik:

| Dashboard-Chart | → Detailseite |
|---|---|
| Body Battery | `/metrics/body-battery-custom` |
| Stress | `/metrics/stress-score-custom` |
| Schlaf-Score | `/metrics/sleep-score-custom` |
| HRV-Verlauf | `/metrics/hrv-status-custom` |
| Schlafphasen | `/metrics/sleep-score-custom` |
| Training Load | `/metrics/physical` (CTL/TSB = Physische Energie) |
| Intensitätsminuten | `/metrics/intensity-minutes` |
| Ruhepuls | `/metrics/hr-zscore` |
| Schritte | `/metrics/steps` |
| Trainingsübersicht / Kalorien | kein Custom-Pendant → kein Link |

Plus: `battery-pattern` + `correlations` in die `/metrics`-Übersicht aufgenommen (neue Gruppe „ML & Muster").

**Geänderte Dateien Phase 1:**
- `api/src/static/style.css` — `.card[data-href]` + `.card-title-link` (+ Chevron, Hover, kein Overlay)
- `api/src/templates/dashboard.html` — 9 Cards: `data-href` + Titel-Link
- `api/src/static/dashboard.js` — delegierter Card-Klick-Handler (ignoriert Klicks auf `a, button`)
- `api/src/static/metrics-overview.js` — Gruppe „ML & Muster" mit `battery-pattern`, `correlations`

**Bewusst NICHT geändert:** `api/src/routes/pages.py` (`_VALID_METRICS` bleibt komplett, `/ml/*`-Redirects bleiben gültig) → bestehende `test_pages.py` bleiben grün.

### Phase 2 — Kuratierte „Deine Metriken"-Leiste am Dashboard  ⏳ OFFEN
Kompakte Tile-Leiste (Wert + Evidence-Badge + Link zur Detailseite) mit den wichtigsten *eigenen* Metriken, die sonst nicht am Dashboard sind (z. B. Energie-Trio, `training-monotony`, `sleep-consistency`, `hrv-recovery`, `spo2-trend`, `running-economy`).
- **Daten aus bereits geladenen Responses** (`/api/ml-insights`, `/api/energy`) → kein zusätzlicher Request.
- Nicht *alle 22* (Few/Tufte), sondern kuratierte Auswahl.
- Platzierung: eigene Sektion nahe der Hero-Card oder pro Tab; Tile-Rendering analog `metrics-overview.js` (CSP-konform, kein Inline-Handler; bei dynamischem HTML `DOMPurify.sanitize`).

### Phase 3 — „Verwandte Metriken"-Block auf Detailseiten  ⏳ OFFEN
Kleiner Link-Block je Detailseite (2–3 thematisch verwandte Metriken), z. B. HRV → autonome Energie / HRV-Recovery / Stress. In `metrics.js` rendern; Mapping als kleine Konstante je Metrik. Macht u. a. `recovery`/`battery-pattern`/`correlations` natürlich auffindbar.

---

## 5. Constraints / Definition of Done

- **Sicherheit/CSP**: keine Inline-Event-Handler (Nonce-CSP); dynamisches HTML nur via `DOMPurify.sanitize` (Muster vorhanden in `dashboard-utils.js:166`, `metrics.js:38`).
- **A11y**: Titel-Link fokussierbar, sichtbarer Fokus (global vorhanden); Canvas-a11y bereits via `makeChart`. Block-Link nicht als ganzes `<a>`.
- **KISS**: kein Framework, kein neuer Build-Step. Keine neuen Tailwind-Utility-Klassen in Templates → **kein** `make tailwind-build` nötig (nur falls neue Utilities dazukommen).
- **Tests/CI**: JS-Unit-Tests via Vitest (`cd api && npm ci && npm test` — lokal aktuell kein `node_modules`, Netzwerk-Install war nicht gewünscht → CI-Jobs `js-test`/`js-lint` decken ab). E2E + axe-core Gate (`e2e`) muss grün bleiben. Python: `ruff`, `mypy`, `pytest`.
- **Git**: alles auf `claude/dashboard-metrics-charts-c7tuno`, `git push -u origin <branch>`. Kein PR ohne explizite Aufforderung.

## 6. Status

- Phase 1: **Code fertig**, `node --check` grün, noch **nicht committet/gepusht**.
- Phase 2 + 3: offen.
- Offene Mini-Entscheidung: `recovery` bewusst nicht in Übersicht promotet (redundant zu „Erholung").
