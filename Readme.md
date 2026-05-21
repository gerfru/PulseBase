# PulseBase

**Your fitness data. Your server. Your rules.**

PulseBase syncs your Garmin data to a self-hosted dashboard — multi-user, privacy-first, no cloud required.

## Features

- Automatic daily sync from Garmin Connect (activities, sleep, HRV, body battery, stress)
- Continuous glucose monitoring via LibreLinkUp (Libre 3, every 5 min) — optional
- Slate/Emerald dark instrument panel dashboard — tabbed layout (Training / Verlauf / Erholung), dark + light mode
- Unified Tagesstatus hero card: animated partial arc gauge (Readiness, Oura-style) with HRV/Schlaf/Puls contributor rows, Energie-Triptychon (Physisch / Autonom / Kognitiv), vitals strip
- Time navigation (← →) for all charts — browse any historical period without switching time range
- ML insights: anomaly detection (resting HR Z-score), sleep→HRV Pearson correlation, Random Forest readiness prediction, Body Battery K-Means pattern — each with dedicated detail pages
- Activity detail page with GPS map (Leaflet.js), HR/pace/elevation/cadence charts
- Training status tracking (PRODUCTIVE, MAINTAINING, RECOVERY, …)
- Weekly training volume overview (run km / ride km stacked bar)
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

Requires [homelab-gateway](https://github.com/gerfru/homelab-gateway) running for `garmin.home.lab` DNS + HTTPS.

```bash
cp env/.env.example env/.env          # fill in DB credentials
cp env/.env.api.example env/.env.api  # fill in SESSION_SECRET (make gen-secrets)
cp env/.env.sync.example env/.env.sync
cp env/.env.ml.example env/.env.ml
make up                     # build + start all services
# → https://garmin.home.lab/register  (accept self-signed cert warning once)
# → https://garmin.home.lab/garmin/link
make sync                   # trigger first sync immediately
# → https://garmin.home.lab/dashboard
```

**Standalone (without homelab-gateway):**
```bash
make up-standalone          # starts with bundled Traefik instead
```

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
| `make gen-secrets` | Generate SESSION_SECRET (put in `env/.env.api`) |
| `make secure-env` | Set `chmod 600` on all env files |

## Security

- HTTPS via Caddy (homelab-gateway) or Traefik (standalone) — self-signed cert, accept browser warning once
- Rate limiting on login (10 requests/minute)
- Query parameter validation on all API endpoints
- Passwords stored as bcrypt hashes
- Session via signed cookie (httpOnly, secure)
- Garmin password wiped from memory immediately after token retrieval
- Database not exposed on host network
- Security headers (HSTS, X-Frame-Options, CSP, Referrer-Policy) via Caddy
