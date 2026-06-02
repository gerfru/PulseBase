# PulseBase — App Evaluation Report

**Stack:** FastAPI · TimescaleDB (PostgreSQL 16) · Python 3.14 · Docker Compose
**Regelquelle:** Dev-Best-Practices Plugin (essential/app/github/architecture-rules.md)
**ASVS-Level:** L2 (Auth + sensible Gesundheitsdaten, DSGVO, Epilepsie-Modus)
**Team:** Solo · Homelab
**Dokumentierte Ausnahmen (nicht gemeldet):** ARCH-M2, ARCH-M3, ARCH-L2, ARCH-L3, CICD-M3, QUAL-M2, OBS-L1, TEST-L1, SEC-L1, OBS-L2, TEST-L2, CICD-L4

---

## Eval-Historie

| Datum | Beschreibung | Ergebnis |
|---|---|---|
| 2026-05-29 | Eval 1 — Security-Fokus (Wave 0) | 8H · 17M · 17L |
| 2026-06-01 | Eval 2 — Vollständiges App-Audit (alle 6 Achsen) | 7H · 21M · 24L (neu entdeckt, vor Wave 1) |
| 2026-06-01 | Wave 1 — Bug Fixes & Security Quick Wins | H-02, H-03, M-01–05, L-11 gefixt |
| 2026-06-01 | Wave 2 — CSRF + Reset-Token-Invalidierung | H-01, M-06 gefixt |
| 2026-06-01 | Wave 3 — CI/CD-Härtung | H-06, M-15–18, L-14–16 gefixt |
| 2026-06-01 | Wave 4 — Code-Qualität | M-07–09, M-11–12, L-06–10, L-17–19 gefixt |
| 2026-06-01 | Wave 5 — ML Restrukturierung | M-10 gefixt |
| 2026-06-01 | Wave 6 — Tests | H-04, H-05, M-14, M-30, M-31, L-12, L-22, L-23 gefixt |
| 2026-06-01 | Wave 7 — Observability & Docker-Härtung | M-20, L-01–05, L-20, L-24, L-25 gefixt |
| 2026-06-01 | Wave 8 — Code-Qualität (Return-Annotations) | L-26 gefixt |
| 2026-06-01 | Eval 3 — Re-Audit nach Wave 8 (6 Subagenten parallel) | 5H · 8M · 6L neu entdeckt |
| 2026-06-01 | Wave 9 Runde 1 — Security Quick Wins | H-11, M-32, M-33, L-30 gefixt |
| 2026-06-02 | Wave 9 Runde 2 — Architektur / Disposability | M-34, M-35 gefixt |
| 2026-06-02 | Wave 9 Runde 3 — Tests | M-38, M-39 gefixt · L-33 → TEST-L3 · E2E: Register, E-Mail-Verify, Passwort-Reset, Öffentliche Seiten, Epilepsie-Seite ergänzt |

---

## Achsen-Übersicht

| Achse | Eval 1 | Eval 2 | W1 | W2 | W5 | W6 | W7/8 | Eval 3 | Noch offen |
|---|---|---|---|---|---|---|---|---|---|
| Architektur & 12-Factor | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟡 | L-31 |
| Security (ASVS L2) | 🔴 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | — |
| Code-Qualität | 🔴 | 🟡 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🔴 | H-12, H-13, H-14, H-15 |
| Tests & Zuverlässigkeit | 🔴 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟢 | 🟡 | — |
| CI/CD & Delivery | 🟡 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | M-37, L-32, L-35 |
| Observability & Betrieb | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟡 | H-07 (manuell), M-19 (manuell), M-36, L-34 |

**Eval 3 Begründung:**
- **Architektur 🔴:** H-11 (Admin-Credentials in App-Service-Env) ist High-Severity-Befund; stop_grace_period für api+sync fehlt trotz W7-Fix (W7 adressierte nur ml-service).
- **Code-Qualität 🔴:** 4 neue High-Befunde (DAL-Bypass backfill.py, Dateigrößen, lange Funktionen).
- **Security/Tests/CI/Obs 🟡:** Jeweils 1–3 mittlere Befunde, kein systemisches Versagen.

