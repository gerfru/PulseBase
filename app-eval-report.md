# PulseBase — App-Evaluierungs-Report
**Datum:** 2026-05-29
**Stack:** FastAPI 0.136 · Python 3.12/3.14 · TimescaleDB/PG16 · Docker Compose · Chart.js · scikit-learn
**ASVS-Level:** L2 (Gesundheitsdaten, DSGVO, Epilepsie-Modus)
**Regelquelle:** Dev-Best-Practices Plugin (essential/app/github/architecture-rules.md)
**Scope:** api/ · sync-service/ · ml-service/ · .github/ · docker-compose.yml

---

## Achsen-Übersicht

| Achse | Ampel | #Critical | #High | #Medium | #Low | Wichtigste verletzte Regel |
|-------|-------|-----------|-------|---------|------|---------------------------|
| Architektur & 12-Factor | 🟡 Gelb | 0 | 0 | 1 | 5 | 12-Factor: Disposability (SIGTERM) |
| Security (ASVS L2) | 🟡 Gelb | 0 | 1 | 5 | 0 | CSRF auf state-mutierenden Endpoints |
| Code-Qualität | 🟡 Gelb | 0 | 2 | 6 | 7 | get_today_daily_summary ohne Datumsfilter (stilles Fehlverhalten) |
| Tests & Zuverlässigkeit | 🟡 Gelb | 0 | 2 | 3 | 3 | Coverage-Gates (ML 30%, Sync 50%) + main.py Sync ungetestet |
| CI/CD & Delivery | 🟡 Gelb | 0 | 1 | 5 | 3 | Kein All-Green-Gate-Job |
| Observability & Betrieb | 🟡 Gelb | 0 | 1 | 2 | 4 | Sentry nicht konfiguriert |

**Gesamt: 🟡 Gelb — keine kritischen Schwachstellen, aber 7 High-Befunde blockieren grün.**

---

## Konsolidierte Befundliste (nach Severity)

### HIGH (7 Befunde)

---

**[H-01] CSRF-Schutz fehlt auf state-mutierenden Form-Endpoints**
`api/src/routes/garmin.py:33` · `api/src/routes/account.py:29` · `api/src/routes/auth.py:145,232,310`
Severity: **High** · Confidence: 9 · Achse: Security
Verletzte Regel: App-Rules "Authentication & Authorization — sameSite=Lax", ASVS 4.2.2
`sameSite=Lax` schützt nicht vor Cross-Site POST-Requests. `/garmin/link` akzeptiert Garmin-Credentials ohne CSRF-Token, `/account/delete` löscht Konto ohne Token.
Fix: `starlette-csrf` oder Double-Submit-Cookie einbinden.
Aufwand: **M**

---

**[H-02] `get_today_daily_summary` ohne Datumsfilter — stilles Fehlverhalten**
`ml-service/src/db.py:602–612`
Severity: **High** · Confidence: 9 · Achse: Code-Qualität
Verletzte Regel: Code-Qualität — korrekte Semantik
Query nutzt `ORDER BY date DESC LIMIT 1` ohne `WHERE date = CURRENT_DATE`. Bei fehlendem Sync heute liefert die Funktion alte Daten (Tage), die direkt in `compute_body_battery()` und `compute_stress_score()` fließen — stille Falschberechnung.
Fix: `WHERE user_id = $1 AND date = CURRENT_DATE`, `None` bei fehlendem Wert zurückgeben.
Aufwand: **S**

---

**[H-03] Inkonsistente Parameter-Reihenfolge in `upsert_training_status`**
`sync-service/src/repositories/timescale.py:185–199`
Severity: **High** · Confidence: 9 · Achse: Code-Qualität
Verletzte Regel: Code-Qualität — Konventionskonsistenz
`INSERT INTO daily_summary (user_id, date, training_status) VALUES ($2, $3, $1)` — Arguments werden als `(status, user_id, day)` übergeben, Query nummeriert quer. Fehleranfällig bei Refactoring.
Fix: Argument-Reihenfolge angleichen: `$1`=user_id, `$2`=date, `$3`=status.
Aufwand: **S**

