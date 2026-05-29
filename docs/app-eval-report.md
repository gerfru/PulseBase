# PulseBase — App-Eval-Report

**Datum:** 2026-05-28 | **ASVS-Level:** L1 (Solo) | **Regelquelle:** Dev-Best-Practices Plugin (essential/app/github/architecture-rules.md)

---

## Achsen-Übersicht

| Achse | Ampel | #High | #Medium | wichtigste verletzte Regel |
|-------|-------|-------|---------|---------------------------|
| Architektur & 12-Factor | 🟡 Gelb | 1 | 6 | architecture-rules.md → Docker HEALTHCHECK, Schichtung |
| Security (ASVS L1) | 🔴 Rot | 4 | 4 | app-rules.md → Auth/Secrets/Input-Validation |
| Code-Qualität | 🟡 Gelb | 0 | 5 | Funktion >50 Zeilen, duplizierter GarminClient |
| Tests & Zuverlässigkeit | 🔴 Rot | 4 | 6 | essential-rules.md → Coverage-Enforcement, kritische Pfade |
| CI/CD & Delivery | 🟡 Gelb | 2 | 4 | github-rules.md → Lockfile, semgrep |
| Observability & Betrieb | 🟡 Gelb | 0 | 4 | app-rules.md → Sentry, PII in Logs, HEALTHCHECK |

---

## Alle Findings (nach Severity sortiert)

### HIGH (9 Findings)

---

**[SEC-H1] X-Forwarded-For blind trusted — Rate-Limiter bypassable**
`api/src/deps.py:19-23` · Security · Confidence 9 · app-rules.md → Rate Limiting / Auth
`_get_real_ip` nimmt ohne Validierung den ersten `X-Forwarded-For`-Wert. Jeder Client kann diesen Header fälschen und damit den IP-basierten Rate-Limiter auf `/login`, `/register` und Passwort-Reset umgehen.
Fix: Trusted-Proxy-Allowlist konfigurieren (Traefik IP) oder `key_func` auf `request.client.host` pinnen; `uvicorn.ProxyHeadersMiddleware` mit `trusted_hosts`.
Aufwand: **M**

---

**[SEC-H2] FERNET_KEY optional — Tokens bei leerem Key unverschlüsselt gespeichert**
`api/src/deps.py` + `api/src/main.py:86-88` · Security · Confidence 8 · app-rules.md → Environment & Secrets
`fernet_key: str = ""` macht Verschlüsselung opt-in. Lifespan-Code loggt nur eine Warnung und startet weiter — Garmin OAuth-Tokens und LibreLinkUp-Credentials landen dann als Plaintext in `user_tokens`.
Fix: Default entfernen, Pydantic-Validator hinzufügen der bei leerem Wert `ValueError` wirft → App crasht beim Start.
Aufwand: **S**

---

**[SEC-H3] Path Traversal in `restore_token_dir` via Dateinamen aus DB**
`api/src/crypto.py:25-29` + `sync-service/src/crypto.py:25-29` · Security · Confidence 8 · app-rules.md → Input-Validierung
`Path(token_dir, name)` wird mit `name` aus dem JSON-Blob (kommt aus DB) konstruiert. Malicious Filename (`../../etc/...`) würde außerhalb des Temp-Dirs schreiben.
Fix: `name = Path(name).name` (strippt alle Pfad-Komponenten) vor Pfad-Konstruktion; absolute Separatoren ablehnen.
Aufwand: **S**

---

**[SEC-H4] semgrep fehlt in CI und pre-commit (cross-file Taint-Analyse fehlend)**
`.github/workflows/ci.yml` + `.pre-commit-config.yaml` · Security/CI · Confidence 10 · app-rules.md → Security Assessment
bandit deckt nur Einzel-Dateien ab. semgrep für cross-file Taint-Analyse (z.B. SQL-Injection über Funktionsgrenzen) fehlt komplett. ml-service ist zusätzlich aus dem pre-commit bandit-Hook ausgeschlossen.
Fix: `semgrep/semgrep-action` in security-Job + `--config p/python --config p/owasp-top-ten`; bandit-Args um `ml-service/src/` erweitern.
Aufwand: **S**

---

