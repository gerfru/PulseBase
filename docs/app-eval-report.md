# PulseBase — App Evaluation Report

**Datum:** 2026-05-29
**Stack:** FastAPI · TimescaleDB (PostgreSQL 16) · Python 3.12 · Docker Compose
**Regelquelle:** Dev-Best-Practices Plugin (essential/app/github/architecture-rules.md)
**ASVS-Level:** L2 (Auth + sensible Gesundheitsdaten)
**Team:** Solo · Homelab
**Dokumentierte Ausnahmen (nicht gemeldet):** ARCH-M2, ARCH-M3, ARCH-L2, ARCH-L3, CICD-M3, QUAL-M2, OBS-L1, TEST-L1

---

## Achsen-Übersicht

| Achse | Ampel | #Critical | #High | #Medium | #Low | Wichtigste verletzte Regel |
|---|---|---|---|---|---|---|
| Architektur & 12-Factor | 🟡 Gelb | 0 | 0 | 3 | 1 | Docker: Port Binding, Disposability |
| Security (ASVS L2) | 🔴 Rot | 0 | 3 | 5 | 1 | DOM XSS, is_active-Filter, BOLA |
| Code-Qualität | 🔴 Rot | 0 | 2 | 5 | 3 | Dateigröße >400 Z., Duplikation, 12-Factor Config |
| Tests & Zuverlässigkeit | 🔴 Rot | 0 | 3 | 2 | 3 | Ungetestete ml-service-Infrastruktur, fehlende Coverage-CI |
| CI/CD & Delivery | 🟡 Gelb | 0 | 0 | 2 | 4 | semgrep Fail-Config, npm statt pnpm |
| Observability & Betrieb | 🟡 Gelb | 0 | 0 | 2 | 5 | Sentry nicht aktiviert, PII in Logs |

**Gesamt: 0 Critical · 8 High · 17 Medium · 17 Low**

---

## Alle Befunde — nach Severity sortiert

### HIGH

| # | Titel | Datei:Zeile | Achse | Confidence | Fix | Aufwand |
|---|---|---|---|---|---|---|
| H1 | **Auth: `is_active`-Flag nicht geprüft** | `api/src/db/users.py:26–45` | Security | 9 | `AND is_active = true` in `get_user_by_email` und `get_user_by_id` ergänzen | S |
| H2 | **BOLA: `activity_records` ohne User-Bindung** | `api/src/db/activities.py:54–65` | Security | 8 | Zweiten `pool.fetch`-Aufruf um `user_id`-Filter erweitern | S |
| H3 | **DOM XSS: Seizure Notes — unvollständiges Escaping** | `api/src/static/epilepsy.js:91` | Security | 9 | `esc(e.notes)` aus `dashboard-utils.js` statt manueller Regex | S |
| H4 | **Oversized File: `ml-service/db.py`** | `ml-service/src/db.py:1` | Code-Qualität | 9 | 670 Zeilen; nach Domänen aufteilen (`db/health.py`, `db/activity.py`, `db/ml.py`) | L |
| H5 | **Oversized File: `ml-service/main.py`** | `ml-service/src/main.py:1` | Code-Qualität | 9 | 640 Zeilen, 20+ Funktionen; Inference-Runner-Module auslagern | L |
| H6 | **ml-service: `main.py`, `db.py`, `backfill.py` komplett ungetestet** | `ml-service/src/` (Test fehlt) | Tests | 9 | Unit-Tests für DB-Queries (Mock-Pool) und Scheduler-Initialisierung ergänzen | L |
| H7 | **Keine Coverage-Messung in CI für sync-service und ml-service** | `pyproject.toml` (fehlt `[tool.coverage]`) | Tests | 8 | `pytest --cov` mit `fail_under=70` in `pyproject.toml` beider Services + CI-Job | M |
| H8 | **api: `db/activities.py` und `db/health.py` nicht unit-getestet** | `api/tests/` (Test fehlt) | Tests | 8 | Unit-Tests mit Mock-Pool für `get_daily_summaries`, `get_sleep_sessions`, `get_latest_hrv` | L |

---

### MEDIUM

