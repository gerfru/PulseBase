# Design Decisions

Key architectural choices and the reasoning behind them.

---

## No Grafana

**Removed in Phase 4.**

Grafana requires a separate login and an admin to manually provision accounts — a non-starter
for a self-service, multi-user app where users register themselves. Replaced by a custom `/dashboard`
in FastAPI that serves HTML and loads data via `fetch()` + Chart.js. No build step, no
framework, no extra service.

---

## No Authelia

Initially considered for SSO. Dropped because it adds operational complexity (another
service, config files, LDAP or file-based users) that isn't justified for a single
self-hosted app with self-service registration. FastAPI handles auth directly with
bcrypt + signed session cookies, email verification, and account lockout.

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

All queries are written as prepared statements in the `db/` layer (`api/src/db/`, `ml-service/src/db/`). No SQLAlchemy, no Tortoise,
no Prisma. Reasons:

- Full control over SQL (important for time-series queries with TimescaleDB-specific syntax)
- asyncpg is the fastest PostgreSQL async driver for Python
- The query surface is small and well-defined — an ORM would add more complexity than it removes
- Prepared statements prevent SQL injection by design

---

## Garmin passwords never stored

When a user links their Garmin account, the password is used once to fetch a session
token, then explicitly deleted from memory (`del garmin_password`). The token is
serialized as a filename-agnostic JSON blob, Fernet-encrypted, and stored as `BYTEA`
in the `user_tokens` table. The sync-service loads and decrypts it on every run,
using a tmpdir for garth's file-based auth — the decrypted bytes never leave RAM beyond
the OS-managed tmpdir.

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

## Caddy everywhere (home gateway + bundled public)

HTTPS uses **Caddy** in both deployment modes — chosen over Traefik for the simplest
automatic Let's Encrypt setup (matches the dev-best-practices recommendation and the
existing gateway).

