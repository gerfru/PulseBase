# PulseBase — App Evaluation Report
**Date:** 2026-06-10
**Stack:** Python 3.12 + FastAPI · TimescaleDB (PostgreSQL 16) · Docker Compose · Biome/Vitest (JS)
**Services:** api · sync-service · ml-service · backup
**ASVS Level:** L2 (auth + sensitive health/medical data, GDPR)
**Rule source:** gerald-dev-best-practices plugin (essential/app/github/architecture-rules.md)
**Documented exceptions carried over:** ARCH-M2, ARCH-L2, ARCH-L3, ARCH-M3, CICD-M4, QUAL-M2, OBS-L1/L2/L3, TEST-L4

---

## Axis Summary

| Axis | Status | #High | #Medium | #Low | Most violated rule |
|---|---|---|---|---|---|
| Architecture & 12-Factor | 🟡 Yellow | 1 | 3 | 4 | architecture-rules.md → Docker Architecture |
| Security (ASVS L2) | 🟡 Yellow | 0 | 1 | 5 + 1 Compliance | app-rules.md → Security (token logging, GDPR consent) |
| Code Quality | 🟡 Yellow | 0 | 6 | 9 | architecture-rules.md → Layering (business logic in DB layer) |
| Tests & Reliability | 🟢 Green | 0 | 3 | 5 | architecture-rules.md → Testing Strategy |
| CI/CD & Delivery | 🟡 Yellow | 1 | 2 | 3 | github-rules.md → Docker (uv.lock bypass), Security (syft) |
| Observability & Operations | 🔴 Red | 4 | 3 | 2 | app-rules.md → Monitoring (Sentry gaps, image hygiene) |

---

## Wave Overview

| Wave | Scope | Findings | Status |
|---|---|---|---|
| **Wave 1** | Security & Observability | H1 · H2 · H3 · H4 · M4 · C1 · L9 | ✅ |
| **Wave 2** | Docker & CI Infrastructure | H5 · H6 · M1 · M2 · M3 · M11 · M12 · M13 · M14 · M15 · L1 · L3 · L4 · L24 | ✅ |
| **Wave 3** | Python Code Quality | M9 · L10 · L13 · L14 · L15 · L16 · L17 | ✅ |
| **Wave 4** | JS Code Quality | M5 · M6 · M7 · M8 · M10 · L7 · L8 · L11 · L12 · L19 | ✅ |
| **Wave 5** | Tests | M16 · M17 · M18 · L20 · L21 · L22 · L23 | ⏳ |
| **Wave 6** | Docs, Cosmetics & Minor Fixes | L2 · L5 · L6 · L18 · L25 · L26 · L27 · L28 | ⏳ |

---

## All Findings

### HIGH

**H1 · Reset Token TTL mismatch — email says "1 Stunde", token expires after 15 min**
`api/src/auth_tokens.py:17` + `api/src/mail.py:57` · High · Conf 10
Violated: app-rules.md → Security (accurate user communication + no misleading error UX)
Fix: change `mail.py:57` copy to "gültig 15 Minuten" OR raise `_RESET_MAX_AGE` to 3600. Also fix `mail.py:84` deletion email "24 Stunden" → "1 Stunde" (`_DELETION_MAX_AGE = 3600`).
Wave: 1 · Status: ✅

**H2 · Sentry not active in sync-service and ml-service — runtime errors silent**
`docker-compose.yml:118-119, 154-155` (SENTRY_DSN only in `.env.api`) · High · Conf 10
Violated: app-rules.md → Monitoring & Logging (Error Tracking: Sentry)
Fix: add `SENTRY_DSN=` to `env/.env.app` (shared by all 3 services).
Wave: 1 · Status: ✅

**H3 · Backup base image not digest-pinned**
`backup/Dockerfile:3` (`FROM postgres:16-alpine`, no digest) · High · Conf 10
Violated: app-rules.md → Docker (Base Images mit Digest pinnen); all 3 app images already pinned.
Fix: `FROM postgres:16-alpine@sha256:<digest>`. Renovate dockerfile rule added in Wave 2 (M14).
Wave: 1 · Status: ✅