| # | Titel | Datei:Zeile | Achse | Confidence | Fix | Aufwand |
|---|---|---|---|---|---|---|
| M1 | **DOM XSS: Seizure Event-Type — kein Escaping Fallback** | `api/src/static/epilepsy.js:87` | Security | 8 | `${TYPE_LABELS[e.type] \|\| esc(e.type)}` | S |
| M2 | **DOM XSS: Sport-Type — unescaped Fallback in innerHTML** | `api/src/static/dashboard-utils.js:67` | Security | 7 | Fallback mit `esc(type \|\| 'Sonstige').replace(/_/g, ' ')` | S |
| M3 | **DOM XSS: `metrics.js` — `result.value`/KPI ohne Escaping** | `api/src/static/metrics.js:37,63–74` | Security | 7 | `esc()` für alle `k.label`/`k.value`/`result.value` oder `textContent` nutzen | M |
| M4 | **PII-Logging: E-Mail bei fehlgeschlagenem Login** | `api/src/routes/auth.py:208–212` | Security | 9 | `email`-Feld durch `email_hash` ersetzen oder weglassen | S |
| M5 | **IP-Spoofing: trusted CIDR `172.0.0.0/8` zu breit** | `api/src/deps.py:31–37` | Security | 7 | CIDR auf tatsächlichen Traefik-Container-Bereich einschränken | S |
| M6 | **Kein SIGTERM-Handler in sync-service** | `sync-service/src/main.py:301` | Architektur | 8 | `loop.add_signal_handler(signal.SIGTERM, scheduler.shutdown)` eintragen | S |
| M7 | **Flyway-Image: `latest`-Tag statt versionierter Tag** | `docker-compose.yml:34` | Architektur | 9 | Tag auf `flyway/flyway:11@sha256:...` setzen (Renovate-kompatibel) | S |
| M8 | **Traefik-Ports binden auf `0.0.0.0`** | `docker-compose.yml:69–70` | Architektur | 8 | `"127.0.0.1:80:80"` und `"127.0.0.1:443:443"` | S |
| M9 | **Oversized File: `api/routes/auth.py`** | `api/src/routes/auth.py:1` | Code-Qualität | 9 | 438 Zeilen; Email-Helper in `src/email.py` extrahieren | M |
| M10 | **Duplizierte Anomalie-Funktionen (5×)** | `ml-service/src/main.py:91` | Code-Qualität | 10 | Generische `_run_anomaly(user_id, today, history_fn, today_fn, model_key)` | S |
| M11 | **Duplizierte Email-Send-Struktur (3×)** | `api/src/routes/auth.py:75` | Code-Qualität | 10 | Gemeinsame `_send_email(to, subject, html) -> bool`-Hilfsfunktion | S |
| M12 | **Hardcoded Token-Pfad `/app/tokens` ohne Config** | `sync-service/src/main.py:133` (+ 4 weitere Stellen) | Code-Qualität | 9 | `TOKEN_BASE_DIR` als `Path`-Setting in beide `Settings`-Klassen | M |
| M13 | **Fehlende Return-Type-Annotations in `db/`-Schicht** | `api/src/db/health.py:7` (51 Funktionen) | Code-Qualität | 8 | `-> list[dict[str, Any]]` / `-> dict \| None` ergänzen | M |
| M14 | **E2E: Test für `POST /account/delete` fehlt** | `api/tests/e2e/` (Test fehlt) | Tests | 8 | Login → Delete → Redirect auf `/login?deleted=1` verifizieren | M |
| M15 | **sync-service: Mapper-Tests ohne `None`-Feld-Edge-Cases** | `sync-service/tests/test_mapper.py` | Tests | 7 | Behaviour-Tests mit `None`-Feldern in Input-Dicts | M |
| M16 | **semgrep ohne explizites Fail-on-Findings** | `.github/workflows/ci.yml:89–95` | CI/CD | 8 | `run: semgrep ci --error` ersetzen oder `SEMGREP_APP_TOKEN` setzen | M |
| M17 | **npm statt pnpm in CI (JS-Tests)** | `.github/workflows/ci.yml:158–160` | CI/CD | 8 | `npm ci` → `pnpm install --frozen-lockfile`, `package-lock.json` → `pnpm-lock.yaml` | M |
| M18 | **PII in Access-Logs: IP-Adresse** | `api/src/routes/auth.py:241,320` + 6 weitere | Observability | 9 | `ip=`-Feld entfernen oder `ip_hash=sha256(ip)[:12]` | S |
| M19 | **Sentry nicht aktiviert (alle Services)** | `env/.env.api`, `.env.sync`, `.env.ml` | Observability | 9 | `SENTRY_DSN` von sentry.io eintragen | S |

---

### LOW

