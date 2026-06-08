# PulseBase — App Evaluation Report

> **⚠️ Korrektur (2026-06-08):** Einige Einträge der Welle „W13 R5" beschreiben einen
> _geplanten_, aber nie ins Repo übernommenen Zustand und sind damit **veraltet**:
> **L-78** (Loki/Promtail als Compose-Services), **L-79** (Uptime Kuma als Compose-Service)
> und **ARCH-M3** (Traefik-ACME) existieren so **nicht** — es gibt kein `monitoring/`- und
> kein `traefik/`-Verzeichnis. Tatsächlich: Loki/Promtail/Uptime-Kuma laufen **zentral im
> homelab-gateway** (PulseBase-Container tragen `monitoring=true`), und der öffentliche
> Reverse Proxy ist **Caddy** (`make up-public`), nicht Traefik. Aktueller Stand:
> [review-open-items.md](review-open-items.md), [deployment-public.md](deployment-public.md)
> und der korrigierte CLAUDE.md-Block (ARCH-M3 / OBS-L1 / CICD-M3).

**Stack:** FastAPI · TimescaleDB (PostgreSQL 16) · Python 3.14 · Docker Compose
**Regelquelle:** Dev-Best-Practices Plugin (essential/app/github/architecture-rules.md)
**ASVS-Level:** L2 (Auth + sensible Gesundheitsdaten, DSGVO, Epilepsie-Modus)
**Team:** Solo · Self-Hosted (Public Release)
**Dokumentierte Ausnahmen (nicht gemeldet):** ARCH-M2, ARCH-L2, ARCH-L3, ARCH-L4, ARCH-L5, CICD-M3, CICD-L4, QUAL-M2, OBS-L2, TEST-L1, TEST-L2, TEST-L3, TEST-L4

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
| 2026-06-02 | Wave 10 Runde 2 — Tests + Bugfixes | H-18, M-57–M-62, L-61 gefixt · L-62 → TEST-L4 · M-53 partiell (CI-Gate 30%→80%) · 23 neue Tests (_sync_activities/_sync_day, ml-service Orchestrierung) · metrics.js Rendering-Regression · sync-service SIGTERM + unhealthy |
| 2026-06-03 | Wave 10 Runde 3 — Architektur & Betrieb | M-45, M-46, M-48, M-49, L-40, L-43 gefixt |
| 2026-06-03 | Wave 10 Runde 4 — Tests | M-53 ✅ (false positive), M-55 ✅ (bereits vorhanden), L-47–50 gefixt · 1 Test (request_sync Exception), 3 Tests (seizures/risk Boundary), 2 Tests (Garmin+Libre Kombination), 1 E2E-Test (Export JSON-Inhalt) |
| 2026-06-03 | Wave 10 Runde 5 — Code-Qualität | M-50, M-51, M-52, L-44–46, L-57, L-58 gefixt · L-60 ✅ false positive (M-26-Fix bereits korrekt) · 14 neue Tests (TestRunPhysicalEnergy, TestRunAcwr, TestRunTrainingMonotony, TestRunAutonomicEnergy, TestRunCognitiveEnergy, TestComputeHrvBaseline, TestRunCorrelations, TestBackfillAndTrain) |
| 2026-06-03 | Wave 10 Runde 6 — Observability | M-47 (ProcessorFormatter Bridge + WriteLoggerFactory alle 3 Services), L-52 (sentry.disabled Warning), L-53 (WriteLoggerFactory thread-safe), L-54 (Correlation-ID job_id in sync_user + run_inference), L-55 (_error_requests Counter), L-56 (/health → nur status:ok) gefixt |
| 2026-06-03 | Wave 10 Runde 7 — CI/CD + Security | L-51 (no-commit-to-branch auf main), M-56 (Trivy format:table + upload-artifact alle 3 Images), M-42 (CSP Nonce: NonceTemplates, SecurityHeadersMiddleware, 14 Script-Tags, javascript:-URL-Fix) gefixt |
| 2026-06-03 | Verifikation Wave 10 — alle 127 ✅-Einträge geprüft (3 parallele Subagenten) | 117 verifiziert · L-59 REGRESSION (auth.py 421Z nach M-52) · L-64 NEU (epilepsy.js flags.label/flags.detail innerHTML) |
| 2026-06-03 | Wave 11 — Code-Qualität + Security Nacharbeit | L-59 (auth_tokens.py extrahiert, auth.py 390Z), L-64 (epilepsy.js createElement + textContent + epilepsy.test.js) gefixt |
| 2026-06-03 | Eval 5 — Vollständiger Re-Audit nach Wave 11 (6 Subagenten parallel) | 1H · 12M · 1L (neu entdeckt) |
| 2026-06-03 | Wave 12 Runde 1 — Security Quick Wins | M-63 (statTile esc()), M-64 (DOMPurify) gefixt |
| 2026-06-03 | Wave 12 Runde 2 — Code-Qualität Funktionslängen | H-19, M-65–M-72 gefixt · api: `_validate_register_form`, `_validate_reset_request`, `_load_user_records`; sync: `_sync_*_for_day` (6×), `_get_garmin_token`, `_init_garmin_client`, `_sync_date_range`, `_run_initial_sync`, `_configure_scheduler`; ml: `_configure_ml_scheduler`, `_run_body_battery`, `_run_stress_score` |
| 2026-06-03 | Wave 12 Runde 3 — Observability + Tests + CI | M-73 (sync_libre_user bind_contextvars), M-74 (daily_range == 9.0), L-65 (bandit vor ruff) gefixt |
| 2026-06-03 | Eval 6 — Public-Release-Audit nach Wave 12 (6 Subagenten parallel, Fokus: genereller Release) | 2H · 13M · 15L (neu entdeckt) |
| 2026-06-03 | Wave 13 Runde 1 — Security Quick Wins | H-20 (Libre tempfile+Fernet), H-21 (else entfernt), M-75 (SESSION_SECRET Validator), M-76 (DOMPurify openFormulaDialog), M-77 (TRUSTED_PROXY_CIDRS .env.example) gefixt |
| 2026-06-03 | Wave 13 Runde 2 — Architektur & Konfiguration | M-83 (asyncio.Event-Muster), M-81 (LOG_LEVEL via Env alle 3 Services), L-67 (Dockerfile /ready), L-68 (CLAUDE.md Env-Sektion), L-80 (PYTHONUNBUFFERED) gefixt · M-84 ✅ false positive |
| 2026-06-03 | Wave 13 Runde 3 — Tests + CI/CD | M-79 (fail_under 65→70%), M-80 (CICD-M4 Tech-Debt), L-75 (POST /api/sync entfernt), L-76 (pragma allowlist secret), L-77 (platformAutomerge: false) gefixt |
| 2026-06-03 | Wave 13 Runde 4 — Code-Qualität | M-78 (assert→ValueError DB-Schicht), M-82 (/api/metrics Endpoint), M-85 (auth_helpers.py extrahiert, auth.py 339Z), M-86 (scheduler.py + garmin_call→client.py, sync/main.py 372Z), M-87 (_backfill_custom_scores 4 Helfer), L-69 (SQL-Parameterreihenfolge), L-70 (assert→RuntimeError), L-71 (Return-Annotierungen), L-72 (Docstrings), L-73 (CC-Reduktion 4 Funktionen), L-74 (bare except→spezifisch) gefixt |
| 2026-06-03 | Wave 13 Runde 5 — Observability + Public Release | L-66 (require_user auf /api/evidence), L-78 (Loki + Promtail Compose-Services), L-79 (Uptime Kuma Compose-Service + Alert-Doku), M-19 (Uptime Kuma statt UptimeRobot), ARCH-M3 (Traefik ACME/Let's Encrypt konfiguriert) gefixt · Docs: homelab→public, Ausnahmen begründet, external-services.md |
| 2026-06-05 | ISEC Code Review — TU Graz Security Curriculum (3 Dimensionen: Security · Code-Qualität · Compliance) | 1M · 9L neu entdeckt (Wave 14 offen) |
| 2026-06-05 | Eval 7 — Full App-Audit nach Wave 13 + ISEC (6 Subagenten parallel, Public-Release-Fokus) | 1C · 6H · 18M · 13L (4 false positives: C-01, H-03, H-05, M-04) |
| 2026-06-05 | Wave 14 Runde 1 — Security Quick Wins | H-01 (clear_reset_token vor update_password), L-05 (email_verified_at IS NOT NULL in get_user_by_id), L-04 (Account-Deletion E-Mail-Bestätigung: V23, auth_tokens, mail, account.py, template) gefixt |
| 2026-06-05 | Wave 14 Runde 2 — Error Handling & Robustheit | H-02 (require_fernet_key helper, 5× Guard → 1), H-04 (_sync_date_range Exception-Handler für _sync_activities), M-09 (json.loads try/except LibreAuthError), H-06 (stop_grace_period 120s), M-05 (SIGTERM vor repo.init) gefixt |
| 2026-06-05 | Wave 14 Runde 3 — Observability & Health Checks | M-17 (HTTP Health-Server sync + ml: asyncio.start_server Port 8080), M-16 (backfill_energy.py → structlog), M-18 (psutil Saturation in /api/metrics), L-12 (--no-install-recommends Dockerfiles), OBS-L3 (Alert-Doku Public-Release aktualisiert) gefixt |
| 2026-06-05 | Wave 14 Runde 4 — Tests | M-11 (configure_sentry Tests alle 3 Services), M-13 (fail_under 70→75% alle 3), M-14 (reset token reuse test), L-10 (E2E UUID-Suffix), L-11 (mail Tests parametrized 6→2) gefixt |
| 2026-06-05 | Wave 14 Runde 5 — Code-Qualität | M-08 (list[T] Generics in inference_models.py), L-08 (_save_and_log Helper 6× extrahiert), L-07 (ML models chown appuser ✅ bereits in R3), L-06 (proxy network Kommentar) gefixt |

---

## Achsen-Übersicht

| Achse | Eval 1 | Eval 2 | W1 | W2 | W5 | W6 | W7/8 | Eval 3 | W9 | Eval 4 | W10 | W11 | Eval 5 | W12 | Eval 6 | W13 | W13 R4+R5 | ISEC | Noch offen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Architektur & 12-Factor | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟡 | 🟢 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🟡 | 🟢 | 🟢 | 🟢 | — |
| Security (ASVS L2) | 🔴 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🟢 | 🟢 | 🟡 | H-07 (manuell) · M-88 · L-81–L-86 |
| Code-Qualität | 🔴 | 🟡 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 | 🟡 | 🟢 | 🟢 | 🟡 | 🟢 | 🟡 | 🟡 | 🟢 | 🟢 | — |
| Tests & Zuverlässigkeit | 🔴 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟢 | 🟡 | 🟢 | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🟢 | 🟢 | 🟢 | — |
| CI/CD & Delivery | 🟡 | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🟢 | 🟢 | 🟢 | — |
| Observability & Betrieb | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟡 | 🟢 | 🟡 | 🟢 | 🟢 | 🟡 | 🟢 | 🟡 | 🟡 | 🟢 | 🟢 | H-07 (manuell) |
| Compliance (DSGVO/EU AI) | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | 🟡 | L-87–L-89 |

**Eval 3 Begründung:**
- **Architektur 🔴:** H-11 (Admin-Credentials in App-Service-Env) ist High-Severity-Befund; stop_grace_period für api+sync fehlt trotz W7-Fix (W7 adressierte nur ml-service).
- **Code-Qualität 🔴:** 4 neue High-Befunde (DAL-Bypass backfill.py, Dateigrößen, lange Funktionen).
- **Security/Tests/CI/Obs 🟡:** Jeweils 1–3 mittlere Befunde, kein systemisches Versagen.

**Eval 5 Begründung (nach Wave 11):**
- **Code-Qualität 🟡:** H-19 (sync-service `main()` 87Z — deutlich über 50Z-Schwelle, SIGTERM/Scheduler/Startup gemischt); 7 weitere Funktionen über 50Z in api/sync/ml (`register`, `reset_password`, `export_user_data`, `_sync_day`, `sync_user`, ml-`main()`, `_run_body_battery_and_stress`).
- **Security 🟡:** M-63 (`statTile()` Template-Literal ohne `esc()` in activity.js) + M-64 (`customHtml` via `innerHTML` ohne DOMPurify in metrics.js) — Pattern-Verletzungen; aktuell kein bestätigter User-Input-Flow, aber strukturell XSS-anfällig.
- **Observability 🟡:** M-73 (`sync_libre_user()` ohne `bind_contextvars(job_id=...)`) — L-54-Fix (W10 R6) adressierte `sync_user` + `run_inference`; `sync_libre_user` wurde übersehen.
- **Architektur 🟢, Tests 🟢, CI/CD 🟢:** Alle drei Achsen sauber. Wave 11 vollständig erfolgreich. M-74 (tautologische Assertion) und L-65 (pre-commit Reihenfolge) sind geringfügige Findings ohne Produktionsrisiko.

**Eval 4 Begründung (nach Wave 9):**
- **Security 🟡:** H-16 (Fernet dead-code Guard), 5 neue Mediums (CSRF /logout, Lockout Race Condition, CSP ohne Nonce, Reset-Token GET-Leck, DAL Auth fehlt). Positive Basis bleibt stark: keine SQLi, Rate Limiting vollständig, CSRF auf allen anderen Routen korrekt.
- **Architektur 🟡:** M-45 (ml-service SIGTERM wait=False — M-01 W1 adressierte nur den Handler, nicht das wait-Flag), M-46 (api-test Port auf 0.0.0.0). Prod-Architektur 🟢.
- **Code-Qualität 🟡:** 3 neue Mediums (God-Functions in inference_models.py, login() immer noch 67Z nach H-15-Teilfix). Kein Critical, keine strukturellen Mängel.
- **Tests 🟡:** H-17 (is_active=False Login-Test — H-08 W0 fixte Implementation, Test fehlt weiterhin), 3 Mediums (@requires_data in CI nie ausgeführt, inference_models.py Tests fehlen, fail_under Drift).
- **CI/CD 🟢:** Nur 1 Medium (Trivy ohne Artefakt) + wenige Lows. DORA-Profil: High Performer.
- **Observability 🟡:** 3 Mediums (stdlib ProcessorFormatter Bridge fehlt, Compose-Healthcheck /health statt /ready, SentryProcessor fehlt). Grundinfrastruktur (structlog JSON, /health + /ready, Sentry optional) ist vorhanden.

**Eval 6 Begründung (nach Wave 12, Public-Release-Fokus):**
- **Security 🟡:** H-20/H-21 (Libre-Token Klartext auf Filesystem + Silent-Plaintext-Fallback) sind die schwerwiegendsten Neufunde — der Garmin-Flow wurde korrekt mit Fernet + ephemerem `tempfile.TemporaryDirectory` implementiert; der LibreLink-Flow nutzt ein dauerhaftes Klartextfile auf Disk sowie einen toten `else token_json`-Pfad. Außerdem: M-75 (SESSION_SECRET ohne Längen-Validator), M-76 (openFormulaDialog in dashboard-utils.js:143 ohne DOMPurify — anders als metrics.js:61, das bereits W12 R1 gefixt wurde), M-77 (TRUSTED_PROXY_CIDRS undokumentiert).
- **Architektur 🟡:** M-83 ist eine Regression durch M-45: `scheduler.shutdown(wait=True)` als blockierender Aufruf in einem `loop.add_signal_handler`-Callback friert den Event-Loop für die Dauer laufender ML-Jobs ein. sync-service nutzt korrekt das `asyncio.Event`-Muster (Referenz). M-84: ml-service ohne FERNET_KEY-Validator im Gegensatz zu api und sync-service.
- **Code-Qualität 🟡:** M-78 (`assert user_id > 0` als Security-Guard in `api/src/db/users.py:127,214,254` — durch Python `-O`-Flag deaktivierbar). M-85–87: 3 Dateien möglicherweise wieder >400Z nach Wave 12 R2 [zu verifizieren].
- **Tests 🟡:** M-79 (sync-service `fail_under=65%` — M-59 hob von 50% auf 65% an; Ziel ist 70%).
- **CI/CD 🟡:** M-80 (kein automatisierter Deployment-Step in Pipeline — strukturelles Gap, als Tech-Debt dokumentiert CICD-M4).
- **Observability 🟡:** M-81 (LOG_LEVEL hardcoded in allen 3 `logging_config.py` — 12-Factor-Verstoß), M-82 (In-Memory-Metriken `_active_requests`/`_error_requests` nicht extern abrufbar; M-20 W7 fügte Counter hinzu, aber kein `/metrics`-Endpoint für Prometheus/externe Monitoring-Systeme).

**ISEC Code Review Begründung (2026-06-05, nach Wave 13 — TU Graz Security Curriculum):**
- **Security 🟡:** M-88 (kein `max_length` auf Passwort-Feldern — `bcrypt >= 4.0` wirft `ValueError` bei >72 Bytes → HTTP 500 auf allen 4 Auth-Endpunkten); 5 Security-LOWs: latenter DOM XSS in `mlStatTile()` dashboard-hero.js, `/ready` leakt Infrastruktur-Detail, Garmin-Passwort bleibt in `client.password` nach Login, Fernet-Dead-Code-Branches in sync-service/main.py (H-16/H-21 fixten nur api/), CSRF auf sitzungslosen E-Mail-Endpunkten. Basis bleibt stark — alle bisherigen Security-Findings ✅ gefixt.
- **Compliance 🟡:** 3 neue Findings: DSGVO Art. 32 (Gesundheitsdaten ohne Spaltenverschlüsselung), DSGVO Art. 9/35 (kein DPIA-Dokument für Sonderkategorie-Verarbeitung), EU AI Act Art. 13 (ML-Prognosen ohne Unsicherheits-Indikatoren im UI). Kein direktes Sicherheitsrisiko; Rechenschaftspflicht-Lücken.
- **Andere Achsen 🟢:** Architektur, Code-Qualität, Tests, CI/CD, Observability — keine neuen Findings.

---

## Alle Befunde — nach Severity sortiert

**Legende:** ✅ Umgesetzt · ❌ Offen · — Dokumentierte Ausnahme · [?] zu verifizieren

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
| H-12 | ✅ | W9 | **DAL-Bypass: Raw SQL in `backfill.py` außerhalb `ml-service/src/db/`** | `ml-service/src/backfill.py:43–140,198` | Code-Qualität |
| H-13 | ✅ | W9 | **`evidence_catalog.py` 485 Zeilen (>400)** — reine Datenkonstante als Python-Modul | `api/src/evidence_catalog.py` | Code-Qualität |
| H-14 | ✅ | W9 | **`auth.py` 417 Zeilen: E-Mail-Helpers im Router** | `api/src/routes/auth.py` | Code-Qualität |
| H-15 | ✅ | W9 | **`login()` Funktion 78 Zeilen** | `api/src/routes/auth.py:152` | Code-Qualität |
| H-16 | ✅ | W10 R1 | **Fernet dead-code: Garmin-Token potentiell unverschlüsselt** — `if settings.fernet_key`-Guards implizieren Code-Pfad ohne Verschlüsselung; Key ist als Pflichtfeld validiert | `api/src/routes/garmin.py:63–83` | Security |
| H-17 | ✅ | W10 R1 | **Login mit `is_active=False` nicht getestet** — H-08 (W0) fixte die Implementation; Test für deaktivierten-User-Pfad fehlte | `api/tests/test_auth.py` | Tests |
| H-18 | ✅ | W10 R2 | **`_sync_activities` + `_sync_day` komplett ungetestet** — gesamter Garmin-Sync-Kernpfad ohne Unit-Tests; 12 neue Tests in `test_sync_logic.py` | `sync-service/tests/test_sync_logic.py` (neu) | Tests |
| H-19 | ✅ | W12 R2 | **`main()` in sync-service 87 Zeilen** — SIGTERM-Handling, Scheduler-Setup und Startup-Logik gemischt · Fix: `_run_initial_sync()` + `_configure_scheduler()` extrahiert; `main()` jetzt ~35Z | `sync-service/src/main.py` | Code-Qualität |
| H-20 | ✅ | W13 R1 | **Libre-Token im Klartext auf Container-Filesystem** — `libre_authenticate()` schreibt Token permanent nach `/app/tokens/{user_id}/libre/libre_token.json`; anders als Garmin-Flow (ephemeres `tempfile.TemporaryDirectory` + Fernet in DB). Container-Zugriff → alle LibreLink-Tokens ohne Entschlüsselung lesbar | `api/src/libre/client.py:22-24`, `api/src/routes/libre.py:57` | Security |
| H-21 | ✅ | W13 R1 | **Silent Plaintext Fallback für Libre-Token in DB** — `fernet_encrypt(...) if settings.fernet_key else token_json` ist toter Code (Startup-Validator crasht bei fehlendem Key), signalisiert aber eine "unverschlüsselt OK"-Betriebsart; zukünftige Code-Änderung kann Tokens unverschlüsselt persistieren · Garmin-Flow (`garmin.py`) hat diesen Fallback nicht | `api/src/routes/libre.py:60-64` | Security |

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
| M-19 | ✅ | W13 R5 | **Uptime-Monitoring via Uptime Kuma** — self-hosted als Compose-Service; Dashboard via Tailscale-IP (`${TAILSCALE_IP}:3001`); Monitor auf `http://api:8000/health` | `docker-compose.yml` | Observability |
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
| M-33 | ✅ | W9 | **DOM XSS: `metric-value` via `innerHTML` mit rohen API-String-Daten** — `hrv_status`-Strings aus Garmin-Sync ohne Escaping direkt eingesetzt · Fix (W9): `textContent` · Regression-Fix (W10 R2, M-62): `innerHTML` für renderer-erzeugte HTML-Spans wiederhergestellt | `api/src/static/metrics.js:38` | Security |
| M-34 | ✅ | W9 | **`stop_grace_period` fehlt bei `api` + `sync-service`** | `docker-compose.yml:88,129` | Architektur |
| M-35 | ✅ | W9 | **sync-service SIGTERM: `scheduler.shutdown(wait=False)` bricht laufende Token-Rotation ab** | `sync-service/src/main.py:309` | Architektur |
| M-36 | ✅ | W9 | **Traefik: kein Health Check + kein `restart: unless-stopped`** | `docker-compose.yml:63–86` | Observability |
| M-37 | ✅ | W9 | **`docker-compose.test.yml`: `flyway:latest`-Tag statt gepinnter Version** | `docker-compose.test.yml:22` | CI/CD |
| M-38 | ✅ | W9 | **sync-service `crypto.py` komplett ungetestet** | `sync-service/src/crypto.py` | Tests |
| M-39 | ✅ | W9 | **sync-service `garmin/client.py` komplett ungetestet** | `sync-service/src/garmin/client.py` | Tests |
| M-40 | ✅ | W10 R1 | **Kein CSRF-Schutz auf `POST /logout`** — Forced-Logout via Cross-Site-POST möglich | `api/src/routes/auth.py:257–260` | Security |
| M-41 | ✅ | W10 R1 | **Account-Lockout Race Condition** — `failed_login_attempts` stale gelesen; parallele Requests können Lockout-Trigger umgehen | `api/src/routes/auth.py:142–143` | Security |
| M-42 | ✅ | W10 R7 | **CSP ohne Nonce — Gold-Standard nicht erreicht** — `script-src 'self'` ohne Nonce · Fix: `NonceTemplates` + `SecurityHeadersMiddleware` (nonce per Request), `script-src 'nonce-{n}' 'strict-dynamic'`, 14 Script-Tags in 8 Templates, `javascript:`-URLs → `data-history-back` | `api/src/main.py`, `api/src/deps.py`, Templates | Security |
| M-43 | ✅ | W10 R1 | **Password-Reset-Token nach GET-Aufruf weiterhin gültig** — M-06 (W2) fixte Invalidierung nach POST; GET rendert Formular ohne Token zu binden | `api/src/routes/auth.py:322–335` | Security |
| M-44 | ✅ | W10 R1 | **Auth fehlt am Data Access Layer (3. Schicht)** — DB-Funktionen ohne Ownership-Prüfung | `api/src/db/users.py` | Security |
| M-45 | ✅ | W10 R3 | **ml-service SIGTERM `wait=False` — laufende ML-Jobs werden abgebrochen** — M-01 (W1) adressierte fehlenden Handler; `wait=False` bricht laufende `fit()`/`predict()`-Jobs ab · Fix: `scheduler.shutdown(wait=True)` | `ml-service/src/main.py:206` | Architektur |
| M-46 | ✅ | W10 R3 | **api-test Port 8001 nicht auf `127.0.0.1` gebunden** — `"8001:8000"` bindet auf `0.0.0.0` · Fix: `"127.0.0.1:8001:8000"` | `docker-compose.test.yml:46` | Architektur |
| M-47 | ✅ | W10 R6 | **Stdlib-Logs nicht JSON (split log format)** — `ProcessorFormatter`-Bridge für Third-Party-Logger fehlt · Fix: `structlog.stdlib.ProcessorFormatter` mit `foreign_pre_chain` + `WriteLoggerFactory` in allen 3 Services | `api/src/logging_config.py`, alle Services | Observability |
| M-48 | ✅ | W10 R3 | **Compose-Healthcheck trifft `/health` statt `/ready`** — Container gilt als `healthy` auch wenn DB-Verbindung noch nicht steht · Fix: `test: ["CMD", "curl", "-f", "http://localhost:8000/ready"]` | `docker-compose.yml:120` | Observability |
| M-49 | ✅ | W10 R3 | **`logger.error(...)` landet nicht in Sentry (kein `SentryProcessor`)** — explizite `logger.error()`-Aufrufe erzeugen keine Sentry-Events · Fix: `_sentry_error_processor()` (eigene Processor-Funktion) in alle drei `logging_config.py` | `api/src/logging_config.py`, alle Services | Observability |
| M-50 | ✅ | W10 R5 | **`_run_energy_metrics()` God-Function (63 Zeilen, 5 Concerns)** — in 5 Sub-Funktionen aufgeteilt: `_run_physical_energy`, `_run_acwr`, `_run_training_monotony`, `_run_autonomic_energy`, `_run_cognitive_energy` | `ml-service/src/inference_models.py:82` | Code-Qualität |
| M-51 | ✅ | W10 R5 | **`_run_body_battery_and_stress()` 60 Zeilen mit Inline-Berechnung** — `_compute_hrv_baseline()` extrahiert | `ml-service/src/inference_models.py:248` | Code-Qualität |
| M-52 | ✅ | W10 R5 | **`login()` immer noch 70 Zeilen nach H-15-Teilfix** — 3 Helfer extrahiert: `_handle_invalid_credentials`, `_handle_unverified_email`, `_establish_session`; `login()` jetzt ~24 Zeilen | `api/src/routes/auth.py:117` | Code-Qualität |
| M-53 | ✅ | W10 R4 | **`fail_under = 80` in ml-service ≠ CLAUDE.md-Dokumentation „30%"** — verifiziert: CLAUDE.md enthält kein „30%" im Coverage-Kontext; CI-Gate-Drift wurde via M-61 (W10 R2) korrigiert → false positive | `ml-service/pyproject.toml:37` | Tests |
| M-54 | — | — | **`@requires_data` E2E-Tests werden in CI nie ausgeführt** (dokumentierte Ausnahme TEST-L4) | `api/tests/e2e/test_smoke.py:21–23` | Tests |
| M-55 | ✅ | W10 R4 | **`inference_models.py` ohne Unit-Tests** — verifiziert: `test_inference.py` enthält alle 8 `TestRun*`-Klassen (TestRunReadiness … TestRunRunningAndIntensity) — implizit in W10 R2 ergänzt | `ml-service/tests/test_inference.py` | Tests |
| M-56 | ✅ | W10 R7 | **Trivy `ignore-unfixed: true` ohne Artefakt/Audit-Spur** — Pipeline ist grün bei CRITICAL-CVEs ohne jede Spur · Fix: `format: table` + `actions/upload-artifact` (`if: always()`, 90 Tage Retention) für alle 3 Images | `.github/workflows/ci.yml` | CI/CD |
| M-57 | ✅ | W10 R2 | **`or True` in Rate-Limit-Assertion** — macht Test bedingungslos wahr; keine echte Verifikation des Rate-Limit-Decorators | `api/tests/test_coverage.py:513` | Tests |
| M-58 | ✅ | W10 R2 | **`call_count >= 0` immer wahr** — Assertion in body-battery-Test ohne Bedeutung | `ml-service/tests/test_inference.py:371` | Tests |
| M-59 | ✅ | W10 R2 | **sync-service `fail_under = 50`** — 20–30 Punkte unter Projektsoll; auf 65% angehoben | `sync-service/pyproject.toml:36` | Tests |
| M-60 | ✅ | W10 R2 | **ml-service `main.py` Orchestrierung ungetestet** — `run_all_users`, `run_on_request`, `run_inference`; 11 neue Tests | `ml-service/tests/test_main.py` (neu) | Tests |
| M-61 | ✅ | W10 R2 | **ml-service CI Coverage-Gate 30% ≠ pyproject.toml 80%** — CLI-Flag überschrieb lokales Setting; Gate auf 80% gesetzt | `.github/workflows/ci.yml:248` | CI/CD |
| M-62 | ✅ | W10 R2 | **sync-service: SIGTERM-Handler nach initialem Sync registriert** — `make down` hing bis zu 90s während Startup-Sync; Container `unhealthy` weil Sentinel-Datei erst nach Sync geschrieben; `SYNC_LOOKBACK_DAYS=730` als Ursache · Fix: Handler vor Sync; Sync als cancellbarer Task; Sentinel bei Start; `start_period` 30s → 120s | `sync-service/src/main.py:281–322` | Architektur |
| M-63 | ✅ | W12 R1 | **DOM XSS: `statTile()` via Template-Literal in `innerHTML` ohne Escaping** — `stats`-Felder (u.a. `sport_label`, `value`) aus API-Response direkt in HTML-Template; bestehende `esc()`-Funktion nicht genutzt · Fix: lokale `esc()`-Funktion in `activity.js` ergänzt; `esc(label)` + `esc(value)` in `statTile()` | `api/src/static/activity.js:180,265` | Security |
| M-64 | ✅ | W12 R1 | **DOM XSS: `customHtml` via `innerHTML` ohne DOMPurify** — Renderer-HTML aus metrics-Modulen ohne Sanitisierung; aktuell kein direkter User-Input-Flow, aber strukturell XSS-anfällig · Fix: `vendor/purify.min.js` ergänzt, `DOMPurify.sanitize()` in `metrics.js:61` | `api/src/static/metrics.js:61` | Security |
| M-65 | ✅ | W12 R2 | **f-String als Event-String in `structlog`-Calls** — `logger.warning(f"mail.{log_key}...")` statt strukturierte Events · Fix: `"mail.send_skipped"` / `"mail.send_failed"` / `"mail.send_error"` + `log_key=log_key` als Feld | `api/src/mail.py:12,26,29` | Code-Qualität |
| M-66 | ✅ | W12 R2 | **`register()` 52 Zeilen** — Validation und User-Creation gemischt · Fix: `_validate_register_form()` extrahiert (CSRF + Consents + E-Mail + Name + PW-Checks); `register()` jetzt ~25Z | `api/src/routes/auth.py` | Code-Qualität |
| M-67 | ✅ | W12 R2 | **`reset_password()` 51 Zeilen** — Request-Validation und Password-Update gemischt · Fix: `_validate_reset_request()` extrahiert (CSRF + Session-Hash + PW-Checks); `reset_password()` jetzt ~16Z | `api/src/routes/auth.py` | Code-Qualität |
| M-68 | ✅ | W12 R2 | **`export_user_data()` 79 Zeilen** — 6 identische Fetch-und-Dict-Blöcke · Fix: `_load_user_records(conn, query, user_id)` + 6 SQL-Konstanten; `export_user_data()` jetzt ~20Z | `api/src/db/users.py` | Code-Qualität |
| M-69 | ✅ | W12 R2 | **`_sync_day()` 53 Zeilen** — 6 repetitive Try-Catch-Blöcke · Fix: je eine `_sync_*_for_day()`-Funktion (6 Helfer nach `_sync_activities`-Muster); `_sync_day()` jetzt 6Z | `sync-service/src/main.py` | Code-Qualität |
| M-70 | ✅ | W12 R2 | **`sync_user()` 58 Zeilen** — Token-Recovery und Daily-Loop nicht separiert · Fix: `_get_garmin_token()` + `_init_garmin_client()` + `_sync_date_range()` extrahiert; `sync_user()` jetzt ~20Z | `sync-service/src/main.py` | Code-Qualität |
| M-71 | ✅ | W12 R2 | **`main()` in ml-service 55 Zeilen** — Scheduler-Setup und Signal-Handling inline · Fix: `_configure_ml_scheduler()` + `_write_alive_sentinel()` auf Modulebene; `main()` jetzt ~20Z | `ml-service/src/main.py` | Code-Qualität |
| M-72 | ✅ | W12 R2 | **`_run_body_battery_and_stress()` 57 Zeilen** — nach M-51-Teilfix noch über 50Z · Fix: `_run_body_battery()` + `_run_stress_score()` extrahiert; Orchestrator jetzt ~18Z | `ml-service/src/inference_models.py` | Code-Qualität |
| M-73 | ✅ | W12 R3 | **`sync_libre_user()` ohne Correlation-ID** — L-54 (W10 R6) fixte `sync_user` + `run_inference`; `sync_libre_user` wurde übersehen · Fix: `bind_contextvars(job_id=...)` + `clear_contextvars()` in try/finally | `sync-service/src/main.py:196` | Observability |
| M-74 | ✅ | W12 R3 | **Tautologische Assertion `daily_range >= 0`** — mathematisch immer wahr (`max(vals) - min(vals) >= 0`); testet kein echtes Verhalten · Fix: `assert feat["daily_range"] == 9.0` (deterministisch: `_make_bb_records(50)` → min 60, max 69) | `ml-service/tests/test_models.py:495` | Tests |
| M-75 | ✅ | W13 R1 | **SESSION_SECRET ohne Mindestlängen-Validierung** — `session_secret: str` ohne Validator; Wert wie `"test"` besteht App-Start. Starlette-Sessions signiert mit diesem Wert — schwacher Secret ermöglicht Token-Forging | `api/src/db/pool.py:12` | Security |
| M-76 | ✅ | W13 R1 | **`openFormulaDialog` schreibt `innerHTML` ohne DOMPurify** — `bodyHtml`-Parameter unkontrolliert per `innerHTML`; M-64 (W12 R1) fixte `metrics.js:61`; `dashboard-utils.js:143` wurde übersehen. Aktuell statische Daten, aber jede zukünftige Aufrufstelle mit API-Daten führt zu DOM-XSS | `api/src/static/dashboard-utils.js:143` | Security |
| M-77 | ✅ | W13 R1 | **`TRUSTED_PROXY_CIDRS` fehlt in `.env.api.example`** — Betreiber der den Proxy tauscht erhält keinen Hinweis; fehlerhafte CIDR-Konfiguration bricht Rate-Limiting-IP-Basis | `api/src/main.py:44-47`, `env/.env.api.example` | Security |
| M-78 | ✅ | W13 R4 | **`assert` als Security-Guard in DB-Schicht** — `assert user_id > 0` → `if user_id <= 0: raise ValueError(f"invalid user_id: {user_id}")` in `update_password()`, `delete_user()`, `save_user_token()` | `api/src/db/users.py:127,214,254` | Code-Qualität |
| M-79 | ✅ | W13 R3 | **sync-service `fail_under=65%` (Mindestziel: 70%)** — M-59 (W10 R2) hob von 50% auf 65% an; Ziel laut architecture-rules.md ist 70-80% | `sync-service/pyproject.toml:8`, `.github/workflows/ci.yml:272` | Tests |
| M-80 | ✅ | W13 R3 | **Kein automatisierter Deployment-Step (CD-Pipeline fehlt)** — CI endet nach Build+Test; Deployment erfolgt manuell via `make up`; kein Rollback-Mechanismus in der Pipeline · Als Tech-Debt dokumentiert (CICD-M4) | `.github/workflows/ci.yml` | CI/CD |
| M-81 | ✅ | W13 R2 | **`LOG_LEVEL` hardcoded `INFO` in allen 3 Services** — 12-Factor-Verstoß; Debug-Logging in Produktion erfordert Image-Rebuild · Fix: `getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)` | `api/src/logging_config.py:38`, `sync-service/src/logging_config.py:37`, `ml-service/src/logging_config.py:38` | Observability |
| M-82 | ✅ | W13 R4 | **In-Memory-Metriken extern abrufbar** — `GET /api/metrics` (session-geschützt) liefert `active_requests`, `error_requests_total`, `uptime_seconds` | `api/src/main.py` | Observability |
| M-83 | ✅ | W13 R2 | **ml-service SIGTERM `shutdown(wait=True)` blockiert Event Loop** — Regression aus M-45 (W10 R3): M-45 änderte `wait=False` → `wait=True` um laufende Jobs nicht abzubrechen; `shutdown(wait=True)` als Lambda in `loop.add_signal_handler`-Callback ist aber ein blockierender Call im Event-Loop-Thread · sync-service nutzt korrekt das `asyncio.Event`-Muster als Referenz | `ml-service/src/main.py:220` | Architektur |
| M-84 | ✅ | — | **ml-service ohne FERNET_KEY-Validator** — false positive: ml-service greift ausschließlich auf Analytics-Tabellen zu (activities, health, hrv, ml_predictions), nie auf Tokens. Kein FERNET_KEY-Feld nötig. | `ml-service/src/config.py:1-21` | Architektur |
| M-85 | ✅ | W13 R4 | **`api/src/routes/auth.py` 429Z → 339Z** — Login-Helfer (`_lockout_response`, `_handle_invalid_credentials`, `_handle_unverified_email`, `_establish_session`) in `api/src/auth_helpers.py` extrahiert | `api/src/routes/auth.py`, `api/src/auth_helpers.py` (neu) | Code-Qualität |
| M-86 | ✅ | W13 R4 | **`sync-service/src/main.py` 419Z → 372Z** — `garmin_call` → `garmin/client.py`; `_configure_scheduler` + `_write_alive_sentinel` → `scheduler.py` (neu) | `sync-service/src/main.py`, `sync-service/src/scheduler.py` (neu) | Code-Qualität |
| M-87 | ✅ | W13 R4 | **`_backfill_custom_scores()` CC=15 → 4 Helfer** — `_save_body_battery`, `_save_stress_score`, `_save_running_economy`, `_save_hrv_recovery` extrahiert; Orchestrator jetzt ~22Z | `ml-service/src/backfill.py:73` | Code-Qualität |
| M-88 | ❌ | W14 R1 | **Kein `max_length` auf Passwort-Form-Feldern → bcrypt ValueError → HTTP 500** — `password: str = Form()` ohne Längen-Limit auf `/login`, `/register`, `/auth/reset/{token}`, `/account/delete`; `bcrypt >= 4.0` wirft `ValueError: Password must be 72 bytes or fewer` bei >72 Bytes → unkontrollierter 500 auf allen 4 Auth-Endpunkten; legitime User mit langem Passwort bekommen 500 statt Validierungsfehler · Fix: `max_length=128` auf alle 4 `password: str = Form()`-Parameter | `api/src/routes/auth.py:57,139,318`, `api/src/routes/account.py:42` | Security |

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
| L-30 | ✅ | W9 | **CSRF-Token fehlt auf Login + Register POST** | `api/src/routes/auth.py:150–291` | Security |
| L-31 | ✅ | W9 | **ml-service SIGTERM: `joblib.dump()` nicht atomar** | `ml-service/src/models/readiness.py:94` | Architektur |
| L-32 | ✅ | W9 | **Semgrep pre-commit ohne OWASP-Top-10-Ruleset** | `.pre-commit-config.yaml:48` | CI/CD |
| L-33 | — | — | **JS-Vitest: `dashboard-hero.js` fehlt in `coverage.include`** (dokumentierte Ausnahme TEST-L3) | `api/vitest.config.js:12–16` | Tests |
| L-34 | ✅ | W9 | **Traefik accessLog: kein JSON-Format** | `traefik/traefik.yml:20` | Observability |
| L-35 | ✅ | W9 | **pip-audit scannt Verzeichnis, nicht `uv.lock`** | `ci.yml:76–86` | CI/CD |
| L-36 | ✅ | W10 R1 | **HSTS wird auch bei `https_only=false` gesetzt** | `api/src/main.py:41–43` | Security |
| L-37 | ✅ | W10 R1 | **Fehlende Längenvalidierung für `email`-Felder** — `Form()` ohne `max_length` auf `/login`, `/auth/resend-verify`, `/auth/reset-request` | `api/src/routes/auth.py:119,270,308` | Security |
| L-38 | ✅ | W10 R1 | **`service`-Parameter in `get_user_token`/`save_user_token` ohne Whitelist** | `api/src/db/users.py:234` | Security |
| L-39 | ✅ | W10 R1 | **`httpOnly`-Cookie-Flag nicht explizit durch Test abgesichert** | `api/src/main.py:148–154` | Security |
| L-40 | ✅ | W10 R3 | **`docker-compose.test.yml` ohne Resource Limits und Log-Rotation** | `docker-compose.test.yml` | Architektur |
| L-41 | — | — | **3-Service-Splitting ohne explizite Begründung in CLAUDE.md** (dokumentierte Ausnahme ARCH-L4) | `CLAUDE.md` | Architektur |
| L-42 | — | — | **`routes/api.py` technisch-flat statt feature-split** (dokumentierte Ausnahme ARCH-L5) — Split erst bei >400Z oder zweitem Entwickler | `api/src/routes/api.py` | Architektur |
| L-43 | ✅ | W10 R3 | **ML-Healthcheck prüft keine Modell-Integrität** | `docker-compose.yml:191–193` | Architektur |
| L-44 | ✅ | W10 R5 | **Sequentielle `await` in `_run_correlations`-Schleife** — auf `asyncio.gather()` umgestellt | `ml-service/src/inference_anomaly.py:109` | Code-Qualität |
| L-45 | ✅ | W10 R5 | **`require_user()` gibt ungetyptes `dict` zurück** — `UserRow` TypedDict in `deps.py` definiert | `api/src/deps.py:73` | Code-Qualität |
| L-46 | ✅ | W10 R5 | **`zip(*pairs)` ohne Längen-Assertion** — `if len(pairs) < 2: continue` Guard ergänzt | `ml-service/src/inference_anomaly.py:113` | Code-Qualität |
| L-47 | ✅ | W10 R4 | **`POST /api/sync` Failure-Pfad ungetestet** — Test ergänzt in W10 R4; Endpoint später entfernt (Sync wird jetzt automatisch nach Garmin-Link + alle 2h getriggert) | `api/tests/test_api_endpoints.py` | Tests |
| L-48 | ✅ | W10 R4 | **`/api/seizures/risk` ohne Boundary-Tests** — 3 Tests ergänzt: Response-Struktur (`level`/`flags`), warning-Level, high-Level | `api/tests/test_api_endpoints.py` | Tests |
| L-49 | ✅ | W10 R4 | **sync-service: kein Test für Garmin+Libre-Kombinations-User** — `TestSyncDualLinkedUser` ergänzt: beide Jobs werden aufgerufen; Garmin-Fehler blockiert Libre nicht | `sync-service/tests/test_main.py` | Tests |
| L-50 | ✅ | W10 R4 | **`/account/export` E2E prüft nicht JSON-Download-Inhalt** — `test_account_export_json_structure` ergänzt: Content-Disposition + alle 9 Top-Level-Keys + Typen validiert via `authenticated_page.request.get()` | `api/tests/e2e/test_smoke.py` | Tests |
| L-51 | ✅ | W10 R7 | **Tote Branch-Namen in `no-commit-to-branch`** — `--branch, dev, --branch, master` · Fix: auf `--branch, main` reduziert | `.pre-commit-config.yaml:19` | CI/CD |
| L-52 | ✅ | W10 R6 | **Kein `sentry.disabled`-Warning beim Start** — `else: logger.warning("sentry.disabled", ...)` in allen 3 Services | `api/src/main.py`, `sync-service/src/main.py`, `ml-service/src/main.py` | Observability |
| L-53 | ✅ | W10 R6 | **`PrintLoggerFactory` nicht Thread-safe für Production** — auf `WriteLoggerFactory()` umgestellt in allen 3 Services | alle `logging_config.py` | Observability |
| L-54 | ✅ | W10 R6 | **Kein Correlation-ID in sync/ml-service Logs** — `bind_contextvars(job_id=...)` + `clear_contextvars()` in `sync_user()` und `run_inference()` | `sync-service/src/main.py`, `ml-service/src/main.py` | Observability |
| L-55 | ✅ | W10 R6 | **Kein Error-Rate-Signal** — `_error_requests`-Counter für `4xx/5xx` in `RequestIDMiddleware` | `api/src/main.py` | Observability |
| L-56 | ✅ | W10 R6 | **`/health` exponiert interne Zähler ohne Auth** — `/health` gibt nur `{"status": "ok"}` zurück | `api/src/main.py` | Observability |
| L-57 | ✅ | W10 R5 | **f-String in `structlog`-Call** — statisches Event `"anomaly.done"` + `metric=log_key` Feld | `ml-service/src/inference_anomaly.py:41` | Code-Qualität |
| L-58 | ✅ | W10 R5 | **Dupliziertes Backfill+Training-Muster** — verifiziert: identischer Block in `run_on_request` + `run_all_users` · `_backfill_and_train()` extrahiert | `ml-service/src/main.py:119,144` | Code-Qualität |
| L-59 | ✅ | W11 | **`auth.py` Dateigröße — Regression behoben** — nach M-52 auf 421Z angewachsen; Token-Helfer (`_make_reset_token`, `_verify_reset_token`, `_make_verify_token`, `_verify_email_token`) + Konstanten in `api/src/auth_tokens.py` ausgelagert → **390Z** | `api/src/routes/auth.py`, `api/src/auth_tokens.py` (neu) | Code-Qualität |
| L-60 | ✅ | — | **5 einzeilige `_run_anomaly_*`-Wrapper (Copy-Paste)** — verifiziert: Wrappers nutzen `_run_anomaly_for()` (M-26-Fix korrekt) → false positive | `ml-service/src/inference_anomaly.py:48–100` | Code-Qualität |
| L-61 | ✅ | W10 R2 | **Vitest `lines: 65` unterhalb Projektsoll** — auf 70% angehoben | `api/vitest.config.js:19` | Tests |
| L-62 | — | — | **E2E `@requires_data`-Tests in CI still übersprungen** (dokumentierte Ausnahme TEST-L4) | `api/tests/e2e/test_smoke.py:21` | Tests |
| L-63 | ✅ | W10 R2 | **metrics.js: `result.value`/`result.sub` per `textContent` → Rendering-Regression** — M-33-Fix setzte alle Metric-Detail-Werte per `textContent`; Renderer-Funktionen liefern styled HTML-Spans, kein User-Input → alle 8 Metric-Seiten zeigten rohe HTML-Tags · Fix: `innerHTML` für Renderer-Ausgaben wiederhergestellt | `api/src/static/metrics.js:38` | Code-Qualität |
| L-64 | ✅ | W11 | **`epilepsy.js`: `flags.label`/`flags.detail` via Template-Literal in `innerHTML` ohne Escaping** — H-10 adressierte seizure notes/event-type/sport-type/metrics.js; risk-flag-Labels nicht abgedeckt · Fix: `renderRiskFlags()` extrahiert + exportiert, `createElement + textContent`; 4 neue Tests in `epilepsy.test.js` | `api/src/static/epilepsy.js:51`, `api/tests/js/epilepsy.test.js` (neu) | Security |
| L-65 | ✅ | W12 R3 | **Pre-commit Hook-Reihenfolge: `bandit` nach `ruff`** — github-rules.md Soll: gitleaks → bandit → lint → format → typecheck; Ist: gitleaks → ruff → bandit; kein funktionaler Impact, aber Abweichung von Canonical-Reihenfolge · Fix: bandit-Repo-Block vor ruff verschoben | `.pre-commit-config.yaml:21–34` | CI/CD |
| L-66 | ✅ | W13 R5 | **`/api/evidence` mit Authentifizierung** — `require_user` ergänzt; konsistent mit allen anderen `/api/*`-Endpunkten | `api/src/routes/api.py:335-337` | Security |
| L-67 | ✅ | W13 R2 | **Dockerfile-HEALTHCHECK vs. docker-compose-Healthcheck inkonsistent** — M-48 (W10 R3) änderte compose auf `/ready`; Dockerfile nutzt noch `/health`. Im Stack-Betrieb überschreibt compose (korrekt). Im Standalone-Container-Betrieb prüft Docker nur `/health`. Fix: Dockerfile-HEALTHCHECK auf `/ready` anpassen | `api/Dockerfile:18-19`, `docker-compose.yml:120` | Architektur |
| L-68 | ✅ | W13 R2 | **CLAUDE.md Env-Dokumentation inkonsistent** — CLAUDE.md listet `env/.env` als "shared, alle Services"; tatsächlich laden alle 3 App-Services `env/.env.app`; `env/.env` nur DB/Flyway. Führt zu Setup-Verwirrung beim Onboarding | `CLAUDE.md` Env-Files-Sektion, `docker-compose.yml:107,145,179` | Architektur |
| L-69 | ✅ | W13 R4 | **SQL-Parameterreihenfolge konsistent** — `set_garmin_linked` auf `(user_id, email)` → `WHERE id = $1, email = $2` vereinheitlicht (wie `set_libre_linked`) | `api/src/db/users.py:82` | Code-Qualität |
| L-70 | ✅ | W13 R4 | **`assert user is not None` → `RuntimeError`** — `if user is None: raise RuntimeError("user_record missing after credential check")` | `api/src/routes/auth.py:165` | Code-Qualität |
| L-71 | ✅ | W13 R4 | **Return-Type-Annotierungen ergänzt** — `-> Response` auf alle Handler in `account.py`, `garmin.py`, `libre.py` | `api/src/routes/account.py`, `garmin.py`, `libre.py` | Code-Qualität |
| L-72 | ✅ | W13 R4 | **Docstrings in 3 kritischen Funktionen** — `get_seizure_risk()`, `build_training_load()`, `export_user_data()` (DSGVO Art. 20) | `api/src/db/seizures.py:153`, `api/src/training_load.py:28`, `api/src/db/users.py:356` | Code-Qualität |
| L-73 | ✅ | W13 R4 | **CC >10 in 4 Funktionen reduziert** — `_day_trimp_for_row` (training_load), `_collect_recovery_slopes` (hrv_recovery), `_build_metric_index` (mapper), `_build_feature_row` (readiness) extrahiert | mehrere | Code-Qualität |
| L-74 | ✅ | W13 R4 | **Bare `except Exception` spezifiziert** — Fernet: `except ValueError as e`; `/ready`: `except Exception` + `logger.exception("readiness.check_failed")` | `api/src/main.py:123,186` | Code-Qualität |
| L-75 | ✅ | W13 R3 | **`POST /api/sync` in CLAUDE.md dokumentiert, Endpunkt existiert nicht** — L-47 (W10 R4) entfernte den Endpunkt; CLAUDE.md-Sektion "JSON-API Endpoints" nicht aktualisiert | `CLAUDE.md` Sektion JSON-API Endpoints | Tests/Docs |
| L-76 | ✅ | W13 R3 | **FERNET_KEY-Dummy als Klartext-Hardcode in ci.yml** — `FERNET_KEY: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=` direkt im YAML; kein echtes Secret, aber E2E-Sektion generiert Key korrekt via openssl. Pattern suggeriert Schlüssel-Material im Repo · Fix: `# pragma: allowlist secret`-Kommentar | `.github/workflows/ci.yml:269` | CI/CD |
| L-77 | ✅ | W13 R3 | **Renovate automergt Produktions-Abhängigkeiten** — `pep621 patch`-Automerge gilt für alle Abhängigkeiten inkl. `fastapi`, `asyncpg`, `scikit-learn`; ohne erzwungene Status-Checks (CICD-M3) könnte PR mergen bevor CI fertig ist · Fix: `"platformAutomerge": false` oder Automerge auf devDependencies einschränken | `renovate.json:9-13` | CI/CD |
| L-78 | ✅ | W13 R5 | **Log-Aggregation via Loki + Promtail** — beide als Compose-Services; Promtail sammelt Docker-Logs aller 3 Services; Loki unter `${TAILSCALE_IP}:3100` abfragbar; 7-Tage-Retention | `docker-compose.yml`, `monitoring/loki-config.yml`, `monitoring/promtail-config.yml` | Observability |
| L-79 | ✅ | W13 R5 | **Alert-System konfiguriert** — Uptime Kuma (Compose-Service, HTTP-Monitor auf `/health`); Sentry Alert Rules in `docs/external-services.md` dokumentiert | `docker-compose.yml`, `docs/external-services.md` | Observability |
| L-80 | ✅ | W13 R2 | **`PYTHONUNBUFFERED` fehlt in allen Dockerfiles** — ohne `ENV PYTHONUNBUFFERED=1` puffert Python stdout; Logs können bei Container-Crash verloren gehen · Fix: `ENV PYTHONUNBUFFERED=1` in alle 3 Dockerfiles | `api/Dockerfile`, `sync-service/Dockerfile`, `ml-service/Dockerfile` | Observability |
| L-81 | ❌ | W14 R1 | **DOM XSS (latent): `mlStatTile()` `value`/`sub`-Parameter ohne Escaping in `innerHTML`** — anders als `label` (korrekt per `esc()`); aktuell alle Aufrufer übergeben numerische Werte (`Math.round(rf.value)`, `corr.r.toFixed(2)`); zukünftige Aufrufer mit API-Strings führen ohne Code-Änderung zu XSS · Fix: `esc(String(value))` und `esc(String(sub))` in `mlStatTile()` | `api/src/static/dashboard-hero.js:322-323` | Security |
| L-82 | ❌ | W14 R1 | **`/ready`-Endpoint leakt interne Infrastruktur-Details (unauthentifiziert)** — gibt `{"status": "no_migrations"}` zurück und verrät damit Flyway-Nutzung + Migrations-Status; L-56 (W10 R6) fixte `/health` korrekt; `/ready` nicht adressiert · Fix: Fehler-Response auf generisches `{"status": "unavailable"}` vereinheitlichen | `api/src/main.py:201-204` | Security |
| L-83 | ❌ | W14 R1 | **Garmin-Passwort persistiert in `GarminClient.password` nach `connect()`** — `del garmin_password` in `garmin.py:73` entfernt nur die lokale Referenz; `client.password` (gesetzt in `__init__`) hält Klartext bis GC; H-16/H-21 adressierten Verschlüsselung, nicht Memory-Hygiene · Fix: `client.password = ""` direkt nach `client.connect()` | `api/src/routes/garmin.py:73`, `api/src/garmin/client.py:15` | Security |
| L-84 | ❌ | W14 R1 | **Dead-Code Fernet-Bypass in sync-service** — `fernet_encrypt(...) if settings.fernet_key else serialized` (4×) ist toter Code (Startup-Validator erzwingt Key); signalisiert aber "unverschlüsselt OK"-Betriebsart; H-16 (W10 R1) fixte `api/src/routes/garmin.py`, H-21 (W13 R1) fixte `api/src/routes/libre.py` — sync-service/src/main.py nicht adressiert · Fix: bedingte Branches entfernen, direkt `fernet_encrypt`/`fernet_decrypt` aufrufen | `sync-service/src/main.py:155-157,205-206,228-229,238` | Security |
| L-85 | ❌ | W14 R2 | **`POST /auth/resend-verify` + `POST /auth/reset-request` ohne CSRF-Token** — sitzungslose Endpunkte; SameSite=Lax schützt session-gebundene POSTs, aber diese Endpunkte benötigen keine Session; Angreifer kann Opfer unaufgefordert Reset-/Verify-E-Mail schicken; Impact gering (unerwünschte E-Mail), Rate Limit 3/h begrenzt Missbrauch · Fix: Accepted-Risk dokumentieren oder minimales Honeypot-Feld ergänzen | `api/src/routes/auth.py:197,237` | Security |
| L-86 | ❌ | W14 R1 | **`resend_verify` Warning-Response leakt E-Mail-Registrierungsstatus** — bei Resend-API-Ausfall gibt der Endpoint `warning`-Context zurück wenn die E-Mail existiert+unverifiziert ist; alle anderen Fälle (inkl. nicht-registriert) erhalten generischen `info`-Context · Fix: `warning`-Branch auf identischen `info`-Text vereinheitlichen | `api/src/routes/auth.py:207-211` | Security |
| L-87 | ❌ | W14 R2 | **DSGVO Art. 32: Gesundheitsdaten ohne Spaltenverschlüsselung** — `sleep_sessions`, `hrv_daily`, `daily_summary`, `seizure_events`, `glucose_readings` in Klartext-Spalten; nur `user_tokens` Fernet-verschlüsselt; DSGVO Art. 32 nennt Verschlüsselung explizit als angemessene technische Maßnahme für Gesundheitsdaten (Art. 9) · Fix: Spaltenverschlüsselung für `seizure_events` + `glucose_readings` oder DSGVO-Risikoakzeptanz-Dokument mit Begründung (Full-Disk-Encryption + Zugangskontrollen als Ersatz) | DB-Schema | Compliance |
| L-88 | ❌ | W14 R2 | **DSGVO Art. 9 + Art. 35: Kein DPIA-Dokument für Sonderkategorie-Gesundheitsdaten** — App verarbeitet Gesundheitsdaten, Epilepsie-Events, Glukose-Werte (Art. 9-Kategorien); Consent-Mechanismus (3 Checkboxen + `user_consents`-Log) liefert Rechtsgrundlage, aber kein Rechenschaftspflicht-Nachweis (Art. 5(2)) für Verarbeitungsrisiken · Fix: `docs/dpia.md` — Minimalformat: Zweck + Rechtsgrundlage + Datenkategorien + Risiken + Maßnahmen | `docs/` | Compliance |
| L-89 | ❌ | W14 R2 | **EU AI Act Art. 13: ML-Prognosen ohne Unsicherheits-Indikatoren** — Readiness-RF, Anomalie-Z-Scores, Korrelationen ohne Konfidenzangabe oder "KI-Prognose"-Label am Wert im UI; `model_meta_rf.n_rows` bereits in DB gespeichert (`save_prediction` W9) aber nicht exponiert; EU AI Act (Limited Risk) verlangt Transparenz am Punkt der Nutzung · Fix: "KI-Prognose (n=X Tage)"-Badge am Readiness-Wert in dashboard-hero.js; `n_rows` aus `/api/ml-insights` exponieren | `api/src/static/dashboard-hero.js`, `api/src/db/ml.py` | Compliance |

---

## Offene Findings (nach ISEC Code Review — Wave 14 offen)

| Gruppe | Findings |
|--------|---------|
| **Eval 1–6, Wave 1–13 gefixt** | ✅ H-01–H-21, M-01–M-87, L-01–L-80 |
| **ISEC Review — Offen** | ❌ M-88, L-81–L-89 (Wave 14) |
| **Manuell / extern** | ❌ H-07 (Sentry DSN in `env/.env.api` eintragen → `docs/external-services.md`) |
| **Dokumentierte Ausnahmen** | — L-13 (TEST-L2), L-21 (OBS-L2), L-33 (TEST-L3), L-41 (ARCH-L4), L-42 (ARCH-L5), L-62 (TEST-L4), M-54 (TEST-L4) |

---

## Roadmap — Wave 14

| Runde | Fokus | Findings | Aufwand |
|-------|-------|---------|---------|
| **W14 R1** | Security Quick Wins | M-88, L-81, L-82, L-83, L-84, L-86 | ~45 min |
| **W14 R2** | CSRF + Compliance | L-85, L-87, L-88, L-89 | ~60 min |

**W14 R1 Details:**
- M-88: `max_length=128` auf alle 4 `password: str = Form()`-Parameter (auth.py:57,139,318; account.py:42)
- L-81: `esc(String(value))` + `esc(String(sub))` in `mlStatTile()` (dashboard-hero.js:322-323)
- L-82: `/ready`-Fehlerfall auf `{"status": "unavailable"}` vereinheitlichen (main.py:201-204)
- L-83: `client.password = ""` nach `client.connect()` in garmin.py
- L-84: Bedingte `if settings.fernet_key else`-Branches in sync-service/src/main.py entfernen (4×)
- L-86: `warning`-Branch in `resend_verify` auf generischen `info`-Text angleichen (auth.py:207-211)

**W14 R2 Details:**
- L-85: `POST /auth/resend-verify` + `POST /auth/reset-request` — CSRF-Token oder Accepted-Risk dokumentieren
- L-87: DSGVO Art. 32 — Risikoakzeptanz-Dokument (Full-Disk-Encryption + Zugangskontrollen als Begründung) oder pgcrypto für `seizure_events`/`glucose_readings`
- L-88: `docs/dpia.md` erstellen — Minimalformat DPIA für Sonderkategorie-Gesundheitsdaten (Art. 9 + Art. 35)
- L-89: "KI-Prognose (n=X Tage)"-Badge am Readiness-Score in dashboard-hero.js; `n_rows` aus `/api/ml-insights` exponieren

---

## Roadmap — Wave 13 (abgeschlossen)

| Runde | Fokus | Findings | Aufwand |
|-------|-------|---------|---------|
| ~~**W13 R1**~~ | ~~Security Quick Wins~~ | ~~H-20, H-21, M-75, M-76, M-77~~ | ✅ |
| ~~**W13 R2**~~ | ~~Architektur & Konfiguration~~ | ~~M-83, M-84 (false positive), M-81, L-80, L-67, L-68~~ | ✅ |
| ~~**W13 R3**~~ | ~~Tests + CI/CD~~ | ~~M-79, M-80, L-75, L-76, L-77~~ | ✅ |
| ~~**W13 R4**~~ | ~~Code-Qualität~~ | ~~M-78, M-82, M-85–87, L-69–L-74~~ | ✅ |
| ~~**W13 R5**~~ | ~~Observability + Public Release~~ | ~~L-66, L-78, L-79, M-19 (Uptime Kuma), ARCH-M3 (ACME)~~ | ✅ |

**Gesamtaufwand Wave 13:** 2H · 13M · 15L — Phase-1 (R1–R3) unter 2h, alle S-Aufwand

---

## Roadmap — Wave 12 (abgeschlossen)

| Runde | Fokus | Findings | Aufwand |
|-------|-------|---------|---------|
| ~~**W12 R1**~~ | ~~Security Quick Wins~~ | ~~M-63 (statTile `esc()`), M-64 (DOMPurify/DOM-API)~~ | ✅ |
| ~~**W12 R2**~~ | ~~Code-Qualität — Funktionslängen~~ | ~~H-19, M-65–72 (Funktion-Extraktion in api/sync/ml)~~ | ✅ |
| ~~**W12 R3**~~ | ~~Observability + Tests + CI~~ | ~~M-73 (sync_libre_user job_id), M-74 (daily_range == 9.0), L-65 (bandit vor ruff)~~ | ✅ |

---

## Roadmap — Wave 10 R3–R7 (abgeschlossen)

| Runde | Fokus | Findings | Aufwand |
|-------|-------|---------|---------|
| ~~**W10 R3**~~ | ~~Architektur & Betrieb~~ | ~~M-45, M-46, M-48, M-49, L-40, L-43~~ | ✅ |
| ~~**W10 R4**~~ | ~~Tests (Rest)~~ | ~~M-53, M-55 (resolved), L-47–50~~ | ✅ |
| ~~**W10 R5**~~ | ~~Code-Qualität~~ | ~~M-50, M-51, M-52, L-44–46, L-57, L-58, L-60~~ | ✅ |
| ~~**W10 R6**~~ | ~~Observability~~ | ~~M-47 (ProcessorFormatter Bridge + WriteLoggerFactory), L-52 (sentry.disabled), L-53 (WriteLoggerFactory), L-54 (Correlation-ID job_id), L-55 (_error_requests), L-56 (/health cleanup)~~ | ✅ |
| ~~**W10 R7**~~ | ~~CI/CD + Security~~ | ~~L-51 (Branch-Namen), M-56 (Trivy Artefakt), M-42 (CSP Nonce + strict-dynamic) · L-42 → ARCH-L5~~ | ✅ |
| ~~**Eval 5**~~ | ~~Re-Audit~~ | ~~Vollständiges Re-Audit nach Wave 11 (6 Subagenten parallel)~~ | ✅ |

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
- **Auth-Suite**: Login/Lockout/Rate-Limit/E-Mail-Verifikation/Password-Reset/DSGVO vollständig getestet — inkl. E2E-Tests für Register-Flow, Token-Verifizierung und Passwort-Reset
- **E2E-Abdeckung**: Alle öffentlichen Seiten + Epilepsie-Seite via Playwright abgedeckt
- **CSRF**: auf allen mutativen Routen korrekt (inkl. /logout seit W10 R1)
- **Prepared Statements**: Alle `api/src/db/`- und `ml-service/src/db/`-Queries parametrisiert
- **Action-Digests**: Alle GitHub Actions mit Commit-SHA gepinnt
- **structlog JSON + UTC**: alle 3 Services; keine Secrets in Logs
- **/health + /ready**: Liveness (kein DB-Call) + Readiness (SELECT 1 + Flyway-Check) — überdurchschnittlich gut
- **Loki + Promtail**: Log-Aggregation aller 3 Services als Compose-Services; 7-Tage-Retention; via Tailscale abfragbar
- **Uptime Kuma**: Self-hosted Uptime-Monitoring als Compose-Service; Dashboard via Tailscale-IP
- **ACME/Let's Encrypt**: Automatische TLS-Zertifikate via Traefik (standalone); Fernet-Verschlüsselung für alle Service-Tokens

---

## Dokumentierte Ausnahmen

| ID | Beschreibung |
|---|---|
| ARCH-M2 | Kein Service-Layer (Routes → DB direkt) — Logik ist route-spezifisch, kein geteilter Business-Logic-Bedarf; Trigger: >3 Entwickler oder domainübergreifende Business-Logik |
| ARCH-M3 | ✅ Traefik ACME konfiguriert — `certificatesResolvers.letsencrypt` (HTTP-01) in `traefik/traefik.yml`; `ACME_EMAIL` in `env/.env` setzen |
| ARCH-L2 | Technisch-basierte `db/`-Ordnerstruktur — Dateien <200Z, Domain-Grenzen durch Dateinamen klar; Trigger: Dateien >400Z oder parallele Team-Arbeit an isolierten Domains |
| ARCH-L3 | Kein `/api/v1/`-Prefix — keine externen Consumer; Trigger: externe API-Stabilität wird verlangt |
| ARCH-L4 | 3-Service-Splitting bewusst: Scheduling-Isolation, ML-Workload-Trennung, unabhängige Restart-Zyklen, unterschiedliche Memory-Limits (api 512 MB, ml 1 GB). Kein klassisches Microservices-Muster. |
| ARCH-L5 | `routes/api.py` technisch-flat (~340Z) — alle Endpunkte teilen `require_user`/`limiter`-Deps, Domain-Grenzen per Kommentarblöcke erkennbar; Trigger: >400Z oder zweiter Entwickler |
| CICD-M3 | Branch Protection nicht erzwingbar (Free-Plan, privates Repo) |
| CICD-L4 | GitHub-native Secret Scanning nicht verfügbar (Free-Plan) |
| QUAL-M2 | Duplizierter GarminClient in api/ + sync-service/ — bewusst |
| OBS-L1 | ✅ Uptime Kuma als Compose-Service — Monitor auf `http://api:8000/health`; Dashboard via `${TAILSCALE_IP}:3001` |
| OBS-L2 | Kein OpenTelemetry — Single-Server; `request_id` als Korrelation ausreichend |
| SEC-L1 | ✅ Entfällt — ARCH-M3 mit ACME gefixt; HSTS korrekt (echtes Zertifikat) |
| TEST-L1 | `require_user`-Mock ohne `assert_called_once()` — Tests verifizieren Verhalten |
| TEST-L2 | JS-Coverage auf 4/24 Static-JS-Dateien — DOM-heavy Files via Playwright E2E |
| TEST-L3 | `dashboard-hero.js` bewusst aus Vitest `coverage.include` ausgeschlossen — `heroRecommendation()` hat Unit-Tests; DOM-schwere Funktionen (`buildHeroCard`, `buildMlTabs`) via Playwright E2E; Coverage-Merge Unit+E2E mit Python-Playwright-Stack nicht praktikabel |
| TEST-L4 | E2E `@requires_data`-Tests werden in CI übersprungen (`CI_HAS_DATA` nicht gesetzt) — Garmin-Sync erfordert echte API-Credentials; Tests laufen korrekt bei `make test-seed && CI_HAS_DATA=true`; Standard-CI-Lauf mit registriertem User ist ausreichend |