**H4 · Backup container not scanned by Trivy in CI**
`.github/workflows/ci.yml` (trivy job scans api/sync/ml but not backup) · High · Conf 10
Violated: app-rules.md → Docker (Container-Scanning: Trivy CRITICAL+HIGH, exit-code 1)
Fix: add build + scan steps for `pulsebase-backup:ci` in the trivy job.
Wave: 1 · Status: ✅

**H5 · Docker socket mount in public deployment — container-level host access**
`docker-compose.public.yml:60` (`/var/run/docker.sock:/var/run/docker.sock:ro`) · High · Conf 9
Violated: architecture-rules.md → Docker Architecture (least privilege)
Fix: add `security_opt: ["no-new-privileges:true"]` to vector service. Document file-source alternative in CLAUDE.md.
Wave: 2 · Status: ⏳

**H6 · Dockerfiles install from pyproject.toml, bypassing uv.lock — non-reproducible builds**
`api/Dockerfile:6`, `sync-service/Dockerfile:6`, `ml-service/Dockerfile:6` · High · Conf 9
Violated: github-rules.md → Docker & Package Management (lockfiles always committed, `--frozen`)
Fix: add uv install + `uv export --frozen --no-dev` step in all 3 builder stages.
Wave: 2 · Status: ⏳

---

### MEDIUM

**M1 · No PID 1 / zombie reaping in sync-service and ml-service**
`sync-service/Dockerfile:21`, `ml-service/Dockerfile:21` · Medium · Conf 8
Violated: architecture-rules.md → Docker Architecture (process model)
Fix: add `init: true` to both services in `docker-compose.yml`.
Wave: 2 · Status: ⏳

**M2 · `asyncio.get_event_loop()` deprecated (Python 3.10+) in both health servers**
`sync-service/src/health_server.py:21`, `ml-service/src/health_server.py:21` · Medium · Conf 9
Violated: architecture-rules.md → 12-Factor (Dev/Prod parity; project uses Python 3.14 base)
Fix: replace with `asyncio.get_running_loop().create_task(...)`.
Wave: 2 · Status: ⏳

**M3 · Compose healthcheck probes HTTP but scheduler failure is invisible**
`docker-compose.yml:126` (sync-service), `docker-compose.yml:165` (ml-service) · Medium · Conf 7
Violated: architecture-rules.md → Docker Architecture (health checks: liveness must reflect actual scheduler state)
Fix: extend healthcheck to also verify the sentinel: `CMD-SHELL: test -f /tmp/sync_alive && python -c "..."`.
Wave: 2 · Status: ⏳

**M4 · Deletion-confirmation token logged on email-send failure**
`api/src/routes/account.py:70` · Medium · Conf 9
Violated: app-rules.md → Security / Logging ("Never log secrets")
Fix: log only `user_id`, remove `confirm_url` with raw token from log output.
Wave: 1 · Status: ✅

**M5 · `activity.js` redefines 7 utility functions already in `chart-utils.js`**
`api/src/static/activity.js:52–79` · Medium · Conf 10
Violated: Code Quality (duplication >3%)
Fix: import `fmtDuration`, `fmtDist`, `fmtDate`, `SPORT_EMOJI`, `SPORT_LABEL` from existing modules. Keep `fmtPace`, `fmtSpeed`, `fmtTime` local (not yet in shared modules).
Wave: 4 · Status: ⏳

**M6 · `C` color palette used as undeclared global in two JS modules**
`api/src/static/dashboard-hero.js:295`, `api/src/static/dashboard-loaders.js:127` · Medium · Conf 9
Violated: Code Quality (implicit globals undermine static analysis)
Fix: add `/* global C */` at the top of both files.
Wave: 4 · Status: ⏳

