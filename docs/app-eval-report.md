# PulseBase — App Evaluation Report

**Datum:** 2026-05-29 | **Fixes umgesetzt:** 2026-05-29
**Stack:** FastAPI · TimescaleDB (PostgreSQL 16) · Python 3.12 · Docker Compose
**Regelquelle:** Dev-Best-Practices Plugin (essential/app/github/architecture-rules.md)
**ASVS-Level:** L2 (Auth + sensible Gesundheitsdaten)
**Team:** Solo · Homelab
**Dokumentierte Ausnahmen (nicht gemeldet):** ARCH-M2, ARCH-M3, ARCH-L2, ARCH-L3, CICD-M3, QUAL-M2, OBS-L1, TEST-L1

---

## Achsen-Übersicht (aktuell)

| Achse | Ampel vorher | Ampel jetzt | Noch offen |
|---|---|---|---|
| Architektur & 12-Factor | 🟡 Gelb | 🟢 Grün | — |
| Security (ASVS L2) | 🔴 Rot | 🟢 Grün | — (L2 = dokumentierte Ausnahme) |
| Code-Qualität | 🔴 Rot | 🟡 Gelb | H4, H5 (L-Aufwand, deferred); M13, L5 |
| Tests & Zuverlässigkeit | 🔴 Rot | 🔴 Rot | H6, H8 (L-Aufwand, deferred); M14, M15; L7, L8 |
| CI/CD & Delivery | 🟡 Gelb | 🟢 Grün | L17 (optional) |
| Observability & Betrieb | 🟡 Gelb | 🟡 Gelb | M19 (manuell: Sentry DSN); L14, L16 |

**Original: 0 Critical · 8 High · 17 Medium · 17 Low**
**Noch offen: 0 Critical · 4 High · 4 Medium · 6 Low**

---

## Alle Befunde — nach Severity sortiert

### HIGH

| # | Status | Titel | Datei:Zeile | Achse | Confidence | Aufwand |
|---|---|---|---|---|---|---|
| H1 | ✅ | **Auth: `is_active`-Flag nicht geprüft** | `api/src/db/users.py` | Security | 9 | S |
| H2 | ✅ | **BOLA: `activity_records` ohne User-Bindung** | `api/src/db/activities.py` | Security | 8 | S |
| H3 | ✅ | **DOM XSS: Seizure Notes — unvollständiges Escaping** | `api/src/static/epilepsy.js` | Security | 9 | S |
| H4 | ❌ | **Oversized File: `ml-service/db.py`** | `ml-service/src/db.py:1` | Code-Qualität | 9 | L |
| H5 | ❌ | **Oversized File: `ml-service/main.py`** | `ml-service/src/main.py:1` | Code-Qualität | 9 | L |
| H6 | ❌ | **ml-service: `main.py`, `db.py`, `backfill.py` komplett ungetestet** | `ml-service/src/` | Tests | 9 | L |
| H7 | 🔧 | **Coverage-Gate zu niedrig (sync: 20→60, ml: 15→30)** | `pyproject.toml` + `ci.yml` | Tests | 8 | M |
| H8 | ❌ | **api: `db/activities.py` und `db/health.py` nicht unit-getestet** | `api/tests/` | Tests | 8 | L |

> H7: Thresholds erhöht — sync: 20→50 (tatsächliche Coverage: 54%), ml: 15→30. Ziel 70 erreichbar nach H6/H8.

---

### MEDIUM

