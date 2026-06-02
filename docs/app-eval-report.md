# PulseBase — App Evaluation Report

**Stack:** FastAPI · TimescaleDB (PostgreSQL 16) · Python 3.14 · Docker Compose
**Regelquelle:** Dev-Best-Practices Plugin (essential/app/github/architecture-rules.md)
**ASVS-Level:** L2 (Auth + sensible Gesundheitsdaten, DSGVO, Epilepsie-Modus)
**Team:** Solo · Homelab
**Dokumentierte Ausnahmen (nicht gemeldet):** ARCH-M2, ARCH-M3, ARCH-L2, ARCH-L3, ARCH-L4, CICD-M3, QUAL-M2, OBS-L1, OBS-L2, TEST-L1, TEST-L2, TEST-L3, SEC-L1, CICD-L4

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
| 2026-06-02 | Wave 9 Runde 4 — Code-Qualität | H-12 (DAL-Bypass backfill.py → db/), H-13 (evidence_catalog.py → JSON), H-14 (mail.py extrahiert), H-15 (login() aufgeteilt) gefixt |
| 2026-06-02 | Wave 9 Runde 5 — CI/CD + Observability | M-36 (Traefik ping HEALTHCHECK), M-37 (flyway:11 Test-Compose), L-31 (joblib atomar), L-32 (semgrep OWASP), L-34 (accessLog JSON), L-35 (pip-audit uv.lock) gefixt |
| 2026-06-02 | Eval 4 — Vollständiger Re-Audit nach Wave 9 (6 Subagenten parallel) | 2H · 17M · 25L (neu entdeckt) |
| 2026-06-02 | Wave 10 Runde 1 — Security Quick Wins | H-16, H-17, M-40, M-41, M-43, M-44, L-36–39 gefixt · L-59 ✅ resolved · M-52 ❌ confirmed open |

---

## Achsen-Übersicht

| Achse | Eval 1 | Eval 2 | W1 | W2 | W5 | W6 | W7/8 | Eval 3 | W9 | Eval 4 | W10 | Noch offen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Architektur & 12-Factor | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟡 | 🟢 | 🟡 | 🟡 | M-45, M-46, L-40–43 |
| Security (ASVS L2) | 🔴 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🟢 | H-07 (manuell), M-42 (Nonce, Aufwand hoch), L-28 (Ausnahme) |
| Code-Qualität | 🔴 | 🟡 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 | 🟡 | 🟡 | M-50–52, L-44–46, L-57–60 |
| Tests & Zuverlässigkeit | 🔴 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟢 | 🟡 | 🟢 | 🟡 | 🟡 | M-53–55, L-47–50 |
| CI/CD & Delivery | 🟡 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🟢 | 🟢 | 🟢 | M-19 (manuell), M-56, L-51 |
| Observability & Betrieb | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟡 | 🟢 | 🟡 | 🟡 | M-47–49, L-52–56 |

**Eval 3 Begründung:**
- **Architektur 🔴:** H-11 (Admin-Credentials in App-Service-Env) ist High-Severity-Befund; stop_grace_period für api+sync fehlt trotz W7-Fix (W7 adressierte nur ml-service).
- **Code-Qualität 🔴:** 4 neue High-Befunde (DAL-Bypass backfill.py, Dateigrößen, lange Funktionen).
- **Security/Tests/CI/Obs 🟡:** Jeweils 1–3 mittlere Befunde, kein systemisches Versagen.

**Eval 4 Begründung (nach Wave 9):**
- **Security 🟡:** H-16 (Fernet dead-code Guard), 5 neue Mediums (CSRF /logout, Lockout Race Condition, CSP ohne Nonce, Reset-Token GET-Leck, DAL Auth fehlt). Positive Basis bleibt stark: keine SQLi, Rate Limiting vollständig, CSRF auf allen anderen Routen korrekt.
- **Architektur 🟡:** M-45 (ml-service SIGTERM wait=False — M-01 W1 adressierte nur den Handler, nicht das wait-Flag), M-46 (api-test Port auf 0.0.0.0). Prod-Architektur 🟢.
- **Code-Qualität 🟡:** 3 neue Mediums (God-Functions in inference_models.py, login() immer noch 67Z nach H-15-Teilfix). Kein Critical, keine strukturellen Mängel.
- **Tests 🟡:** H-17 (is_active=False Login-Test — H-08 W0 fixte Implementation, Test fehlt weiterhin), 3 Mediums (@requires_data in CI nie ausgeführt, inference_models.py Tests fehlen, fail_under Drift).
- **CI/CD 🟢:** Nur 1 Medium (Trivy ohne Artefakt) + wenige Lows. DORA-Profil: High Performer.
- **Observability 🟡:** 3 Mediums (stdlib ProcessorFormatter Bridge fehlt, Compose-Healthcheck /health statt /ready, SentryProcessor fehlt). Grundinfrastruktur (structlog JSON, /health + /ready, Sentry optional) ist vorhanden.