---

**[H-04] ML-Service Coverage-Gate bei 30% (Ziel: 70–80%)**
`ml-service/pyproject.toml:36` · `.github/workflows/ci.yml:240`
Severity: **High** · Confidence: 10 · Achse: Tests
Verletzte Regel: Testing — "Coverage: 70–80% Lines"
`src/db.py`, `src/main.py`, `src/backfill.py`, `src/config.py` vollständig ungetestet. Gate von 30% macht diesen blinden Fleck unsichtbar.
Fix: Gate auf 60% anheben, Smoke-Tests für `db.py` ergänzen.
Aufwand: **M**

---

**[H-05] Sync-Service: `main.py`-Orchestrierungslogik (311 Zeilen) ohne jeden Test**
`sync-service/pyproject.toml:36` · `sync-service/src/main.py`
Severity: **High** · Confidence: 10 · Achse: Tests
Verletzte Regel: Testing — "Priorität 1: kritische Pfade testen"
`sync_user()`, `process_sync_requests()`, `sync_all_users()` und APScheduler-Startup komplett ungetestet. Coverage-Gate von 50% kaschiert dies.
Fix: Gate auf 60%, mindestens `sync_user()` mit gemocktem Repository (happy path + Exception).
Aufwand: **L**

---

**[H-06] Kein All-Green-Gate-Job in CI**
`.github/workflows/ci.yml:168`
Severity: **High** · Confidence: 9 · Achse: CI/CD
Verletzte Regel: GitHub-Rules — "Jeder PR muss durch alle CI-Steps"
`e2e` hängt nur von `[test, trivy]` ab. `lint`, `js-lint`, `security`, `typecheck`, `js-test` sind keine Voraussetzung. Kein aggregierender `ci-ok`-Job für Required Status Checks.
Fix: `ci-ok`-Job mit `needs: [check-pr-size, lint, js-lint, security, typecheck, trivy, test, js-test, e2e]` ergänzen.
Aufwand: **S**

---

**[H-07] Sentry nicht aktiv konfiguriert (kein SENTRY_DSN in .env-Files)**
`env/.env.api` · `env/.env.sync` · `env/.env.ml`
Severity: **High** · Confidence: 9 · Achse: Observability
Verletzte Regel: App-Rules "Error Tracking: Sentry"
Code-Integration ist vollständig vorhanden (`if settings.sentry_dsn:`), aber kein DSN konfiguriert — kein Error Tracking in Produktion aktiv.
Fix: `SENTRY_DSN` in alle drei `.env`-Files eintragen.
Aufwand: **S** (Konfiguration, keine Code-Änderung)

---

### MEDIUM (21 Befunde)

---

**[M-01] ml-service: Kein SIGTERM-Handler (12-Factor Disposability)**
`ml-service/src/main.py:641–648`
Severity: Medium · Confidence: 9 · Achse: Architektur
sync-service hat SIGTERM-Handler (Zeile 305), ml-service nicht. Bei `docker compose down` riskiert man korrupte joblib-Modelldateien.
Fix: `loop.add_signal_handler(signal.SIGTERM, lambda: scheduler.shutdown(wait=False))` analog zu sync-service/src/main.py:305.
Aufwand: **S**

---

**[M-02] Kein Rate Limit auf `/garmin/link` und `/libre/link` POST**
`api/src/routes/garmin.py:33–84` · `api/src/routes/libre.py:24–66`
Severity: Medium · Confidence: 9 · Achse: Security
Verletzte Regel: App-Rules "Rate Limiting auf Middleware/Gateway-Level", ASVS 2.2.1
`/login` hat `@limiter.limit("10/minute")`, Garmin/Libre-Link-Endpoints nicht. Faktisch unlimitierter Credential-Stuffing-Proxy gegen Garmin Connect.
Fix: `@limiter.limit("5/hour")` ergänzen.
Aufwand: **S**

