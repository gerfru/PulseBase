<!-- DEV-BEST-PRACTICES:START — via /dev-best-practices:install-rules aktualisieren -->
<!-- Version: essential-rules.md @ 2026-05-29 | Umfang: essential -->

## Dev Best Practices

Die wichtigsten Regeln fuer jedes Projekt -- kompakt genug fuer CLAUDE.md.
Ausfuehrlichere Regeln: `app-rules.md`, `github-rules.md`, `architecture-rules.md`

---

## Security

- Security Headers setzen: CSP (`default-src 'self'`), HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy
- CSP-Strategie: Nonce-basiert mit `'strict-dynamic'`. `'unsafe-inline'` nur fuer `style-src`
- Auth an 3 Schichten: Middleware → Route → **Data Access Layer** (wichtigste!)
- Passwort: bcrypt/Argon2, nie Plaintext. Rate Limiting auf Login
- Sessions: httpOnly, secure, sameSite=Lax
- Input validieren an System-Grenze: TS → Zod, Python → Pydantic
- SQL: Immer Prepared Statements. Shell: Nie User-Input in Commands
- DOM XSS: Kein `innerHTML` mit User-Daten. Trusted Types + DOMPurify bei dynamischem HTML
- Keine Secrets in Error-Responses. Keine Secrets loggen
- `.env` nie committen, `.env.example` committen. Env-Validierung beim App-Start (crasht sofort wenn Variable fehlt)
- Security Assessment: `bandit`+`semgrep` (SAST), `pip-audit` (SCA), ASVS 5.0 als Pruefrahmen

## API & Datenbank

- Einheitliches Error-Format: `{ error: { code, message, details } }`
- Rate Limiting auf Middleware/Gateway-Level. Pagination fuer alle Listen
- API-Typ: Intern → tRPC. Extern → REST
- DB: Immer Migrations-Tool (nie manuell SQL auf Prod). Prepared Statements, Least Privilege User
- ORM-Wahl: Query Builder (Drizzle, SQLAlchemy Core) als Sweet Spot
- Connection Pooling Pflicht. Serverless → externer Pooler

## Architecture

- **Feature-basierte** Ordnerstruktur (nicht technisch)
- Schichtung: Routes → Services → Data Access (2-3 Schichten reichen fuer Solo)
- **Starte mit Monolith.** Microservices nur bei konkretem Grund
- Monorepo fuer Full-Stack (Turborepo / pnpm Workspaces / uv Workspaces)
- 12-Factor: Config in Env, Stateless Processes, Logs auf Stdout, Port Binding
- Server Components als Default (React/Next.js). `"use client"` nur bei Interaktivitaet
- Server State (TanStack Query) und Client State (useState/Zustand) nie mischen

## GitHub & CI/CD

- Pre-commit Hooks Pflicht: gitleaks → bandit → Lint+Fix → Format → Type Check
- TS: ESLint Flat Config + Prettier + Husky. Python: Ruff + mypy + pre-commit
- TS Package Manager: pnpm. Python: uv. Lockfiles immer committen
- CI: Jeder PR durch Pipeline (Install → Lint → Type Check → Build/Test → gitleaks)
- Branch Protection auf main: Require PR, Status Checks, No Force Push
- Renovate (nicht Dependabot). devDeps patch Automerge, Major manuell
- PR-Groesse: < 400 LOC, darueber aufteilen

## Testing

- TS: Vitest + Playwright. Python: pytest + Playwright
- Prioritaet: 1) API Endpoints 2) Data Transformationen 3) E2E Smoke Test
- Tests testen Verhalten, nicht Implementierung. Mocke nur an Systemgrenzen
- Coverage: 70-80% Lines. Kritische Pfade (Auth, Payment) ~100%. 100% gesamt ist kein Ziel

## Docker & Deployment

- Multi-Stage Build (Builder + Runner). Base Images mit Digest pinnen
- Non-root User. HEALTHCHECK. `.dockerignore` pflegen
- Ports nur auf `127.0.0.1` binden. Named Volumes fuer Prod
- Reverse Proxy vor der App (Caddy / Nginx). Automatisches HTTPS
- Health Checks: `/health` (Liveness) + `/ready` (Readiness)
- Container-Scanning: Trivy (CRITICAL, HIGH, exit-code 1)

## Monitoring & Logging

