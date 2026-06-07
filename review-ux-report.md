# UX Review: PulseBase (Garmin Health Dashboard)
Datum: 2026-06-06
Framework-Basis: HAX (18 Guidelines) · PAIR (23 Patterns) · CHI 2024 (6 Prinzipien) · NNG AI Anti-Patterns

## Erkannter Kontext
**Typ:** Web-App (FastAPI · Jinja2 · Vanilla JS · Chart.js) — Self-Tracking-Dashboard
**KI-Beteiligung:** ML-Engine (scikit-learn) — Random-Forest-Readiness-Prognose, Z-Score-Anomalie-Detektion, Pearson-Korrelationen, k-Means-Body-Battery-Muster; zusätzlich regelbasierter Epilepsie-Anfallsrisiko-Indikator (klinische Heuristiken)
**Nutzertyp:** Konsumenten/Laien (Self-Tracking), teils Epilepsie-Betroffene (sicherheitskritische Subgruppe)
**Phase:** Production / Pre-Public-Release
**Kanal:** Web-Dashboard (responsive, Dark Mode)
**Kritische Domäne:** Gesundheitsdaten → Überreliance-Risiko real; DSGVO Art. 9 + BFSG-relevant

> Hinweis: Dieser Review wertet die UI-Schicht aus (21 Templates in `api/src/templates/`, 25 JS-Dateien in `api/src/static/`, `evidence_catalog.json`). Befunde aus Codelese, nicht aus Usability-Tests mit echten Nutzern.

---

## Ampel-Übersicht

| Dimension | Ampel | #Critical | #High | Wichtigste verletzte Guideline |
|-----------|-------|-----------|-------|-------------------------------|
| 1 · Erwartungen & Mentale Modelle | 🟡 | 0 | 1 | HAX G1: Fähigkeiten/Datenlatenz nicht beim Einstieg kommuniziert |
| 2 · Vertrauen & Transparenz | 🟡 | 0 | 1 | PAIR P11: Konfidenz/Unsicherheit nicht im UI sichtbar |
| 3 · Feedback & Kontrolle | 🟡 | 0 | 2 | HAX G9/G15: Kein Korrektur-/Feedback-Weg für ML-Outputs; Anfallseinträge nicht editierbar |
| 4 · Fehlerbehandlung | 🟡 | 0 | 0 | CHI 2024 P6: `alert()` statt inline; kein expliziter ML-Fallback |
| 5 · Langzeit & Adaptation | 🟡 | 0 | 0 | HAX G18: Modell-Retraining nicht kommuniziert |
| 6 · Anti-Pattern Check | 🟡 | 0 | 1 | Überreliance ohne Reibung (Dashboard); Über-Anthropomorphisierung |
| **A · Accessibility (BFSG)** | 🔴 | 2 | 3 | WCAG 1.1.1 / 1.3.1 / 4.1.3 — Charts & Karte ohne Alternative, `<main>` fehlt, Fehler ohne `aria-live` |

**Gesamtbild:** Inhaltlich/wissenschaftlich überdurchschnittlich (Quellenangaben, Disclaimer, Evidence-System, vorbildliche Epilepsie-Reibung). Die größte Schwäche ist **Accessibility** (gesetzlich, 🔴) — gefolgt von zwei systematischen KI-UX-Lücken: **keine Unsicherheits-Anzeige im Dashboard** und **kein Feedback-/Korrektur-Kanal für ML-Outputs**.

---

## Umsetzungsstatus