---

**[M-03] Keine E-Mail-Format-Validierung im `/register`-Endpoint**
`api/src/routes/auth.py:149,232–266`
Severity: Medium · Confidence: 8 · Achse: Security
Verletzte Regel: App-Rules "Input-Validierung — Typ, Format", ASVS 5.1.3
`email: str = Form()` ohne RFC5322-Check. Ungültige Adressen werden gespeichert, Verifikations-E-Mails an invalide Adressen verschickt.
Fix: `email: EmailStr = Form()` (via `pydantic[email]`).
Aufwand: **S**

---

**[M-04] Kein Längen-Limit auf `SeizureBody.notes`**
`api/src/routes/api.py:282`
Severity: Medium · Confidence: 8 · Achse: Security
Verletzte Regel: App-Rules "Input-Validierung — Länge", ASVS 5.1.3
`notes: str | None = None` ohne `max_length`. Unbeschränkter Freitext für Epilepsie-Notizen → DoS via Storage.
Fix: `Field(default=None, max_length=2000)`.
Aufwand: **S**

---

**[M-05] Raw-IP in DSGVO-Consent-Tabelle (nicht pseudonymisiert)**
`api/src/routes/auth.py:298–301`
Severity: Medium · Confidence: 7 · Achse: Security
Verletzte Regel: ASVS 8.3.1, DSGVO Art. 5(1)(c)
Alle Logs nutzen `_ip_hash()`, aber der Consent-Audit-Log speichert `request.client.host` als Klartext. IP = PII in der EU. Zusätzlich: falsche IP hinter Proxy (Proxy-IP statt Client-IP).
Fix: `_get_real_ip(request)` verwenden + sha256-Hash vor Speicherung.
Aufwand: **S**

---

**[M-06] Password-Reset-Token nicht invalidiert nach Verwendung**
`api/src/routes/auth.py:388–420` · `api/src/db/users.py:125–131`
Severity: Medium · Confidence: 7 · Achse: Security
Verletzte Regel: ASVS 2.5.4 (Single-use tokens)
Token bleibt nach erfolgreichem Passwort-Reset für 1h wiederverwendbar (kein Revoke).
Fix: Token-Fingerprint (sha256[:16]) in `users`-Tabelle speichern und bei Reset prüfen.
Aufwand: **M**

---

**[M-07] Fehlende Return-Type-Annotierungen in Route-Handlern und Middleware**
`api/src/routes/pages.py:42,47,53,63,69,77,89,100` · `api/src/main.py:32,59,78,141,145,150`
Severity: Medium · Confidence: 10 · Achse: Code-Qualität
Verletzte Regel: Code-Qualität — Typisierung
Keine `-> Response` / `-> dict`-Annotierungen auf Middleware-`dispatch()`-Methoden und Route-Handlern. `_garmin_call` in sync-service/src/main.py:41 komplett untypisiert.
Fix: Return-Typ ergänzen. `_garmin_call`: `Callable[[], T] -> T` mit TypeVar.
Aufwand: **S**

---

**[M-08] Inkonsistentes Logging: stdlib vs. structlog in ml-service und sync-service**
`ml-service/src/db.py:1,8` · `sync-service/src/repositories/timescale.py:1,17` · `sync-service/src/garmin/mapper.py:1,14`
Severity: Medium · Confidence: 10 · Achse: Code-Qualität / Observability
Verletzte Regel: App-Rules "Strukturiertes JSON-Logging"
Diese drei Dateien nutzen `import logging` statt `structlog`. Kein JSON-Output, kein request_id-Context für DB-Operationen.
Fix: `import structlog; logger = structlog.get_logger(__name__)` in allen drei Dateien.
Aufwand: **S**

---

