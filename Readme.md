# PulseBase

**Your fitness data. Your server. Your rules.**

PulseBase syncs your Garmin data to a self-hosted dashboard — multi-user, privacy-first, no cloud required.

## Features

- Automatic daily sync from Garmin Connect (activities, sleep, HRV, body battery, stress)
- Continuous glucose monitoring via LibreLinkUp (Libre 3, every 5 min) — optional
- Slate/Emerald dark instrument panel dashboard — tabbed layout (Training / Verlauf / Erholung), dark + light mode
- Unified Tagesstatus hero card: animated partial arc gauge (Readiness, Oura-style) with HRV/Schlaf/Puls contributor rows, Energie-Triptychon (Physisch / Autonom / Kognitiv), vitals strip
- Time navigation (← →) for all charts — browse any historical period without switching time range
- ML insights: anomaly detection (resting HR + SpO2 + stress Z-score), sleep→HRV Pearson correlation, Random Forest readiness prediction, Body Battery K-Means pattern, ACWR, Training Monotony, Running Economy, Sleep Consistency, SpO2 trend, and more — each with dedicated detail pages
- Metrics overview (`/metrics`) — all health metrics as tiles with color-coded Evidence Badges (Meta-Analysis / Replicated / Model)
- EN 62366-inspired metric disclosure: every metric shows intended use, limitations, time horizon, and actionable recommendation — methodology in searchable `/help` page with 20 articles
- Activity detail page with GPS map (Leaflet.js), HR/pace/elevation/cadence charts
- Training status tracking (PRODUCTIVE, MAINTAINING, RECOVERY, …)
- Weekly training volume overview (run km / ride km stacked bar)
- Epilepsy seizure diary with rule-based risk indicator (6 biomarker heuristics, optional feature)
- Central settings page — Garmin + LibreLinkUp connection management in one place
- Self-service registration — no admin needed
- Garmin and LibreLinkUp passwords are **never stored** — token-only

## Documentation

Two levels — pick what you need:

**Non-technical:**
- [ELI5 — Das System erklärt wie für ein Kind](docs/eli5.md) — Was PulseBase tut, wie ML funktioniert, was Passwörter nie gespeichert werden, was Trend-Pfeile bedeuten

**Technical:**
- [ML Deep Dive](docs/ml-deep-dive.md) — Algorithmen, Formeln, Thresholds, Trainings-Pipeline
- [Architecture](docs/architecture.md) — Services, Datenpfade, Netzwerk-Setup
- [Database](docs/database.md) — Schema, Hypertables, Spaltennamen, Queries
- [API Reference](docs/api.md) — Alle Endpunkte mit Request/Response-Format
- [Design Decisions](docs/design-decisions.md) — Warum kein Grafana, kein ORM, kein JWT, Caddy vs Traefik, ...
- [Setup Guide](docs/setup.md) — Vollständige Installationsanleitung

## Quickstart

```bash
cp env/.env.example env/.env              # fill in DB admin credentials + HOST_IP=your-domain.com
cp env/.env.app.example env/.env.app      # fill in DB_APP_USER, DB_APP_PASSWORD, FERNET_KEY (make gen-secrets)
cp env/.env.api.example env/.env.api      # fill in SESSION_SECRET (make gen-secrets, min. 32 chars) + APP_BASE_URL
cp env/.env.sync.example env/.env.sync
cp env/.env.ml.example env/.env.ml
make up                     # build + start all services (requires a reverse proxy on the proxy network)
# → https://your-domain.com/register
# → https://your-domain.com/garmin/link
make sync                   # trigger first sync immediately
# → https://your-domain.com/dashboard
```

**Standalone (with bundled Traefik, self-signed cert):**
```bash
make up-standalone          # starts with bundled Traefik — ideal for local/homelab use
```

**Homelab with [homelab-gateway](https://github.com/gerfru/homelab-gateway):** use `make up` after starting homelab-gateway.

Full walkthrough: [docs/setup.md](docs/setup.md)

## Commands

| Command | Description |
|---------|-------------|
| `make up` | Build images and start all services (requires homelab-gateway) |
| `make up-standalone` | Start with Traefik (standalone, no homelab-gateway needed) |
| `make down` | Stop services |
| `make reset` | Wipe everything + fresh DB (deletes all users!) |
| `make sync` | Trigger Garmin sync immediately |
| `make dashboard` | Rebuild + restart API (dashboard service) |
| `make analytics` | Rebuild + restart ML/analytics service |
| `make migrate` | Run DB migrations |
| `make logs-dashboard` | Live API logs |
| `make logs-analytics` | Live analytics-service logs |
| `make logs-sync` | Live sync-service logs |
| `make status` | Container status |
| `make db` | Open psql shell |
| `make gen-secrets` | Generate SESSION_SECRET (→ `env/.env.api`) and FERNET_KEY (→ `env/.env.app`) |
| `make secure-env` | Set `chmod 600` on all env files |
| `make test` | Run all unit tests (api + sync + ml) |
| `make test-e2e` | Run Playwright E2E tests (builds image first, starts test stack) |
| `make test-coverage` | Coverage report for all 3 services |

## Security

- HTTPS via Caddy (homelab-gateway) or Traefik (standalone) — self-signed cert, accept browser warning once
- Rate limiting on login (10/min), register (5/min), reset (3/h), Garmin/Libre link (5/h)
- Account lockout after 5 failed login attempts (15-minute automatic lockout + email notification)
- Email verification required after registration (signed token, 24h TTL, resend endpoint)
- CSRF protection on all state-changing forms (login, register, garmin/link, account/delete, password reset)
- Input validation via Pydantic on all API endpoints
- Passwords stored as bcrypt hashes (direct, no passlib), timing-safe dummy hash for non-existent users
- Session via signed cookie (httpOnly, secure, sameSite=Lax)
- Garmin password wiped from memory immediately after token retrieval — only Fernet-encrypted token stored
- Database not exposed on host network; app uses least-privilege DB user
- Security headers: HSTS, X-Frame-Options, CSP, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- SAST: bandit + semgrep (p/python + p/owasp-top-ten) in pre-commit and CI
- SCA: pip-audit via frozen uv.lock in CI; Trivy image scan (CRITICAL+HIGH → exit 1)