- Structured Logging (JSON): TS → Pino, Python → structlog. Timestamps UTC
- Error Tracking: Sentry. Uptime: UptimeRobot. Logs: Better Stack / Axiom
- Alert-Schwellen: Error Rate > 1%, p95 > 2s, CPU/Memory > 80%
- OpenTelemetry als Standard. Metrics/Traces erst bei Bedarf

## Accessibility

- Gesetzlich Pflicht (EU Accessibility Act, BFSG)
- Semantisches HTML, Heading-Hierarchie, alt auf Bildern, Fokus-Styles nicht entfernen
- Testen: axe-core + Lighthouse (automatisch), Tastatur + Screen Reader (manuell)

<!-- DEV-BEST-PRACTICES:END -->

---

@./claude/app-rules.md

---

# Garmin Dashboard — Projektspezifisch

## Stack

FastAPI · TimescaleDB (PostgreSQL 16) · Docker Compose · Chart.js · scikit-learn
Zugriff: `https://<APP_BASE_URL>` — eigener Reverse Proxy (homelab-gateway) oder `make up-standalone` mit Traefik

## Entwicklungs-Workflow

```bash
make dashboard        # API neu bauen + starten (nach Code-Änderungen in api/)
make analytics        # Analytics-Service neu bauen + starten (nach Code-Änderungen in ml-service/)
make up               # Alle Services starten
make reset            # Alles löschen + DB neu aufsetzen (löscht alle User!)
make sync             # Garmin-Sync sofort auslösen (nicht auf 6 Uhr warten)
make tailwind-build   # Tailwind CSS neu bauen (nach Template-Änderungen)
make logs-dashboard   # API-Logs live
make logs-analytics   # Analytics-Service-Logs live
make logs-sync        # Sync-Service-Logs live
make logs-all         # Alle Logs zusammen
make migrate          # DB-Migrationen ausführen
make db               # psql-Shell (liest DB_APP_USER aus env/.env)
```

## Verzeichnisstruktur