---

## Alle Befunde — nach Severity sortiert

**Legende:** ✅ Umgesetzt · ❌ Offen · 🔧 Teilweise · — Dokumentierte Ausnahme · [?] zu verifizieren

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
| H-12 | ✅ | W9 | **DAL-Bypass: Raw SQL in `backfill.py` außerhalb `ml-service/src/db/`** — `_load_activity_hrv_data()`, `_load_sleep_daily_gaps()`, SQL in `_backfill_custom_scores()`; `get_yesterday_prediction()` bereits in db/ vorhanden | `ml-service/src/backfill.py:43–140,198` | Code-Qualität |
| H-13 | ✅ | W9 | **`evidence_catalog.py` 485 Zeilen (>400)** — reine Datenkonstante als Python-Modul; jede Erweiterung bläht sie weiter auf | `api/src/evidence_catalog.py` | Code-Qualität |
| H-14 | ✅ | W9 | **`auth.py` 417 Zeilen: E-Mail-Helpers im Router** — `_send_email`, `_send_lockout_email`, `_send_reset_email`, `_send_verify_email` (Zeilen 52–145) gehören nicht in eine Router-Datei | `api/src/routes/auth.py` | Code-Qualität |
| H-15 | ✅ | W9 | **`login()` Funktion 78 Zeilen** — Account-Lockout-Block (Zeilen 159–183) isoliert extrahierbar | `api/src/routes/auth.py:152` | Code-Qualität |
| H-16 | ✅ | W10 | **Fernet dead-code: Garmin-Token potentiell unverschlüsselt** — `if settings.fernet_key`-Guards implizieren Code-Pfad ohne Verschlüsselung; Key ist als Pflichtfeld validiert, aber `else`-Zweig bleibt latent im Code | `api/src/routes/garmin.py:63–83` | Security |
| H-17 | ✅ | W10 | **Login mit `is_active=False` nicht getestet** — H-08 (W0) fixte die Implementation; ein Test für den deaktivierten-User-Pfad fehlt weiterhin (`TEST_USER` hat kein `is_active`-Feld) | `api/tests/test_auth.py` | Tests |

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
| M-36 | ✅ | W9 | **Traefik: kein Health Check + kein `restart: unless-stopped`** — abgestürzter Traefik-Prozess wird nicht als unhealthy markiert; kein automatischer Neustart | `docker-compose.yml:63–86` | Observability |
| M-37 | ✅ | W9 | **`docker-compose.test.yml`: `flyway:latest`-Tag statt gepinnter Version** — `docker-compose.yml` nutzt gepinnten Digest, Test-Compose nicht | `docker-compose.test.yml:22` | CI/CD |
| M-38 | ✅ | W9 | **sync-service `crypto.py` komplett ungetestet** — Fernet-Encrypt/Decrypt + Token-Dir-Serialisierung ohne Roundtrip-Tests (api/ hat äquivalente Tests in test_coverage.py:242–384) | Lücke: `sync-service/src/crypto.py` | Tests |
| M-39 | ✅ | W9 | **sync-service `garmin/client.py` komplett ungetestet** — H-05 (W6) testete Orchestrierung; Client-Logik (Token-Login, Fallback, save_token) weiterhin ohne Test | Lücke: `sync-service/src/garmin/client.py` | Tests |
| M-40 | ✅ | W10 | **Kein CSRF-Schutz auf `POST /logout`** — Forced-Logout via Cross-Site-POST möglich; alle anderen mutativen Routen korrekt geschützt · Fix: `verify_csrf_token()` analog zu `garmin_unlink` | `api/src/routes/auth.py:257–260` | Security |
| M-41 | ✅ | W10 | **Account-Lockout Race Condition** — `failed_login_attempts` wird vor `increment_failed_login` gelesen + manuell +1 addiert; parallele Requests können Lockout-Trigger umgehen · Fix: `UPDATE ... SET failed_login_attempts = failed_login_attempts + 1 RETURNING failed_login_attempts` | `api/src/routes/auth.py:142–143` | Security |
| M-42 | ❌ | E4 | **CSP ohne Nonce — Gold-Standard nicht erreicht** — `script-src 'self'` ohne Nonce; laut app-rules.md ist nonce-basiert mit `'strict-dynamic'` der Soll-Standard · Fix: Nonce-Middleware + `script-src 'nonce-{n}' 'strict-dynamic'` · Vorher im Report-Only-Modus testen | `api/src/main.py:44–57` | Security |
| M-43 | ✅ | W10 | **Password-Reset-Token nach GET-Aufruf weiterhin gültig** — M-06 (W2) fixte Invalidierung nach POST; GET rendert Formular ohne Token zu invalidieren; Angreifer mit abgegriffenem Token kann weiterhin POST senden · verifiziert: GET-Case offen · Fix: `request.session["reset_token_hash"]` beim GET setzen, beim POST prüfen + entfernen | `api/src/routes/auth.py:322–335` | Security |
| M-44 | ✅ | W10 | **Auth fehlt am Data Access Layer (3. Schicht)** — DB-Funktionen akzeptieren `user_id: int` ohne Ownership-Prüfung; defense-in-depth gemäß app-rules.md fehlt · Fix (kurzfristig): `assert user_id > 0` + `# CALLER MUST verify session ownership` auf kritischen Schreibops (`delete_user`, `update_password`, `save_user_token`) | `api/src/db/users.py` | Security |
| M-45 | ❌ | E4 | **ml-service SIGTERM `wait=False` — laufende ML-Jobs werden abgebrochen** — M-01 (W1) adressierte fehlenden Handler; `wait=False` bricht laufende `fit()`/`predict()`-Jobs trotz `stop_grace_period: 60s` ab; sync-service löst das korrekt (M-35 W9) · Fix: SIGTERM-Handler analog zu sync-service mit `asyncio.Event` + `scheduler.shutdown(wait=True)` | `ml-service/src/main.py:206` | Architektur |
| M-46 | ❌ | E4 | **api-test Port 8001 nicht auf `127.0.0.1` gebunden** — `"8001:8000"` bindet auf `0.0.0.0`; Test-Stack läuft auf demselben Mac mini wie Prod; API-Test-Container ohne Auth von LAN erreichbar · Fix: `"127.0.0.1:8001:8000"` | `docker-compose.test.yml:46` | Architektur |
| M-47 | ❌ | E4 | **Stdlib-Logs nicht JSON (split log format)** — `logging.basicConfig(format="%(message)s")` leitet uvicorn/APScheduler/garminconnect-Logs als Plain-Text; M-08 (W4) fixte interne structlog-Calls, aber `ProcessorFormatter`-Bridge für Third-Party-Logger fehlt weiterhin · Fix: `structlog.stdlib.ProcessorFormatter` mit `foreign_pre_chain` als Root-Logger-Handler | `api/src/logging_config.py:24`, `sync-service/src/logging_config.py:21`, `ml-service/src/logging_config.py:24` | Observability |
| M-48 | ❌ | E4 | **Compose-Healthcheck trifft `/health` statt `/ready`** — Docker prüft Liveness, nicht Readiness; Container gilt als `healthy` auch wenn DB-Verbindung noch nicht steht · Fix: `test: ["CMD", "curl", "-f", "http://localhost:8000/ready"]` | `docker-compose.yml:120` | Observability |
| M-49 | ❌ | E4 | **`logger.error(...)` landet nicht in Sentry (kein `SentryProcessor`)** — FastAPI-Integration fängt nur unhandled Exceptions; explizite `logger.error(..., exc_info=True)`-Aufrufe in sync/ml-service erzeugen keine Sentry-Events · Fix: `structlog.SentryProcessor(level=logging.ERROR)` vor `JSONRenderer` in alle drei `logging_config.py` | `api/src/logging_config.py`, alle Services | Observability |
| M-50 | ❌ | E4 | **`_run_energy_metrics()` God-Function (63 Zeilen, 5 Concerns)** — berechnet und persistiert physical energy, ACWR, training monotony, autonomic energy, cognitive energy in einer Funktion; verhindert Einzel-Tests · Fix: in fünf `_run_*`-Funktionen aufteilen | `ml-service/src/inference_models.py:82` | Code-Qualität |
| M-51 | ❌ | E4 | **`_run_body_battery_and_stress()` 60 Zeilen mit Inline-Berechnung** — manualle HRV-Baseline-Berechnung (Z. 264–268) inline statt in dedizierter Model-Funktion · Fix: `compute_hrv_baseline()` extrahieren; Funktion aufteilen | `ml-service/src/inference_models.py:248` | Code-Qualität |
| M-52 | ❌ | E4 | **`login()` immer noch 70 Zeilen nach H-15-Teilfix** — H-15 (W9) extrahierte Lockout-Block; verifiziert: Z.115–184 = 70Z, weiterhin >50Z-Schwelle | `api/src/routes/auth.py:117` | Code-Qualität |
| M-53 | ❌ | E4 | **`fail_under = 80` in ml-service ≠ CLAUDE.md-Dokumentation „30%"** — Dokumentations-Drift; CI bricht bei Coverage < 80% ab · Fix: CLAUDE.md korrigieren auf 80% | `ml-service/pyproject.toml:37` | Tests |
| M-54 | ❌ | E4 | **`@requires_data` E2E-Tests werden in CI nie ausgeführt** — `test_formula_modal_opens_on_score_click` + `test_activity_detail_page_loads` übersprungen ohne `CI_HAS_DATA=true`; JS-Interaktionen nie in CI getestet · Fix: E2E-Stack mit Seed-Daten; `CI_HAS_DATA=true` setzen | `api/tests/e2e/test_smoke.py:21–23` | Tests |
| M-55 | ❌ | E4 | **`inference_models.py` ohne Unit-Tests** — `_run_readiness`, `_run_body_battery`, `_run_hrv_status` u.a. (8 `_run_*`-Funktionen) nicht abgedeckt; bei `fail_under=80` ist das ein Coverage-Risiko · Fix: Unit-Tests für alle 8 `_run_*`-Funktionen | `ml-service/tests/` | Tests |
| M-56 | ❌ | E4 | **Trivy `ignore-unfixed: true` ohne Artefakt/Audit-Spur** — Pipeline ist grün bei CRITICAL-CVEs ohne verfügbaren Fix, ohne jede Spur im Job-Log · Fix: `format: table` + `actions/upload-artifact` ergänzen, oder `.trivyignore` mit dokumentierten Ausnahmen | `.github/workflows/ci.yml:135,143,151` | CI/CD |

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
| L-31 | ✅ | W9 | **ml-service SIGTERM: `joblib.dump()` nicht atomar** — Modell-Datei auf Named Volume kann in unvollständigem Zustand hinterlassen werden; Temp-Pfad + `Path.rename()` als atomare Alternative | `ml-service/src/models/readiness.py:94` | Architektur |
| L-32 | ✅ | W9 | **Semgrep pre-commit ohne OWASP-Top-10-Ruleset** — CI nutzt `p/python + p/owasp-top-ten`; pre-commit Hook nur `p/python` → Cross-file-Taint-Findings erst in CI sichtbar | `.pre-commit-config.yaml:48` | CI/CD |
| L-33 | — | — | **JS-Vitest: `dashboard-hero.js` fehlt in `coverage.include`** — dedizierter Testfile vorhanden, aber Datei erscheint nicht im Coverage-Report (dokumentierte Ausnahme TEST-L3) | `api/vitest.config.js:12–16` | Tests |
| L-34 | ✅ | W9 | **Traefik accessLog: kein JSON-Format** — Common Log Format (CLF) statt JSON; inkompatibel mit structlog-Logging der anderen Services | `traefik/traefik.yml:20` | Observability |
| L-35 | ✅ | W9 | **pip-audit scannt Verzeichnis, nicht `uv.lock`** — `pip-audit api/` löst Abhängigkeiten neu auf statt eingefrorenes Lockfile zu prüfen | `ci.yml:76–86` | CI/CD |
| L-36 | ✅ | W10 | **HSTS wird auch bei `https_only=false` gesetzt** — HSTS in Dev/Test-Umgebungen kann Browser-HSTS-State für die Domain setzen und HTTP dauerhaft blockieren · Fix: `if settings.https_only:` Guard um HSTS-Header | `api/src/main.py:41–43` | Security |
| L-37 | ✅ | W10 | **Fehlende Längenvalidierung für `email`-Felder in Auth-Formularen** — `Form()` ohne `max_length` auf `/login`, `/auth/resend-verify`, `/auth/reset-request`; sehr lange E-Mails erreichen bcrypt/structlog ungefiltert · Fix: `Form(max_length=320)` | `api/src/routes/auth.py:119,270,308` | Security |
| L-38 | ✅ | W10 | **`service`-Parameter in `get_user_token`/`save_user_token` ohne Whitelist** — akzeptiert beliebigen String; erlaubte Werte sind implizit `"garmin"` und `"libre"` · Fix: `Literal["garmin", "libre"]` Typ-Annotation | `api/src/db/users.py:234` | Security |
| L-39 | ✅ | W10 | **`httpOnly`-Cookie-Flag nicht explizit durch Test abgesichert** — Starlette `SessionMiddleware` setzt `httponly=True` per Default; kein Vertrag-Test der `set-cookie`-Header · Fix: Unit-Test `assert "httponly" in response.headers["set-cookie"].lower()` | `api/src/main.py:148–154` | Security |
| L-40 | ❌ | E4 | **`docker-compose.test.yml` ohne Resource Limits und Log-Rotation** — Prod-Compose hat vollständige `deploy.resources.limits` + `json-file logging`; Test-Compose läuft auf demselben Mac mini wie Prod · Fix: pragmatische Limits (db-test: 512 MB, api-test: 256 MB) + `logging: json-file` | `docker-compose.test.yml` | Architektur |
| L-41 | — | — | **3-Service-Splitting ohne explizite Begründung in CLAUDE.md** — bewusstes Splitting wegen Scheduling-Isolation, ML-Workload-Trennung, unabhängiger Restart-Zyklen, unterschiedlicher Memory-Limits (dokumentierte Ausnahme ARCH-L4) | `CLAUDE.md` | Architektur |
| L-42 | ❌ | E4 | **`routes/api.py` domain-übergreifend (352 Zeilen, wächst)** — alle 20+ JSON-Endpunkte quer über alle Domains in einer Datei; wächst mit jeder neuen Domain · Fix: Subdomain-Router (`routes/api/activities.py`, `routes/api/health.py`, …) oder als ARCH-L5 dokumentieren | `api/src/routes/api.py` | Architektur |
| L-43 | ❌ | E4 | **ML-Healthcheck prüft keine Modell-Integrität** — prüft nur ob APScheduler-Loop lebt; korrumpierte `.joblib`-Dateien bleiben unerkannt · Fix: Startup-Probe die vorhandene `.joblib`-Files beim ersten Start lädt | `docker-compose.yml:191–193` | Architektur |
| L-44 | ❌ | E4 | **Sequentielle `await` in `_run_correlations`-Schleife** — 3× unabhängige DB-Queries sequenziell statt parallel · Fix: `await asyncio.gather(*[coro for coro, _ in correlation_tasks])` | `ml-service/src/inference_anomaly.py:109` | Code-Qualität |
| L-45 | ❌ | E4 | **`require_user()` gibt ungetyptes `dict` zurück** — mypy erkennt falsche Key-Zugriffe nicht · Fix: `UserRow = TypedDict("UserRow", {"id": int, "email": str, …})` einführen | `api/src/deps.py:73` | Code-Qualität |
| L-46 | ❌ | E4 | **`zip(*pairs)` ohne Längen-Assertion** — bei `pairs` mit falscher Dimensionierung kein Fehler · Fix: `xs = [p[0] for p in pairs]; ys = [p[1] for p in pairs]` | `ml-service/src/inference_anomaly.py:113` | Code-Qualität |
| L-47 | ❌ | E4 | **`POST /api/sync` Failure-Pfad ungetestet** — `request_sync`-Exception nicht abgedeckt · Fix: Mock-Test mit `AsyncMock(side_effect=Exception)` | `api/tests/test_api_endpoints.py:154` | Tests |
| L-48 | ❌ | E4 | **`/api/seizures/risk` ohne Boundary-Tests** — nur `severity=3` geprüft; keine Tests für severity=1, severity=5, ungültige Werte · Fix: parametrisierter Test mit Edge-Cases | `api/tests/` | Tests |
| L-49 | ❌ | E4 | **sync-service: kein Test für Garmin+Libre-Kombinations-User** — kombinierter Sync-Pfad ungetestet | `sync-service/tests/test_main.py` | Tests |
| L-50 | ❌ | E4 | **`/account/export` E2E prüft nicht JSON-Download-Inhalt** — Unit-Test vorhanden; E2E prüft nur ob Link sichtbar, nicht Struktur/kein password_hash | `api/tests/e2e/test_smoke.py:213` | Tests |
| L-51 | ❌ | E4 | **Tote Branch-Namen in `no-commit-to-branch`** — `--branch, dev, --branch, master` schützt nicht-existente Branches · Fix: auf `--branch, main` reduzieren | `.pre-commit-config.yaml:19` | CI/CD |
| L-52 | ❌ | E4 | **Kein `sentry.disabled`-Warning beim Start** — wenn Sentry-DSN leer ist, gibt es keinen sichtbaren Hinweis in den Logs · Fix: `else: logger.warning("sentry.disabled")` in allen drei Services | `api/src/main.py`, `sync-service/src/main.py`, `ml-service/src/main.py` | Observability |
| L-53 | ❌ | E4 | **`PrintLoggerFactory` nicht Thread-safe für Production** — `print()` bei concurrent Writes (ml-service mit scikit-learn-Threads) kann zu interleavten Log-Zeilen führen · Fix: `structlog.WriteLoggerFactory()` in allen drei `logging_config.py` | `api/src/logging_config.py:20`, `sync-service/src/logging_config.py:19`, `ml-service/src/logging_config.py:20` | Observability |
| L-54 | ❌ | E4 | **Kein Correlation-ID in sync/ml-service Logs** — API bindet `request_id` per `bind_contextvars`; sync/ml nutzen es nicht; gleichzeitige User-Jobs in Logs nicht unterscheidbar · Fix: `bind_contextvars(job_id=str(uuid.uuid4())[:8], user_id=uid)` am Job-Eingang | `sync-service/src/main.py:136`, `ml-service/src/main.py:55` | Observability |
| L-55 | ❌ | E4 | **Kein Error-Rate-Signal** — `RequestIDMiddleware` zählt Traffic + Latency; kein `_error_requests`-Counter für `4xx/5xx`; eines der vier goldenen Signale nicht messbar · Fix: `_error_requests` Counter in `RequestIDMiddleware` | `api/src/main.py:61` | Observability |
| L-56 | ❌ | E4 | **`/health` exponiert interne Zähler ohne Auth** — `active_requests` + `total_requests` öffentlich; für Liveness-Check genügt `{"status": "ok"}` · Fix: Zähler aus Public-Response entfernen oder in separates `/metrics`-Endpoint verlagern | `api/src/main.py:162–168` | Observability |
| L-57 | ❌ | E4 | **f-String in `structlog`-Call** — `logger.info(f"{log_key}.done", ...)` verhindert strukturiertes Event-Matching in Log-Aggregatoren · Fix: `logger.info("anomaly.done", metric=log_key, ...)` | `ml-service/src/inference_anomaly.py:41` | Code-Qualität |
| L-58 | [?] | E4 | **Dupliziertes Backfill+Training-Muster** — identischer 5-Zeilen-Block in `run_on_request` und `run_all_users`; H-12 (W9) restrukturierte backfill.py → db/, aber main.py-Duplikat ggf. erhalten · zu verifizieren · Fix: `_run_training_with_backfill(uid, settings)` extrahieren | `ml-service/src/main.py:119,144` | Code-Qualität |
| L-59 | ✅ | — | **`auth.py` Dateigröße nach H-14** — H-14 (W9) extrahierte E-Mail-Helpers; verifiziert: 381 Zeilen < 400Z-Schwelle → resolved | `api/src/routes/auth.py` | Code-Qualität |
| L-60 | [?] | E4 | **5 einzeilige `_run_anomaly_*`-Wrapper (Copy-Paste)** — jede Funktion leitet nur an `_run_anomaly_for` weiter; M-26 (W4) adressierte main.py-Duplikate; Wrapper in inference_anomaly.py ggf. neues Duplikat · zu verifizieren | `ml-service/src/inference_anomaly.py:48–100` | Code-Qualität |

