# Architecture

## Overview

PulseBase is a self-hosted fitness dashboard that syncs Garmin data to a local TimescaleDB
and serves it via a FastAPI web app. All processing happens on-premises — no cloud, no
third-party analytics.

### With homelab-gateway (default)

```
Browser (Tailnet device)
  │
  ▼
CoreDNS  (garmin.home.lab → Tailscale IP, via homelab-gateway repo)
  │
  ▼
Caddy  (HTTPS termination, shared proxy network, homelab-gateway repo)
  │
  ▼
FastAPI  (Auth + Dashboard HTML + JSON API)
  │
  ▼
TimescaleDB  (PostgreSQL 16 + TimescaleDB extension)
  ▲
  │
Sync-Service  (APScheduler, daily Garmin Connect pull)
  │
  ▼
Garmin Connect API  (external)
```

### Standalone (make up-standalone)

Traefik replaces Caddy for local use without homelab-gateway (e.g. Windows/WSL, no Tailscale).

```
Browser
  │
  ▼
Traefik v3  (HTTPS, self-signed cert, HTTP → HTTPS redirect)
  │
  ▼
FastAPI  ...
```

---

## Services

| Container | Image / Build | Role |
|-----------|--------------|------|
| `garmin-db` | `timescale/timescaledb:latest-pg16` | Time-series database |
| `garmin-flyway` | `flyway/flyway:latest` | Runs DB migrations on startup, then exits |
| `garmin-api` | `./api` (FastAPI) | Web app: auth, HTML pages, JSON API |
| `garmin-sync` | `./sync-service` (Python) | Daily Garmin data pull |

HTTPS is handled externally:
- **homelab-gateway** (default): Caddy on the shared `proxy` Docker network
- **Standalone**: Traefik (`make up-standalone`) included in PulseBase compose

---

## Startup Order

```
db (healthy)
  └─ flyway (migrate, then exits)
       ├─ api (starts after flyway completes)
       └─ sync-service (starts after flyway completes)
```

Flyway runs migrations on every start and exits. The API and sync-service only start
after migrations have completed successfully.

---

## Data Flow

### Sync (daily at configured hour)

```
Garmin Connect API
  → garminconnect library (token auth)
  → GarminClient wrapper
  → Mapper (Garmin JSON → Domain models)
  → TimescaleRepository
  → asyncpg
  → TimescaleDB
```

Data synced per user per day:
- Activities + GPS records (`activity_records`)
- Daily summary (steps, calories, stress, SpO2, body battery, resting HR)
- Sleep session (duration, stages, score)
- HRV (last night, weekly avg, status)
- Body battery intraday (every ~5 min)
- Stress intraday (every ~5 min)

### Web Request (dashboard)

```
Browser GET /dashboard
  → Caddy (TLS termination, homelab-gateway)
  → FastAPI (session check → render dashboard.html)
  → Browser executes fetch() calls to /api/*
  → FastAPI JSON endpoints (session check → asyncpg query → JSON)
  → Chart.js renders charts
```

---

## Network

PulseBase services communicate on the internal `internal` Docker network by service name
(`db`, `api`, etc.). The `garmin-api` container also joins the external `proxy` network,
which is shared with homelab-gateway's Caddy container.

```
proxy (external Docker network)
  ├── gateway-caddy  (homelab-gateway)
  └── garmin-api     (PulseBase)

internal (PulseBase-only)
  ├── garmin-api
  ├── garmin-db
  ├── garmin-flyway
  └── garmin-sync
```

No ports are exposed to the host in the default setup — all traffic enters via Caddy
on the `proxy` network.

---

## Volumes

| Volume | Content |
|--------|---------|
| `timescale-data` | PostgreSQL data directory (persisted) |
| `garmin-tokens` | Garmin session tokens per user (`/app/tokens/{user_id}/`) |

Tokens are shared between `api` and `sync-service` via the same named volume.