```
api/src/
├── main.py              App-Setup + Router-Registrierung
├── deps.py              Settings (Pydantic), require_user(), Limiter, Templates
├── evidence_catalog.py  Thin Loader → liest api/src/data/evidence_catalog.json
├── mail.py              E-Mail-Helpers: send_lockout/reset/verify_email via Resend API
├── training_load.py     Banister TRIMP für Physical Energy (Edwards 1993)
├── data/
│   └── evidence_catalog.json  Evidence-Catalog aller 21 Metriken (Level, EN-62366-Felder)
├── db/
│   ├── __init__.py      Re-exports aller DB-Funktionen
│   ├── pool.py          asyncpg Connection Pool
│   ├── users.py         User-Queries (create, get, delete, export, consent, …)
│   ├── activities.py    Aktivitäts-Queries + RPE
│   ├── health.py        daily/sleep/hrv/readiness/training-status/energy Queries
│   ├── ml.py            ML-Predictions lesen/schreiben, ml-status
│   ├── seizures.py      Anfallsereignisse (Epilepsie-Modus, V15)
│   └── glucose.py       Glukose-Readings (Libre-User, V9)
├── routes/
│   ├── auth.py          /login, /register, /auth/*, /logout (consent, 12-Zeichen-PW) — E-Mail via src.mail
│   ├── account.py       /account/delete (DSGVO Art. 17), /account/export (DSGVO Art. 20)
│   ├── api.py           Alle /api/* JSON-Endpunkte
│   ├── garmin.py        /garmin/link, /garmin/unlink
│   ├── libre.py         /libre/link, /libre/unlink
│   └── pages.py         /dashboard, /settings, /metrics/*, /help, /epilepsy + öffentliche Seiten
├── garmin/
│   ├── __init__.py
│   └── client.py        Garmin Connect Client (Token-Login)
├── libre/
│   └── client.py        LibreLinkUp Client (pylibrelinkup)
└── templates/           Jinja2 Templates (login, register, dashboard, activity, settings,
                         metrics, metrics_overview, help, epilepsy, privacy, terms, imprint, …)

sync-service/src/
├── main.py           APScheduler + Sync-Loop pro User (Garmin täglich, Libre 5-min)
├── config.py         Settings (Pydantic): DB-Credentials, SYNC_HOUR, FERNET_KEY
├── crypto.py         Fernet: fernet_encrypt/decrypt, serialize/restore_token_dir
├── domain/
│   ├── __init__.py
│   └── models.py
├── garmin/
│   ├── __init__.py
│   ├── client.py
│   └── mapper.py
├── libre/
│   ├── client.py
│   └── mapper.py
└── repositories/
    ├── __init__.py
    ├── base.py
    └── timescale.py  TimescaleRepository (upsert, bulk_insert)

ml-service/src/
├── main.py              APScheduler + Orchestrierung (run_inference/run_training/run_on_request/run_all_users)
├── inference_anomaly.py _run_anomaly_* (5×) + _run_anomaly_for + _run_correlations
├── inference_models.py  _run_readiness/battery_pattern/energy/training_effect/sleep/hrv/body_battery/running
├── config.py            Settings (DB_APP_USER/PASSWORD, MODEL_DIR, ML_INFER_HOUR)
├── db/
│   ├── __init__.py      Re-Exports aller öffentlichen Symbole (from db import … bleibt kompatibel)
│   ├── pool.py          asyncpg Connection Pool (init_pool, close_pool, get_pool)
│   ├── users_ml.py      User-Queries + ML-Management + save_prediction/get_yesterday_prediction
│   ├── health.py        Sleep, HRV, Daily-Metrics, SPO2, Body-Battery, Stress Queries
│   └── activities.py    Activity-TRIMP, Features, Correlation-Pairs, Running-Economy Queries
├── backfill.py          Prediction-Backfill (make backfill-battery / backfill-energy)
└── models/
    ├── anomaly.py         Z-Score: resting_hr, spo2, sleep_duration, steps, stress
    ├── correlation.py     Pearson r: sleep→HRV, sleep→RHR, body battery→RHR (min. 10 Paare)
    ├── readiness.py       RandomForestRegressor: 8 Features → Score (min. 30 Paare)
    ├── battery_pattern.py k-Means: Body-Battery-Tagesmuster (frisch/erschöpft/…)
    ├── body_battery.py    Fresh-State-Modell: Schlafqualität(40%) + HRV(25%) + Drain
    ├── energy_metrics.py  Physical (CTL/TSB), Autonomic (HRV-σ), Cognitive (Schlafschuld)
    ├── hrv_status.py      BALANCED/UNBALANCED/LOW/POOR Klassifikation
    ├── sleep_score.py     Custom Sleep Score (Phasen + Dauer)
    ├── intensity_minutes.py  WHO-Intensitätsminuten (moderat/intensiv)
    ├── training_load.py   ACWR (7d/42d-Ratio) + Training Monotony
    ├── stress_metrics.py  Stress-Score (HRV-basiert, invertierte autonome Balance)
    ├── spo2_metrics.py    SpO2-Trendanalyse + Apnoe-Flag (min_spo2 < 90%)
    ├── sleep_metrics.py   Sleep Consistency Score (zirkuläre σ-Statistik)
    ├── training_effect.py Banister TRIMP → atan-Skalierung 0–5
    ├── running_economy.py GCT / Vertikal-Oszillation / Vertical Ratio → Score
    └── hrv_recovery.py    HRV-Erholungstrajektorie nach Belastung (ΔHRV/Tag)

db/migrations/        Flyway: V1–V20 (V15 Epilepsie, V19 Consents, V20 user_tokens)
```

Die `__init__.py`-Dateien in den sync-service-Sub-Paketen sind Pflicht — ohne sie erkennt mypy die
Namespace-Pakete nicht eindeutig und meldet Duplikat-Modul-Fehler (`domain.models` vs. `models`).

## Architektur-Entscheidungen

- **Kein Grafana** — eigenes Dashboard mit fetch + Chart.js (kein Build-Step, kein Framework)
- **Kein Authelia** — eigene Register/Login-Routen in FastAPI mit bcrypt
- **Kein JWT** — Starlette SessionMiddleware (signiertes Cookie, httpOnly, secure)
- **bcrypt direkt** (nicht passlib) — passlib inkompatibel mit bcrypt>=4.0
- **Starlette 1.0 TemplateResponse-API** — `TemplateResponse(request, "name.html", ctx)` nicht die alte Form mit `{"request": request}` im Context
- **Garmin-Passwörter nie speichern** — Login-Token Fernet-verschlüsselt in `user_tokens`-Tabelle (V20)
- **asyncpg direkt** (kein ORM) — alle Queries als Prepared Statements in `ml-service/src/db/` (Package)

## mypy-Quirks

