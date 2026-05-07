# Setup Guide

## Requirements

- Docker + Docker Compose
- WSL2 (on Windows)
- `make`
- A Garmin Connect account

---

## 1. Clone and configure

```bash
git clone https://github.com/gerfru/PulseBase.git
cd PulseBase
cp .env.example .env
```

Edit `.env`:

```bash
DB_USER=garmin
DB_PASSWORD=<strong password>

SESSION_SECRET=   # see step 2

HOST_IP=garmin.local
SYNC_HOUR=6
SYNC_LOOKBACK_DAYS=30
```

---

## 2. Generate session secret

```bash
make gen-secrets
```

Copy the output value into `.env` at `SESSION_SECRET`.

---

## 3. Add garmin.local to hosts file

Run in an **Admin PowerShell** on Windows:

```powershell
Add-Content C:\Windows\System32\drivers\etc\hosts '127.0.0.1 garmin.local'
```

---

## 4. Start services

```bash
make up
```

This builds the images, runs Flyway migrations, and starts all containers.
Wait until the API is ready (check with `make status` or `make logs`).

> **With Niles:** If Niles AI is running on the same host, Caddy handles HTTPS
> for PulseBase at `https://garmin.local`. No Traefik needed — `make up` is enough.
>
> **Standalone (without Niles):** Use `make up-standalone` to start with Traefik
> for self-signed HTTPS.

---

## 5. Register your account

Open `https://garmin.local/register` in a browser.

The browser will show a certificate warning (self-signed cert) — accept it once and it
won't appear again for this domain.

Create your account with name, email, and password (min. 8 characters).

---

## 6. Link Garmin

Go to `https://garmin.local/garmin/link` (or click the link on the home page).

Enter your Garmin Connect email and password. The password is used once to fetch a
session token and then deleted from memory — it is never stored anywhere.

---

## 7. Trigger the first sync

```bash
make sync
```

This restarts the sync-service, which immediately syncs the last `SYNC_LOOKBACK_DAYS`
days for all linked users. Watch progress with:

```bash
make logs-sync
```

After sync completes, go to `https://garmin.local/dashboard`.

---

## Day-to-day

The sync-service runs automatically every day at `SYNC_HOUR` (default: 6:00).
No manual action needed after initial setup.

---

## Commands

| Command | What it does |
|---------|-------------|
| `make up` | Build images and start all services (without Traefik) |
| `make up-standalone` | Build and start with Traefik (standalone, no Niles) |
| `make down` | Stop all services |
| `make reset` | Stop + wipe all data + re-run migrations (deletes all users!) |
| `make migrate` | Run pending Flyway migrations |
| `make sync` | Trigger Garmin sync immediately (don't wait for 6:00) |
| `make build-api` | Rebuild and restart only the API container |
| `make logs` | Live logs from the API |
| `make logs-sync` | Live logs from the sync-service |
| `make status` | Show container status |
| `make db` | Open a psql shell on the database |
| `make gen-secrets` | Generate a random SESSION_SECRET value |

---

## Adding a second user

1. Open `https://garmin.local/register` in a browser (or incognito window)
2. Register the new account
3. Log in and go to `/garmin/link`
4. Link the second Garmin account

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

**Garmin link fails:**
- Check credentials (try logging into connect.garmin.com in a browser)
- Garmin sometimes requires 2FA — if so, the initial link may time out

**Dashboard shows no data after sync:**
```bash
make logs-sync   # look for errors
make db          # then: SELECT count(*) FROM activities WHERE user_id = 1;
```

**Reset everything (nuclear option):**
```bash
make reset
```
This wipes the database and all tokens. All users must re-register and re-link.