**M7 · `buildHeroCard` function is 249 lines**
`api/src/static/dashboard-hero.js:221–469` · Medium · Conf 10
Violated: Code Quality (function length >50 lines)
Fix: extract `_signalTiles()`, `_capacityTilesOnly()`, `_animateRing()` as standalone named functions.
Wave: 4 · Status: ⏳

**M8 · `buildHealthCharts` function is 274 lines**
`api/src/static/dashboard-loaders.js:123–396` · Medium · Conf 10
Violated: Code Quality (function length >50 lines)
Fix: extract each chart type into its own `_renderXxxChart(data)` function.
Wave: 4 · Status: ⏳

**M9 · Business logic (score computation + label/CSS mapping) in `db/health.py`**
`api/src/db/health.py:165–211` (`get_readiness`) · Medium · Conf 9
Violated: architecture-rules.md → Layering (Routes → Service → Data Access)
Fix: move to new `api/src/readiness.py`; `db/health.py` exposes raw rows only.
Wave: 3 · Status: ⏳

**M10 · `dashboard-hero.js` at 555 lines — exceeds 400-line threshold**
`api/src/static/dashboard-hero.js` · Medium · Conf 10
Violated: Code Quality (file length >400 lines)
Fix: split into `dashboard-ml-feedback.js`, `dashboard-evidence.js`, keep `dashboard-hero.js` for ring/hero card only.
Wave: 4 · Status: ⏳

**M11 · Backup container missing `.dockerignore`**
`backup/` (no `.dockerignore` file) · Medium · Conf 10
Violated: github-rules.md → Docker (.dockerignore pflegen)
Fix: create `backup/.dockerignore` with `*.md`, `*.tmp`, `.git`, `.env*`.
Wave: 2 · Status: ⏳

**M12 · No `/ready` readiness probe in sync-service and ml-service**
`sync-service/src/health_server.py`, `ml-service/src/health_server.py` · Medium · Conf 9
Violated: app-rules.md → Deployment (/health liveness + /ready readiness)
Fix: extend `start_health_server(pool=None)` with a `/ready` handler that runs `pool.fetchval("SELECT 1")`; update Compose healthcheck to hit `/ready`.
Wave: 2 · Status: ⏳

**M13 · DB connection pool saturation not exposed in `/api/metrics`**
`api/src/main.py:229–241` · Medium · Conf 9
Violated: app-rules.md → Monitoring & Logging (four golden signals: saturation)
Fix: add `db_pool_used` and `db_pool_max` fields using `pool.get_size() - pool.get_idle_size()`.
Wave: 2 · Status: ⏳

**M14 · Renovate missing `dockerfile` manager — base image digests never auto-updated**
`renovate.json` (entire file) · Medium · Conf 9
Violated: github-rules.md → Dependency Management (Renovate covers Docker digest updates)
Fix: add `{ "matchManagers": ["dockerfile"], "matchUpdateTypes": ["digest"], "automerge": true }`.
Wave: 2 · Status: ⏳

**M15 · `syft` installed via `curl | sh` from mutable `main` branch — supply-chain risk**
`.github/workflows/ci.yml:106–107` · Medium · Conf 9
Violated: github-rules.md → Security / CI supply chain (all other Actions are SHA-pinned)
Fix: replace with `anchore/sbom-action@<SHA>` (also resolves L24 — automatic artifact upload).
Wave: 2 · Status: ⏳

**M16 · No validation test for `PATCH /api/seizures/{id}` missing required field**
`api/tests/test_api_endpoints.py` · Medium · Conf 9
Violated: architecture-rules.md → Testing Priority (API input validation)
Fix: add `test_update_seizure_missing_occurred_at_returns_422`.
Wave: 5 · Status: ⏳

**M17 · Activity IDOR verified only at mock level, not with real DB ownership filter**
`api/tests/test_api.py:276` · Medium · Conf 8
Violated: architecture-rules.md → Testing Priority (critical paths: auth, data mutations)
Fix: add E2E fixture `idor_activity_pair` + `test_activity_idor_cross_user_blocked`.
Wave: 5 · Status: ⏳

