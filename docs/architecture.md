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
| `garmin-ml` | `./ml-service` (Python) | ML inference daily + training weekly |

HTTPS is handled externally:
- **homelab-gateway** (default): Caddy on the shared `proxy` Docker network
- **Standalone**: Traefik (`make up-standalone`) included in PulseBase compose

---

## Startup Order

```
db (healthy)
  └─ flyway (migrate, then exits)
       ├─ api (starts after flyway completes)
       ├─ sync-service (starts after flyway completes)
       └─ ml-service (starts after flyway completes)
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

### Libre Sync (every 5 minutes, if `libre_linked = true`)

```
LibreLinkUp API (EU endpoint)
  → pylibrelinkup (token auth, token loaded from user_tokens DB table)
  → libre/client.py  get_recent_glucose(hours=2)
  → libre/mapper.py  map_reading → {time, user_id, value_mgdl, trend, is_high, is_low}
  → TimescaleRepository.bulk_insert_glucose()
  → ON CONFLICT (user_id, time) DO NOTHING
  → glucose_readings hypertable
```

Libre tokens are stored encrypted in the `user_tokens` DB table (same as Garmin tokens).

### ML Inference (daily at configured hour, default 7:00)

```
TimescaleDB
  → ml-service reads history (resting HR, sleep, HRV)
  → anomaly.py    Z-score on resting HR
  → correlation.py  Pearson r: sleep score → next-day HRV
  → readiness.py  RandomForestRegressor: [hrv, sleep, resting_hr] → predicted score
  → ml_predictions table (upsert)
  → /api/ml-insights exposes results to dashboard
```

ML model training runs once per week (Sunday 3:00). Models are serialized with `joblib`
to a Docker volume (`ml-models`). Inference runs daily and writes to `ml_predictions`.

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
| `ml-models` | Serialized scikit-learn models (`joblib`) for ML inference |

Session tokens (Garmin, LibreLink) are stored Fernet-encrypted in the `user_tokens` DB table — no separate Docker volume required. ML models are written by `ml-service` and read back on the next inference run.