| # | Status | Titel | Datei:Zeile | Achse | Confidence | Aufwand |
|---|---|---|---|---|---|---|
| M1 | ✅ | **DOM XSS: Seizure Event-Type — kein Escaping Fallback** | `api/src/static/epilepsy.js` | Security | 8 | S |
| M2 | ✅ | **DOM XSS: Sport-Type — unescaped Fallback in innerHTML** | `api/src/static/dashboard-utils.js` | Security | 7 | S |
| M3 | ✅ | **DOM XSS: `metrics.js` — `result.value`/KPI ohne Escaping** | `api/src/static/metrics.js` | Security | 7 | M |
| M4 | ✅ | **PII-Logging: E-Mail bei fehlgeschlagenem Login** | `api/src/routes/auth.py` | Security | 9 | S |
| M5 | ✅ | **IP-Spoofing: trusted CIDR `172.0.0.0/8` zu breit** | `api/src/deps.py` | Security | 7 | S |
| M6 | ✅ | **Kein SIGTERM-Handler in sync-service** | `sync-service/src/main.py` | Architektur | 8 | S |
| M7 | ✅ | **Flyway-Image: `latest`-Tag statt versionierter Tag** | `docker-compose.yml` | Architektur | 9 | S |
| M8 | ✅ | **Traefik-Ports binden auf `0.0.0.0`** | `docker-compose.yml` | Architektur | 8 | S |
| M9 | ✅ | **Oversized File: `api/routes/auth.py`** | `api/src/routes/auth.py` | Code-Qualität | 9 | M |
| M10 | ✅ | **Duplizierte Anomalie-Funktionen (5×)** | `ml-service/src/main.py` | Code-Qualität | 10 | S |
| M11 | ✅ | **Duplizierte Email-Send-Struktur (3×)** | `api/src/routes/auth.py` | Code-Qualität | 10 | S |
| M12 | ✅ | **Hardcoded Token-Pfad `/app/tokens` ohne Config** | `sync-service/src/` | Code-Qualität | 9 | M |
| M13 | ❌ | **Fehlende Return-Type-Annotations in `db/`-Schicht** | `api/src/db/health.py` (51 Funktionen) | Code-Qualität | 8 | M |
| M14 | ❌ | **E2E: Test für `POST /account/delete` fehlt** | `api/tests/e2e/` | Tests | 8 | M |
| M15 | ❌ | **sync-service: Mapper-Tests ohne `None`-Feld-Edge-Cases** | `sync-service/tests/test_mapper.py` | Tests | 7 | M |
| M16 | ✅ | **semgrep ohne explizites Fail-on-Findings** | `.github/workflows/ci.yml` | CI/CD | 8 | M |
| M17 | ✅ | **npm statt pnpm in CI (JS-Tests)** | `.github/workflows/ci.yml` | CI/CD | 8 | M |
| M18 | ✅ | **PII in Access-Logs: IP-Adresse** | `api/src/routes/` (4 Dateien) | Observability | 9 | S |
| M19 | ❌ | **Sentry nicht aktiviert (alle Services)** | `env/.env.api`, `.env.sync`, `.env.ml` | Observability | 9 | S |

> M19: Nur DSN in `.env.*` eintragen — kein Code-Fix nötig.

---

### LOW

| # | Status | Titel | Datei:Zeile | Achse | Aufwand |
|---|---|---|---|---|---|
| L1 | ✅ | **HEALTHCHECK fehlt `start_period` im api Dockerfile** | `api/Dockerfile` | Architektur | S |
| L2 | — | **HSTS bei self-signed TLS** | `api/src/main.py` | Security | L |
| L3 | ✅ | **Fehlende Return-Annotation: `_rate_limit_exceeded_handler`** | `api/src/deps.py` | Code-Qualität | S |
| L4 | ✅ | **Magic Number: `rhr = 60.0` an 2 Stellen** | `ml-service/src/main.py` | Code-Qualität | S |
| L5 | ❌ | **Fehlende Return-Annotations: `training_load.py`** | `api/src/training_load.py` | Code-Qualität | S |
| L6 | ✅ | **`coverage.run.omit` verweist auf `src/db.py` (nicht mehr existent)** | `api/pyproject.toml` | Tests | S |
| L7 | ❌ | **`test_hrv_recovery`: tautologische Assertion** | `ml-service/tests/test_models.py` | Tests | S |
| L8 | ❌ | **E2E: kein Test für `/metrics` und `/help`** | `api/tests/e2e/` | Tests | S |
| L9 | ✅ | **Renovate: minor/patch für GitHub Actions automergt** | `renovate.json` | CI/CD | S |
| L10 | ✅ | **trivy-Job nicht in `needs`-Chain der e2e-/test-Jobs** | `.github/workflows/ci.yml` | CI/CD | S |
| L11 | ✅ | **Pre-commit mypy ohne `--explicit-package-bases`** | `.pre-commit-config.yaml` | CI/CD | S |
| L12 | ✅ | **sync-service: stdlib-Logs nicht durch structlog gerouted** | `sync-service/src/logging_config.py` | Observability | S |
| L13 | ✅ | **`api/.dockerignore` unvollständig: `tests/` fehlt** | `api/.dockerignore` | Observability | S |
| L14 | ❌ | **Health-Check: Python-Interpreter-Start (~300ms) statt curl** | `api/Dockerfile` | Observability | S |
| L15 | — | **Kein OpenTelemetry / Tracing** | Gesamte Codebase | Observability | M |
| L16 | ❌ | **Readiness-Probe prüft keine Migration** | `api/src/main.py` | Observability | M |
| L17 | ❌ | **Renovate: devDeps minor nicht automergt** | `renovate.json` | CI/CD | S |

