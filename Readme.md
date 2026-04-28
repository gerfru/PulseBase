# PulseBase

**Your fitness data. Your server. Your rules.**

PulseBase syncs your Garmin data to a self-hosted dashboard — multi-user, privacy-first, no cloud required.

## Features

- Automatic daily sync from Garmin Connect (activities, sleep, HRV, body battery, stress)
- Personal dashboard with charts in the browser
- Self-service registration — no admin needed
- Garmin passwords are **never stored** — token-only

## Architecture

```
Browser → Traefik (HTTPS) → FastAPI (Auth + Dashboard + API)
                                        ↓
                              TimescaleDB (PostgreSQL)
                                        ↑
                              Sync-Service (daily via Garmin Connect API)
```

| Service | Stack | Role |
|---------|-------|------|
| `api` | FastAPI + Python | Web app, auth, JSON API |
| `db` | TimescaleDB (PostgreSQL 16) | Time-series data storage |
| `sync-service` | Python + APScheduler | Daily Garmin sync |
| `traefik` | Traefik v3 | HTTPS reverse proxy |
| `flyway` | Flyway | Database migrations |

## Quickstart

### 1. Requirements

- Docker + Docker Compose
- WSL2 (Windows) or Linux
- `make`

### 2. Setup

```bash
# Generate session secret
make gen-secrets
# → paste value into .env at SESSION_SECRET

# Add garmin.local to Windows hosts file (Admin PowerShell)
Add-Content C:\Windows\System32\drivers\etc\hosts '127.0.0.1 garmin.local'

# Run database migrations
make migrate

# Start all services
make up
```

### 3. Register

```
https://garmin.local/register
```

### 4. Link Garmin

```
https://garmin.local/garmin/link
```

Enter your Garmin email + password — **not stored**, only the session token is kept.

### 5. Trigger sync

```bash
make sync
```

Then open: `https://garmin.local/dashboard`

## Commands

| Command | Description |
|---------|-------------|
| `make up` | Start all services (with build) |
| `make down` | Stop services |
| `make reset` | Wipe everything + fresh DB |
| `make migrate` | Run DB migrations |
| `make sync` | Trigger Garmin sync immediately |
| `make build-api` | Rebuild + restart API |
| `make logs` | Live API logs |
| `make logs-sync` | Live sync-service logs |
| `make logs-all` | Live logs for all services |
| `make status` | Container status |
| `make db` | Open psql shell |
| `make gen-secrets` | Generate SESSION_SECRET |

## Configuration (.env)

```bash
DB_USER=garmin
DB_PASSWORD=changeme

SESSION_SECRET=        # make gen-secrets

HOST_IP=garmin.local
SYNC_HOUR=6            # daily sync hour (24h)
SYNC_LOOKBACK_DAYS=30  # how many days to sync on first run
```

## Database Schema

| Table | Content |
|-------|---------|
| `users` | Accounts (name, email, bcrypt hash) |
| `activities` | Workouts (sport, duration, distance, HR, ...) |
| `daily_summary` | Daily stats (steps, resting HR, body battery, ...) |
| `sleep_sessions` | Sleep (duration, stages, score) |
| `hrv_daily` | HRV (last night, weekly avg, status) |
| `activity_records` | GPS + HR time-series per activity (hypertable) |
| `body_battery_intraday` | Body battery intraday (hypertable) |
| `stress_intraday` | Stress intraday (hypertable) |

## Security

- HTTPS via Traefik (self-signed cert — confirm browser warning once)
- Passwords stored as bcrypt hashes
- Session via signed cookie (httpOnly, secure)
- Garmin password wiped from memory immediately after token retrieval