Umsetzung erfolgt in 4 Pull Requests (siehe Plan-Datei `bitte-erstelle-einen-plan-sorted-rabbit.md`, Abschnitt „Reihenfolge / PR-Schnitt").

| PR | Inhalt | Status |
|----|--------|--------|
| **PR1** | Accessibility (A-1…A-7) | ✅ **Umgesetzt** (Branch `a11y/pr1-accessibility`, 2026-06-06) |
| **PR2** | KI-Transparenz (B-1…B-5, E-2) | ✅ **Umgesetzt** (Branch `ai/pr2-ki-transparenz`, 2026-06-06) |
| **PR3** | Anfälle editierbar + Fehler inline + Onboarding (C-1, C-3, D-1, E-1, F-1) | ✅ **Umgesetzt** (Branch `ux/pr3-feedback-kontrolle`, 2026-06-07) |
| **PR4** | ML-Feedback (C-2/D3-1, Migration V25) + Lows [A-6], [D4-2] | ✅ **Umgesetzt** (Branch `ux/pr4-ml-feedback`, 2026-06-07) |

### ✅ PR1 — Accessibility (erledigt 2026-06-06)

Behebt alle 🔴-Befunde der Dimension Accessibility. Verifiziert: Biome sauber · Vitest 119/119 · pytest 390/390.

- **A-1** Charts mit Textalternative — `makeChart` setzt `role="img"` + automatisch erzeugtes `aria-label` (Typ + Serien + aktueller Wert); `activity.js` und `metrics.js` analog. *(behebt [A-1] Critical)*
- **A-2** GPS-Karte — Routen-Textzusammenfassung als `aria-label` + `sr-only`-Block in `activity.js`/`activity.html`. *(behebt [A-2] Critical)*
- **A-3** `<main id="main">`-Landmark + Skip-Link in `base.html` (eigene `.skip-link`-Klasse, kein Tailwind-Rebuild nötig). *(behebt [A-3] High)*
- **A-4** `role="alert"` (Fehler) / `role="status" aria-live="polite"` (Info/Erfolg/Warnung) in 8 Templates. *(behebt [A-4] High, Quick Win #1)*
- **A-5** Dashboard-Tabs nach WAI-ARIA Tabs-Pattern (`role=tablist/tab/tabpanel`, `aria-selected`, Pfeiltasten-Navigation); Zeitraum-Buttons mit `aria-label`/`aria-pressed`.
- **A-6** Globale `:focus-visible`-Regel in `style.css` (WCAG 2.4.7 / 1.4.11). *(behebt [A-6] Low)*
- **A-7** `accessibility.html` ehrlich aktualisiert (umgesetzte Maßnahmen + verbleibende Einschränkungen).

**Bewusst offen (ehrlich dokumentiert in `accessibility.html`):** Diagramme bieten eine *zusammenfassende* Textalternative, aber keine vollständige Datentabelle je Messpunkt; GPS-Karte ist über die Routen-Textzusammenfassung zugänglich, aber nicht vollständig per Tastatur zoom-/verschiebbar.

> Hinweis: Die Befund-Codes [A-5] (Icon-Buttons) aus der ursprünglichen Liste haben sich bei der Umsetzung als bereits weitgehend gelöst herausgestellt (die meisten Icon-Buttons hatten schon `aria-label`); offen waren v. a. die Zeitraum-Buttons und das Tabs-Pattern — beide in PR1 behoben.

---

### ✅ PR2 — KI-Transparenz (erledigt 2026-06-06)

Behebt die zwei systematischen KI-UX-Lücken aus dem Gesamtbild: **keine Unsicherheits-Anzeige** und **kein angemessener Unsicherheitsrahmen** um die ML-Outputs. Rein Frontend — die Konfidenzdaten (`confidence_low`/`confidence_high`, 10./90. Perzentil der RF-Bäume) flossen bereits über `/api/ml-insights`, nur die Ausspielung fehlte. Verifiziert: Biome sauber · Vitest 125/125.

- **B-1** Konfidenzintervall sichtbar — ML-Prognose-Tile zeigt `Spanne lo–hi`; Detailseite `readiness-rf` mit KPI „Konfidenz (10–90%)". Null-/Empty-State fällt sauber auf „—" zurück. *(behebt [D2-1] High — dashboard-hero.js, metrics-ml.js)*
- **B-2** `limitations`-Feld im Hilfe-Artikel gerendert (Block „Einschränkungen" analog Evidence-Dialog) + in die Hilfe-Suche aufgenommen. *(behebt [D2-3] Medium — help.js, style.css)*
- **B-3** Empfehlungssprache von direktivem Imperativ („Voll belasten") → Vorschlagsform mit Unsicherheit („Deutet auf gute Erholung hin — intensives Training wäre möglich"). *(behebt [D6-1] Medium — dashboard-hero.js)*
- **B-4** Anomalie-Label „⚠ Anomalie" → „⚠ Mögliche Auffälligkeit" + Z-Wert/Schwelle als Tooltip; konsistent auf Dashboard und Metrik-Detailseite. *(behebt [D2-2] Medium — dashboard-hero.js, metrics-ml.js)*
- **B-5** Disclaimer-Reibung direkt unter den ML-Tiles statt nur im Footer („Schätzung auf Basis deiner Daten — kein medizinischer Befund"). *(behebt [D6-2] Medium — dashboard-hero.js)*
- **E-2** Tag-zu-Tag-Streuung in den Hilfe-Artikeln zu Readiness und Anomalie erklärt („auf den Trend achten, nicht auf den Einzelwert"). *(behebt [D1-2] Low — help.js)*

**Zusätzlich im selben PR (außerhalb der UX-Befundliste):**
- **Bugfix Anfallstagebuch:** `epilepsy.js` wurde als klassisches `<script>` geladen, nutzt aber ES-Module-`export` (für die Vitest-Tests) → `SyntaxError`, die Seite blieb auf „Lade…" (kein Datums-Prefill, keine Schwere-Chips, Risiko/Verlauf leer). Fix: `type="module"` in `epilepsy.html` — identisch zu dashboard/help/metrics.
- **Test-Coverage:** api · sync-service · ml-service auf **100%** gehoben (echte Lücken getestet, nicht-ausführbare ABC-Stubs/Entrypoints via `pragma`/`exclude_lines` ehrlich ausgeklammert).

---

### ✅ PR3 — Feedback, Kontrolle & Onboarding (erledigt 2026-06-07)

Behebt die verbleibenden High-/Medium-Befunde zu Feedback & Kontrolle, Fehlerbehandlung und Erwartungsmanagement. Keine DB-Migration nötig — `seizure_events` (V15) existiert, es fehlten nur UPDATE/DELETE. Verifiziert: pytest 416/416 · Vitest 151/151 · JS-Coverage `epilepsy.js`/`onboarding.js` 100% · mypy + Biome sauber.

- **C-1** Anfälle editierbar/löschbar — `update_seizure`/`delete_seizure` (DB, Ownership-Filter `id AND user_id` gegen IDOR) + `PATCH`/`DELETE /api/seizures/{id}` (404 bei fremder/fehlender ID). Frontend: Bearbeiten/Löschen-Buttons pro Eintrag (Event-Delegation, CSP-konform), Edit-Modus mit Formular-Vorausfüllung, Löschen mit nativem `<dialog>`-Bestätigung. *(behebt [D3-2] High — seizures.py, api.py, epilepsy.js/.html)*
- **C-3** Libre-Unlink-Bestätigung — natives `<dialog>` (Muster wie `#formula-dialog`) vor dem destruktiven Trennen. *(behebt [D3-3] Medium — settings.html, settings.js)*
- **D-1** Inline-Fehler statt `alert()` im Anfallsformular — `#log-error` mit `role="alert"`, Formularinhalt bleibt bei Fehler erhalten (Retry). *(behebt [D4-1] Medium — epilepsy.js/.html)*
- **E-1** Onboarding-/Datenlatenz-Hinweis — dismissbares Banner („Erste Trends nach ~7 Tagen, ML-Prognose nach ~30 Tagen Daten") mit localStorage-Persistenz. *(behebt [D1-1] High — onboarding.js, dashboard.html/.js)*
- **F-1** „Zuletzt analysiert"-Indikator — Label im Header von „🤖 ML · vor 3h" → „🤖 Zuletzt analysiert vor 3h". *(behebt [D5-1] Medium — dashboard-status.js)*

---

## Nächste Schritte

✅ Alle Befunde der Befundliste sind umgesetzt. Verbleibend nur dokumentierte Ausnahmen.

### ✅ PR4 — ML-Feedback + Rest-Lows (erledigt 2026-06-07)

Behebt den letzten High-Befund [D3-1] sowie die zwei verbleibenden Lows. Verifiziert: pytest 421/421 · Vitest 157/157 · E2E 38/38 · ruff/biome/mypy sauber.

- **C-2 / [D3-1]** Item-Level-ML-Feedback — binäres, pro Tag/Modell umschaltbares 👍/👎 auf Readiness- und Anomalie-Tile (HAX G9/G15). Server stempelt `prediction_date = CURRENT_DATE` (ml_predictions hat keinen Auto-PK); `UNIQUE (user_id, model, prediction_date)` macht das Feedback per `ON CONFLICT` idempotent/umschaltbar. Migration V25 (`ml_feedback`-Tabelle + Grants: api schreibt, ml-service read-only fürs spätere Kalibrierungssignal), `db/ml_feedback.py`, `GET/POST /api/ml-feedback`, CSP-konforme Event-Delegation in dashboard.js. *(dashboard-hero.js, dashboard.js, api.py, db/ml_feedback.py, V25)*
- **[A-6]** Fokus-Ring-Kontrast — `focus:ring-emerald-500/20` (20 % Deckkraft, von der globalen `:focus-visible`-Regel via `focus:outline-none` ausgehebelt) → `focus:ring-emerald-400` (volle Deckkraft, ≥3:1 auf dunklem Slate) in allen 9 Auth-/Form-Templates. *(behebt [A-6] Low)*
- **[D4-2]** ML-Fallback-Hinweis — die drei „zu wenig Daten"-Leerzustände in metrics-ml.js (hr-zscore, battery-pattern, correlations) verweisen jetzt auf die verfügbare Rohdaten-/Chart-Ansicht. *(behebt [D4-2] Low)*

**Zusätzlich (Test-Infrastruktur):** Die neuen E2E-Tests authentifizieren per injiziertem, signiertem Session-Cookie (`make_session_cookie`) statt über das `/login`-Formular — rate-limit-sicheres Muster (die Suite teilt ein 10/min-Login-Budget; UI-Logins hier ließen sonst andere Tests flaken). Beweist den realen DB-Upsert + Per-User-Scoping unter der echten `garmin_app`-Rolle.

> [D1-2] generative Variabilität wurde bereits in PR2 (E-2) adressiert.

---

## Top-3 Quick Wins

1. **Fehlermeldungen für Screenreader ankündigen** · WCAG 4.1.3 (AA) · Aufwand: **S (<30min)** · `role="alert" aria-live="polite"` auf alle `{{ error }}`-/Status-Blöcke in `login.html`, `register.html`, `settings.html`, `reset_*.html`. Aktuell hat nur der Toast in [dashboard.html:185](api/src/templates/dashboard.html#L185) das Attribut.
2. **`<main>`-Landmark + Skip-Link in base.html** · WCAG 1.3.1 / 2.4.1 (A) · Aufwand: **S (<30min)** · In [base.html:12-13](api/src/templates/base.html#L12-L13) `{% block content %}` in `<main id="main">` kapseln und einen `<a href="#main" class="sr-only focus:not-sr-only">Zum Inhalt springen</a>` als erstes `<body>`-Kind ergänzen. `<main>` kommt aktuell in **keinem** Template vor.
3. **Vorhandene `limitations`/`not_for`-Felder rendern** · PAIR P12 · Aufwand: **S (<30min)** · `evidence_catalog.json` enthält pro Metrik bereits `limitations` (z.B. „Optischer Garmin-Sensor … weniger präzise als EKG"), aber [help.js](api/src/static/help.js) rendert nur `intended_use`/`not_for`, nicht `limitations`. Daten existieren — nur Ausspielung fehlt.

---

## Vollständige Befundliste

### 🔴 Critical

**[A-1] Charts ohne Textalternative — Kernfunktion für Screenreader unzugänglich**
- Severity: **Critical** · Dimension: Accessibility
- Befund: Sämtliche Chart.js-Diagramme (Dashboard, Metrik-Seiten) und die Leaflet-GPS-Karte transportieren die zentrale Information rein visuell. Die App räumt das in [accessibility.html:41-49](api/src/templates/accessibility.html#L41-L49) selbst ein: „Diagramme (Chart.js) enthalten keine Textalternative für Screenreader" und „GPS-Karte (Leaflet.js) ist nicht vollständig per Tastatur bedienbar". Für blinde/sehbehinderte Nutzer ist damit der Kerninhalt (Trends, Scores) nicht erfassbar.
- Fix: Pro Chart eine textuelle Zusammenfassung (`aria-label` oder versteckte Datentabelle mit `sr-only`) ausgeben — die Werte liegen ohnehin als JSON vor. Karte: Mindestens Start/Distanz/Dauer als Textblock; Tastaturfokus für Marker.
- Referenz: WCAG 1.1.1 (A), 1.4.1 (A)

**[A-2] GPS-Karte nicht tastaturbedienbar**
- Severity: **Critical** · Dimension: Accessibility
- Befund: Leaflet-Karte auf der Aktivitätsseite ist laut [accessibility.html:44](api/src/templates/accessibility.html#L44) „nicht vollständig per Tastatur bedienbar" — Tastatur-only-Nutzer können die Routendarstellung nicht erreichen/bedienen.
- Fix: Tastaturfokus + Pan/Zoom per Tastatur aktivieren oder die Karte als optionale, klar gekennzeichnete Ergänzung zu einem textuellen Routen-Summary degradieren.
- Referenz: WCAG 2.1.1 (A)

> Begründung Critical-Einstufung: Skill-Regel — Accessibility-Verstöße gegen EU Accessibility Act / BFSG sind mindestens High; vollständige Blockade einer Kernfunktion (Daten nur visuell) ist Critical.

---

### 🔴 High

**[A-3] `<main>`-Landmark fehlt vollständig + kein Skip-Link**
- Severity: **High** · Dimension: Accessibility
- Befund: `grep` über alle Templates findet **null** `<main>`-Elemente. [base.html:12-22](api/src/templates/base.html#L12-L22) kapselt den Content direkt in `<body>` plus `<footer>`; ein Skip-Link existiert nicht. Screenreader-/Tastatur-Nutzer haben keinen Landmark zum Hauptinhalt und müssen Navigation bei jeder Seite durchtabben. Widerspricht zudem der Selbstaussage „Semantisches HTML mit korrekter Überschriftenhierarchie" in [accessibility.html:31](api/src/templates/accessibility.html#L31).
- Fix: Quick Win #2.
- Referenz: WCAG 1.3.1 (A), 2.4.1 (A)

**[A-4] Fehler-/Status-Meldungen ohne `role="alert"` / `aria-live`**
- Severity: **High** · Dimension: Accessibility
- Befund: Login-/Register-/Settings-Fehlerblöcke (z.B. [login.html:25-26](api/src/templates/login.html#L25-L26): `<div ...>{{ error }}</div>`) sind nur farblich markiert. Screenreader kündigen sie nicht an. Einziger korrekt ausgezeichneter Live-Bereich ist der Toast in [dashboard.html:185](api/src/templates/dashboard.html#L185).
- Fix: Quick Win #1.
- Referenz: WCAG 4.1.3 (AA), 3.3.1 (A)

**[A-5] Icon-Schaltflächen ohne `aria-label`**
- Severity: **High** · Dimension: Accessibility
- Befund: Selbst eingeräumt in [accessibility.html:45](api/src/templates/accessibility.html#L45): „Einige Icon-Schaltflächen besitzen noch kein `aria-label`". Reine Icon-Buttons sind für Screenreader bedeutungslos.
- Fix: Alle Icon-only-Buttons mit `aria-label` versehen (Audit per axe-core).
- Referenz: WCAG 1.1.1 (A), 4.1.2 (A)

**[D3-1] Kein Korrektur-/Feedback-Weg für KI-Outputs**
- Severity: **High** · Dimension: 3 (Feedback & Kontrolle)
- Befund: Readiness-Prognose, Anomalie-Flag, Korrelationen und Muster werden präsentiert ([dashboard-hero.js:245-392](api/src/static/dashboard-hero.js#L245-L392)), aber es gibt **keinen** Mechanismus, einen ML-Output zu bestätigen, abzulehnen oder als falsch zu markieren (kein Thumbs-up/down, kein „stimmt nicht", kein Report-Pfad). Bei einem System mit personalisierten Baselines verschenkt das sowohl Vertrauensbildung als auch potenzielles Kalibrierungs-Signal.
- Fix: Mindestens ein leichtgewichtiges Item-Level-Feedback („War diese Einschätzung treffend? 👍/👎") auf Anomalie- und Readiness-Tiles. Optional Kommentarfeld.
- Referenz: HAX G9 (Korrektur), G15 (granulares Feedback), G16 (Konsequenzen sichtbar)

**[D3-2] Anfallstagebuch-Einträge nicht editierbar/löschbar**
- Severity: **High** · Dimension: 3 (Feedback & Kontrolle)
- Befund: [epilepsy.js:95-117](api/src/static/epilepsy.js#L95-L117) rendert den Verlauf read-only; keine Edit-/Delete-Buttons. In der medizinischen Domäne werden Anfalls-Einträge häufig nachträglich korrigiert (Datum, Dauer, Schweregrad). Falsch erfasste Daten fließen unkorrigierbar in den Risiko-Indikator und einen DSGVO-Export.
- Fix: Edit + Delete pro Eintrag (PATCH/DELETE `/api/seizures/{id}`), mit Bestätigung beim Löschen.
- Referenz: HAX G9 (effiziente Korrektur)

**[D2-1] Konfidenz/Unsicherheit nicht im UI sichtbar**
- Severity: **High** · Dimension: 2 (Vertrauen & Transparenz)
- Befund: Das RF-Modell berechnet ein Konfidenzintervall (10./90. Perzentil der Bäume) — erwähnt nur im Science-Text [metrics-ml.js](api/src/static/metrics-ml.js). Auf dem Dashboard erscheint die Prognose als blanke Zahl `~{score}` ([dashboard-hero.js:246](api/src/static/dashboard-hero.js#L246)) ohne Streuung/Fehlerband. Im Gesundheitskontext fördert das eine Scheingenauigkeit und Überreliance.
- Fix: Konfidenzintervall an der Score-Anzeige sichtbar machen (z.B. „~67 (Spanne 58–74)") oder eine qualitative Sicherheits-Markierung. Charts mit Unsicherheitsband.
- Referenz: PAIR P11 (Konfidenz darstellen), CHI 2024 P6 S1 (Unsicherheit sichtbar machen)

**[D1-1] Fähigkeiten & Datenlatenz nicht beim Einstieg kommuniziert**
- Severity: **High** · Dimension: 1 (Erwartungen & Mentale Modelle)
- Befund: Die eingeloggte Startseite [index.html:5-6](api/src/templates/index.html#L5-L6) zeigt nur „PulseBase / Hallo, {{ user.name }}" — keine Erklärung, was die App/ML leistet, was sie nicht leistet, und vor allem **nicht**, dass ML-Insights erst nach Tagen/Wochen Daten erscheinen. [link_garmin.html](api/src/templates/link_garmin.html) erklärt die Passwort-Sicherheit, aber nicht die Daten-/Analyse-Latenz. Neue Nutzer sehen anfangs leere Tiles („zu wenig Daten") ohne Erwartungsrahmen.
- Fix: Kurzer First-Run-Hinweis nach dem Verknüpfen („Erste Trends nach ~7 Tagen, ML-Prognose nach ~30 Tagen Daten"). Auf der Landing knappe „Was kann / was nicht"-Zeile.
- Referenz: HAX G1 (Fähigkeiten kommunizieren), G2 (Qualität), PAIR P2 (mentale Modelle)

---

### 🟡 Medium

**[D6-1] Über-Anthropomorphisierung / Coach-Imperative ohne Unsicherheitsrahmen**
- Severity: **Medium** · Dimension: 6 (Anti-Pattern)
- Befund: Empfehlungen sind direktive Imperative: „Voll belasten — Körper ist erholt", „Heute ruhen — Erholung prioritär" ([dashboard-hero.js:68-79](api/src/static/dashboard-hero.js#L68-L79)), „Volles Training möglich" ([metrics-ml.js](api/src/static/metrics-ml.js)). In Kombination mit fehlender Konfidenzanzeige (D2-1) suggeriert das mehr Gewissheit, als das Modell hat.
- Fix: Sprache in Vorschlags-Form mit sichtbarer Unsicherheit („Deutet auf gute Erholung hin — intensives Training wäre möglich"). Nicht doppelt mit D2-1 fixen, aber zusammen denken.
- Referenz: NNG (Über-Anthropomorphisierung), CHI 2024 P3 (angemessenes Vertrauen)

**[D6-2] Überreliance ohne Reibung auf dem Dashboard**
- Severity: **Medium** · Dimension: 6 (Anti-Pattern)
- Befund: Auf dem Haupt-Dashboard stehen Scores/Empfehlungen prominent und selbstbewusst; der einzige Disclaimer („dient nur zu Informationszwecken … ersetzt keine medizinische Beratung") steht klein im Footer [dashboard.html:187-189](api/src/templates/dashboard.html#L187-L189). Anders als die vorbildliche Epilepsie-Seite (s. Positivbefunde) fehlt dem Dashboard kontextuelle Reibung.
- Fix: Disclaimer/Unsicherheits-Hinweis näher an die ML-Tiles rücken (z.B. dezenter Hinweistext im Tile-Footer oder „?"-Tooltip).
- Referenz: CHI 2024 P3 S3 (Reibung wo Überreliance gefährlich), HAX G2

**[D2-2] Anomalie-Status zu faktisch formuliert**
- Severity: **Medium** · Dimension: 2 (Vertrauen & Transparenz)
- Befund: [dashboard-hero.js:339-348](api/src/static/dashboard-hero.js#L339-L348) zeigt „⚠ Anomalie" / „⚠ Anomalie erkannt" als definitive Aussage. Ein Z-Score-Ausreißer ist ein statistisches Signal, keine Tatsache — „mögliche Anomalie" / „auffälliger Wert" wäre kalibrierter.
- Fix: Wording entschärfen, idealerweise mit Z-Wert/Schwelle als Tooltip.
- Referenz: NNG (falsche Autorität), PAIR P11

**[D2-3] `limitations`-Feld vorhanden, aber nicht gerendert**
- Severity: **Medium** · Dimension: 2 (Vertrauen & Transparenz)
- Befund: `evidence_catalog.json` pflegt pro Metrik ein `limitations`-Feld (Sensorpräzision, Messmethodik). [help.js:473-525](api/src/static/help.js#L473-L525) rendert `intended_use`/`not_for`/Quellen, aber nicht `limitations`. Wertvolle Ehrlichkeit bleibt unsichtbar.
- Fix: Quick Win #3.
- Referenz: PAIR P12 (entscheidungsrelevante Erklärungen)

**[D3-3] Libre-Unlink löscht Daten ohne Bestätigungsdialog**
- Severity: **Medium** · Dimension: 3 (Feedback & Kontrolle)
- Befund: [settings.html](api/src/templates/settings.html) bietet „Trennen & Daten löschen" (Libre) als direkten Form-Submit ohne Modal — der Hinweistext „Beim Trennen werden alle Messwerte gelöscht" steht daneben, aber ein Fehlklick ist sofort destruktiv und irreversibel. (Garmin-Unlink ist weniger kritisch, da keine lokale Datenlöschung.)
- Fix: Bestätigungs-Modal vor Submit („Alle Glukosewerte werden unwiderruflich gelöscht. [Abbrechen] [Löschen]").
- Referenz: PAIR P17 (Automatisierungsgrad an Risiko anpassen), HAX G10

**[D4-1] Anfallseintrag: `alert()` statt inline, kein Retry**
- Severity: **Medium** · Dimension: 4 (Fehlerbehandlung)
- Befund: [epilepsy.js:119-156](api/src/static/epilepsy.js#L119-L156) nutzt `alert('Fehler beim Speichern.')` und `alert('Bitte Datum und Uhrzeit angeben.')`. Browser-`alert()` ist disruptiv, nicht stylebar, bietet keinen Retry — im Kontrast zum guten Inline-Pattern bei RPE ([activity.js:140-156](api/src/static/activity.js#L140-L156)).
- Fix: Inline-Fehlermeldung im Formular + erneuter Submit-Versuch, analog RPE.
- Referenz: CHI 2024 P6 S3/S4 (Edit/Retry/Feedback-Pfade)

**[D5-1] Modell-Retraining / Verhaltensänderungen nicht kommuniziert**
- Severity: **Medium** · Dimension: 5 (Langzeit & Adaptation)
- Befund: Das RF-Modell wird laut Doku wöchentlich neu trainiert; personalisierte Baselines verschieben sich über Zeit. Es gibt keinen UI-Hinweis, wenn sich Modell-/Score-Verhalten ändert. Nutzer könnten Sprünge als Datenfehler missdeuten.
- Fix: Dezenter Hinweis bei spürbaren Modell-Updates oder ein „zuletzt trainiert"-Indikator (existiert teils in `/api/ml-status` — im UI sichtbar machen).
- Referenz: HAX G18 (Änderungen kommunizieren), G14 (Updates vorsichtig)

---

### 🟢 Low

**[D1-2] Generative Variabilität nicht erklärt**
- Severity: **Low** · Dimension: 1
- Befund: Dass gleiche/ähnliche Inputs leicht schwankende Scores erzeugen können (Modell-Rauschen, gleitende Baseline), wird nirgends im UI erklärt. Für ein deterministisch wirkendes Dashboard niedrigprior, aber relevant für Vertrauen bei Tagesschwankungen.
- Fix: Eine Zeile im Help-Artikel zu Readiness/Anomalie zur erwartbaren Tag-zu-Tag-Streuung.
- Referenz: CHI 2024 P4 S1

**[A-6] Fokus-Ring-Kontrast prüfen**
- Severity: **Low** · Dimension: Accessibility · `[zu verifizieren]`
- Befund: Fokus-Styles existieren (gut), nutzen aber teils niedrige Deckkraft, z.B. `focus:ring-emerald-500/20` ([login.html:36-37](api/src/templates/login.html#L36-L37)). 20 % Opacity könnte das 3:1-Kontrastminimum für Fokusindikatoren unterschreiten.
- Fix: Kontrast des Fokusindikators messen (axe-core/manuell), ggf. Deckkraft/Border erhöhen.
- Referenz: WCAG 1.4.11 (AA), 2.4.7 (AA)

**[D4-2] Kein expliziter „manueller Fallback"-Text bei ML-Ausfall**
- Severity: **Low** · Dimension: 4
- Befund: Leere/ML-lose Zustände zeigen „zu wenig Daten" ([metrics-ml.js](api/src/static/metrics-ml.js)) — korrekt, aber es gibt keinen Hinweis „nutze stattdessen die Rohdaten-Charts" o.ä. Empty-States sind generell stark (s. Positivbefunde), daher Low.
- Fix: Optionaler Verweis auf verfügbare Roh-/Rule-based-Ansicht.
- Referenz: PAIR P18 (Fallback zu manueller Kontrolle)

---

## Positive Befunde (explizit beibehalten)

- **Epilepsie-Risiko-Indikator = Referenzqualität für sicherheitskritische KI** ([epilepsy.html:37-102](api/src/templates/epilepsy.html#L37-L102)): Amber-Disclaimer-Box „klinisch plausible Heuristiken, keine in klinischen Studien validierten Anfallsprädiktoren. Kein Ersatz für neurologische Betreuung"; jede Regel mit Schwellwert **und** Primärquellen (Frucht et al. 2000, Jansen & Lagae 2010, Bazil 2003 …); explizite Sensor-Limitationen; Abschluss „Kein medizinischer Befund." → vorbildlich gegen HAX G1/G2, PAIR P12, CHI 2024 P3.
- **Wissenschaftliche Quellentransparenz** durchgängig: PubMed-Links und Autor/Jahr in `help.js` und `evidence_catalog.json` (Plews 2013, Buchheit 2014, Van Dongen 2003, Walker 2017, Edwards 1993). Stark gegen CHI 2024 P3 S2.
- **Dreistufige Erklärungen** (`eli5` → `recommendation` → `science`) pro Metrik mit kollabierbaren Methodik-Details — gute Tiefenstaffelung (PAIR P12).
- **Evidence-/Zeithorizont-System** mit `intended_use` und `not_for` pro Metrik — kommuniziert Eignung **und** Nicht-Eignung (HAX G1).
- **RPE-Feedback** ([activity.js:108-157](api/src/static/activity.js#L108-L157)): granular, Live-Konsequenzen (Session Load, HR:RPE), Inline-Fehlerbehandlung mit Retry — Best-Practice gegen HAX G15/G16.
- **Empty-States mit Kontext**: „Noch keine Aktivitäten — Sync läuft täglich um 6 Uhr." ([dashboard-loaders.js:8-9](api/src/static/dashboard-loaders.js#L8-L9)) erklärt Warum + Wann.
- **DSGVO-Kontrollen**: Export (Art. 20) und Konto-Löschung (Art. 17) mit angemessener Reibung (E-Mail + Passwort, rote „Gefahrenbereich"-Card) — HAX G10/G11, PAIR P18.
- **Help-Navigation**: Suche, Deep-Links `/help#<metric>`, `?q=`-Parameter — gute Auffindbarkeit.
- **Hilfreiche, nicht-leaky Auth-Statusmeldungen** in [login.html:10-22](api/src/templates/login.html#L10-L22) (z.B. Resend-Verify-Link statt „Server-Fehler").

---

## Nicht bewertet / Annahmen

- **[zu verifizieren] BFSG-Geltungsbereich**: Heute (2026-06-06) ist das BFSG seit ~11 Monaten in Kraft (Stichtag 28.06.2025). Ob PulseBase als privater Dienst konkret unter den BFSG-Anwendungsbereich fällt, ist eine juristische Frage außerhalb dieses Reviews. Unabhängig davon hält sich die App per veröffentlichter Erklärung ([accessibility.html:25-28](api/src/templates/accessibility.html#L25-L28)) selbst an WCAG 2.1 AA — die Befunde A-1…A-6 stehen dieser Selbstverpflichtung entgegen.
- **[Annahme]** Charts/Karten-Befunde (A-1, A-2) basieren auf der Selbstaussage in `accessibility.html` plus Code-Struktur, nicht auf einem Screenreader-Live-Test.
- **[zu verifizieren]** `{{ error }}` in [login.html:25](api/src/templates/login.html#L25) gibt eine Backend-Variable direkt aus — ob dort je ungefilterte interne Meldungen landen, ist nur im Backend prüfbar (Security-, nicht UX-Befund).
- **Dimension 5 (Langzeit & Adaptation)** ist aus der UI-Schicht nur teilweise beurteilbar — History-Persistenz/Lernverhalten liegt überwiegend im ml-service, nicht in den Templates. `[Schlussfolgerung]` auf Basis der sichtbaren UI-Muster.
- **Charts/Visualisierungen** wurden inhaltlich nicht auf Farbkontrast/Datendichte geprüft (kein gerendertes Bild vorgelegt).

---
*Erstellt mit KI-Unterstützung (Claude Code + dev-best-practices Plugin).
Findings sind zu verifizieren — kein Ersatz für manuelle Usability-Tests mit echten Nutzern (insbesondere Screenreader-Test für die Accessibility-Befunde und Tests mit Epilepsie-Betroffenen für die sicherheitskritischen Flows).*