---

## Alle Befunde — nach Severity sortiert

**Legende:** ✅ Umgesetzt · ❌ Offen · 🔧 Teilweise · — Dokumentierte Ausnahme

---

### HIGH

| # | Status | Welle | Titel | Datei | Achse |
|---|---|---|---|---|---|
| H-01 | ✅ | W2 | **CSRF fehlt auf `/garmin/link`, `/libre/link`, `/account/delete`, `/auth/reset`** | `api/src/routes/garmin.py:33` u.a. | Security |
| H-02 | ✅ | W1 | **`get_today_daily_summary` ohne `WHERE date = CURRENT_DATE`** — stille Falschberechnung in Body-Battery/Stress | `ml-service/src/db.py:602` | Code-Qualität |
| H-03 | ✅ | W1 | **`upsert_training_status` überkreuzte `$1/$2/$3`-Reihenfolge** | `sync-service/src/repositories/timescale.py:185` | Code-Qualität |
| H-04 | ✅ | W6 | **ML-Service Coverage-Gate 30% → 50%** — test_db.py + test_backfill.py; Coverage 55.7% | `ml-service/pyproject.toml:37` | Tests |
| H-05 | ✅ | W6 | **Sync-Service `main.py` Orchestrierung komplett ungetestet** | `sync-service/tests/test_main.py` | Tests |
| H-06 | ✅ | W3 | **Kein `ci-ok` All-Green-Gate-Job** — `lint`/`security`/`typecheck` nicht in `e2e`-Voraussetzungen | `.github/workflows/ci.yml:168` | CI/CD |
| H-07 | ❌ | — | **Sentry nicht konfiguriert** — kein Error Tracking in Produktion (manuell: DSN eintragen) | `env/.env.*` | Observability |
| H-08 | ✅ | W0 | **Auth: `is_active`-Flag nicht geprüft** | `api/src/db/users.py` | Security |
| H-09 | ✅ | W0 | **BOLA: `activity_records` ohne User-Bindung** | `api/src/db/activities.py` | Security |
| H-10 | ✅ | W0 | **DOM XSS: Seizure Notes / Event-Type / Sport-Type / Metrics** | `epilepsy.js`, `dashboard-utils.js`, `metrics.js` | Security |
| H-11 | ✅ | W9 | **Admin-Credentials (`DB_USER`/`DB_PASSWORD`) in allen App-Service-Environments** — Least-Privilege-Verletzung; Admin-Creds über `/proc/<pid>/environ` einsehbar | `docker-compose.yml:99-101,136-138,170-172` | Architektur |
| H-12 | ❌ | — | **DAL-Bypass: Raw SQL in `backfill.py` außerhalb `ml-service/src/db/`** — `_load_activity_hrv_data()`, `_load_sleep_daily_gaps()`, SQL in `_backfill_custom_scores()`; `get_yesterday_prediction()` bereits in db/ vorhanden | `ml-service/src/backfill.py:43–140,198` | Code-Qualität |
| H-13 | ❌ | — | **`evidence_catalog.py` 485 Zeilen (>400)** — reine Datenkonstante als Python-Modul; jede Erweiterung bläht sie weiter auf | `api/src/evidence_catalog.py` | Code-Qualität |
| H-14 | ❌ | — | **`auth.py` 417 Zeilen: E-Mail-Helpers im Router** — `_send_email`, `_send_lockout_email`, `_send_reset_email`, `_send_verify_email` (Zeilen 52–145) gehören nicht in eine Router-Datei | `api/src/routes/auth.py` | Code-Qualität |
| H-15 | ❌ | — | **`login()` Funktion 78 Zeilen** — Account-Lockout-Block (Zeilen 159–183) isoliert extrahierbar | `api/src/routes/auth.py:152` | Code-Qualität |

---

### MEDIUM