**[M-09] `export_user_data`: Unbegrenzte SELECT *-Abfragen ohne Paging**
`api/src/db/users.py:296–336`
Severity: Medium · Confidence: 9 · Achse: Code-Qualität / Tests
Verletzte Regel: App-Rules "Pagination für alle Listen"
Sechs `SELECT *`-Abfragen ohne LIMIT über alle User-Daten. Bei mehrjährigem Datenbestand: Hunderte MB in einem Request im Heap.
Fix: Streaming-Export via `COPY TO` oder `LIMIT 50000` pro Query. Explizite Spalten statt `*` (verhindert unbeabsichtigten Export interner Felder).
Aufwand: **M**

---

**[M-10] `ml-service/src/db.py` und `ml-service/src/main.py` überschreiten 400 Zeilen**
`ml-service/src/db.py` (670 Zeilen) · `ml-service/src/main.py` (648 Zeilen)
Severity: Medium · Confidence: 10 · Achse: Code-Qualität
Verletzte Regel: Code-Qualität — Dateilänge >400 Zeilen
Fix: `db.py` nach Domänen aufteilen (db/anomaly.py, db/energy.py, db/training.py, db/sleep.py). `main.py` Orchestrierungslogik in `orchestration.py` auslagern.
Aufwand: **M**

---

**[M-11] TRIMP-Formel dreifach dupliziert**
`ml-service/src/main.py:81–92` · `ml-service/src/models/energy_metrics.py:80–92` · `ml-service/src/models/hrv_recovery.py:26–30`
Severity: Medium · Confidence: 10 · Achse: Code-Qualität
Verletzte Regel: Code-Qualität — Duplikation >3%
Identische TRIMP-Formel dreifach implementiert, mit bereits vorhandenen Abweichungen zwischen den Kopien.
Fix: Zentrale `_compute_trimp(row, hrmax)` in `models/utils.py` extrahieren.
Aufwand: **S**

---

**[M-12] `battery_pattern.py`: Verschachtelung >4, komplexe if/elif-Kaskade**
`ml-service/src/models/battery_pattern.py:48–98`
Severity: Medium · Confidence: 8 · Achse: Code-Qualität
Verletzte Regel: Code-Qualität — Verschachtelung >4
`_assign_pattern_labels` hat Tiefe 5. Fallback-Loop kann `"erholung"` falsch setzen.
Fix: Datengetriebene Zuweisung: AUC-rank → Label-Lookup-Dict statt sequentielle if/elif-Kaskade.
Aufwand: **M**

---

**[M-13] api/pyproject.toml: `[tool.coverage.run]` ohne `source`-Direktive**
`api/pyproject.toml:41–43`
Severity: Medium · Confidence: 10 · Achse: Tests
Verletzte Regel: Testing — Coverage-Konfiguration
Ohne `source = ["src"]` greift `fail_under` nur über CLI-Argument. sync-service und ml-service haben `source` korrekt gesetzt — inkonsistent.
Fix: `source = ["src"]` ergänzen.
Aufwand: **S**

---

**[M-14] E2E-Tests: 7× `wait_for_timeout()` (feste Delays — flaky-Risiko)**
`api/tests/e2e/test_smoke.py:56,62,68,85,152,180,184`
Severity: Medium · Confidence: 9 · Achse: Tests
Verletzte Regel: Testing — keine flaky Tests
300–800ms feste Delays reagieren nicht auf tatsächliche DOM-Zustände. Auf CI-Rechnern mit variablen Container-Startzeiten potentiell zu kurz.
Fix: Ersetzen durch `wait_for_load_state("networkidle")` oder `locator.wait_for(state="visible")`.
Aufwand: **S**

---

**[M-15] Python 3.12 im CI vs. 3.14 in Dockerfiles (Versions-Mismatch)**
`api/Dockerfile:2` · `ci.yml:103`
Severity: Medium · Confidence: 9 · Achse: CI/CD
Verletzte Regel: CI-Pipeline — Build/Test gegen Runtime-Umgebung
mypy/pytest laufen mit Python 3.12, Production-Images nutzen `python:3.14-slim`. Python-3.14-spezifische Typ-Fehler bleiben unentdeckt.
Fix: `python-version: "3.14"` in typecheck/test-Jobs setzen.
Aufwand: **S**