**M18 · Seizure IDOR E2E test has no CI skip guard — breaks CI without live DB**
`api/tests/e2e/test_seizure_ownership.py:39, 72` · Medium · Conf 8
Violated: architecture-rules.md → Testing Strategy (E2E tests requiring live stack must be guarded)
Fix: add `pytestmark = pytest.mark.skipif(not os.getenv("CI_HAS_DATA"), ...)`. Also fix bug on line 44 (`p` not defined → remove duplicate line).
Wave: 5 · Status: ⏳

---

### LOW

**L1 · `PYTHONDONTWRITEBYTECODE=1` missing from all three Dockerfiles**
`api/Dockerfile:16`, `sync-service/Dockerfile:15`, `ml-service/Dockerfile:16` · Low · Conf 8
Fix: add `ENV PYTHONDONTWRITEBYTECODE=1` alongside `PYTHONUNBUFFERED=1`.
Wave: 2 · Status: ⏳

**L2 · CLAUDE.md documents `SYNC_HOUR` but actual env var is `SYNC_INTERVAL_HOURS` — stale docs**
`CLAUDE.md:154, 372` vs `sync-service/src/config.py:14` · Low · Conf 10
Fix: update CLAUDE.md env-file table to `SYNC_INTERVAL_HOURS`.
Wave: 6 · Status: ⏳

**L3 · Vector container (public deploy) has no health check**
`docker-compose.public.yml:53–73` · Low · Conf 8
Fix: add healthcheck `CMD wget -qO- http://localhost:8686/health`; enable `[api]` in `vector.public.toml`.
Wave: 2 · Status: ⏳

**L4 · `security_opt: [no-new-privileges:true]` absent on all application containers**
`docker-compose.yml` (api:69, sync-service:106, ml-service:142) · Low · Conf 7
Fix: add `security_opt: ["no-new-privileges:true"]` to api, sync-service, ml-service.
Wave: 2 · Status: ⏳

**L5 · `libre_password` not explicitly deleted after use (unlike `garmin_password`)**
`api/src/routes/libre.py:36, 59` · Low · Conf 7
Fix: add `del libre_password` immediately after `libre_authenticate()`.
Wave: 6 · Status: ⏳

**L6 · bcrypt cost factor not explicitly set — relies on library default**
`api/src/deps.py:51, 55` · Low · Conf 7
Fix: change `bcrypt.gensalt()` to `bcrypt.gensalt(rounds=12)` in both calls.
Wave: 6 · Status: ⏳

**L7 · `econRow` in `activity.js` interpolates `val`/`label`/`sub` into `innerHTML` without `esc()`**
`api/src/static/activity.js:202–206` · Low · Conf 7
Fix: apply `esc()` to `val`, `label`, and `sub` parameters inside `econRow`.
Wave: 4 · Status: ⏳

**L8 · `dashboard-loaders.js` interpolates `a.calories` and `a.avg_hr` into `innerHTML` without coercion**
`api/src/static/dashboard-loaders.js:23–24` · Low · Conf 7
Fix: coerce with `Number(a.calories) || '—'` and `Number(a.avg_hr) || '—'`.
Wave: 4 · Status: ⏳

**L9 · `/api/seizures` endpoints accessible regardless of `epilepsy_mode` flag**
`api/src/routes/api_seizures.py:47–108` · Low · Conf 7
Ownership checks correct (no IDOR). Mode guard missing.
Fix: add `if not user.get("epilepsy_mode"): raise HTTPException(403)` in all 5 endpoints.
Wave: 1 · Status: ✅

**L10 · `_ip_hash(request)` called twice in register — variable not reused**
`api/src/routes/auth.py:172` · Low · Conf 10
Fix: replace second `_ip_hash(request)` call with the already-stored `ip_hash` variable.
Wave: 3 · Status: ⏳

