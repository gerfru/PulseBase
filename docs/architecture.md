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
CoreDNS / DNS (your-domain.com → server IP, via homelab-gateway or your DNS provider)
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
Sync-Service  (APScheduler, Garmin Connect pull every 2h)
  │
  ▼
Garmin Connect API  (external)
```

### Public SaaS (make up-public)

A bundled **Caddy** terminates TLS via Let's Encrypt for a public instance without
homelab-gateway. The overlay `docker-compose.public.yml` decouples `api` from the
external `proxy` network. See [deployment-public.md](deployment-public.md).

```
Internet
  │
  ▼
Caddy 2  (HTTPS via Let's Encrypt, HTTP → HTTPS redirect, :80/:443)
  │
  ▼
FastAPI  ...
```

---

## Services

| Container | Image / Build | Role |
|-----------|--------------|------|
| `pulsebase-db` | `timescale/timescaledb:2.x-pg16` (SHA-pinned) | Time-series database |
| `pulsebase-flyway` | `flyway/flyway:12` (SHA-pinned) | Runs DB migrations on startup, then exits |
| `pulsebase-api` | `./api` (FastAPI) | Web app: auth, HTML pages, JSON API |
| `pulsebase-sync` | `./sync-service` (Python) | Garmin data pull every 2h (Libre every 5 min) |
| `pulsebase-ml` | `./ml-service` (Python) | ML inference daily + training weekly |
| `pulsebase-backup` | `./backup` (`postgres:18-alpine` + shell) | Age-encrypted DB backups (`pg_dump` → `backups` volume) |

HTTPS:
- **homelab-gateway** (default, `make up`): Caddy on the shared `proxy` Docker network (Tailscale-only)
- **Public SaaS** (`make up-public`): bundled Caddy + Let's Encrypt via `docker-compose.public.yml`

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

### Sync (every 2 hours by default, configurable via `SYNC_INTERVAL_HOURS`)

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

### ML Inference (after every Garmin sync + daily fallback at `ML_INFER_HOUR`, default 7:00)

```
TimescaleDB
  → ml-service reads history (resting HR, sleep, HRV, activities, glucose)
  → anomaly.py         Z-score (resting HR, SpO2, stress, steps, sleep duration)
  → correlation.py     Pearson r (sleep→HRV, sleep→RHR, body-battery→RHR)
  → readiness.py       RandomForestRegressor: energy-composite target → score 0–100
  → battery_pattern.py K-Means clustering: body-battery intraday features → 3 patterns
  → energy_metrics.py  Physical (TSB), Autonomic (HRV σ-norm), Cognitive (sleep debt)
  → body_battery.py    Fresh-State model: sleep quality + HRV factor + drain
  → training_load.py   ACWR + Training Monotony
  → hrv_recovery.py    HRV recovery trajectory post-peak
  → sleep_metrics.py   Sleep consistency (circular σ on wake/sleep times)
  → spo2_metrics.py    SpO2 trend + apnea flag
  → stress_metrics.py  Stress score (HRV-based)
  → running_economy.py GCT / vertical oscillation / vertical ratio score
  → ml_predictions table (upsert per model, per user, per day)
  → /api/ml-insights exposes latest predictions to dashboard
```

ML model training (RandomForest, K-Means) runs once per week (Sunday 03:00 UTC).
Models are serialized atomically with `joblib` to a Docker volume (`ml-models`).
All other models are rule-based/algorithmic and run on every inference cycle.

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
(`db`, `api`, etc.). The `pulsebase-api` container also joins the external `proxy` network,
which is shared with homelab-gateway's Caddy container.

```
proxy (external Docker network)
  ├── gateway-caddy  (homelab-gateway)
  └── pulsebase-api     (PulseBase)

internal (PulseBase-only)
  ├── pulsebase-api
  ├── pulsebase-db
  ├── pulsebase-flyway
  ├── pulsebase-sync
  ├── pulsebase-ml
  └── pulsebase-backup
```

No ports are exposed to the host in the default setup — all traffic enters via Caddy
on the `proxy` network.

---

## Graceful Shutdown

Both sync-service and ml-service use an `asyncio.Event`-based SIGTERM pattern:

```python
shutdown_event = asyncio.Event()

def _on_sigterm() -> None:
    logger.info("shutdown.sigterm_received")
    shutdown_event.set()          # non-blocking — no scheduler.shutdown() here

loop.add_signal_handler(signal.SIGTERM, _on_sigterm)
await shutdown_event.wait()       # blocks until SIGTERM
scheduler.shutdown(wait=True)     # gracefully outside the signal handler
```

Docker Compose `stop_grace_period` values allow time for in-flight jobs:

| Service | `stop_grace_period` | Reason |
|---------|--------------------|-|
| api | 45s | uvicorn `--timeout-graceful-shutdown 30` + buffer |
| sync-service | 120s | long-running Garmin sync jobs |
| ml-service | 120s | ML inference/training |

---

## Health Checks

| Service | Endpoint / Mechanism | Notes |
|---------|---------------------|-------|
| api | `/ready` (HTTP 200 → DB ping + Flyway check) | Dockerfile + Compose both use `/ready` |
| api | `/health` (HTTP 200 → `{"status":"ok"}`) | Liveness only — no DB call |
| sync-service | `/health` on `:8080` (HTTP server) | Compose healthcheck `urllib.request.urlopen('http://localhost:8080/health')`; `/tmp/sync_alive` sentinel still touched as internal heartbeat |
| ml-service | `/health` on `:8080` (HTTP server) | Compose healthcheck `urllib.request.urlopen('http://localhost:8080/health')`; `/tmp/ml_alive` sentinel still touched as internal heartbeat |

---

## Volumes

| Volume | Content |
|--------|---------|
| `timescale-data` | PostgreSQL data directory (persisted) |
| `ml-models` | Serialized scikit-learn models (`joblib`) for ML inference |
| `backups` | Age-encrypted DB backup archives written by `backup` service |

Session tokens (Garmin, LibreLink) are stored Fernet-encrypted in the `user_tokens` DB table — no separate Docker volume required. ML models are written by `ml-service` and read back on the next inference run.
