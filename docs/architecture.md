# Architecture

## Overview

PulseBase is a self-hosted fitness dashboard that syncs Garmin data to a local TimescaleDB
and serves it via a FastAPI web app. All processing happens on-premises — no cloud, no
third-party analytics.

```
Browser
  │
  ▼
Traefik v3  (HTTPS reverse proxy, auto-redirect HTTP → HTTPS)
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

## Services

| Container | Image / Build | Role |
|-----------|--------------|------|
| `garmin-db` | `timescale/timescaledb:latest-pg16` | Time-series database |
| `garmin-flyway` | `flyway/flyway:latest` | Runs DB migrations on startup |
| `garmin-traefik` | `traefik:v3` | HTTPS termination, HTTP→HTTPS redirect |
| `garmin-api` | `./api` (FastAPI) | Web app: auth, HTML pages, JSON API |
| `garmin-sync` | `./sync-service` (Python) | Daily Garmin data pull |

## Startup Order

```
db (healthy)
  └─ flyway (migrate, then exits)
       ├─ api (starts after flyway completes)
       └─ sync-service (starts after flyway completes)
```

Flyway runs migrations on every start and exits. The API and sync-service only start
after migrations have completed successfully.

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
  → Traefik (TLS termination)
  → FastAPI (session check → render dashboard.html)
  → Browser executes fetch() calls to /api/*
  → FastAPI JSON endpoints (session check → asyncpg query → JSON)
  → Chart.js renders charts
```

## Volumes

| Volume | Content |
|--------|---------|
| `timescale-data` | PostgreSQL data directory (persisted) |
| `garmin-tokens` | Garmin session tokens per user (`/app/tokens/{user_id}/`) |

Tokens are shared between `api` and `sync-service` via the same named volume.

## Network

All inter-service communication is on the internal Docker network by service name
(`db`, `api`, etc.). Only Traefik exposes ports 80 and 443 to the host.
Port 8080 (Traefik dashboard) is also exposed for local debugging.
