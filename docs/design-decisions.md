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

## CSS: Tailwind CDN + custom style.css

Templates use **Tailwind CSS** (CDN Play Script, no build step required for dev) for layout,
spacing, and color utilities. A companion `api/src/static/style.css` (~600 lines) handles
only the classes that JavaScript generates dynamically at runtime (`.card`, `.badge-*`,
`.metric-tile-*`, `.toast`, `.hero-grid`, `.hero-chip`, `.nav-bar`, etc.) — these cannot be
inlined because they are constructed in dashboard.js/activity.js/metrics.js via string
concatenation.

**Light / Dark theme:**
- `theme-init.js` runs before Tailwind CDN to set `.dark` on `<html>` from `localStorage`
  (key `pb-theme`) — prevents FOUC
- `tailwind.config.js` sets `darkMode: 'class'`; all templates use `dark:` variants
- Toggle switch in Settings page writes to `localStorage` and toggles the class live

**Production (Phase 5 — pending):**
Tailwind CLI standalone binary (no Node.js) in the `api` Dockerfile generates a minified
`style.css` from `input.css`, replacing the CDN script. Not yet implemented.

**Sport type display:**
`subActivityType.typeKey` is read before `activityType.typeKey` so activities like
Krafttraining, Yoga, Indoor Cycling get their specific label instead of "Other".
German display labels are mapped in `dashboard.js` and `activity.js` (`SPORT_LABEL`).

### Slate/Emerald Dark Instrument Panel

The dashboard uses a "Dark Instrument Panel" aesthetic — precision-focused, information-dense,
inspired by WHOOP and Bloomberg Terminal. Replaced the earlier glassmorphism style.

- Slate background (`#0f172a` / `#1e293b`) with subtle emerald radial gradient accents
- Cards: flat with `rgba(255,255,255,0.04–0.08)` fill + `1px` border — no blur
- Accent colors: emerald green (#22c55e), amber (#f59e0b), red (#ef4444) for score-based
  color coding — only three semantic colors used throughout the dashboard

---

## Hero Section: Unified Tagesstatus Card

**Phase:** Implemented (replaced the 4 separate Bento cards).

Four separate cards (Readiness, Heute, Energie, ML Status) were merged into a single
"Tagesstatus" card using a WHOOP-style 3-tier hierarchy:

**Tier 1 (left) — Readiness Ring:**
SVG ring animates on load (`stroke-dashoffset`, 800ms ease-out). Score counts up from 0
via `requestAnimationFrame` (600ms). Ring color and fill determined by score: ≥75 green,
≥50 amber, <50 red.

**Tier 2 (right) — Energie-Triptychon + Vitals:**
Three energy rows (Physisch / Autonom / Kognitiv) with color-coded dots, scores, sub-labels
(TSB, σ-deviation, sleep debt hours), and arrow links. A 2×2 vitals strip below shows
steps, sleep score, HRV avg, resting HR.

**Tier 3 (bottom) — ML Status Chips:**
Compact badge pills for: HRV status (BALANCED/UNBALANCED/LOW/POOR), Z-score anomaly,
RF readiness forecast, Body Battery pattern, training effect. Only rendered when data exists.

**Layout:** Two-column grid (ring | right-panel) on desktop, stacked on mobile ≤600px.

---

## Time Navigation (← → Period Shifting)

**Phase:** Implemented.

The 7T/14T/30T/90T/365T buttons set the window size. The ← → nav bar (between tabs and
chart panels) shifts that window into the past via a `currentOffset` integer (0 = current
period, 1 = one period back, etc.).

`getEndDate()` computes `today - offset × days` as an ISO date string.
All 6 data endpoints (`/api/activities`, `/api/daily`, `/api/sleep`, `/api/hrv/trend`,
`/api/weekly`, `/api/ml-history`) accept `end_date` as an optional query parameter.
The DB layer uses a date-range `WHERE date >= end_date - days AND date <= end_date`
instead of the previous `WHERE date >= NOW() - interval`.

Switching time range (7T→30T etc.) resets offset to 0.
The forward button (`→`) is disabled when offset=0.

---

## ML as a separate container

The ML inference and training logic runs in a dedicated `ml-service` container rather than
inside the API or sync-service. Reasons:

- **Dependency isolation**: scikit-learn, scipy, numpy, and joblib don't belong in the
  API image — they'd triple its size and have no business there
- **Independent schedule**: inference runs daily at 7:00, training weekly on Sundays —
  completely decoupled from the Garmin sync schedule (6:00) and the API
- **Failure isolation**: a broken model or training run doesn't affect the API or sync

The ML service writes results to `ml_predictions` in the shared TimescaleDB. The API reads
from that table via `/api/ml-insights` — the ML service and the API never talk directly.

### Rule-based score as Random Forest target

The RF readiness model is trained against the **rule-based readiness score** (the weighted
HRV/sleep/body-battery/stress formula), not a user-provided label. This means:

- Training data is always available — no labeling effort required
- The model learns to predict what the rule-based formula would output given tomorrow's inputs
- As more data accumulates, the RF can generalize across partial inputs better than the
  hard-coded formula does (which excludes missing components entirely)

### Z-score for anomaly detection (not IQR or isolation forest)

Z-score was chosen over more complex methods because:

- Resting HR is approximately normally distributed for a single individual over time
- The 30-day rolling baseline is short enough to track fitness changes, long enough to
  be stable
- Threshold of 1.5 σ is intentionally sensitive (early warning), not a strict outlier test
- Interpretable: the dashboard can show "1.3 σ above baseline" without further explanation

---

## TimescaleDB for intraday data

Regular PostgreSQL tables would work for daily summaries and activities. Intraday data
(body battery, stress every ~5 min = 288 rows/day/user) benefits from TimescaleDB:

- Hypertables partition data by time automatically
- Compression policy reduces storage by ~10x after the retention window
- Time-bucket aggregations (`time_bucket()`) are native and fast

Regular tables (`activities`, `daily_summary`, `sleep_sessions`, `hrv_daily`) don't need
hypertables — they're too small and queried differently.