| # | Status | Welle | Titel | Datei | Achse |
|---|---|---|---|---|---|
| M-01 | ✅ | W1 | **SIGTERM-Handler ml-service fehlt** | `ml-service/src/main.py:641` | Architektur |
| M-02 | ✅ | W1 | **Kein Rate Limit auf `/garmin/link` + `/libre/link`** | `api/src/routes/garmin.py:33` | Security |
| M-03 | ✅ | W1 | **Keine E-Mail-Format-Validierung im `/register`** | `api/src/routes/auth.py:232` | Security |
| M-04 | ✅ | W1 | **`SeizureBody.notes` ohne `max_length`** | `api/src/routes/api.py:282` | Security |
| M-05 | ✅ | W1 | **Consent-Tabelle speichert Raw-IP (DSGVO Art. 5)** — jetzt SHA-256-Hash + Migration V21 | `api/src/db/users.py:259` | Security |
| M-06 | ✅ | W2 | **Password-Reset-Token nicht nach Verwendung invalidiert** (ASVS 2.5.4) | `api/src/routes/auth.py:388` | Security |
| M-07 | ✅ | W4 | **Fehlende Return-Type-Annotierungen** in Route-Handlern, Middleware, `_garmin_call` | `api/src/routes/pages.py`, `sync-service/src/main.py:41` | Code-Qualität |
| M-08 | ✅ | W4 | **stdlib `logging` statt `structlog`** in `ml-service/src/db.py`, `timescale.py`, `mapper.py`, `garmin/client.py` | mehrere | Code-Qualität |
| M-09 | ✅ | W4 | **`export_user_data` `SELECT *` ohne LIMIT** — Memory-Risk bei mehrjährigen Daten | `api/src/db/users.py:296` | Code-Qualität |
| M-10 | ✅ | W5 | **`ml-service/src/db.py` (670 Z.) + `main.py` (648 Z.)** überschreiten 400-Zeilen-Schwelle | `ml-service/src/` | Code-Qualität |
| M-11 | ✅ | W4 | **TRIMP-Formel dreifach dupliziert** mit bereits vorhandenen Abweichungen | `ml-service/src/models/trimp.py` (neu) | Code-Qualität |
| M-12 | ✅ | W4 | **`battery_pattern._assign_pattern_labels` Verschachtelung >4** | `ml-service/src/models/battery_pattern.py:48` | Code-Qualität |
| M-13 | ✅ | W1 | **`api/pyproject.toml` `[tool.coverage.run]` ohne `source`** | `api/pyproject.toml:41` | Tests |
| M-14 | ✅ | W6 | **E2E: 7× `wait_for_timeout()` — flaky-Risiko** | `api/tests/e2e/test_smoke.py` | Tests |
| M-15 | ✅ | W3 | **Python 3.12 in CI vs. 3.14 in Dockerfiles** | `.github/workflows/ci.yml:103` | CI/CD |
| M-16 | ✅ | W3 | **semgrep/bandit/pip-audit ohne Versions-Pin** | `.github/workflows/ci.yml:80` | CI/CD |
| M-17 | ✅ | W3 | **Semgrep fehlt in Pre-commit-Hooks** | `.pre-commit-config.yaml` | CI/CD |
| M-18 | ✅ | W3 | **GitHub-native Secret Scanning undokumentiert** | `.github/` | CI/CD |
| M-19 | ❌ | — | **Uptime-Monitoring nicht eingerichtet** (manuell: UptimeRobot) | — | Observability |
| M-20 | ✅ | W7 | **Traffic + Saturation nicht messbar** (2 von 4 goldenen Signalen) | `api/src/main.py:66` | Observability |
| M-21 | ✅ | W0 | **PII-Logging: E-Mail bei Login-Fail** | `api/src/routes/auth.py` | Security |
| M-22 | ✅ | W0 | **IP-Spoofing: trusted CIDR `172.0.0.0/8` zu breit** | `api/src/deps.py` | Security |
| M-23 | ✅ | W0 | **Flyway-Image: `latest`-Tag** | `docker-compose.yml` | Architektur |
| M-24 | ✅ | W0 | **Traefik-Ports auf `0.0.0.0`** | `docker-compose.yml` | Architektur |
| M-25 | ✅ | W0 | **`api/routes/auth.py` oversized + E-Mail-Duplikate** | `api/src/routes/auth.py` | Code-Qualität |
| M-26 | ✅ | W0 | **Anomalie-Funktionen (5×) dupliziert** | `ml-service/src/main.py` | Code-Qualität |
| M-27 | ✅ | W0 | **Hardcoded Token-Pfad `/app/tokens`** | `sync-service/src/` | Code-Qualität |
| M-28 | ✅ | W0 | **semgrep ohne `--error`** | `.github/workflows/ci.yml` | CI/CD |
| M-29 | ✅ | W0 | **npm statt pnpm in CI** | `.github/workflows/ci.yml` | CI/CD |
| M-30 | ✅ | W6 | **E2E-Test für `POST /account/delete` fehlt** | `api/tests/e2e/test_smoke.py` | Tests |
| M-31 | ✅ | W6 | **Mapper-Tests ohne `None`-Feld-Edge-Cases** | `sync-service/tests/test_mapper.py` | Tests |
| M-32 | ✅ | W9 | **DOM XSS: `training_status` ohne `esc()` in `innerHTML`** — Fallback-Label direkt aus DB-Wert eingesetzt; bestehende `esc()`-Funktion nicht genutzt | `api/src/static/activity.js:285–289` | Security |
| M-33 | ✅ | W9 | **DOM XSS: `metric-value` via `innerHTML` mit API-String-Daten** — `hrv_status`-Strings aus Garmin-Sync ohne Escaping; `textContent` ausreichend | `api/src/static/metrics.js:38` | Security |
| M-34 | ✅ | W9 | **`stop_grace_period` fehlt bei `api` + `sync-service`** — Docker-Default 10s < uvicorn graceful-shutdown 30s; W7 adressierte nur ml-service (L-01) | `docker-compose.yml:88,129` | Architektur |
| M-35 | ✅ | W9 | **sync-service SIGTERM: `scheduler.shutdown(wait=False)` bricht laufende Token-Rotation ab** — `save_user_token()` wird nicht mehr aufgerufen wenn Garmin-Sync >10s läuft | `sync-service/src/main.py:309` | Architektur |
| M-36 | ❌ | — | **Traefik: kein Health Check + kein `restart: unless-stopped`** — abgestürzter Traefik-Prozess wird nicht als unhealthy markiert; kein automatischer Neustart | `docker-compose.yml:63–86` | Observability |
| M-37 | ❌ | — | **`docker-compose.test.yml`: `flyway:latest`-Tag statt gepinnter Version** — `docker-compose.yml` nutzt gepinnten Digest, Test-Compose nicht | `docker-compose.test.yml:22` | CI/CD |
| M-38 | ✅ | W9 | **sync-service `crypto.py` komplett ungetestet** — Fernet-Encrypt/Decrypt + Token-Dir-Serialisierung ohne Roundtrip-Tests (api/ hat äquivalente Tests in test_coverage.py:242–384) | Lücke: `sync-service/src/crypto.py` | Tests |
| M-39 | ✅ | W9 | **sync-service `garmin/client.py` komplett ungetestet** — H-05 (W6) testete Orchestrierung; Client-Logik (Token-Login, Fallback, save_token) weiterhin ohne Test | Lücke: `sync-service/src/garmin/client.py` | Tests |

