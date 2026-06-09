# Review — Offene Punkte (konsolidiert)

Stand: 2026-06-08. Fasst die **verbliebenen** Punkte aus den drei Reviews zusammen
(App/Security/CI, UX/AI/Accessibility, Style/CSS). Die Vollberichte wurden nach
vollständiger Umsetzung entfernt — sie liegen in der Git-Historie.

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
- [ ] **Backup scharfschalten** — täglicher `pg_dump`-Cron (Runbook in
  [deployment-public.md](deployment-public.md#backups-health-pii-pflicht)) + monatlich `make restore-test`.
- [ ] **GitHub-native Secret-Scanning** aktivieren, sobald Public-Repo / GHAS verfügbar
  (aktuell blocked-by-plan; Layer 1+2 gitleaks decken ab). *(App-Review M3)*

## 2 · Bewusst aufgeschoben (Trigger dokumentiert)

- **CD-Pipeline** (CICD-M4) — Auto-Deploy via SSH. Für solo/Single-Server marginal;
  einführen bei häufigem Deploy oder Multi-Environment. Architektur + Trigger:
  [`docs/adr/0002-cd-pipeline.md`](adr/0002-cd-pipeline.md).
- **JS-Coverage Phase 2** — DOM-/fetch-lastige Loader (`dashboard-loaders`, `activity`,
  restliche `metrics-*`) ins Vitest-Gate. Hoher Aufwand; metrics-ml ist bereits gegated.
  Hinweis: `colors.js`/`help.js`/`metrics-overview.js` sind globale `<script>`s ohne
  Export → per v8-Coverage prinzipiell nicht gate-bar. *(App-Review M2 „Vollständig")*
- **Style-Politur** *(Style-Review „Bewusst offen")*: Motion-Token-Migration der
  verstreuten Timings auf `--dur-*`; data-driven Accent/Hero (Readiness als einziges
  Farbsignal); Chart-Mikro-Interaktionen (`animation:false` ist Bestandsentscheidung).

## 3 · Dokumentierte Ausnahmen / empfohlene Verifikation

- **Accessibility — manueller Test empfohlen:** Charts bieten eine *zusammenfassende*
  Textalternative (sr-only), aber keine vollständige Datentabelle je Messpunkt; die
  GPS-Karte ist über die Routen-Textzusammenfassung zugänglich, aber nicht vollständig
  per Tastatur zoom-/verschiebbar. Ehrlich vermerkt in `accessibility.html`. Ein echter
  **Screenreader-Live-Test** (NVDA/VoiceOver) steht aus — Code-Review ≠ Usability-Test.
  *(UX-Review A-1/A-2 Rest)*
- **BFSG-Geltungsbereich** — juristische Frage außerhalb des Reviews; die App hält sich
  per veröffentlichter Erklärung freiwillig an WCAG 2.1 AA.
- **App-Review Tech-Debt** (ARCH-M2 Service-Layer, ARCH-L2 db-Struktur, OBS-L2
  OpenTelemetry, QUAL-M2 GarminClient-Duplikat …) — bewusste Solo-Entscheidungen,
  dauerhaft dokumentiert in `CLAUDE.md` (Abschnitt „Bewusste Tech-Debt-Entscheidungen").

---
*Konsolidiert aus den ursprünglichen `review-app-report.md`, `review-ux-report.md`,
`review-style-report.md` (in Git-Historie). Design-Entscheidungen dauerhaft in
`docs/design-decisions.md`, Tech-Debt in `CLAUDE.md`.*