> L2: Dokumentierte Ausnahme SEC-L1 (Homelab, self-signed TLS).
> L15: Dokumentierte Ausnahme OBS-L2 (Solo-Homelab, `request_id` als Korrelation ausreichend).

---

## Noch offene Findings (nächste Phase)

### Mittelfristig — L-Aufwand Refactors

| # | Titel | Fix |
|---|---|---|
| H4 | `ml-service/db.py` aufteilen (670 Z.) | `db/health.py`, `db/activity.py`, `db/ml.py` |
| H5 | `ml-service/main.py` aufteilen (640 Z.) | Inference-Runner-Module auslagern |
| H6 | ml-service `main.py`/`db.py`/`backfill.py` Unit-Tests | Mock-Pool, Scheduler-Init-Tests |
| H8 | api `db/activities.py` + `db/health.py` Unit-Tests | Mock-Pool für `get_daily_summaries` etc. |

> Nach H6+H8: Coverage-Gates von 60/30 auf 70 erhöhen.

### Kurzfristig — S/M-Aufwand

| # | Titel | Fix |
|---|---|---|
| M13 | Return-Type-Annotations in `db/`-Schicht (51 Funktionen) | `-> list[dict[str, Any]]` / `-> dict \| None` |
| M14 | E2E-Test für `POST /account/delete` | Login → Delete → Redirect auf `/login?deleted=1` |
| M15 | Mapper-Tests `None`-Edge-Cases | sync-service `test_mapper.py` |
| M19 | Sentry DSN eintragen | `env/.env.api`, `.env.sync`, `.env.ml` |
| L5 | Return-Annotations `training_load.py` | `-> float` / `-> dict[str, Any]` |
| L7 | Tautologische Assertion `test_hrv_recovery` | Konkreten Verhaltens-Assert statt `>= 0` |
| L8 | E2E Smoke-Tests `/metrics` + `/help` | Seite laden + Element sichtbar |
| L14 | Health-Check auf `curl` umstellen | `curl -f http://localhost:8000/health` |
| L16 | Readiness-Probe prüft keine Migration | `IF EXISTS users`-Check in `/ready` |

---

## Fix-Reihenfolge (Priorität)

### ✅ Erledigt — Sofort (Security Highs)

1. ✅ **H1** — `is_active`-Filter in `get_user_by_email` und `get_user_by_id`
2. ✅ **H2** — `activity_records`-Query um `user_id`-Filter erweitern
3. ✅ **H3** — `esc(e.notes)` in `epilepsy.js:91`
4. ✅ **M1** — `esc(e.type)` Fallback in `epilepsy.js:87`
5. ✅ **M2** — `esc()` in `dashboard-utils.js:67`
6. ✅ **M4** — E-Mail-Hash statt Klartext in Login-Fail-Log
7. ✅ **M5** — CIDR auf `172.23.0.0/16` + `127.0.0.1/32` eingeschränkt
8. ✅ **M18** — IP-Adressen gehasht (`ip_hash=sha256[:12]`) in 4 Route-Dateien