---

### LOW

| # | Status | Welle | Titel | Datei | Achse |
|---|---|---|---|---|---|
| L-01 | ✅ | W7 | **Kein `stop_grace_period` für ml-service** | `docker-compose.yml:162` | Architektur |
| L-02 | ✅ | W7 | **Traefik: kein Access-Log** | `traefik/traefik.yml` | Architektur |
| L-03 | ✅ | W7 | **uvicorn: kein `--timeout-graceful-shutdown`** | `api/Dockerfile:19` | Architektur |
| L-04 | ✅ | W7 | **`proxy`-Netzwerk kein Makefile-Fallback** | `docker-compose.yml:205` | Architektur |
| L-05 | ✅ | W7 | **CSP: `worker-src` + `manifest-src` fehlen** | `api/src/main.py:43` | Architektur |
| L-06 | ✅ | W4 | **auth.py: 6× identische `TemplateResponse`-Blöcke** | `api/src/routes/auth.py:244` | Code-Qualität |
| L-07 | ✅ | W4 | **`get_ml_status` in `ml.py` — toter Code** | `api/src/db/ml.py:54` | Code-Qualität |
| L-08 | ✅ | W4 | **`export_user_data`: `SELECT *` statt explizite Spalten** | `api/src/db/users.py:299` | Code-Qualität |
| L-09 | ✅ | W4 | **`_garmin_call` in sync-service untypisiert** | `sync-service/src/main.py:41` | Code-Qualität |
| L-10 | ✅ | W4 | **`hrv_vals` unnötig neu zugewiesen** | `ml-service/src/models/hrv_recovery.py:33` | Code-Qualität |
| L-11 | ✅ | W1 | **`asyncio.get_event_loop()` deprecated** | `sync-service/src/main.py:304` | Code-Qualität |
| L-12 | ✅ | W6 | **E2E: 3 conditional `pytest.skip`** | `api/tests/e2e/test_smoke.py` | Tests |
| L-13 | — | — | **JS-Coverage nur 4/24 Static-JS-Dateien** (dokumentierte Ausnahme TEST-L2) | `api/vitest.config.js:10` | Tests |
| L-14 | ✅ | W3 | **Renovate: `minor`-Updates undokumentiert** | `renovate.json:7` | CI/CD |
| L-15 | ✅ | W3 | **GitHub-Actions Kommentar-Tags falsch** (`# v6` statt `# v4`) | `ci.yml:21,75` | CI/CD |
| L-16 | ✅ | W3 | **E2E-Job: DB-Credentials via `grep` aus `.env`** | `ci.yml:205` | CI/CD |
| L-17 | ✅ | W4 | **`logging_config.py` (sync-service): `level=logging.INFO` fehlt** | `sync-service/src/logging_config.py:21` | Observability |
| L-18 | ✅ | W4 | **`garmin/client.py` + `libre/client.py`: stdlib statt structlog** | mehrere | Observability |
| L-19 | ✅ | W4 | **`LibreAuthError`-String enthält `user_id` doppelt** | `sync-service/src/main.py:194` | Observability |
| L-20 | ✅ | W7 | **Sentry `traces_sample_rate=0.0`** in sync/ml (kein Job-Tracing) | `sync-service/src/main.py:268` | Observability |
| L-21 | — | — | **Kein OpenTelemetry / Tracing** (dokumentierte Ausnahme OBS-L2) | — | Observability |
| L-22 | ✅ | W6 | **`test_hrv_recovery`: tautologische Assertion** | `ml-service/tests/test_models.py` | Tests |
| L-23 | ✅ | W6 | **E2E: kein Test für `/metrics` und `/help`** | `api/tests/e2e/test_smoke.py` | Tests |
| L-24 | ✅ | W7 | **Health-Check: Python-Interpreter statt `curl`** | `api/Dockerfile` | Observability |
| L-25 | ✅ | W7 | **Readiness-Probe prüft keine Migration** | `api/src/main.py:150` | Observability |
| L-26 | ✅ | W8 | **Fehlende Return-Annotierungen in `training_load.py`** | `api/src/training_load.py` | Code-Qualität |
| L-27 | ✅ | W0 | **HEALTHCHECK `start_period` fehlt im api Dockerfile** | `api/Dockerfile` | Architektur |
| L-28 | — | — | **HSTS bei self-signed TLS** (dokumentierte Ausnahme SEC-L1) | `api/src/main.py` | Security |
| L-29 | ✅ | W0 | Renovate GitHub-Actions minor/patch automerge · trivy nicht in needs-Chain · pre-commit mypy ohne `--explicit-package-bases` · `.dockerignore` unvollständig · coverage omit veraltet · Magic Number `_DEFAULT_RHR` · Return-Annotation `_rate_limit_exceeded_handler` | mehrere | diverse |
| L-30 | ✅ | W9 | **CSRF-Token fehlt auf Login + Register POST** — `verify_csrf_token()`-Infrastruktur vorhanden; nur auf garmin/link, libre/link, account/delete verwendet; ASVS 5.0 V4.10.1 | `api/src/routes/auth.py:150–291` | Security |
| L-31 | ❌ | — | **ml-service SIGTERM: `joblib.dump()` nicht atomar** — Modell-Datei auf Named Volume kann in unvollständigem Zustand hinterlassen werden; Temp-Pfad + `Path.rename()` als atomare Alternative | `ml-service/src/main.py:206` | Architektur |
| L-32 | ❌ | — | **Semgrep pre-commit ohne OWASP-Top-10-Ruleset** — CI nutzt `p/python + p/owasp-top-ten`; pre-commit Hook nur `p/python` → Cross-file-Taint-Findings erst in CI sichtbar | `.pre-commit-config.yaml:48` | CI/CD |
| L-33 | — | — | **JS-Vitest: `dashboard-hero.js` fehlt in `coverage.include`** — dedizierter Testfile vorhanden, aber Datei erscheint nicht im Coverage-Report | `api/vitest.config.js:12–16` | Tests |
| L-34 | ❌ | — | **Traefik accessLog: kein JSON-Format** — Common Log Format (CLF) statt JSON; inkompatibel mit structlog-Logging der anderen Services | `traefik/traefik.yml:20` | Observability |
| L-35 | ❌ | — | **pip-audit scannt Verzeichnis, nicht `uv.lock`** — `pip-audit api/` löst Abhängigkeiten neu auf statt eingefrorenes Lockfile zu prüfen | `ci.yml:76–86` | CI/CD |