- **garminconnect hat keine Type-Stubs** → Client-Attribute als `Any` annotieren (nicht `garminconnect.Garmin | None`), sonst union-attr-Fehler auf allen Method-Calls
- **asyncpg Pool optional** → `_db`-Property in `TimescaleRepository` mit `if self._pool is None: raise RuntimeError(...)` → gibt `asyncpg.Pool` zurück (nicht `Pool | None`) — verhindert union-attr-Fehler
- **Pydantic BaseSettings()** liest Env-Vars → mypy sieht keine Argumente → `Settings()  # type: ignore[call-arg]`
- **slowapi RateLimitExceeded handler** → `app.add_exception_handler(...)` erwartet anderen Typ → `# type: ignore[arg-type]`
- **CI mypy** läuft mit `--explicit-package-bases` (working-directory: api/ oder sync-service/) — lokal läuft mypy vom Projekt-Root aus ohne dieses Flag

## CI/CD Pipeline

Jobs in `.github/workflows/ci.yml`:

| Job | Tool | Was |
| --- | ---- | --- |
| `lint` | ruff | Check + Format-Check (Python) |
| `js-lint` | Biome 2.x | Lint + Format-Check (JS: api/src/static/) |
| `security` | gitleaks + pip-audit + bandit | Secret-Scan, SCA, SAST |
| `typecheck` | mypy | api/ + sync-service/ + ml-service/ mit `--explicit-package-bases` |
| `test` | pytest | api/tests/ + sync-service/tests/ + ml-service/tests/ |
| `js-test` | Vitest | api/src/static/ JS Unit-Tests mit Coverage |
| `e2e` | Playwright | E2E Smoke-Tests auf test-docker-compose Stack (api-test auf Port 8001) |
| `trivy` | trivy | Docker-Image-Scan für api + sync + ml, CRITICAL+HIGH (`ignore-unfixed: true`) |

## Pre-commit Hooks

Reihenfolge in `.pre-commit-config.yaml`:

1. **gitleaks** — Secret-Scan (läuft als Erstes)
2. **pre-commit-hooks** — trailing-whitespace, end-of-file-fixer, check-yaml/json/toml, no-commit-to-branch
3. **ruff** — Lint + Fix
4. **ruff-format** — Format
5. **bandit** — SAST (`-r api/src/ sync-service/src/`, `pass_filenames: false`)
6. **detect-secrets** — Baseline `.secrets.baseline`
7. **mypy-api** (local) — `mypy api/src/ --ignore-missing-imports`
8. **mypy-sync** (local) — `mypy sync-service/src/ --ignore-missing-imports`
9. **mypy-ml** (local) — `mypy ml-service/src/ --ignore-missing-imports`

Wichtig: bandit und mypy als `pass_filenames: false` mit absoluten Pfaden vom Projekt-Root — sonst scannt bandit `src/` relativ und findet nichts.

## Datenbankschema — echte Spaltennamen

| Tabelle | Wichtige Spalten |
|---------|-----------------|
| `users` | `id`, `name`, `email`, `password_hash`, `failed_login_attempts`, `locked_until`, `email_verified_at`, `garmin_linked`, `garmin_email`, `is_active` |
| `activities` | `started_at` (nicht start_time!), `sport_type`, `duration_seconds`, `distance_meters`, `avg_hr` (nicht avg_heart_rate!), `calories` (nicht total_calories!), `aerobic_effect`, `anaerobic_effect` |
| `daily_summary` | `date`, `steps` (nicht total_steps!), `resting_hr`, `body_battery_high`, `body_battery_low` |
| `sleep_sessions` | `start_time`, `sleep_score`, `total_sleep_seconds` (nicht duration_seconds!) |
| `hrv_daily` | `hrv_last_night`, `hrv_weekly_avg` (nicht weekly_avg!), `hrv_status` (nicht status!) |
| `user_consents` | `user_id`, `consent_type` (`health_data`, `terms`, `age_16plus`), `accepted`, `timestamp`, `ip_address`, `privacy_policy_version` — DSGVO Art. 5(2) Audit-Log (V19) |

## JSON-API Endpoints (alle session-geschützt)