**[TEST-H1] Kein `--cov` / kein `fail_under` in CI (Coverage nie gemessen)**
`.github/workflows/ci.yml` (pytest-Job) · Tests · Confidence 10 · essential-rules.md → Testing
pytest läuft ohne `--cov`-Flag. `pytest-cov` ist installiert aber nie aktiviert. Die `[tool.coverage.run]`-Konfiguration greift damit nicht in CI.
Fix: `pytest -v --ignore=tests/e2e --cov=src --cov-fail-under=70` in CI.
Aufwand: **S**

---

**[TEST-H2] 10 von 16 ML-Modellen vollständig ungetestet**
`ml-service/src/models/` · Tests · Confidence 10 · essential-rules.md → Testing (Data Transformations priorisieren)
Ungetestet: `hrv_recovery`, `hrv_status`, `intensity_minutes`, `running_economy`, `sleep_metrics`, `sleep_score`, `spo2_metrics`, `stress_metrics`, `training_effect`, `training_load`. Diese berechnen gesundheitskritische Metriken (SpO2-Apnoe-Flag, Intensitätsminuten, HRV-Status).
Fix: Unit-Tests für jeden ungetesteten Fall (pure Python, kein DB-Mock nötig); mindestens Normalfall + Edge Case (None/leere Liste).
Aufwand: **L**

---

