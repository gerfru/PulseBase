# Essential Rules

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
- Keine Secrets in Error-Responses. Keine Secrets loggen
- `.env` nie committen, `.env.example` committen. Env-Validierung beim App-Start (crasht sofort wenn Variable fehlt)

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

- Pre-commit Hooks Pflicht: gitleaks → Lint+Fix → Format → Type Check
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

# Garmin Dashboard — Projektspezifisch

## Stack

FastAPI · TimescaleDB (PostgreSQL 16) · Docker Compose · Chart.js
Zugriff: `https://garmin.home.lab` (via homelab-gateway) oder `make up-standalone` mit Traefik

## Entwicklungs-Workflow

```bash
make build-api      # API neu bauen + starten (nach Code-Änderungen in api/)
make up             # Alle Services starten
make reset          # Alles löschen + DB neu aufsetzen (löscht alle User!)
make sync           # Garmin-Sync sofort auslösen (nicht auf 6 Uhr warten)
make logs           # API-Logs live
make logs-sync      # Sync-Service-Logs live
make migrate        # DB-Migrationen ausführen
make db             # psql-Shell (Achtung: DB_USER muss als Shell-Var gesetzt sein)
```

## Verzeichnisstruktur

```
api/src/
├── main.py           Alle Routen (Auth + Dashboard + /api/*)
├── db.py             Alle DB-Funktionen (asyncpg, kein ORM)
├── garmin/client.py  Garmin Connect Client (Token-Login)
└── templates/        Jinja2 Templates (login, register, dashboard, activity, link_garmin)

sync-service/src/
├── main.py           APScheduler + Sync-Loop pro User
├── garmin/           API-Client + Mapper (Garmin → Domain-Modelle)
└── repositories/     TimescaleRepository (upsert, bulk_insert)

db/migrations/        Flyway: V1 Schema, V2 User-Auth, V3 password_hash, V4 intensity+training_status, V5 training_effect
```

## Architektur-Entscheidungen

- **Kein Grafana** — eigenes Dashboard mit fetch + Chart.js (kein Build-Step, kein Framework)
- **Kein Authelia** — eigene Register/Login-Routen in FastAPI mit bcrypt
- **Kein JWT** — Starlette SessionMiddleware (signiertes Cookie, httpOnly, secure)
- **bcrypt direkt** (nicht passlib) — passlib inkompatibel mit bcrypt>=4.0
- **Starlette 1.0 TemplateResponse-API** — `TemplateResponse(request, "name.html", ctx)` nicht die alte Form mit `{"request": request}` im Context
- **Garmin-Passwörter nie speichern** — nur Login-Token in `/app/tokens/{user_id}/`
- **asyncpg direkt** (kein ORM) — alle Queries als Prepared Statements in `db.py`

## Datenbankschema — echte Spaltennamen

| Tabelle | Wichtige Spalten |
|---------|-----------------|
| `users` | `id`, `name`, `email`, `password_hash`, `garmin_linked`, `garmin_email`, `is_active` |
| `activities` | `started_at` (nicht start_time!), `sport_type`, `duration_seconds`, `distance_meters`, `avg_hr` (nicht avg_heart_rate!), `calories` (nicht total_calories!), `aerobic_effect`, `anaerobic_effect` |
| `daily_summary` | `date`, `steps` (nicht total_steps!), `resting_hr`, `body_battery_high`, `body_battery_low` |
| `sleep_sessions` | `start_time`, `sleep_score`, `total_sleep_seconds` (nicht duration_seconds!) |
| `hrv_daily` | `hrv_last_night`, `hrv_weekly_avg` (nicht weekly_avg!), `hrv_status` (nicht status!) |

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
```

## Seiten-Routen

```
GET /dashboard               Dashboard (Chart.js, fetch)
GET /activity/{id}           Aktivitäts-Detail (GPS-Karte, Charts)
GET /garmin/link             Garmin-Account verknüpfen
```

## .env Pflichtfelder

```
DB_USER=garmin
DB_PASSWORD=
SESSION_SECRET=     # make gen-secrets
HOST_IP=garmin.home.lab
SYNC_HOUR=6
SYNC_LOOKBACK_DAYS=30
```