- **Home (default, `make up`):** TLS terminated by the separate
  [`homelab-gateway`](https://github.com/gerfru/homelab-gateway) repo running Caddy on a
  shared `proxy` Docker network. PulseBase joins it — no host ports exposed. One Caddy
  serves all self-hosted services; `*.home.lab` resolves via CoreDNS + Tailscale Split DNS;
  reachable only inside the Tailnet.
- **Public SaaS (`make up-public`):** a **bundled Caddy** terminates TLS via Let's Encrypt
  on a public domain (`docker-compose.public.yml`, ports 80/443). Used when running a
  public instance without the home gateway.

The earlier "Traefik standalone" fallback was never implemented and is replaced by the
bundled-Caddy public path. Security headers (`HSTS`, `CSP`, …) are emitted by the app
(`api/src/main.py`), so Caddy does not duplicate them.

---

## CSS: Tailwind CLI Build + custom style.css

Templates use **Tailwind CSS** for layout, spacing, and color utilities. A companion
`api/src/static/style.css` handles only the classes that JavaScript generates dynamically
at runtime (`.card`, `.badge-*`, `.metric-tile-*`, `.toast`, etc.) — these cannot be
purged by the CLI because they are constructed in JS via string concatenation.

**Build:**
Tailwind CLI standalone binary (no Node.js) generates `api/src/static/tailwind.min.css`
from `input.css` + `api/tailwind.config.js`. Run after any template changes:

```bash
make tailwind-build
```

The output (`tailwind.min.css`, ~19 KB) is committed and served as a static file.
No CDN, no runtime script, no build step in Docker.

**Light / Dark theme:**
- `theme-init.js` runs before the stylesheet to set `.dark` on `<html>` from `localStorage`
  (key `pb-theme`) — prevents FOUC
- `tailwind.config.js` sets `darkMode: 'class'`; all templates use `dark:` variants
- Toggle switch in Settings page writes to `localStorage` and toggles the class live

**Motion & Reduced Motion:**
- Motion is tokenized in `:root` like spacing/type: `--dur-fast|base|slow`, `--ease-out`,
  `--ease-spring` (single source of truth for timings/easing)
- A global `@media (prefers-reduced-motion: reduce)` guard neutralizes all animations and
  transitions (WCAG 2.3.3) — the one deliberate `!important` exception (accessibility override)
- The hero readiness ring (`dashboard-hero.js`) animates draw-in + score count-up with cubic
  ease-out. Because it is driven by JS `setAttribute` (not a CSS animation), the CSS guard does
  **not** cover it — an explicit `window.matchMedia('(prefers-reduced-motion: reduce)')` check
  sets the end state instantly instead of animating
- Dashboard cards fade up with a staggered `card-in` entrance (`nth-child` delays); reduced-motion
  is handled automatically by the global guard

**Loading states — Skeleton Screens:**
- Hero card (`#bento-hero`) and the activities table render skeleton placeholders instead of a
  `Lade…` text — they **mirror the final layout** by reusing the same layout classes
  (`.hero-grid`, `.hero-signals-row`, …) so there is **no layout shift** when real content arrives
- The skeleton is replaced automatically: `buildHeroCard()` / `renderActivitiesTable()` overwrite
  the container `innerHTML`, so no JS wiring of the placeholders is needed
- **300 ms rule (CSS-only, no JS timer):** the `.skeleton` wrapper stays `opacity: 0` and fades in
  via `animation-delay: 300ms`. If data arrives sooner, the placeholder is replaced before it ever
  shows — no flash for fast loads (NN/g / LogRocket guidance)
- Placeholders carry `aria-hidden="true"` (decorative); reduced-motion turns off the pulse
- Chart cards are intentionally excluded: `.chart-wrap` already reserves a fixed height
  (240/280 px), so there is no shift to fix

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

**Tier 1 (left) — Readiness Arc:**
SVG partial arc (240°, opens at bottom — Oura/WHOOP style). Score counts up from 0 via
`requestAnimationFrame` (600ms), arc fill animated via `stroke-dasharray`. Arc color
determined by score: ≥75 green, ≥50 amber, <50 red.

**Tier 2 (right) — Energie-Triptychon + Vitals:**
Three energy rows (Physisch / Autonom / Kognitiv) with color-coded dots, scores, sub-labels
(Form/Fitness, σ-deviation, sleep debt hours), and arrow links. A 2×2 vitals strip below
shows steps, sleep score, HRV avg, resting HR.

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
- **Independent schedule**: inference is triggered after every Garmin sync (via `ml_requested` flag)
  and runs on a daily fallback schedule (7:00); training runs weekly on Sundays — decoupled from the API
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

## Body Battery: Fresh-State model (not Banister accumulation)

**Changed:** May 2026. `ml-service/src/models/body_battery.py` v2.

The original `body_battery_custom` used a linear Banister fitness-fatigue accumulation:
`score = clamp(prev + recovery − drains, 5, 100)`. At rest, `drains ≈ 0` and `recovery`
was constant — so the score hit 100 and stayed there indefinitely. Users saw flat plateaus
at 100 for multi-day rest periods, which contradicted reality.

**Why fresh-state wins:**
- Banister FFM has fundamental statistical flaws at the individual level (Scientific
  Reports, 2025, doi:10.1038/s41598-025-88153-7)
- No wearable manufacturer publishes a clinically validated composite score formula
  (Wearable Composite Health Scores Require Validation, 2025)
- Fresh-state `score = 0.30 × prev + 0.70 × fresh − drains` avoids the plateau while
  preserving multi-day continuity via the 30% inertia term

**Sleep phases are primary, duration secondary (60/40 split):**
- Deep sleep (SWS) and REM quality are stronger recovery signals than total hours
  (Walker 2017; Dijk & Czeisler 1995)
- HRV vs. personal 30-day baseline as recovery indicator (Plews et al. 2013)

**Backfill:** `make backfill-battery` deletes all `body_battery_custom` predictions
and re-runs the backfill script against full history.

---

## EN 62366-inspired Metric Disclosure + Progressive Disclosure UX

**Implemented:** May 2026. `/help`, `/metrics/{name}`. Data: `api/src/data/evidence_catalog.json` (loaded via thin `api/src/evidence_catalog.py`).

Every health metric needs to communicate what it measures, what it is and is not intended for,
and the quality of its evidence. EN 62366 (medical device usability engineering) provided the
framework for thinking about this, even though PulseBase is not a regulated device.

**Three-layer disclosure architecture:**

1. **Metrics overview** (`/metrics`) — Evidence Badges on every tile:
   - 🟢 **M** Meta-Analysis / clinical guideline standard
   - 🟡 **R** Replicated (multiple independent studies)
   - 🔵 **E** Eigenmodell (PulseBase-specific, literature-based)
   Source: `GET /api/evidence` → `evidence_catalog.json` (21 entries). Each entry has `level`, `metric_type`,
   `time_horizon`, `intended_use`, `not_for`, `limitations`, `sources`.

2. **Metric detail pages** (`/metrics/{name}`) — simplified: value + chart + 1-sentence summary +
   score-dependent recommendation. No formula block, no ELI5 card, no sources card.
   Deep-link to the full help article via `? Hilfe-Artikel`.

3. **Help page** (`/help`) — full methodology for each metric: evidence level, formula,
   science background, sources, intended use, limitations. Client-side searchable (20 articles,
   6 categories). Deep-linkable via `#metric-key` (e.g. `/help#energy_autonomic`).

**Why Progressive Disclosure instead of all-in-one detail pages:**
- Practitioners need the recommendation fast; researchers need the formula — different needs
- EN 62366: intended use and not-for statements prevent misinterpretation of health data
- Avoids cognitive overload: 5-block detail pages discouraged exploration of the methodology

## TimescaleDB for intraday data

Regular PostgreSQL tables would work for daily summaries and activities. Intraday data
(body battery, stress every ~5 min = 288 rows/day/user) benefits from TimescaleDB:

- Hypertables partition data by time automatically
- Compression policy reduces storage by ~10x after the retention window
- Time-bucket aggregations (`time_bucket()`) are native and fast

Regular tables (`activities`, `daily_summary`, `sleep_sessions`, `hrv_daily`) don't need
hypertables — they're too small and queried differently.