---

## Offene Findings (Eval 3)

| Wave | Findings |
|------|---------|
| **W2–W8** (abgeschlossen) | ✅ H-01–H-06, H-08–H-10, M-01–M-18, M-20–M-31, L-01–L-12, L-14–L-20, L-22–L-27, L-29 |
| **Manuell** | ❌ H-07 (Sentry DSN), M-19 (UptimeRobot) |
| **Wave 9 Runde 1 — Security** | ✅ H-11, M-32, M-33, L-30 gefixt |
| **Wave 9 — Architektur/Disposability** | ✅ M-34, M-35 · ❌ L-31 |
| **Wave 9 — Code-Qualität** | ❌ H-12, H-13, H-14, H-15 |
| **Wave 9 — Tests** | ✅ M-38, M-39 · — L-33 (dokumentierte Ausnahme TEST-L3) |
| **Wave 9 — CI/CD + Obs** | ❌ M-36, M-37, L-32, L-34, L-35 |
| **Wave 9 — Architektur Low** | ❌ L-31 |

**Empfohlene Reihenfolge Wave 9:**
1. H-11 (Admin-Creds env-Trennung — löst L-31-ähnlichen Nebeneffekt mit) · M
2. M-32 + M-33 (DOM XSS activity.js + metrics.js — `esc()` 1-Liner) · S
3. L-30 (CSRF Login/Register — Infrastruktur vorhanden) · S
4. M-34 + M-35 (stop_grace_period + SIGTERM wait=True) · S+M
5. M-38 + M-39 (crypto.py + garmin/client Tests) · S+S
6. H-12 (DAL-Bypass backfill.py → db/) · M
7. H-13 (evidence_catalog.py → JSON) · M
8. H-14 + H-15 (auth.py Email-Helpers + login() aufteilen) · S+S
9. M-36 + M-37 (Traefik Health Check + flyway:latest test-compose) · S+S
10. L-32 + L-34 + L-35 (Semgrep OWASP + accessLog JSON + pip-audit lockfile) · S+S+M
11. L-31 + L-33 (joblib atomar + dashboard-hero coverage) · M+S