**L11 · EV badge constants and `evBadge`/`evBadgeHtml` duplicated across two JS files**
`api/src/static/dashboard-hero.js:164–165`, `api/src/static/metrics-overview.js:294–295` · Low · Conf 10
Fix: move to `dashboard-utils.js`, import from there.
Wave: 4 · Status: ⏳

**L12 · `scoreColor`/`_curatedColor` logic duplicated with inconsistent thresholds**
`api/src/static/metrics-overview.js:287`, `api/src/static/dashboard-hero.js:167` · Low · Conf 10
Fix: align amber threshold to `>=45` in `dashboard-utils.js`, delete local copies, import everywhere.
Wave: 4 · Status: ⏳

**L13 · Bare `-> dict` return types on ~10 public DB functions**
`api/src/db/users.py:9,26,37,186,200`, `api/src/db/health.py:59,95,145,165`, `api/src/db/activities.py:30` · Low · Conf 10
Fix: replace with `dict[str, Any]`; use `UserRow` TypedDict pattern from `deps.py` for complex returns.
Wave: 3 · Status: ⏳

**L14 · Late `from datetime import date as _date` inside `train_and_save` function body**
`ml-service/src/models/readiness.py:115` · Low · Conf 10
Fix: move to module top-level, remove alias.
Wave: 3 · Status: ⏳

**L15 · `_ip_hash` uses magic number `[:12]` with no constant name or comment**
`api/src/deps.py:46` · Low · Conf 8
Fix: extract `_IP_HASH_PREFIX_LEN = 12` with a one-line comment.
Wave: 3 · Status: ⏳

**L16 · HRV filtering logic duplicated in `_run_body_battery_and_stress`**
`ml-service/src/inference_models.py:284–286` vs `_compute_hrv_baseline:198–200` · Low · Conf 9
Fix: extract `_get_last_hrv(hrv_hist)` helper alongside `_compute_hrv_baseline`.
Wave: 3 · Status: ⏳

**L17 · `sync-service/src/main.py` at 367 lines — approaching 400-line threshold**
`sync-service/src/main.py` · Low · Conf 10
Fix (pre-emptive): move `_sync_*` helpers and `sync_user`/`sync_libre_user` to `sync_runner.py`.
Wave: 3 · Status: ⏳

**L18 · `ml-service/src/db/health.py` at 361 lines — approaching 400-line threshold**
`ml-service/src/db/health.py` · Low · Conf 10
Fix (pre-emptive): add comment noting split trigger; split when file exceeds 400 lines.
Wave: 6 · Status: ⏳

**L19 · Nesting depth 6 in `buildHeroCard` animation closure**
`api/src/static/dashboard-hero.js:441–464` · Low · Conf 10
Fix: extract animation to `function _animateRing(progress, scoreEl, fill, score)` at module scope. Covered by M7.
Wave: 4 · Status: ⏳

**L20 · Duplicate test body gives false confidence about unverified-email path**
`api/tests/test_coverage.py:53, 75` · Low · Conf 9
Fix: rename line-75 test; add comment that the SQL filter IS the guard.
Wave: 5 · Status: ⏳

**L21 · Misleading test name: inactive-user login patches `get_user_by_email` to return `None`**
`api/tests/test_auth.py:1009` · Low · Conf 9
Fix: rename to `test_login_unknown_email_returns_400`; add comment.
Wave: 5 · Status: ⏳

**L22 · `test_sync_date_range_handles_activity_failure` does not assert no-raise**
`sync-service/tests/test_coverage.py:129` · Low · Conf 7
Fix: restructure as plain `await`; add `assert _sync_day.await_count >= 1`.
Wave: 5 · Status: ⏳

**L23 · `sync-service/tests/` missing `__init__.py`**
`sync-service/tests/` · Low · Conf 9
Fix: `touch sync-service/tests/__init__.py`.
Wave: 5 · Status: ⏳