**[TEST-H3] Kein IDOR-Test: User A auf User B's Aktivitäten**
`api/tests/test_api_endpoints.py` (fehlend) · Tests · Confidence 8 · essential-rules.md → Security (Auth am Data Access Layer)
DB-Queries setzen `AND user_id = $X` korrekt, aber kein Test verifiziert, dass User A keine Daten von User B erhält (z.B. `GET /api/activities/{id}` mit fremder ID → 404).
Fix: Test mit gemocktem `require_user` (User A) + `get_activity_detail` gibt `None` zurück (User B's ID) → erwartet 404.
Aufwand: **S**

---

**[TEST-H4] `training_load.py` aus Coverage-Omit ausgeschlossen**
`api/pyproject.toml:41` · Tests · Confidence 10 · essential-rules.md → Testing (kritische Pfade ~100%)
`training_load.py` (Banister TRIMP — Basis für Physical-Energy-Score, CTL/TSB) ist in `[tool.coverage.run] omit` eingetragen und hat keine Unit-Tests.
Fix: Aus `omit` entfernen; `api/tests/test_training_load.py` mit bekannten TRIMP-Werten anlegen.
Aufwand: **S**

---

**[CICD-H1] ml-service hat kein uv.lock (kein Lockfile)**
`ml-service/` · CI/CD · Confidence 10 · github-rules.md → Lockfiles immer committen
api und sync-service haben uv.lock, ml-service nicht. CI installiert via `pip install -e ml-service/` ohne Lock — reproduzierbare Builds und SCA-Ergebnisse nicht garantiert.
Fix: `uv lock` im ml-service-Verzeichnis ausführen, uv.lock committen, CI auf `uv sync --frozen` umstellen.
Aufwand: **S**

---

### MEDIUM (25 Findings)

**[SEC-M1] Password-Reset invalidiert Session nicht**
`api/src/routes/auth.py:424` · Security · Confidence 8 · app-rules.md → Auth / Sessions
`reset_password` ruft `request.session.clear()` nicht auf. Angreifer mit gültigem Session-Cookie (via XSS) behalten nach Passwort-Reset Zugriff (ASVS v2.2.4).
Fix: `request.session.clear()` nach `await update_password(...)` einfügen.
Aufwand: **S**

**[SEC-M2] SQL Interval-Verkettung in seizures/glucose Queries**
`api/src/db/seizures.py:38` + `api/src/db/glucose.py` · Security · Confidence 7 · app-rules.md → Datenbank
`($2 || ' days')::interval` — Wert ist durch FastAPI `Query(ge=1, le=365)` auf int begrenzt, aber das Muster ist keine echte Prepared-Statement-Typisierung.
Fix: `NOW() - ($2 * INTERVAL '1 day')` (Integer direkt übergeben, wie in anderen Queries).
Aufwand: **S**

**[SEC-M3] `account/delete` umgeht `require_user()`**
`api/src/routes/account.py:37` · Security · Confidence 7 · app-rules.md → Auth (Defense in Depth)
Manuelle Session-Lessung statt `require_user()`. Divergiert vom Projekt-Auth-Muster; fehlender DB-Revocation-Check.
Fix: `user = await require_user(request)` verwenden.
Aufwand: **S**

**[SEC-M4] `account/export` umgeht `require_user()`**
`api/src/routes/account.py:63-64` · Security · Confidence 7 · app-rules.md → Auth (Defense in Depth)
Identisch zu SEC-M3; gelöschter User mit gültigem Cookie könnte Export versuchen.
Fix: `user = await require_user(request)` verwenden.
Aufwand: **S**

**[ARCH-M1] HEALTHCHECK fehlt in sync-service und ml-service (Dockerfile + Compose)**
`sync-service/Dockerfile`, `ml-service/Dockerfile`, `docker-compose.yml:109-161` · Architektur · Confidence 10 · architecture-rules.md → Docker / CLAUDE.md → Health Checks
Beide Dockerfiles ohne `HEALTHCHECK`, Compose ohne `healthcheck`-Block. API-Dockerfile hat korrekt `HEALTHCHECK`.
Fix: Sentinel-File-Ansatz: Scheduler schreibt `/tmp/sync_alive` periodisch; `HEALTHCHECK CMD find /tmp/sync_alive -mmin -2 || exit 1` in beide Dockerfiles + Compose-healthcheck-Block.
Aufwand: **M**

**[ARCH-M2] Kein Service-Layer (Routes → DB direkt)**
`api/src/routes/api.py:10-38` · Architektur · Confidence 10 · architecture-rules.md → Schichtung
Routes importieren direkt aus `src.db`. Business-Logik (`training_load.py`, `evidence_catalog.py`) liegt in Top-Level-Modulen, nicht in einer kohärenten Service-Schicht.
Fix: Schuld dokumentieren; bei Wachstum `api/src/services/` einführen.
Aufwand: **L** (Refactoring-Kandidat)

**[ARCH-M3] Traefik: kein ACME/Let's Encrypt — selbst signiertes TLS-Fallback**
`traefik/traefik.yml` · Architektur · Confidence 9 · architecture-rules.md → Reverse Proxy & SSL
`tls=true` ohne `certificatesResolvers` → Traefik nutzt self-signed Fallback. Für Homelab ein bekannter Kompromiss, aber nicht dokumentiert.
Fix: ACME mit DNS-Challenge ergänzen oder in CLAUDE.md als bewusste Homelab-Ausnahme dokumentieren.
Aufwand: **M**

**[ARCH-M4] Direkte DB-Queries in sync-service `main.py`**
`sync-service/src/main.py:179,229,235,244,252` · Architektur · Confidence 10 · architecture-rules.md → Schichtung
`get_libre_users()`, `mark_sync_done()` etc. verwenden `repo._db.acquire()` direkt in `main.py` — am Repository vorbei.
Fix: Diese Funktionen in `TimescaleRepository` oder ein `UserRepository` verschieben.
Aufwand: **M**

**[OBS-M1] Sentry nur im api-Service (sync und ml ohne Error-Tracking)**
`sync-service/pyproject.toml`, `ml-service/pyproject.toml` · Observability · Confidence 10 · app-rules.md → Monitoring: Sentry
Fehler im Sync-Scheduler und ML-Training-Loop landen nur in Logs, nicht in Sentry — stille Failures bei Garmin-API-Ausfällen unentdeckt.
Fix: `sentry-sdk>=2.0.0` in beide pyproject.toml; bei Startup initialisieren mit `send_default_pii=False`.
Aufwand: **S**

**[OBS-M2] PII (User-Name) in Logs — sync-service**
`sync-service/src/main.py:129,175,265,288` · Observability · Confidence 8 · app-rules.md → Logging: Keine PII loggen
`user["name"]` (Klarname) in `sync.started`, `sync.done`, `sync.failed`-Events.
Fix: `user["id"]` statt `user["name"]` verwenden.
Aufwand: **S**

**[OBS-M3] PII (E-Mail) in Logs — api auth-route**
`api/src/routes/auth.py:298` · Observability · Confidence 10 · app-rules.md → Logging: Keine PII loggen
`logger.warning("auth.register.fail", email=email)` loggt E-Mail-Adresse im Klartext.
Fix: `email`-Feld entfernen oder Hash (`sha256(email)[:8]`) verwenden.
Aufwand: **S**

**[OBS-M4] Request-Latenz nicht geloggt — Latency als goldenes Signal fehlt**
`api/src/main.py:57-64` · Observability · Confidence 9 · app-rules.md → Observability: 4 goldene Signale
`RequestIDMiddleware` setzt Request-ID, loggt aber weder Method/Path noch Response-Latenz.
Fix: `time.perf_counter()` vor/nach `call_next()` in Middleware; `logger.info("http.request", method=..., status=..., duration_ms=...)`.
Aufwand: **S**

**[TEST-M1] JS-Coverage-Threshold zu niedrig (50% statt 70%)**
`api/vitest.config.js:18-20` · Tests · Confidence 10 · essential-rules.md → Testing (Coverage 70-80%)
Vitest erzwingt nur `lines: 50, functions: 50`.
Fix: Threshold auf `lines: 70, functions: 70` anheben.
Aufwand: **S**

**[TEST-M2] Sync-Service Mapper-Funktionen zu ~60% ungetestet**
`sync-service/src/` · Tests · Confidence 9 · essential-rules.md → Testing (Data Transformations)
`map_records`, `map_summary`, `map_body_battery`, `map_stress`, `map_training_status` und `libre/mapper.py::map_reading` fehlen komplett.
Fix: Testklassen analog zu vorhandenen Klassen anlegen.
Aufwand: **M**

**[TEST-M3] Kein Rate-Limiting-Integrationstest (HTTP 429)**
`api/tests/test_auth.py` (fehlend) · Tests · Confidence 8 · app-rules.md → Auth: Rate Limiting
Nur Unit-Test des Handlers; kein Test der N+1 POST /login → HTTP 429 sendet.
Fix: `for _ in range(11): await client.post("/login", ...)` → letzter Request muss 429 zurückgeben.
Aufwand: **S**

**[TEST-M4] E2E `authenticated_page` session-scoped — Tests teilen State**
`api/tests/e2e/conftest.py:27` · Tests · Confidence 9 · essential-rules.md → Testing (keine Test-Interdependenz)
`scope="session"` — alle E2E-Tests teilen Browser-State. Theme-Toggle-Test kann nachfolgende Tests beeinflussen.
Fix: `authenticated_page` auf `function`-Scope setzen oder autouse-Fixture mit Page-Reset.
Aufwand: **S**

**[TEST-M5] Keine Coverage-Konfiguration für ml-service und sync-service**
`ml-service/pyproject.toml`, `sync-service/pyproject.toml` · Tests · Confidence 10 · essential-rules.md → Testing
Kein `[tool.coverage.*]`, kein `pytest-cov` als Dev-Dep; CI ruft pytest ohne `--cov` auf.
Fix: `pytest-cov` zu Dev-Deps; `[tool.coverage.report] fail_under = 70`; CI-Befehl anpassen.
Aufwand: **S**

**[TEST-M6] Sync-Service Repositories und Libre-Client komplett ungetestet**
`sync-service/src/repositories/timescale.py`, `sync-service/src/libre/client.py` · Tests · Confidence 9 · essential-rules.md → Testing
`TimescaleRepository` (upsert, bulk_insert) und `libre/client.py` haben null Tests.
Fix: Analog zu `api/tests/test_libre_client.py` für sync-service anlegen.
Aufwand: **M**

**[CICD-M1] CI nutzt pip statt uv — uv.lock wird ignoriert**
`.github/workflows/ci.yml` · CI/CD · Confidence 10 · github-rules.md → Package Manager: uv
Alle Python-Installs via `pip install -e ...` trotz vorhandener uv.lock — Lock nicht respektiert, abweichende transitive Versionen möglich.
Fix: `astral-sh/setup-uv` einbinden; alle `pip install` durch `uv sync --frozen` ersetzen.
Aufwand: **M**

**[CICD-M2] Keine globalen Workflow-Permissions (Least Privilege fehlt)**
`.github/workflows/ci.yml` · CI/CD · Confidence 10 · github-rules.md → CI/CD Security
Nur security-Job hat explizite Permissions; andere Jobs erben Repository-Default (`write-all` bei privaten Repos).
Fix: Toplevel `permissions: contents: read` einfügen.
Aufwand: **S**

**[CICD-M3] Branch Protection nicht durchsetzbar (privates Repo, Gratis-Plan)**
GitHub API → 403 · CI/CD · Confidence 10 · github-rules.md → Branch Protection
Direkte Pushes auf main sind möglich; required Status Checks nicht erzwingbar.
Fix: GitHub Pro-Plan oder Repo öffentlich machen; alternativ dokumentieren und pre-commit-Hook als einzige lokale Schutzebene stärken.
Aufwand: **M** (Plan-Entscheidung)

**[CICD-M4] `no-commit-to-branch` schützt `main` nicht**
`.pre-commit-config.yaml:19` · CI/CD · Confidence 10 · github-rules.md → Branch Protection
Hook schützt `dev` und `master`, aber nicht `main` (tatsächlicher Default-Branch).
Fix: `args: [--branch, main, --branch, dev, --branch, master]`
Aufwand: **S** (< 5 Minuten)

**[QUAL-M1] Godfunction: `load()` in dashboard-loaders.js (~410 Zeilen)**
`api/src/static/dashboard-loaders.js:6` · Code-Qualität · Confidence 9 · Schwellwert: Funktion >50 Zeilen
Fix: `renderActivitiesTable()`, `buildActivityCharts()`, `buildHealthCharts()` aufteilen.
Aufwand: **M**

**[QUAL-M2] Duplizierter `GarminClient` in api/ und sync-service/**
`api/src/garmin/client.py` + `sync-service/src/garmin/client.py` · Code-Qualität · Confidence 10 · DRY
Fast identische Klassen; nur `save_token()` / `get_training_status()` unterscheiden sich.
Fix: Shared Python-Paket oder Basisklasse mit Service-spezifischen Erweiterungen.
Aufwand: **L**

**[QUAL-M3] Broad `except Exception` ohne Re-raise bei E-Mail-Helpers**
`api/src/routes/auth.py:94,118,142` · Code-Qualität · Confidence 9 · Schwellwert
`_send_lockout_email()`, `_send_reset_email()`, `_send_verify_email()` fangen alle Exceptions und geben `False` zurück — Konfigurationsfehler (falsche API-Keys) werden still ignoriert.
Fix: Nur `resend.ReplyError`/HTTP-Fehler fangen; unerwartete Exceptions mit `logger.exception()` re-raisen.
Aufwand: **S**

---

### LOW (18 Findings — Kurzform)

| ID | Titel | Datei | Aufwand |
|----|-------|-------|---------|
| ARCH-L1 | DB_HOST/PORT/NAME fehlen bei ml-service in Compose | docker-compose.yml:136 | S |
| ARCH-L2 | Technisch-basierte db/-Ordnerstruktur (kein Feature-Split) | api/src/db/ | L |
| ARCH-L3 | API nicht versioniert (fehlt `/api/v1/`) | api/src/routes/api.py:48 | M |
| ARCH-L4 | flyway image: `latest`-Tag ohne Version-Angabe | docker-compose.yml:34 | S |
| ARCH-L5 | Settings doppelt instanziiert (pool.py + deps.py) | api/src/db/pool.py:34 | S |
| OBS-L1 | Kein Uptime-Monitoring konfiguriert | Projekt-weit | S |
| OBS-L2 | structlog ohne stdlib-Logging-Bridge (APScheduler/Uvicorn nicht in JSON) | logging_config.py | M |
| OBS-L3 | flyway ohne Resource-Limits und Log-Rotation | docker-compose.yml:33-50 | S |
| OBS-L4 | traefik ohne Resource-Limits und Log-Rotation | docker-compose.yml:53-65 | S |
| OBS-L5 | Sentry `traces_sample_rate=0.0` (Performance-Monitoring aus) | api/src/main.py:104 | S |
| TEST-L1 | Mock-Qualität: `require_user` in Route-Tests direkt gepatcht | api/tests/test_api_endpoints.py | M |
| TEST-L2 | E2E ohne Playwright-Config (keine Screenshots bei Fehlern in CI) | fehlend | S |
| CICD-L1 | Kein PR-Template vorhanden | .github/ | S |
| CICD-L2 | Kein PR-Größen-Check in CI | .github/workflows/ci.yml | S |
| CICD-L3 | Kein Python-Dependency-Caching in CI | ci.yml | S |
| CICD-L4 | Renovate deckt npm devDeps nicht für Automerge ab | renovate.json | S |
| QUAL-L1 | f-String-Logging statt Lazy Evaluation | client.py, timescale.py | S |
| QUAL-L2 | Fehlende Return-Type-Annotationen bei Route-Handlern (~20 Fälle) | routes/auth.py, api.py | S |

---

## Fix-Reihenfolge

### ✅ Wave 1 — erledigt (PR #90)

- **SEC-H2** FERNET_KEY Pflicht-Validator → Startup-Crash bei leerem Wert
- **SEC-H3** Path Traversal: `name = Path(name).name` in crypto.py (beide Services)
- **SEC-M1** Password-Reset: `request.session.clear()` nach `update_password()`
- **SEC-M3/M4** `account/delete` + `account/export`: `require_user()` verwenden
- **CICD-M4** `no-commit-to-branch` → `main` ergänzen
- **CICD-H1** ml-service: `uv lock` + committen
- **SEC-H4** semgrep in CI + bandit für ml-service in pre-commit
- **TEST-H1** CI pytest mit `--cov --cov-fail-under=70`
- **TEST-H4** training_load.py aus omit entfernen + Unit-Tests (100% Coverage)
- **OBS-M2/M3** PII in Logs (user_name + email) entfernen
- **TEST-M5** Coverage-Config für ml/sync + pytest-cov

### ✅ Wave 2a — erledigt

- **SEC-M2** SQL Interval-Verkettung in seizures.py + glucose.py (`$2 * INTERVAL '1 day'`)
- **CICD-M2** Toplevel `permissions: contents: read` in ci.yml
- **OBS-M4** Request-Latenz in RequestIDMiddleware (`http.request` Event mit `duration_ms`)
- **OBS-M1** Sentry in sync-service + ml-service (`sentry-sdk>=2.0.0`, `SENTRY_DSN` optional)
- **QUAL-M3** E-Mail-Helpers: `resend.exceptions.ResendError` statt bare `except Exception`
- **TEST-H3** IDOR-Test: `GET /api/activities/{id}` mit fremder ID → 404
- **TEST-M1** JS-Coverage-Threshold: 65% Lines / 70% Functions (war 50/50)
- **TEST-M3** Rate-Limiting-Integrationstest: 11× `/login` → HTTP 429
- **TEST-M4** ~~E2E `authenticated_page` → function-scoped~~ reverted: function-scope triggert Rate-Limiter (13 Tests × 1 Login < 1 min → 429). Bleibt session-scoped.
- **OBS-L5** `traces_sample_rate=0.1` (Performance-Monitoring aktiv)
- **CICD-L1** `.github/pull_request_template.md` angelegt
- **CICD-L4** Renovate: npm devDeps patch automerge

### ✅ Wave 2b — erledigt

- **SEC-H1** X-Forwarded-For: Trusted-Proxy-CIDR-Allowlist in `deps.py` + `pool.py`
- **ARCH-M1** HEALTHCHECK Sentinel-File in sync + ml Dockerfiles + Compose
- **TEST-M2** Sync-Mapper fehlende Tests: `map_records`, `map_summary`, `map_body_battery`, `map_stress`, `map_training_status`, `map_reading` (Libre) — 46 Tests gesamt
- **TEST-H2** 10 ML-Modelle getestet: hrv_recovery, hrv_status, intensity_minutes, running_economy, sleep_metrics, sleep_score, spo2_metrics, stress_metrics, training_effect, training_load — 80+ Tests
- **CICD-M1** CI von pip → uv migriert (`uv sync --frozen --extra dev`)

### ✅ Wave 4 — erledigt

- **TEST-M6** Neue Testdateien: `sync-service/tests/test_repository.py` (TimescaleRepository, 16 Tests) + `sync-service/tests/test_libre_client.py` (LibreClient, 8 Tests)
- **ARCH-L1** DB_HOST/PORT/NAME für ml-service in `docker-compose.yml` ergänzt
- **ARCH-L4** Flyway-Image: `latest@digest` → `10@digest` (explizite Major-Version)
- **ARCH-L5** Doppeltes `Settings()` entfernt: Einzige Instanz in `pool.py`, `deps.py` importiert von dort
- **OBS-L2** structlog stdlib-Bridge in api + ml-service `logging_config.py` (third-party Logs auf WARNING, stdlib-Bridge via `logging.basicConfig`)
- **OBS-L3** Flyway: Resource-Limits (256M/0.25 CPU) + Log-Rotation (5m/2 Files) in Compose
- **OBS-L4** Traefik: Resource-Limits (128M/0.25 CPU) + Log-Rotation (10m/3 Files) in Compose
- **QUAL-L1** 9 f-String-Logger-Aufrufe → lazy `%s` (stdlib) in 4 Dateien
- **QUAL-L2** Return-Type-Annotationen für 36 Route-Handler (`-> Response` / `-> dict`)
- **CICD-L2** PR-Größen-Check (>400 LOC → fail) als neuer CI-Job
- **CICD-L3** uv-Caching (`enable-caching: true`) in allen 3 `setup-uv`-Steps
- **TEST-L2** E2E Screenshot-on-failure in `conftest.py`
- **ARCH-L2/L3, OBS-L1, TEST-L1** Als akzeptierter Tech-Debt in CLAUDE.md dokumentiert

### ✅ Wave 3 — erledigt

- **ARCH-M4** SQL-Helfer (`get_active_users`, `get_sync_requested_users`, `get_libre_users`, `mark_sync_done`, `set_ml_requested`) aus `sync-service/src/main.py` → `TimescaleRepository`
- **QUAL-M1** `load()` in `dashboard-loaders.js` aufgeteilt: `renderActivitiesTable()` + `buildActivityCharts()` + `buildHealthCharts()` (~415 → 3 Funktionen à ~50–130 Zeilen)
- **QUAL-M2** `api/src/garmin/client.py` mit sync-client angeglichen (identische Implementierung, bewusste Duplikation dokumentiert in CLAUDE.md)
- **ARCH-M2** Als Tech-Debt in CLAUDE.md dokumentiert (Service-Layer bei Wachstum)
- **ARCH-M3** Als Homelab-Ausnahme in CLAUDE.md dokumentiert (self-signed TLS im internen LAN)
- **CICD-M3** Als bekannte Limitierung in CLAUDE.md dokumentiert (GitHub Gratis-Plan)

---

## DORA-Metriken [geschätzt — keine CD-Pipeline vorhanden]

| Metrik | Status |
|--------|--------|
| Deployment Frequency | [geschätzt] Kein CD-Job — manuell via `make up` |
| Lead Time for Changes | [geschätzt] Kurz (Solo, direkter Homelab-Deploy) |
| Change Failure Rate | [nicht messbar] Kein Rollback/Hotfix-Tagging |
| MTTR | [nicht messbar] Kein Incident-Tracking |

---

## Was sauber ist ✓

- Alle DB-Queries als asyncpg parameterized Statements
- Security Headers vollständig und korrekt gesetzt (CSP, HSTS, X-Frame-Options …)
- Cookie-Flags korrekt (`httpOnly`, `secure`, `sameSite=Lax`)
- CSP `unsafe-inline` nur für `style-src` (dokumentierte Ausnahme)
- gitleaks, pip-audit, trivy (mit Digest-gepinnten Action-Tags) in CI
- Multi-Stage Dockerfiles mit Digest-Pins und non-root User für alle 3 Services
- Named Volumes, Resource Limits, Log-Rotation für 4/6 Services
- Traefik als Reverse Proxy vorhanden
- structlog JSON-Logging in allen 3 Services (UTC)
- /health + /ready Endpunkte korrekt implementiert
- Sentry in api-Service aktiv
- Renovate konfiguriert
- Flyway für DB-Migrationen (kein manuelles SQL auf Prod)
- Pydantic Settings-Validierung beim App-Start
- `require_user()` konsistent in allen API-Routes (außer SEC-M3/M4)
- bcrypt direkt (korrekte passlib-Umgehung)
- Rate Limiting + Account-Lockout auf Login
- DSGVO-konforme Consent-Logs (V19)
