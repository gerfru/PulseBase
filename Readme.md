# PulseBase

**Your fitness data. Your server. Your rules.**

PulseBase syncs your Garmin data to a self-hosted dashboard — multi-user, privacy-first, no cloud required.

## Features

- Automatic daily sync from Garmin Connect (activities, sleep, HRV, body battery, stress)
- Glassmorphism dashboard — mesh gradient background, frosted glass cards, dark + light mode
- Readiness score (rule-based 0–100) as hero card with HRV, sleep, body battery, stress factors
- ML Einblicke widget — anomaly detection (resting HR Z-score), sleep→HRV correlation, Random Forest readiness prediction
- Activity detail page with GPS map (Leaflet.js), HR/pace/elevation/cadence charts
- Training status tracking (PRODUCTIVE, MAINTAINING, RECOVERY, …)
- Weekly training volume overview (run km / ride km stacked bar)
- Self-service registration — no admin needed
- Garmin passwords are **never stored** — token-only

## Documentation

- [Architecture](docs/architecture.md) — Services, data flow, network setup
- [Design Decisions](docs/design-decisions.md) — Why no Grafana, no ORM, no JWT, Caddy vs Traefik, ...
- [Database](docs/database.md) — Schema, hypertables, column names, useful queries
- [API Reference](docs/api.md) — All endpoints with request/response format
- [Setup Guide](docs/setup.md) — Full installation walkthrough

## Quickstart

Requires [homelab-gateway](https://github.com/gerfru/homelab-gateway) running for `garmin.home.lab` DNS + HTTPS.

```bash
cp .env.example .env        # fill in DB_PASSWORD and SESSION_SECRET (make gen-secrets)
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
| `make build-api` | Rebuild + restart API |
| `make logs` | Live API logs |
| `make logs-sync` | Live sync-service logs |
| `make status` | Container status |
| `make db` | Open psql shell |
| `make gen-secrets` | Generate SESSION_SECRET |

## Security

- HTTPS via Caddy (homelab-gateway) or Traefik (standalone) — self-signed cert, accept browser warning once
- Rate limiting on login (10 requests/minute)
- Query parameter validation on all API endpoints
- Passwords stored as bcrypt hashes
- Session via signed cookie (httpOnly, secure)
- Garmin password wiped from memory immediately after token retrieval
- Database not exposed on host network
- Security headers (HSTS, X-Frame-Options, CSP, Referrer-Policy) via Caddy
