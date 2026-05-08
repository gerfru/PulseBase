# Design Decisions

Key architectural choices and the reasoning behind them.

---

## No Grafana

**Removed in Phase 4.**

Grafana requires a separate login and an admin to manually create user accounts. For a
2-person home network setup that's not acceptable UX. Replaced by a custom `/dashboard`
in FastAPI that serves HTML and loads data via `fetch()` + Chart.js. No build step, no
framework, no extra service.

---

## No Authelia

Initially considered for SSO. Dropped because it adds operational complexity (another
service, config files, LDAP or file-based users) that isn't justified for 2 users on a
home network. FastAPI handles auth directly with bcrypt + signed session cookies.

---

## No JWT

JWT adds stateless token management complexity that's unnecessary here. Starlette's
`SessionMiddleware` uses a signed, httpOnly, secure cookie — simpler, just as safe for
this use case, and sessions can be invalidated server-side by clearing the session store.

---

## bcrypt directly (not passlib)

`passlib` is incompatible with `bcrypt >= 4.0` and raises deprecation warnings. Using
`bcrypt` directly avoids the compatibility layer entirely.

```python
bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
bcrypt.checkpw(password.encode(), hashed.encode())
```

---

## asyncpg directly (no ORM)

All queries are written as prepared statements in `db.py`. No SQLAlchemy, no Tortoise,
no Prisma. Reasons:

- Full control over SQL (important for time-series queries with TimescaleDB-specific syntax)
- asyncpg is the fastest PostgreSQL async driver for Python
- The query surface is small and well-defined — an ORM would add more complexity than it removes
- Prepared statements prevent SQL injection by design

---

## Garmin passwords never stored

When a user links their Garmin account, the password is used once to fetch a session
token, then explicitly deleted from memory (`del garmin_password`). Only the token is
persisted in `/app/tokens/{user_id}/` (Docker volume). The sync-service authenticates
with the stored token on every run.

---

## Starlette 1.0 TemplateResponse API

FastAPI uses Starlette's Jinja2 integration. Since Starlette 1.0, the `TemplateResponse`
signature changed — `request` is the first positional argument, not part of the context
dict:

```python
# Correct (Starlette 1.0+)
templates.TemplateResponse(request, "page.html", {"key": "value"})

# Old form — raises deprecation warning
templates.TemplateResponse("page.html", {"request": request, "key": "value"})
```

---

## Flyway for migrations

Database schema changes are managed via Flyway versioned migrations (`V1__`, `V2__`, ...).
Flyway runs automatically on container startup and exits. This means:

- Schema is always in sync with the codebase
- Migrations are versioned and repeatable
- No manual SQL on the database — ever

---

## Caddy via homelab-gateway (not bundled Traefik)

HTTPS termination is handled by a separate [`homelab-gateway`](https://github.com/gerfru/homelab-gateway)
repo running Caddy on a shared `proxy` Docker network. PulseBase joins this network —
no ports are exposed on the host.

Benefits:
- One Caddy instance handles all self-hosted services (PulseBase, Niles, Vikunja, ...)
- `*.home.lab` subdomains resolve via CoreDNS + Tailscale Split DNS — no hosts file edits
- Security headers (`HSTS`, `X-Frame-Options`, `CSP`, etc.) defined once in a Caddy snippet

For standalone use without homelab-gateway (e.g. Windows/WSL): `make up-standalone`
starts Traefik alongside PulseBase. This is the fallback, not the default.

---

## Shared CSS design system (no inline styles, no framework)

All templates share a single `api/src/static/style.css` using CSS Custom Properties.
No Tailwind, no Bootstrap, no build step — just one file served by FastAPI's `StaticFiles`.

Benefits:
- Dark mode via `prefers-color-scheme` — zero JavaScript
- Design tokens in `:root` make color/spacing changes a one-line edit
- New templates start clean — no copy-pasting inline styles

Inline `<style>` blocks in templates are prohibited: CSP uses `'unsafe-inline'` only for
`style-src`, but keeping styles in `style.css` is enforced by convention so that a future
nonce-based CSP upgrade requires no template changes.

### Glassmorphism

The dashboard uses a glassmorphism aesthetic:
- `body::before` mesh gradient (3 radial blobs: indigo / violet / emerald)
- Cards: `background: rgba(30,41,59,.55)` + `backdrop-filter: blur(16px)` — requires a
  non-white body background in light mode (`#eef2f7`) for the blur to be visible
- Light mode: blobs at higher opacity (`.20/.15/.12`), card borders `rgba(148,163,184,.25)`

---

## TimescaleDB for intraday data

Regular PostgreSQL tables would work for daily summaries and activities. Intraday data
(body battery, stress every ~5 min = 288 rows/day/user) benefits from TimescaleDB:

- Hypertables partition data by time automatically
- Compression policy reduces storage by ~10x after the retention window
- Time-bucket aggregations (`time_bucket()`) are native and fast

Regular tables (`activities`, `daily_summary`, `sleep_sessions`, `hrv_daily`) don't need
hypertables — they're too small and queried differently.
