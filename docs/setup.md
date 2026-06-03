# Setup Guide

## Requirements

- Docker + Docker Compose
- `make`
- A Garmin Connect account
- [homelab-gateway](https://github.com/gerfru/homelab-gateway) running (optional, for homelab proxy setup)

> **Standalone (no homelab-gateway):** Use `make up-standalone` — starts Traefik alongside
> PulseBase. Suitable for Windows/WSL or any machine without homelab-gateway.

---

## 1. Clone and configure

```bash
git clone https://github.com/gerfru/PulseBase.git
cd PulseBase
cp env/.env.example env/.env
cp env/.env.app.example env/.env.app
cp env/.env.api.example env/.env.api
cp env/.env.sync.example env/.env.sync
cp env/.env.ml.example env/.env.ml
```

Edit `env/.env` (DB-Admin + Traefik, nur für Flyway/DB-Service):

```bash
DB_USER=garmin
DB_PASSWORD=<strong password>
HOST_IP=your-domain.com
```

Edit `env/.env.app` (Shared App-Credentials für api + sync-service + ml-service):

```bash
DB_APP_USER=garmin_app
DB_APP_PASSWORD=<strong password>
FERNET_KEY=<from make gen-secrets>
```

Edit `env/.env.sync`:

```bash
SYNC_INTERVAL_HOURS=2   # poll Garmin every X hours (default: 2)
SYNC_LOOKBACK_DAYS=30
SYNC_DAILY_DAYS=2
```

Edit `env/.env.ml`:

```bash
ML_INFER_HOUR=7   # hour (UTC) for daily ML inference; training runs Sunday 3:00
```

---

## 2. Generate secrets

```bash
make gen-secrets
```

Copy the output values:
- `SESSION_SECRET` → `env/.env.api` (min. 32 characters, required)
- `FERNET_KEY` → `env/.env.app` (used by all 3 app services for token encryption)

---

## 3. Start services

```bash
make up
```

This builds the images, runs Flyway migrations, and starts all containers.
The API container joins the external `proxy` network shared with homelab-gateway's Caddy.

Wait until the API is ready:
```bash
make status
make logs
```

> **Standalone (without homelab-gateway):** Use `make up-standalone` instead.
> This starts Traefik for HTTPS. Open `https://your-domain.com` and accept the
> self-signed certificate warning once.

---

## 4. Register your account

Open `https://your-domain.com/register` in a browser.

Caddy (via homelab-gateway) or Traefik (standalone) must be configured with ACME/Let's Encrypt for a valid TLS certificate. See `docs/architecture.md` for setup details.

Create your account with name, email, and password (min. 12 characters).
Check all three consent checkboxes (required):
- Health data processing (DSGVO Art. 9)
- Terms of Service
- Age confirmation ≥ 16 years (DSGVO Art. 8)

---

## 5. Verify your email

After registering you are redirected to `/login?verify=sent` (or `/login?verify=failed` if
the email service is not configured).

**If `RESEND_API_KEY` is set:** Check your inbox and click the verification link.

**If `RESEND_API_KEY` is not set (local/homelab):** The token is printed to the API log.
Copy the token from `make logs-dashboard` and open:
```
https://your-domain.com/auth/verify/<token>
```

If the link expires (24h TTL) or never arrived, use `/auth/resend-verify` to request a new one.

---

## 7. Link Garmin

Go to `https://your-domain.com/garmin/link` (or click the link on the dashboard).

Enter your Garmin Connect email and password. The password is used once to fetch a
session token and then deleted from memory — it is never stored anywhere.

---

## 8. First sync

After linking Garmin, a sync starts automatically within 1 minute (the link sets
`sync_requested = true`, the sync-service polls for it every minute). Watch progress:

```bash
make logs-sync
```

After sync completes, go to `https://your-domain.com/dashboard`.

---

## Day-to-day

The sync-service polls Garmin every `SYNC_INTERVAL_HOURS` (default: 2 hours).
No manual action needed after initial setup.

---

## Commands

| Command | What it does |
|---------|-------------|
| `make up` | Build images and start all services (requires homelab-gateway proxy network) |
| `make up-standalone` | Build and start with Traefik (standalone, no homelab-gateway needed) |
| `make down` | Stop all services |
| `make reset` | Stop + wipe all data + re-run migrations (deletes all users!) |
| `make migrate` | Run pending Flyway migrations |
| `make trigger-sync` | Request immediate Garmin sync for all users (no rebuild, processed within 1 min) |
| `make sync` | Rebuild sync-service + restart (triggers full backfill sync) |
| `make dashboard` | Rebuild and restart the API/dashboard container |
| `make analytics` | Rebuild and restart the ML analytics service |
| `make logs-dashboard` | Live logs from the API |
| `make logs-sync` | Live logs from the sync-service |
| `make logs-analytics` | Live logs from the ML analytics service |
| `make status` | Show container status |
| `make db` | Open a psql shell on the database |
| `make gen-secrets` | Generate SESSION_SECRET (→ `env/.env.api`) and FERNET_KEY (→ `env/.env.app`) |
| `make secure-env` | Set `chmod 600` on all env files |

---

## Adding a second user

1. Open `https://your-domain.com/register` in a browser (or incognito window)
2. Register the new account
3. Verify the email (see Step 5 above)
4. Log in and go to `/garmin/link`
5. Link the second Garmin account

The sync-service picks up all users with `garmin_linked = true` from the database
automatically on the next run.

---

## Troubleshooting

**API won't start / migrations fail:**
Check that the `db` container is healthy before the API starts.
```bash
make status
make logs
```

**`proxy` network not found:**
homelab-gateway must be running before `make up`. Start it first:
```bash
cd ../homelab-gateway && make up
```

**Garmin link fails:**
- Check credentials (try logging into connect.garmin.com in a browser)
- Garmin sometimes requires 2FA — if so, the initial link may time out

**Dashboard shows no data after sync:**
```bash
make logs-sync   # look for errors
make db          # then: SELECT count(*) FROM activities WHERE user_id = 1;
```

**Account locked after failed logins:**
After 5 failed attempts the account is locked for 15 minutes (auto-unlock). To unlock immediately:
```bash
make db
```
Then in psql:
```sql
UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE email = 'your@email.com';
```

**Reset everything (nuclear option):**
```bash
make reset
```
This wipes the database and all tokens. All users must re-register and re-link.