---

**[M-16] Semgrep/bandit/pip-audit ohne gepinnte Version im CI**
`.github/workflows/ci.yml:80,88,92`
Severity: Medium · Confidence: 9 · Achse: CI/CD
Verletzte Regel: CI-Pipeline — reproduzierbare Build-Umgebung
`pip install semgrep` ohne `==x.y.z` zieht bei jedem Run die neueste Version.
Fix: `pip install semgrep==1.x.x bandit==1.8.3 pip-audit==2.x.x` mit Versionspins.
Aufwand: **S**

---

**[M-17] Semgrep fehlt in Pre-commit-Hooks**
`.pre-commit-config.yaml`
Severity: Medium · Confidence: 10 · Achse: CI/CD
Verletzte Regel: GitHub-Rules "Pre-commit Hooks: gitleaks → bandit → Lint → Format → Type Check" + SAST-Defense-in-Depth
Semgrep läuft nur in CI — SAST-Befunde erst nach Push sichtbar, nicht beim Commit.
Fix: `returntocorp/semgrep` als pre-commit-Hook (optional `stages: [push]` für Performance).
Aufwand: **M**

---

**[M-18] GitHub-native Secret Scanning nicht konfiguriert/dokumentiert**
`.github/` (kein `secret_scanning.yml`)
Severity: Medium · Confidence: 8 · Achse: CI/CD
Verletzte Regel: GitHub-Rules "Secret Scanning — 3 Schichten: pre-commit + CI + GitHub-nativ"
Schicht 3 fehlt. Für Free-Plan nicht verfügbar, aber undokumentiert.
Fix: `.github/secret_scanning.yml` anlegen und als bekannte Ausnahme analog CICD-M3 in CLAUDE.md dokumentieren.
Aufwand: **S**

---

**[M-19] Kein Uptime-Monitoring (bekannte Tech-Debt OBS-L1)**
`/health` und `/ready` vorhanden, kein externer Monitor.
Severity: Medium · Confidence: 10 · Achse: Observability
Verletzte Regel: App-Rules "Uptime: UptimeRobot"
Fix: UptimeRobot Gratis-Tier auf `https://garmin.home.lab/health`, Intervall 5 min.
Aufwand: **S**

---

**[M-20] Traffic und Saturation nicht messbar (2 von 4 goldenen Signalen fehlen)**
`api/src/main.py:66–72` (kein Prometheus/OTel-Exporter)
Severity: Medium · Confidence: 9 · Achse: Observability
Verletzte Regel: App-Rules "Vier goldene Signale: Latency, Traffic, Errors, Saturation"
RequestIDMiddleware deckt Latency und Errors ab. Kein `/metrics`-Endpunkt, kein OTel-Exporter.
Fix: `prometheus-fastapi-instrumentator` (1 Zeile) für Traffic + Latency-Histogramm. Container-Saturation via `docker stats` oder cAdvisor.
Aufwand: **M**

---

**[M-21] `export_user_data`: `SELECT *` ohne Spaltenselektion — kein Spalten-Test**
`api/src/db/users.py:299–336` (Überschneidung mit M-09)
Severity: Medium · Confidence: 8 · Achse: Tests
Zukünftige interne Felder (sync_state, ML-Flags) würden automatisch in DSGVO-Art.20-Export landen. Bestehender Test prüft nur Leer-Liste.
Fix: Explizite SELECT-Listen oder Test der Spalten-Rückgabe bei nicht-leerem Ergebnis.
Aufwand: **M**

---

### LOW (24 Befunde)