---

## DORA-Einschätzung [Schätzung — keine CI-Historie]

| Metrik | Wert | Basis |
|---|---|---|
| Deployment Frequency | Niedrig (wöchentlich–monatlich) | Kein Auto-Deploy in CI; manuell per `make up` |
| Lead Time for Changes | Mittel (~1–4h) | Pipeline ~15 min (Engpass: 3× Docker-Build für Trivy) |
| Change Failure Rate | Nicht messbar | Keine CI-Deployment-Historie |
| Recovery Time | Minuten | Docker-Tag-Rollback; `make dashboard` / `make analytics` |

---

## Positive Befunde

- **SQL**: Alle Queries als Prepared Statements via asyncpg — kein SQLi-Vektor
- **Security Headers**: CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy — vollständig
- **Cookie-Flags**: `httpOnly`, `secure`, `sameSite=lax` korrekt
- **Rate Limiting**: Login 10/min, Register 5/min, Reset 3/hour, Garmin/Libre 5/hour
- **bcrypt**: direkt (ohne passlib), DUMMY\_HASH für Timing-Safety
- **Fernet-Verschlüsselung**: Garmin-Tokens korrekt verschlüsselt, Key-Validierung beim Start
- **Sentry PII**: `send_default_pii=False` in allen Services
- **Docker-Hygiene**: Multi-Stage Builds, SHA256-Digest-Pins (alle Images), Non-root User, HEALTHCHECK, Resource Limits, Log-Rotation — vollständig
- **Auth-Suite**: Login/Lockout/Rate-Limit/E-Mail-Verifikation/Password-Reset/DSGVO vollständig getestet — inkl. E2E-Tests für Register-Flow, Token-Verifizierung und Passwort-Reset (test_auth_flows.py)
- **E2E-Abdeckung**: Alle öffentlichen Seiten (Privacy, Terms, Imprint, Accessibility) + Epilepsie-Seite (mit/ohne Modus) via Playwright abgedeckt (test_static_pages.py)
- **ML-Modelle**: 14 Modelle, 80 Unit-Tests inkl. Randfälle
- **Action-Digests**: Alle GitHub Actions mit Commit-SHA gepinnt
- **structlog JSON + UTC**: alle 3 Services; keine Secrets in Logs
- **/health + /ready**: Liveness (kein DB-Call) + Readiness (SELECT 1 + Flyway-Check) — überdurchschnittlich gut