---

## Offene Findings (nach Wave 10 Runde 1)

| Gruppe | Findings |
|--------|---------|
| **Alle Wellen abgeschlossen** | ✅ H-01–H-17, M-01–M-44 (außer H-07, M-19, M-42), L-01–L-39 (außer L-13, L-21, L-28, L-33), L-59 |
| **Manuell / extern** | ❌ H-07 (Sentry DSN eintragen), M-19 (UptimeRobot einrichten) |
| **Dokumentierte Ausnahmen** | — L-13 (TEST-L2), L-21 (OBS-L2), L-28 (SEC-L1), L-33 (TEST-L3), L-41 (ARCH-L4) |
| **Security — noch offen** | ❌ M-42 (CSP Nonce + strict-dynamic, hoher Aufwand — eigener Wave) |
| **Architektur/Betrieb (Prio 2)** | ❌ M-45 (SIGTERM wait=True) · M-46 (Port 127.0.0.1) · M-48 (Healthcheck /ready) · M-49 (SentryProcessor) · L-40, L-42–43 |
| **Tests (Prio 3)** | ❌ M-53 (fail_under Drift) · M-54 (@requires_data CI) · M-55 (inference_models Tests) · L-47–50 |
| **Code-Qualität (Prio 4)** | ❌ M-50 (energy God-Function) · M-51 (body_battery 60Z) · M-52 (login() 70Z) · L-44–46 · L-57 |
| **Observability (Prio 5)** | ❌ M-47 (Stdlib ProcessorFormatter) · L-52–56 |
| **CI/CD** | ❌ M-56 (Trivy Artefakt) · L-51 |
| **zu verifizieren** | [?] L-58 (Backfill-Duplikat nach H-12) · L-60 (anomaly Wrapper nach M-26) |

