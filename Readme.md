# PulseBase

**Your fitness data. Your server. Your rules.**

PulseBase syncs your Garmin data to a self-hosted dashboard — multi-user, privacy-first, no cloud required.

## Features

- Automatic daily sync from Garmin Connect (activities, sleep, HRV, body battery, stress)
- Personal dashboard with charts in the browser
- Self-service registration — no admin needed
- Garmin passwords are **never stored** — token-only

## Documentation

- [Architecture](docs/architecture.md) — Services, data flow, startup order
- [Design Decisions](docs/design-decisions.md) — Why no Grafana, no ORM, no JWT, ...
- [Database](docs/database.md) — Schema, hypertables, column names, useful queries
- [API Reference](docs/api.md) — All endpoints with request/response format
- [Setup Guide](docs/setup.md) — Full installation walkthrough
- [Roadmap](docs/roadmap.md) — Historical import, ML/analytics, planned features

## Quickstart

```bash
cp .env.example .env        # fill in DB_PASSWORD and SESSION_SECRET (make gen-secrets)
make up                     # build + start all services
# → https://garmin.local/register  (accept self-signed cert warning once)
# → https://garmin.local/garmin/link
make sync                   # trigger first sync immediately
# → https://garmin.local/dashboard
```

Full walkthrough: [docs/setup.md](docs/setup.md)

## Commands

| Command | Description |
|---------|-------------|
| `make up` | Build images and start all services |
| `make up-standalone` | Start with Traefik (standalone, no Niles) |
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

- HTTPS via Caddy (with Niles) or Traefik (standalone) — self-signed cert, confirm browser warning once
- Rate limiting on login (10 requests/minute)
- Query parameter validation on all API endpoints
- Passwords stored as bcrypt hashes
- Session via signed cookie (httpOnly, secure)
- Garmin password wiped from memory immediately after token retrieval
- Database not exposed on host network