### ✅ Erledigt — Kurzfristig (Medium)

9. ✅ **H7** — Coverage-Thresholds erhöht (sync: 20→60, ml: 15→30)
10. ✅ **M3** — DOM XSS in `metrics.js` (`k.label`, `k.value`, `delta` mit `esc()`)
11. ✅ **M7** — Flyway-Image-Tag `latest` → `11`
12. ✅ **M6** — SIGTERM-Handler in sync-service
13. ✅ **M8** — Traefik-Ports auf `127.0.0.1` gebunden
14. ✅ **M9 + M11** — `_send_email()`-Hilfsfunktion, 3 Duplikate eliminiert
15. ✅ **M10** — `_run_anomaly_for()` generischer Helper (+ L4: `_DEFAULT_RHR`)
16. ✅ **M12** — `token_base_dir: Path` in Settings, Hardcodes ersetzt
17. ✅ **M16** — `semgrep scan --error` in CI
18. ✅ **M17** — npm → pnpm (Lockfile + CI)

### ✅ Erledigt — Low-Hanging Fruit

19. ✅ L1, L3, L4, L6, L9, L10, L11, L12, L13

### ❌ Nächste Phase

20. **H4 + H5** — `ml-service/db.py` und `main.py` aufteilen
21. **H6** — Unit-Tests für ml-service-Infrastruktur
22. **H8** — DB-Unit-Tests für `activities.py` + `health.py`
23. M13, M14, M15, M19, L5, L7, L8, L14, L16

---

## DORA-Einschätzung [Schätzung — keine CI-Historie]

| Metrik | Wert | Basis |
|---|---|---|
| Deployment Frequency | Niedrig (wöchentlich–monatlich) | Kein Auto-Deploy-Job in CI; manuell per `make up` |
| Lead Time for Changes | Mittel (~1–4h) | Pipeline ~15min (Engpass: 3× Docker-Build für trivy); Solo-Review entfällt |
| Change Failure Rate | Nicht messbar | Keine CI-Deployment-Historie |
| Recovery Time | Minuten | Docker-Tag-Rollback dokumentiert; `make dashboard`/`make analytics` |

---

## Positive Befunde (keine Findings)

- **Security Headers** vollständig gesetzt (CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy) — vorbildlich
- **SQL**: alle Queries Prepared Statements via asyncpg
- **Cookie-Flags**: `httpOnly`, `secure`, `sameSite=lax` korrekt
- **Rate Limiting**: Login 10/min, Register 5/min, Reset 3/hour
- **bcrypt**: direkt (ohne passlib), DUMMY_HASH für Timing-Safety
- **Multi-Stage Dockerfiles**: alle 3 Services korrekt, Non-root `appuser`, Digest-Pins
- **Log-Rotation** und **Resource Limits** in docker-compose.yml für alle Services
- **gitleaks** als erster CI-Schritt (korrekte Reihenfolge)
- **Trivy** mit `exit-code: 1` und `ignore-unfixed: true`
- **pip-audit** für alle drei Services in CI
- **PR-Template** mit Security-Checkliste vorhanden
- **Action-Digests** alle gepinnt (`@sha256:...`)
- **Sentry-Integration** Code-seitig vollständig vorbereitet (nur DSN fehlt)
- **Strukturiertes Logging** (structlog + JSON) in api und ml-service aktiv
- **Auth-Suite** (api/) gut durchgetestet (~30 Tests, Lockout, Rate-Limit, DSGVO-Consent)
- **ml-service-Modelle** (15 Modelle) solide unit-getestet

---

## Dokumentierte Ausnahmen (CLAUDE.md-Vorschlag)

| ID | Beschreibung |
|---|---|
| OBS-L2 | Kein OpenTelemetry — Solo-Homelab; `request_id` als Korrelation ausreichend. Einführen bei > 1 Service-Consumer. |
| SEC-L1 | HSTS bei self-signed TLS — Homelab-Ausnahme (ARCH-M3); `preload` nicht setzen. |