**L24 · SBOM artifact generated but not uploaded — discarded after runner exits**
`.github/workflows/ci.yml:101–110` · Low · Conf 10
Fix: covered by M15 (anchore/sbom-action uploads automatically).
Wave: 2 · Status: ⏳

**L25 · `semgrep` hook runs after `detect-secrets` instead of after `bandit`**
`.pre-commit-config.yaml:53–60` · Low · Conf 8
Fix: move `semgrep` hook block directly after the `bandit` block, before `ruff`.
Wave: 6 · Status: ⏳

**L26 · `ci-ok` gate covers 11 jobs but CLAUDE.md states 9 — documentation drift**
`.github/workflows/ci.yml:432` vs `CLAUDE.md` (CI/CD table) · Low · Conf 10
Fix: update CLAUDE.md CI/CD table to list all 11 jobs.
Wave: 6 · Status: ⏳

**L27 · `garmin.connect.failed` log fuses event key with human description**
`sync-service/src/garmin/client.py:45`, `api/src/garmin/client.py:27` · Low · Conf 9
Fix: `logger.warning("garmin.connect.failed", reason="retrying_fresh_login")`.
Wave: 6 · Status: ⏳

**L28 · `garmin.token.saved` debug log uses German prose string**
`sync-service/src/garmin/client.py:57`, `api/src/garmin/client.py:39` · Low · Conf 8
Fix: `logger.debug("garmin.token.saved")`.
Wave: 6 · Status: ⏳

---

### COMPLIANCE ⚪

**C1 · GDPR consent record overwrites history — Art. 5(2) accountability gap**
`api/src/db/users.py:363–384` (`save_consent` uses `ON CONFLICT DO UPDATE`) · Compliance · Conf 8
Violated: app-rules.md → Database / GDPR Art. 5(2) (accountability requires immutable consent audit log)
Fix: V27 migration adds `user_consent_events` audit table; `save_consent` dual-writes (current state in `user_consents` + immutable row in `user_consent_events`). Also fix: `privacy_policy_version` not updated in ON CONFLICT branch.
Wave: 1 · Status: ✅

---

## DORA Assessment (estimates)

| Metric | Value | Source |
|---|---|---|
| Deployment Frequency | ~3–5 merges/week → **Elite** tier | [Schlussfolgerung] git log |
| Lead Time for Changes | Hours to 1–2 days (CI ~12 min + review) | [Schlussfolgerung] pipeline duration |
| Change Failure Rate | Not measurable — no rollback markers in log | [Nicht verifizierbar] |
| Mean Time to Recovery | Not measurable — no incident data | [Nicht verifizierbar] |

---

## Wave Implementation Plan

### Wave 1 — Security & Observability
**7 Findings: H1 · H2 · H3 · H4 · M4 · C1 · L9**

| # | Finding | File | Change |
|---|---|---|---|
| H1 | Token-TTL-Mismatch | `api/src/mail.py:57,84` | "1 Stunde" → "15 Minuten"; "24 Stunden" → "1 Stunde" |
| H2 | Sentry für sync/ml | `env/.env.app` | `SENTRY_DSN=` Zeile ergänzen |
| H3 | Backup digest-pinnen | `backup/Dockerfile:3` | `FROM postgres:16-alpine@sha256:<digest>` |
| H4 | Backup Trivy-Scan | `.github/workflows/ci.yml` | Build + Scan Steps für `pulsebase-backup:ci` |
| M4 | Token nicht loggen | `api/src/routes/account.py:70` | `confirm_url=...` aus logger entfernen |
| C1 | GDPR Audit-Log | `db/migrations/V27__user_consent_events.sql` + `api/src/db/users.py` | Neue Tabelle + Dual-Write in `save_consent` |
| L9 | Epilepsy-Mode-Gate | `api/src/routes/api_seizures.py` | `if not user.get("epilepsy_mode"): raise HTTPException(403)` in allen 5 Endpoints |