```
GET  /api/activities              Aktivitäten (Query: days=7, limit=500)
GET  /api/activities/{id}         Aktivität Detail + activity_records
GET  /api/daily?days=30           Tagesübersichten
GET  /api/sleep?days=14           Schlaf-Sessions
GET  /api/hrv                     letzter HRV-Eintrag
GET  /api/hrv/trend?days=30       HRV-Verlauf
GET  /api/training-status         letzter Trainingszustand
GET  /api/weekly?weeks=12         Wöchentliche Volumen-Aggregation (run_km, ride_km)
GET  /api/readiness               Readiness-Score 0-100 (regelbasiert, kein ML)
GET  /api/energy                  Energie-Scores: physical / autonomic / cognitive
GET  /api/ml-insights             Alle ML-Predictions: Anomalie, Korrelation, RF, Muster, …
GET  /api/ml-history?days=30      ML-Predictions-Verlauf
GET  /api/ml-status               ML-Service-Status (letzte Inferenz, Training, Modell-Metadaten)
GET  /api/sync-status             Sync-Service-Status (letzter erfolgreicher Sync)
POST /api/sync                    Garmin-Sync manuell auslösen
GET  /api/evidence                Evidence-Catalog aller Metriken (level, time_horizon, …)
GET  /api/seizures                Anfallsereignisse (nur Epilepsie-Modus)
POST /api/seizures                Neues Anfallsereignis speichern
GET  /api/seizures/risk           Aktueller regelbasierter Anfallsrisiko-Indikator
GET  /api/glucose?days=7          Glukose-Messwerte (nur Libre-User)
GET  /api/glucose/stats           Glukose-Statistiken (mean, CV, time-in-range)
PATCH /api/profile                Nutzerprofil: Geb.-Datum, Geschlecht (Banister-TRIMP)
PATCH /api/activities/{id}/rpe    RPE (Rate of Perceived Exertion) für Aktivität setzen
GET  /health                      Liveness-Check (kein Auth nötig)
```

## Seiten-Routen

```
# Auth (öffentlich)
GET/POST /login              Login (rate-limited 10/min, Account-Lockout nach 5 Fehlern)
GET/POST /register           Registrierung (3 Consent-Checkboxen, 12-Zeichen-PW)
GET      /auth/verify/{tok}  E-Mail-Verifizierung (signierter Token, 24h TTL)
POST     /auth/resend-verify Verifikations-E-Mail erneut senden
POST     /auth/reset-request Passwort-Reset anfordern
GET/POST /auth/reset/{tok}   Neues Passwort setzen
POST     /logout             Session beenden

# Geschützte Seiten (Session nötig)
GET  /dashboard              Dashboard (Chart.js, fetch)
GET  /activity/{id}          Aktivitäts-Detail (GPS-Karte, Charts)
GET  /settings               Einstellungen (Garmin/Libre-Link, Profil, Epilepsie-Modus)
GET  /metrics                Metriken-Übersicht (alle Metriken als Kacheln mit Evidence-Badge)
GET  /metrics/{name}         Metrik-Detail (Summary + Empfehlung + Chart + KPIs)
GET  /help                   Hilfe & Methodologie (durchsuchbar, Deep-Links /help#<metric-key>)
GET  /epilepsy               Anfallstagebuch + Risiko-Indikator (nur Epilepsie-Modus)
GET/POST /garmin/link        Garmin-Account verknüpfen
POST     /garmin/unlink      Garmin-Account trennen
GET/POST /libre/link         LibreLinkUp verknüpfen
POST     /libre/unlink       LibreLinkUp trennen
GET  /account/export         Daten-Export als JSON-Download (DSGVO Art. 20)
POST /account/delete         Konto löschen — E-Mail + Passwort nötig (DSGVO Art. 17)

# Öffentliche Seiten (keine Session nötig)
GET /privacy                 Datenschutzerklärung
GET /terms                   Nutzungsbedingungen
GET /imprint                 Impressum
GET /accessibility           Barrierefreiheitserklärung (BFSG)
```

## Env-Files (unter `env/`)

**`env/.env`** — shared, alle Services:
```
DB_USER=garmin
DB_PASSWORD=
DB_APP_USER=garmin_app
DB_APP_PASSWORD=
HOST_IP=your-domain.com
```

**`env/.env.api`** — nur API:
```
SESSION_SECRET=     # make gen-secrets
HTTPS_ONLY=true
TRIMP_LOOKBACK_DAYS=7
TRIMP_FORECAST_DAYS=7
RESEND_API_KEY=     # optional — leer = Reset-Link nur im Log
RESEND_FROM_EMAIL=onboarding@resend.dev
APP_BASE_URL=https://your-domain.com
```

**`env/.env.sync`** — nur sync-service:
```
SYNC_HOUR=6
SYNC_LOOKBACK_DAYS=30
SYNC_DAILY_DAYS=2
```

**`env/.env.ml`** — nur ml-service:
```
ML_INFER_HOUR=7
```