| # | Titel | Datei:Zeile | Achse | Confidence | Aufwand |
|---|-------|-------------|-------|------------|---------|
| L-01 | Kein `stop_grace_period` für ml-service | docker-compose.yml:162 | Arch | 8 | S |
| L-02 | Traefik: kein Access-Log konfiguriert | traefik/traefik.yml | Arch | 9 | S |
| L-03 | uvicorn: kein `--timeout-graceful-shutdown` | api/Dockerfile:19 | Arch | 7 | S |
| L-04 | `proxy`-Netzwerk: kein Fallback im Makefile | docker-compose.yml:205 | Arch | 8 | S |
| L-05 | CSP: `worker-src` und `manifest-src` fehlen | api/src/main.py:43–54 | Arch | 6 | S |
| L-06 | auth.py: 6× identische TemplateResponse-Blöcke | api/src/routes/auth.py:244–286 | Code | 10 | S |
| L-07 | `get_ml_status` in ml.py toter Code (Duplikat in users.py) | api/src/db/ml.py:54–65 | Code | 10 | S |
| L-08 | `SELECT *` statt explizite Spalten in export_user_data | api/src/db/users.py:299 | Code | 9 | M |
| L-09 | `_garmin_call` in sync-service untypisiert | sync-service/src/main.py:41 | Code | 10 | S |
| L-10 | evidence_catalog.py (485 Z.) als reine Datendatei | api/src/evidence_catalog.py | Code | 7 | M |
| L-11 | `asyncio.get_event_loop()` deprecated seit 3.10 | sync-service/src/main.py:304 | Code | 8 | S |
| L-12 | `hrv_vals` unnötig neu zugewiesen | ml-service/src/models/hrv_recovery.py:33–35 | Code | 10 | S |
| L-13 | 3 E2E-Tests mit `pytest.skip` bei fehlendem Testdatenbestand | api/tests/e2e/test_smoke.py:108,127,149 | Tests | 9 | M |
| L-14 | Garmin-Link-Test mockt 5 Implementierungsdetails | api/tests/test_coverage.py:76–98 | Tests | 7 | S |
| L-15 | JS-Coverage nur 4 von 24 Static-JS-Dateien | api/vitest.config.js:10 | Tests | 10 | L |
| L-16 | Renovate: `minor`-Update-Verhalten undokumentiert | renovate.json:7 | CI/CD | 8 | S |
| L-17 | GitHub-Actions Kommentare falsch (`# v6` statt `# v4`) | ci.yml:21,75 | CI/CD | 7 | S |
| L-18 | E2E-Job: DB-Credentials via `grep` aus .env | ci.yml:205–206 | CI/CD | 8 | S |
| L-19 | stdlib-Bridge in sync-service ohne `level=logging.INFO` | sync-service/src/logging_config.py:21 | Obs | 8 | S |
| L-20 | garmin/client.py & libre/client.py: stdlib statt structlog | api/src/garmin/client.py:8 · sync-service/* | Obs | 9 | S |
| L-21 | LibreAuthError-String enthält user_id doppelt | sync-service/src/main.py:194–196 | Obs | 8 | S |
| L-22 | Sentry `traces_sample_rate=0.0` in sync/ml (kein Job-Tracing) | sync-service/src/main.py:268 · ml-service/src/main.py:607 | Obs | 9 | S |
| L-23 | ml-service CI Coverage-Gate 30% doppelt dokumentiert (ci.yml + pyproject.toml) | ci.yml:240 | CI/CD | 9 | S |
| L-24 | `asyncio.get_event_loop()` deprecated — sync-service only (ident. zu L-11) | sync-service/src/main.py:304 | Code | 8 | S |

---

## Fix-Reihenfolge (empfohlen)

### Sprint 1 — Security & kritisches Fehlverhalten (zuerst)
1. **[H-02]** `get_today_daily_summary` Datumsfilter — stille Falschberechnung beheben (S)
2. **[H-03]** Parameter-Reihenfolge `upsert_training_status` (S)
3. **[H-01]** CSRF-Schutz für `/garmin/link`, `/account/delete`, `/auth/reset` (M)
4. **[M-02]** Rate Limit auf `/garmin/link` + `/libre/link` (S)
5. **[M-05]** IP-Adresse in Consent-Tabelle hashen (S)
6. **[M-04]** `SeizureBody.notes` max_length (S)
7. **[M-03]** E-Mail-Format-Validierung im Register (S)

### Sprint 2 — Observability aktivieren
8. **[H-07]** Sentry DSN konfigurieren (alle 3 Services) (S)
9. **[M-19]** UptimeRobot auf `/health` einrichten (S)
10. **[M-20]** prometheus-fastapi-instrumentator einbinden (M)

### Sprint 3 — CI/CD härten
11. **[H-06]** `ci-ok`-Gate-Job ergänzen (S)
12. **[M-15]** Python 3.14 in CI-Jobs (S)
13. **[M-16]** Versionspin für semgrep/bandit/pip-audit (S)
14. **[M-18]** `.github/secret_scanning.yml` anlegen (S)
15. **[M-01]** SIGTERM-Handler ml-service (S)

### Sprint 4 — Code-Qualität & Tests
16. **[H-04]** ML-Service Coverage-Gate auf 60%+ anheben + Tests ergänzen (M)
17. **[H-05]** Sync-Service `sync_user()` testen (L)
18. **[M-06]** Password-Reset-Token Revoke (M)
19. **[M-08]** stdlib → structlog in ml/sync (S)
20. **[M-11]** TRIMP-Duplikat zentral extrahieren (S)
21. **[M-17]** Semgrep als Pre-commit-Hook (M)

### Sprint 5 — Refactoring & Kosmetik (Low)
- L-02 Traefik Access-Log, L-06 TemplateResponse-Helper, L-07 get_ml_status toter Code,
  L-11/L-24 asyncio.get_running_loop(), L-19/L-20 stdlib→structlog in clients,
  L-16 Renovate minor dokumentieren, M-14 E2E timeout→wait_for

---

## Stärken (nicht übersehen)

- **Auth vollständig getestet:** Login, Lockout, Rate-Limiting, E-Mail-Verifikation, Password-Reset, Session-Invalidierung — alle kritischen Pfade mit dedizierten Tests
- **DSGVO-Routen gut abgesichert:** `/account/delete` (5 Tests inkl. falsches Passwort/E-Mail), `/account/export` (kein `password_hash` im Export) — vorbildlich
- **Prepared Statements durchgehend:** Alle asyncpg-Queries nutzen `$1`/`$2`-Parametrisierung — kein SQL-Injection-Vektor gefunden
- **Docker-Hygiene exzellent:** Multi-Stage Builds, Digest-gepinnte Base Images (alle 3 Dockerfiles + docker-compose.yml), Non-root User, HEALTHCHECK, Resource Limits, Log-Rotation
- **Security Headers vollständig:** CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy — alle korrekt gesetzt
- **Fernet-Verschlüsselung korrekt:** Garmin-Tokens verschlüsselt, Key-Validierung beim Start, `del garmin_password` nach Gebrauch
- **Sentry PII-Schutz:** `send_default_pii=False` in allen Services
- **ML-Modell-Tests solide:** 80 Tests für 14 Modelle inkl. Randfälle

---

## Neue Ausnahmen-Empfehlung für CLAUDE.md

Folgende Befunde könnten als bewusste Ausnahmen dokumentiert werden (analog bestehender Tech-Debt):

- **OBS-L2:** Kein Prometheus-Endpunkt / OTel-Exporter — Homelab, docker stats als Saturation-Proxy akzeptabel
- **TEST-L2:** JS-Coverage auf 4 von 24 Static-JS-Dateien beschränkt — DOM-heavy Files via Playwright E2E abgedeckt; Erweiterung wenn Berechnungslogik in JS wächst
- **CICD-L4:** GitHub-native Secret Scanning nicht verfügbar (Free-Plan, privates Repo)

---

*Report generiert von 6 parallelen Subagenten. Alle Befunde mit Datei:Zeile-Bezug. Security-Findings nur Confidence ≥ 7. Nichts automatisch gefixt.*