**Verification:** `pytest api/tests/ --tb=short` · `mypy api/src/` · `ruff check api/src/`

---

### Wave 2 — Docker & CI Infrastructure
**14 Findings: H5 · H6 · M1 · M2 · M3 · M11 · M12 · M13 · M14 · M15 · L1 · L3 · L4 · L24**

| # | Finding | File | Change |
|---|---|---|---|
| H5 | Docker-Socket absichern | `docker-compose.public.yml` | `security_opt: [no-new-privileges:true]` auf vector-Service |
| H6 | uv.lock in Dockerfiles | `api/sync-service/ml-service Dockerfile` | Builder: `pip install uv` + `uv export --frozen` |
| M1 | PID1 / init | `docker-compose.yml` | `init: true` für sync-service + ml-service |
| M2 | asyncio deprecated | `*/src/health_server.py:21` | `get_running_loop()` statt `get_event_loop()` |
| M3 | Healthcheck + Sentinel | `docker-compose.yml:126,165` | `test -f /tmp/sync_alive &&` prefix |
| M11 | backup .dockerignore | `backup/.dockerignore` | neue Datei |
| M12 | /ready Probe | `*/src/health_server.py` | neue `/ready` Route mit DB-Ping |
| M13 | DB-Pool in /metrics | `api/src/main.py:229` | `db_pool_used` + `db_pool_max` ergänzen |
| M14 | Renovate dockerfile | `renovate.json` | `matchManagers: ["dockerfile"]` Rule |
| M15+L24 | syft SHA-gepinnt | `.github/workflows/ci.yml` | `anchore/sbom-action@<SHA>` ersetzt curl |
| L1 | PYTHONDONTWRITEBYTECODE | alle 3 Dockerfiles | `ENV PYTHONDONTWRITEBYTECODE=1` |
| L3 | Vector Healthcheck | `docker-compose.public.yml` + `vector.public.toml` | healthcheck + `[api] enabled = true` |
| L4 | no-new-privileges | `docker-compose.yml` | `security_opt` für api/sync/ml |

**Verification:** `docker build api/ sync-service/ ml-service/ backup/` · `docker compose -f docker-compose.test.yml up --build --abort-on-container-exit`

---

### Wave 3 — Python Code Quality
**7 Findings: M9 · L10 · L13 · L14 · L15 · L16 · L17**

| # | Finding | File | Change |
|---|---|---|---|
| M9 | readiness aus db layer | neue `api/src/readiness.py` + `api/src/db/health.py` | `get_readiness` verschieben |
| L10 | Doppelter ip_hash | `api/src/routes/auth.py:172` | Variable statt zweiter Aufruf |
| L13 | TypedDict Returns | `api/src/db/{users,health,activities}.py` | bare `dict` → `dict[str, Any]` |
| L14 | Late import | `ml-service/src/models/readiness.py:115` | an Modul-Top verschieben |
| L15 | ip_hash Magic Number | `api/src/deps.py:46` | `_IP_HASH_PREFIX_LEN = 12` Konstante |
| L16 | HRV Dedup | `ml-service/src/inference_models.py:284` | `_get_last_hrv()` Helper |
| L17 | sync/main.py split | neue `sync-service/src/sync_runner.py` | `sync_user`, `sync_libre_user`, `_sync_*` |

**Verification:** `pytest api/tests/ sync-service/tests/ ml-service/tests/ --tb=short` · `mypy api/src/ sync-service/src/ ml-service/src/`

---

### Wave 4 — JS Code Quality
**10 Findings: M5 · M6 · M7 · M8 · M10 · L7 · L8 · L11 · L12 · L19**