---

## DORA-Einschätzung [Schätzung — keine CI-Historie]

| Metrik | Wert | Basis |
|---|---|---|
| Deployment Frequency | [Schätzung] ~16 Merges/Monat | ~79 Merge-Commits seit Jan 2026; PR-Size-Check ≤ 400 LOC |
| Lead Time for Changes | Mittel (~1–4h) | Pipeline ~15 min (Engpass: 3× Docker-Build für Trivy) |
| Change Failure Rate | Nicht messbar | Keine CI-Deployment-Historie |
| Recovery Time | Minuten | Docker-Tag-Rollback; `make dashboard` / `make analytics` |

[Schätzung] Profil entspricht **High Performer** (mehrmals/Woche).

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
- **CSRF**: auf allen mutativen Routen außer `/logout` (M-40) korrekt
- **Prepared Statements**: Alle `api/src/db/`- und `ml-service/src/db/`-Queries parametrisiert

---

## Dokumentierte Ausnahmen

| ID | Beschreibung |
|---|---|
| ARCH-M2 | Kein Service-Layer (Routes → DB direkt) — Solo-Projekt |
| ARCH-M3 | Traefik self-signed TLS — Homelab-Ausnahme |
| ARCH-L2 | Technisch-basierte `db/`-Ordnerstruktur — Solo-Projekt |
| ARCH-L3 | Kein `/api/v1/`-Prefix — keine externen Consumer |
| ARCH-L4 | 3-Service-Splitting bewusst: Scheduling-Isolation, ML-Workload-Trennung, unabhängige Restart-Zyklen, unterschiedliche Memory-Limits (api 512 MB, ml 1 GB). Kein klassisches Microservices-Muster. |
| CICD-M3 | Branch Protection nicht erzwingbar (Free-Plan, privates Repo) |
| CICD-L4 | GitHub-native Secret Scanning nicht verfügbar (Free-Plan) |
| QUAL-M2 | Duplizierter GarminClient in api/ + sync-service/ — bewusst |
| OBS-L1 | Kein externes Uptime-Monitoring — Reminder: UptimeRobot einrichten |
| OBS-L2 | Kein OpenTelemetry — Solo-Homelab; `request_id` als Korrelation ausreichend |
| SEC-L1 | HSTS bei self-signed TLS — Homelab-Ausnahme (ARCH-M3) |
| TEST-L1 | `require_user`-Mock ohne `assert_called_once()` — Tests verifizieren Verhalten |
| TEST-L2 | JS-Coverage auf 4/24 Static-JS-Dateien — DOM-heavy Files via Playwright E2E |
| TEST-L3 | `dashboard-hero.js` bewusst aus Vitest `coverage.include` ausgeschlossen — `heroRecommendation()` hat Unit-Tests; DOM-schwere Funktionen (`buildHeroCard`, `buildMlTabs`) via Playwright E2E; Coverage-Merge Unit+E2E mit Python-Playwright-Stack nicht praktikabel |