---

## Dokumentierte Ausnahmen

| ID | Beschreibung |
|---|---|
| ARCH-M2 | Kein Service-Layer (Routes → DB direkt) — Solo-Projekt |
| ARCH-M3 | Traefik self-signed TLS — Homelab-Ausnahme |
| CICD-M3 | Branch Protection nicht erzwingbar (Free-Plan, privates Repo) |
| QUAL-M2 | Duplizierter GarminClient in api/ + sync-service/ — bewusst |
| ARCH-L2 | Technisch-basierte `db/`-Ordnerstruktur — Solo-Projekt |
| ARCH-L3 | Kein `/api/v1/`-Prefix — keine externen Consumer |
| OBS-L1 | Kein externes Uptime-Monitoring — Reminder: UptimeRobot einrichten |
| TEST-L1 | `require_user`-Mock ohne `assert_called_once()` — Tests verifizieren Verhalten |
| SEC-L1 | HSTS bei self-signed TLS — Homelab-Ausnahme (ARCH-M3) |
| OBS-L2 | Kein OpenTelemetry — Solo-Homelab; `request_id` als Korrelation ausreichend |
| TEST-L2 | JS-Coverage auf 4/24 Static-JS-Dateien — DOM-heavy Files via Playwright E2E |
| TEST-L3 | `dashboard-hero.js` bewusst aus Vitest `coverage.include` ausgeschlossen — `heroRecommendation()` hat Unit-Tests; DOM-schwere Funktionen (`buildHeroCard`, `buildMlTabs`) via Playwright E2E; Coverage-Merge Unit+E2E mit Python-Playwright-Stack nicht praktikabel |
| CICD-L4 | GitHub-native Secret Scanning nicht verfügbar (Free-Plan) |
