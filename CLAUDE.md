# Essential Rules

Die wichtigsten Regeln fuer jedes Projekt -- kompakt genug fuer CLAUDE.md.
Ausfuehrlichere Regeln: `./claude/app-rules.md` (importiert unten)

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

---

@./claude/app-rules.md

---

# Garmin Dashboard — Projektspezifisch

## Stack

FastAPI · TimescaleDB (PostgreSQL 16) · Docker Compose · Chart.js · scikit-learn
Zugriff: `https://garmin.home.lab` (via homelab-gateway) oder `make up-standalone` mit Traefik

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
├── main.py           App-Setup + Router-Registrierung
├── db/
│   ├── __init__.py   Re-exports aller DB-Funktionen
│   ├── users.py      User-Queries (create, get, delete, export, consent, …)
│   └── pool.py       asyncpg Connection Pool
├── routes/
│   ├── auth.py       /login, /register, /auth/*, /logout (inkl. consent_health, 12-Zeichen-PW)
│   ├── account.py    /account/delete (DSGVO Art. 17), /account/export (DSGVO Art. 20)
│   └── pages.py      /privacy, /terms, /imprint (öffentlich, keine Session nötig)
├── garmin/
│   ├── __init__.py
│   └── client.py     Garmin Connect Client (Token-Login)
└── templates/        Jinja2 Templates (login, register, dashboard, activity, settings, privacy, terms, imprint, …)

sync-service/src/
├── main.py           APScheduler + Sync-Loop pro User
├── domain/
│   ├── __init__.py
│   └── models.py
├── garmin/
│   ├── __init__.py
│   ├── client.py
│   └── mapper.py
└── repositories/
    ├── __init__.py
    ├── base.py
    └── timescale.py  TimescaleRepository (upsert, bulk_insert)

ml-service/src/
├── main.py           APScheduler: Inference täglich (ML_INFER_HOUR), Training Sonntag 3h
├── config.py         Settings (DB_APP_USER/PASSWORD, MODEL_DIR, ML_INFER_HOUR)
├── db.py             asyncpg: Trainingsdaten laden + Predictions speichern
└── models/
    ├── anomaly.py    Z-Score auf Resting-HR (30-Tage-Rolling-Baseline, min. 7 Punkte)
    ├── correlation.py Pearson r: sleep_score(N) → hrv_last_night(N+1) (min. 10 Paare)
    └── readiness.py  RandomForestRegressor: [hrv, sleep, resting_hr] → Score (min. 30 Paare)

db/migrations/        Flyway: V1-V5 Schema, V6 sync_trigger, V7 app_user, V8 ml_predictions
```

Die `__init__.py`-Dateien in den sync-service-Sub-Paketen sind Pflicht — ohne sie erkennt mypy die
Namespace-Pakete nicht eindeutig und meldet Duplikat-Modul-Fehler (`domain.models` vs. `models`).

## Architektur-Entscheidungen

- **Kein Grafana** — eigenes Dashboard mit fetch + Chart.js (kein Build-Step, kein Framework)
- **Kein Authelia** — eigene Register/Login-Routen in FastAPI mit bcrypt
- **Kein JWT** — Starlette SessionMiddleware (signiertes Cookie, httpOnly, secure)
- **bcrypt direkt** (nicht passlib) — passlib inkompatibel mit bcrypt>=4.0
- **Starlette 1.0 TemplateResponse-API** — `TemplateResponse(request, "name.html", ctx)` nicht die alte Form mit `{"request": request}` im Context
- **Garmin-Passwörter nie speichern** — nur Login-Token in `/app/tokens/{user_id}/`
- **asyncpg direkt** (kein ORM) — alle Queries als Prepared Statements in `db.py`

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
| `lint` | ruff | Check + Format-Check |
| `security` | gitleaks + pip-audit + bandit | Secret-Scan, SCA, SAST |
| `typecheck` | mypy | api/ + sync-service/ + ml-service/ mit `--explicit-package-bases` |
| `test` | pytest | sync-service/tests/ + ml-service/tests/ |
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
| `user_consents` | `user_id`, `consent_type` (`health_data`), `accepted`, `timestamp`, `ip_address`, `privacy_policy_version` — DSGVO Art. 5(2) Audit-Log (V19) |

## JSON-API Endpoints (alle session-geschützt)

```
GET /api/activities              Aktivitäten (Query: days=7, limit=500)
GET /api/activities/{id}         Aktivität Detail + activity_records
GET /api/daily?days=30           Tagesübersichten
GET /api/sleep?days=14           Schlaf-Sessions
GET /api/hrv                     letzter HRV-Eintrag
GET /api/hrv/trend?days=30       HRV-Verlauf
GET /api/training-status         letzter Trainingszustand
GET /api/weekly?weeks=12         Wöchentliche Volumen-Aggregation (run_km, ride_km)
GET /api/readiness               Readiness-Score 0-100 (regelbasiert, kein ML)
GET /api/ml-insights             ML-Ergebnisse (Anomalie, Korrelation, RF-Prognose)
```

## Seiten-Routen

```
GET /dashboard               Dashboard (Chart.js, fetch)
GET /activity/{id}           Aktivitäts-Detail (GPS-Karte, Charts)
GET /garmin/link             Garmin-Account verknüpfen
GET /account/export          Daten-Export als JSON-Download (DSGVO Art. 20)
POST /account/delete         Konto löschen — E-Mail + Passwort nötig (DSGVO Art. 17)
GET /privacy                 Datenschutzerklärung (öffentlich)
GET /terms                   Nutzungsbedingungen (öffentlich)
GET /imprint                 Impressum (öffentlich)
```

## Env-Files (unter `env/`)

**`env/.env`** — shared, alle Services:
```
DB_USER=garmin
DB_PASSWORD=
DB_APP_USER=garmin_app
DB_APP_PASSWORD=
HOST_IP=garmin.home.lab
```

**`env/.env.api`** — nur API:
```
SESSION_SECRET=     # make gen-secrets
HTTPS_ONLY=true
TRIMP_LOOKBACK_DAYS=7
TRIMP_FORECAST_DAYS=7
RESEND_API_KEY=     # optional — leer = Reset-Link nur im Log
RESEND_FROM_EMAIL=onboarding@resend.dev
APP_BASE_URL=https://garmin.home.lab
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