## Bewusste Tech-Debt-Entscheidungen (dokumentiert, nicht akuter Handlungsbedarf)

### ARCH-M2: Kein Service-Layer (Routes → DB direkt)

Routes importieren direkt aus `api/src/db/`. Eine dedizierte `api/src/services/`-Schicht fehlt.
Begründung: Solo-Projekt, Komplexität rechtfertigt Schicht nicht. Bei Wachstum (>3 Entwickler, komplexe Business-Logik) einführen.

### ARCH-M3: Traefik (standalone) nutzt self-signed TLS (kein ACME/Let's Encrypt)

`traefik/traefik.yml` hat kein `certificatesResolvers`. Traefik fällt auf selbst-signiertes Zertifikat zurück.
Für lokalen/internen Betrieb akzeptabel. Für öffentliches Deployment: `certificatesResolvers` mit ACME (HTTP-01 oder DNS-01) in `traefik/traefik.yml` ergänzen, oder eigenen Reverse Proxy (Caddy, nginx) mit automatischem HTTPS vorschalten.

### CICD-M3: Branch Protection nicht erzwingbar (privates Repo, Gratis-Plan)

Direktpushes auf `main` sind technisch möglich; GitHub erzwingt Status Checks nicht für private Repos ohne Pro-Plan.
Begründung: Solo-Projekt, Pre-commit-Hooks (`gitleaks`, `ruff`, `mypy`, `no-commit-to-branch`) sind die primäre Schutzebene. Upgrade auf Pro-Plan würde Branch Protection ermöglichen.

### QUAL-M2: Duplizierter GarminClient in api/ und sync-service/

`api/src/garmin/client.py` und `sync-service/src/garmin/client.py` sind absichtlich identisch gehalten (beide nutzen jetzt den vollständigen Sync-Client als Basis). Ein echtes shared-Package würde Docker-Build-Context-Änderungen und separates `pyproject.toml` erfordern. Bei signifikanter Divergenz: `shared/garmin_client/` als path-dependency in beiden Services einführen.

### ARCH-L2: Technisch-basierte db/-Ordnerstruktur

`api/src/db/` ist technisch strukturiert (kein Feature-Split). Eine Feature-basierte Struktur (`api/src/activities/`, `api/src/health/`) würde ~20 Dateien betreffen.
Begründung: Solo-Projekt, kein konkreter Nutzen gegenüber aktuellem Overhead. Refactoring erst bei deutlichem Wachstum der Codebasis.

### ARCH-L3: API nicht versioniert (kein `/api/v1/`-Präfix)

Alle Endpunkte laufen unter `/api/*` ohne Versionsprefix.
Begründung: Keine externen Consumer. Eine Versionierung würde alle Routen, JS-Fetch-Aufrufe und Tests brechen. Einführen erst wenn externe API-Stabilität verlangt wird.

### OBS-L1: Kein externes Uptime-Monitoring

Kein UptimeRobot oder ähnliches konfiguriert. Internes Docker-Healthcheck ist vorhanden (`/health`, `/ready`).
Reminder: `https://<APP_BASE_URL>/health` als Monitor-URL bei UptimeRobot konfigurieren.

### TEST-L1: Mock-Qualität für `require_user` in Route-Tests

Route-Tests patchen `src.deps.require_user` via `AsyncMock(return_value=TEST_USER)`. Kein `assert_called_once()`.
Begründung: Tests verifizieren korrektes Verhalten (Status-Codes, Response-Inhalte). Die Mock-Stelle ist korrekt (`src.deps`, nicht `fastapi`). `assert_called_once()` wäre redundant da jeder Auth-Fehler den Test bereits fehlschlagen lässt.

### TEST-L4: E2E `@requires_data`-Tests in CI still übersprungen

3 E2E-Tests (`test_formula_modal_opens_on_score_click`, `test_activity_detail_page_loads`, `test_formula_modal_opens_on_score_click`) benötigen einen Garmin-geseedeten Test-User und sind mit `@requires_data` markiert. Wenn `CI_HAS_DATA` nicht gesetzt ist, werden sie via `pytest.mark.skipif` übersprungen.
Begründung: Garmin-Sync erfordert echte API-Credentials und Daten, die in der Standard-CI nicht verfügbar sind. Die Tests laufen korrekt in Umgebungen mit `make test-seed && CI_HAS_DATA=true`. Für den Standard-CI-Lauf ist ein E2E-Smoke-Test mit registriertem User ausreichend.