| # | Finding | File | Change |
|---|---|---|---|
| M5 | activity.js Dedup | `api/src/static/activity.js:52-82` | 5 Funktionen importieren statt neu definieren |
| M6 | C Global | `dashboard-hero.js:1`, `dashboard-loaders.js:1` | `/* global C */` |
| M7+L19 | buildHeroCard split | `dashboard-hero.js:221` | `_signalTiles`, `_capacityTilesOnly`, `_animateRing` extrahieren |
| M8 | buildHealthCharts split | `dashboard-loaders.js:123` | 8 `_renderXxxChart()` Funktionen |
| M10 | dashboard-hero.js split | neue Dateien `dashboard-ml-feedback.js`, `dashboard-evidence.js` | 555 → ~200 Zeilen |
| L7 | econRow esc() | `activity.js:202` | `esc(val)`, `esc(label)`, `esc(sub)` |
| L8 | calories/avg_hr | `dashboard-loaders.js:23` | `Number(a.calories) \|\| '—'` |
| L11 | EV Badge zentralisieren | `dashboard-utils.js` | `EV_LEVEL_SHORT`, `EV_LEVEL_CLS`, `evBadgeHtml` exportieren |
| L12 | scoreColor konsolidieren | `dashboard-utils.js` | Threshold auf `>=45` angleichen; lokale Kopien löschen |

**Verification:** `npx @biomejs/biome@2.4.16 check api/src/static/` · `npx vitest run api/src/static/` · Dashboard manuell testen (Dark/Light, alle Metriken)

---

### Wave 5 — Tests
**7 Findings: M16 · M17 · M18 · L20 · L21 · L22 · L23**

| # | Finding | File | Change |
|---|---|---|---|
| M16 | PATCH Seizure Test | `api/tests/test_api_endpoints.py` | `test_update_seizure_missing_occurred_at_returns_422` |
| M17 | Activity IDOR E2E | neue `api/tests/e2e/test_activity_ownership.py` + conftest fixture | `idor_activity_pair` + Test |
| M18 | IDOR Skip Guard | `api/tests/e2e/test_seizure_ownership.py` | `pytestmark` + Bug fix Zeile 44 |
| L20 | Duplikat Test umbenennen | `api/tests/test_coverage.py:75` | rename + Kommentar |
| L21 | Misleading Testname | `api/tests/test_auth.py:1009` | rename + Kommentar |
| L22 | Sync Assertion | `sync-service/tests/test_coverage.py:129` | direktes await + `await_count` assert |
| L23 | tests/__init__.py | `sync-service/tests/__init__.py` | neue leere Datei |

**Verification:** `pytest api/tests/ sync-service/tests/ --tb=short` · `mypy sync-service/src/`

---

### Wave 6 — Docs, Cosmetics & Minor Fixes
**8 Findings: L2 · L5 · L6 · L18 · L25 · L26 · L27 · L28**

| # | Finding | File | Change |
|---|---|---|---|
| L2 | CLAUDE.md SYNC_HOUR | `CLAUDE.md` | `SYNC_HOUR` → `SYNC_INTERVAL_HOURS` |
| L5 | libre_password del | `api/src/routes/libre.py:59` | `del libre_password` nach `libre_authenticate` |
| L6 | bcrypt rounds | `api/src/deps.py:51,55` | `bcrypt.gensalt(rounds=12)` |
| L18 | ml health.py Kommentar | `ml-service/src/db/health.py:1` | Split-Trigger-Kommentar |
| L25 | semgrep Reihenfolge | `.pre-commit-config.yaml` | semgrep-Block nach bandit verschieben |
| L26 | CI-OK Jobs Doku | `CLAUDE.md` | "9 Jobs" → "11 Jobs" |
| L27 | garmin.connect log | `*/garmin/client.py:27,45` | `reason="retrying_fresh_login"` als kwarg |
| L28 | garmin token log | `*/garmin/client.py:39,57` | deutsches String → `"garmin.token.saved"` |

**Verification:** `pre-commit run --all-files` · `pytest api/tests/ --tb=short`

---

*Created with AI assistance (Claude Code + dev-best-practices plugin).
Findings are to be verified — not a substitute for manual penetration testing.*