| # | Titel | Datei:Zeile | Achse | Confidence | Fix | Aufwand |
|---|---|---|---|---|---|---|
| L1 | **HEALTHCHECK fehlt `start_period` im api Dockerfile** | `api/Dockerfile:17` | Architektur | 7 | `start-period=15s` ergänzen | S |
| L2 | **HSTS bei self-signed TLS** | `api/src/main.py:40–42` | Security | 7 | Homelab-Ausnahme; `preload` nicht hinzufügen (kein akuter Bedarf) | L |
| L3 | **Fehlende Return-Annotations: `_rate_limit_exceeded_handler`** | `api/src/deps.py:53` | Code-Qualität | 9 | `-> Response` ergänzen | S |
| L4 | **Magic Number: `rhr = 60.0` an 2 Stellen** | `ml-service/src/main.py:83` | Code-Qualität | 8 | `_DEFAULT_RHR = 60.0` als Modul-Konstante | S |
| L5 | **Fehlende Return-Annotations: `training_load.py`** | `api/src/training_load.py:18` | Code-Qualität | 7 | `-> float` / `-> dict[str, Any]` | S |
| L6 | **`coverage.run.omit` verweist auf `src/db.py` (nicht mehr existent)** | `api/pyproject.toml:42` | Tests | 9 | Eintrag entfernen | S |
| L7 | **`test_hrv_recovery`: tautologische Assertion** | `ml-service/tests/test_models.py:562` | Tests | 8 | `>= 0` durch konkreten Verhaltens-Assert ersetzen | S |
| L8 | **E2E: kein Test für `/metrics` und `/help`** | `api/tests/e2e/` (Test fehlt) | Tests | 7 | 2 kurze Smoke-Tests: Seite laden + Element sichtbar | S |
| L9 | **Renovate: minor/patch für GitHub Actions automergt** | `renovate.json:12–15` | CI/CD | 7 | `matchUpdateTypes` auf `["patch"]` für Actions beschränken | S |
| L10 | **trivy-Job nicht in `needs`-Chain der e2e-/test-Jobs** | `.github/workflows/ci.yml:115–146` | CI/CD | 6 | e2e-Job um `needs: [..., trivy]` erweitern | S |
| L11 | **Pre-commit mypy ohne `--explicit-package-bases`** | `.pre-commit-config.yaml:52–74` | CI/CD | 7 | Flag zu allen drei mypy-Hook-`args` hinzufügen | S |
| L12 | **sync-service: stdlib-Logs nicht durch structlog gerouted** | `sync-service/src/logging_config.py:1–23` | Observability | 9 | `logging.basicConfig(format="%(message)s", stream=sys.stdout)` ergänzen | S |
| L13 | **`api/.dockerignore` unvollständig: `tests/` fehlt** | `api/.dockerignore` | Observability | 8 | `tests/`, `.mypy_cache/`, `.ruff_cache/` ergänzen | S |
| L14 | **Health-Check: Python-Interpreter-Start (~300ms) statt curl** | `api/Dockerfile:17–18` | Observability | 7 | `curl -f http://localhost:8000/health` (+ `apt-get install curl`) | S |
| L15 | **Kein OpenTelemetry / Tracing** | Gesamte Codebase | Observability | 10 | `opentelemetry-sdk` + `opentelemetry-instrumentation-fastapi` oder als OBS-L2 in CLAUDE.md dokumentieren | M |
| L16 | **Readiness-Probe prüft keine Migration** | `api/src/main.py:150–157` | Observability | 6 | Tabellen-Existenz-Prüfung (`IF EXISTS users`) ergänzen | M |
| L17 | **Renovate: devDeps minor nicht automergt** | `renovate.json:16–20` | CI/CD | 7 | `matchUpdateTypes: ["minor", "patch"]` für npm devDeps (optional) | S |

---

## Fix-Reihenfolge (Priorität)

### Sofort (Security Highs — S-Aufwand, je < 30 min)

1. **H1** — `is_active`-Filter in `get_user_by_email` und `get_user_by_id`
2. **H2** — `activity_records`-Query um `user_id`-Filter erweitern
3. **H3** — `esc(e.notes)` in `epilepsy.js:91`
4. **M1** — `esc(e.type)` Fallback in `epilepsy.js:87`
5. **M2** — `esc()` in `dashboard-utils.js:67`
6. **M4** — E-Mail-Hash statt Klartext in Login-Fail-Log
7. **M5** — CIDR in `trusted_proxy_cidrs` einschränken
8. **M18** — IP-Adressen aus strukturierten Logs entfernen/hashen
9. **M19** — Sentry DSN eintragen

### Kurzfristig (Medium, M-Aufwand)

10. **H7** — Coverage-Messung in CI für sync-service und ml-service
11. **M3** — DOM XSS in `metrics.js` bereinigen
12. **M7** — Flyway-Image auf versionierten Tag
13. **M6** — SIGTERM-Handler in sync-service
14. **M8** — Traefik-Port-Binding auf `127.0.0.1`
15. **M9** + **M11** — auth.py aufräumen, Email-Helper extrahieren
16. **M10** — Anomalie-Funktionen konsolidieren
17. **M12** — `/app/tokens` Hardcoding durch `TOKEN_BASE_DIR`-Setting ersetzen
18. **M16** — semgrep mit `--error`-Flag in CI
19. **M17** — npm → pnpm in CI

### Mittelfristig (High, L-Aufwand — Refactors)

20. **H4 + H5** — `ml-service/db.py` und `main.py` aufteilen
21. **H6** — Unit-Tests für ml-service-Infrastruktur
22. **H8** — DB-Unit-Tests für `activities.py` + `health.py`

### Low-Hanging-Fruit (S-Aufwand, wenn Zeit)

23. L1, L3, L4, L5, L6, L7, L8, L9, L10, L11, L12, L13, L14

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

## Neue dokumentierte Ausnahmen (Vorschlag für CLAUDE.md)

| ID | Beschreibung |
|---|---|
| OBS-L2 | Kein OpenTelemetry — Solo-Homelab; `request_id` als Korrelation ausreichend. Einführen bei > 1 Service-Consumer. |
| SEC-L1 | HSTS bei self-signed TLS — Homelab-Ausnahme (ARCH-M3); `preload` nicht setzen. |
