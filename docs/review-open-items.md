# Review — Offene Punkte (konsolidiert)

Stand: 2026-06-08 (re-verifiziert 2026-06-16 gegen Codebase, Stand v1.3.0). Fasst die
**verbliebenen** Punkte aus den drei Reviews zusammen (App/Security/CI, UX/AI/Accessibility,
Style/CSS). Die Vollberichte wurden nach vollständiger Umsetzung entfernt — sie liegen in
der Git-Historie.

## Status der drei Reviews

| Review | Befunde | Umgesetzt in |
|--------|---------|--------------|
| **App / Security / CI** (ASVS L2, DORA, 12-Factor) | 0 Critical, 3 High, 4 Medium, 6 Low | **v1.0.0** (PR #164) + **Wave 15** (PR #167) |
| **UX / AI / Accessibility** (HAX · PAIR · CHI 2024 · WCAG 2.2) | 2 Critical, 6 High, 7 Medium, 3 Low | **PR1–PR4** (a11y, KI-Transparenz, Feedback/Kontrolle, ML-Feedback) |
| **Style / CSS** (Tailwind, Anti-Slop, NN/g) | 1 🔴, 2 🟠, 3 🟡 | **#161 / #162 / #163** |

→ **Alle konkreten Befunde sind implementiert und verifiziert.** Was unten steht,
sind bewusst aufgeschobene Punkte, manuelle Betriebsschritte und dokumentierte
Ausnahmen — keine offene Implementierungsarbeit.

---

## 1 · Manuell vor Public-Launch (kein Code)

- [ ] **Sentry-Alert-Rules anlegen** — Error-Rate >1%/10min, p95 >2s, neuer Issue.
  Runbook fertig: [deployment-public.md → Sentry-Alert-Runbook](deployment-public.md#sentry-alert-runbook-obs-l3--pflicht-vor-public-launch). Einmaliger Dashboard-Klick. *(App-Review OBS-L3)*
- [ ] **Backup scharfschalten** — `env/.env.backup` anlegen (`AGE_RECIPIENT` aus offsite
  `age-keygen`) + `make up`; der Backup-Container sichert dann täglich verschlüsselt
  (Runbook in [deployment-public.md](deployment-public.md#backups-health-pii-pflicht)),
  monatlich `make restore-test`. *(seit Wave 16 PR-B Container statt Host-Cron)*
- [x] **GitHub-native Secret-Scanning** — ✅ erledigt: Repo ist seit dem Public-Release
  öffentlich (`gerfru/PulseBase`, visibility PUBLIC) und GitHub Secret-Scanning ist aktiv
  (API `repos/.../secret-scanning/alerts` antwortet 200/`[]`, also aktiviert, 0 Alerts).
  Ergänzt die bestehenden gitleaks-Layer 1+2. *(App-Review M3)*

## 2 · Bewusst aufgeschoben (Trigger dokumentiert)

- **CD-Pipeline** (CICD-M4) — *Deploy*-Automatisierung (Auto-Deploy auf den Server via SSH)
  bleibt aufgeschoben (ADR-0002 weiterhin „Deferred"): für solo/Single-Server marginal,
  einführen bei häufigem Deploy oder Multi-Environment. Architektur + Trigger:
  [`docs/adr/0002-cd-pipeline.md`](adr/0002-cd-pipeline.md).
  Hinweis: Die *Release*-Automatisierung (Versionierung/Changelog/GitHub-Release via
  release-please, Conventional Commits) ist seit dem Public-Release vorhanden
  (`.github/workflows/release-please.yml`, zuletzt v1.3.0) — der **Deploy** auf den Server
  erfolgt aber weiterhin manuell per `make up`.
- **JS-Coverage Phase 2** — ✅ die 5 reinen Render-Module (`metrics-energy/readiness/sleep/
  garmin/activity`) sind im Vitest-Gate (7→12 Module, ≥95/90). Offen bleiben nur die
  DOM-/fetch-lastigen Loader (`dashboard-loaders`, `dashboard-hero`, `activity`). Hinweis:
  `colors.js`/`help.js`/`metrics-overview.js` sind globale `<script>`s ohne Export → per
  v8-Coverage prinzipiell nicht gate-bar. *(App-Review M2)*
- **Style-Politur** *(Style-Review „Bewusst offen")*: ✅ Motion-Token-Migration erledigt
  (verstreute Timings → `--dur-fast`/`--dur-base`; `.4s` effect-fill + Skeleton bewusst
  unverändert). Offen: data-driven Accent/Hero (Readiness als einziges Farbsignal — braucht
  Nutzer-Test); Chart-Mikro-Interaktionen (`animation:false` ist Bestandsentscheidung).

## 3 · Dokumentierte Ausnahmen / empfohlene Verifikation

- **Accessibility — umgesetzt; nur Screenreader-Live-Test offen:** Charts haben je eine
  **vollständige sr-only-Datentabelle pro Messpunkt** (`chart-utils.js` `buildChartDataTable`,
  via `aria-describedby` mit dem Canvas verknüpft), nicht nur eine Zusammenfassung. Die
  GPS-Karte ist **per Tastatur fokussier-, verschieb- und zoombar** (Leaflet `keyboard:true`
  + sr-only-Routensummary + `<kbd>`-Anleitung in `activity.html`) und erhält über die globale
  `:focus-visible`-Regel einen sichtbaren Fokus-Ring (Parent-`.card` hat Padding, kein
  Overflow-Clipping). Offen bleibt nur ein echter **Screenreader-Live-Test** (NVDA/VoiceOver)
  — Code-Review ≠ Usability-Test. *(UX-Review A-1/A-2)*
- **BFSG-Geltungsbereich** — juristische Frage außerhalb des Reviews; die App hält sich
  per veröffentlichter Erklärung freiwillig an WCAG 2.1 AA.
- **App-Review Tech-Debt** (ARCH-M2 Service-Layer, ARCH-L2 db-Struktur, OBS-L2
  OpenTelemetry, QUAL-M2 GarminClient-Duplikat …) — bewusste Solo-Entscheidungen,
  dauerhaft dokumentiert in `CLAUDE.md` (Abschnitt „Bewusste Tech-Debt-Entscheidungen").

---
*Konsolidiert aus den ursprünglichen `review-app-report.md`, `review-ux-report.md`,
`review-style-report.md` (in Git-Historie). Design-Entscheidungen dauerhaft in
`docs/design-decisions.md`, Tech-Debt in `CLAUDE.md`.*
