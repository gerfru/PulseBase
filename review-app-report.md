# App Evaluation Report — PulseBase

**Date:** 2026-06-08
**Standard:** dev-best-practices rule files v2.0.0 (`essential-rules.md`, `app-rules.md`, `github-rules.md`, `architecture-rules.md`)
**Method:** 6 parallel sub-agents (Architecture, Security, Code Quality, Tests, CI/CD, Observability)

**Discovered context:**
`Stack: FastAPI (Python) · 3 Services (api / sync-service / ml-service) · TimescaleDB (Postgres 16) · Docker Compose | PkgMgr: uv (3× uv.lock ✓) | CI: GitHub Actions (ci.yml, 9 jobs) | Migrations: Flyway V1–V25 | Pre-commit ✓ | Solo + Health-PII + Auth + DSGVO → ASVS L2`

---

## Scorecard

| Axis | Light | #Critical | #High | Most important violated rule |
|---|---|---|---|---|
| Architecture & 12-Factor | 🟡 | 0 | 1 | architecture-rules.md → Reverse Proxy & SSL (standalone proxy missing) |
| Security (ASVS L2) | 🟢 | 0 | 0 | app-rules.md → Auth (reset-token TTL 60 min > 15 min) |
| Code Quality | 🟢 | 0 | 0 | file > 400 lines (api.py 405, users.py 407) |
| Tests & Reliability | 🟢 | 0 | 0 | github-rules.md → Testing (JS coverage scope 6/25 modules) |
| CI/CD & Delivery (DORA) | 🟢 | 0 | 1 | github-rules.md → Branch Protection (required checks 3/8 jobs) |
| Observability & Ops | 🟡 | 0 | 1 | app-rules.md → Logging/Monitoring (Loki/Promtail/Kuma absent) |

**Overall: 🟢/🟡 — strong, near-release-ready.** 0 Critical, 3 High. The codebase is genuinely well-engineered for a solo project (exemplary Docker hardening, defense-in-depth auth with verified IDOR protection, mature structured logging, comprehensive security scanning in CI). All three High findings are **operational/process gaps**, not code defects — and two of them are **documentation drift**: CLAUDE.md describes monitoring services and a standalone reverse proxy that do not exist in the repo.

---

## Findings — sorted by severity

### 🔴 HIGH

**H1 · Documented monitoring stack (Loki/Promtail/Uptime Kuma) does not exist · `docker-compose.yml` (5 services only) · Confidence 9**
Violated rule: `app-rules.md → Logging (Aggregation) / Observability / Monitoring minimum`.
`docker-compose.yml` defines only `db, flyway, api, sync-service, ml-service`. There is **no Loki, no Promtail, no Uptime Kuma** anywhere in any compose/yml file — yet CLAUDE.md OBS-L1 claims *"Uptime Kuma läuft als Compose-Service (make up startet es automatisch)"* and the Monitoring block claims *"Loki + Promtail (make up startet beides automatisch)"*. **Both claims are false** → currently no log aggregation and no uptime monitoring is running.
Fix: either add the three services to `docker-compose.yml`, or correct CLAUDE.md/OBS-L1 to reflect that they are not yet deployed. **Effort: M**

**H2 · `make up-standalone` starts no reverse proxy — standalone path is non-functional · `Makefile` + `docker-compose.yml` · Confidence 9**
Violated rule: `architecture-rules.md → Reverse Proxy & SSL` / `Docker Architecture`.
`make up-standalone` runs `docker compose --profile standalone up`, but **no service has `profiles: [standalone]`** and there is **no `traefik/` directory, no traefik service, no Caddy** anywhere in the repo. So the standalone command starts the same 5 services with no public-facing proxy and no port published to the host → app unreachable standalone. This makes CLAUDE.md's ARCH-M3 (*"traefik/traefik.yml enthält certificatesResolvers.letsencrypt … Zertifikate werden automatisch geholt"*) **outdated/false**.
Fix: add a `traefik` (or `caddy`) service gated on `profiles: [standalone]` with the ACME config ARCH-M3 describes, **or** remove the `up-standalone` target and correct the ARCH-M3 doc to state the app only runs behind the external homelab-gateway. **Effort: M**

**H3 · Required status checks gate only 3 of 8 CI jobs — the purpose-built `ci-ok` gate isn't wired in · main ruleset + `.github/workflows/ci.yml:289-301` · Confidence 9**
Violated rule: `github-rules.md → Branch Protection ("Require status checks")`.
The `main` ruleset IS active (good — this means CLAUDE.md CICD-M3 is now stale, see below), but `required_status_checks` lists only `Lint & Format`, `Security`, `Tests`. **`Type Check (mypy)`, `JS Tests`, `JS Lint`, `Trivy`, `E2E` are NOT required**, so a PR with a failing mypy/trivy/e2e run can still merge. The `ci-ok` "All Green Gate" job already exists specifically to be the single aggregating required check — it just isn't in the required list.
Fix: set `ci-ok` as the one required status check (it fails if any `needs` failed). **Effort: S**

### 🟡 MEDIUM

**M1 · Password-reset token TTL 60 min exceeds 15 min max · `api/src/auth_tokens.py:11` (`_RESET_MAX_AGE = 3600`) · Confidence 9**
Violated rule: `app-rules.md → Authentication ("Password reset: one-time token, max. 15 min")`.
Token is one-time, SHA-256-hashed in DB, and DB-expiry-checked — so impact is limited to a widened reset window, but the value violates the explicit rule.
Fix: `_RESET_MAX_AGE = 900`. **Effort: S**

**M2 · Vitest coverage gate measures only 6 of 25 static JS modules · `api/vitest.config.js:11-18` · Confidence 8**
Violated rule: `github-rules.md → Testing (coverage scope)`.
The 95/90/95/95 thresholds apply only to 6 utility files; 19 DOM/data-loader modules (`dashboard.js`, `metrics-*.js`, `activity.js`, `theme.js`, `help.js`, glucose/libre loaders) are excluded from the coverage `include`. Config comments them as "covered by Playwright E2E", but E2E only smoke-tests light/dark page loads with no behavioral assertions on those loaders' fetch/render logic. The impressive 95% number covers a quarter of the frontend.
Fix: widen `include` (accept a lower threshold) or add targeted Vitest tests for the `metrics-*` / loader modules. **Effort: M**

**M3 · GitHub-native secret scanning + push protection not enabled (3rd defense layer) · repo `security_and_analysis = null` · Confidence 7**
Violated rule: `github-rules.md → Secret Scanning (3 layers) / Repository Settings`.
Layers 1 (pre-commit gitleaks) and 2 (CI gitleaks) are present; the GitHub-native layer is off. NOTE: on a private free-plan repo, push protection may require GitHub Advanced Security — if so this is blocked-by-plan, not a code defect.
Fix: `gh api ...security_and_analysis[secret_scanning_push_protection][status]=enabled` if available on the plan. **Effort: S**

**M4 · Direct pushes to main occurring despite PR-required ruleset · git history (≈16/30 recent commits lack `#PR`) · Confidence 6 · [to verify]**
Violated rule: `github-rules.md → Repository Settings (clean main / PR flow)`.
Could be admin bypasses or squash-merges without `(#N)` in the subject — needs confirmation. If the owner pushes directly, required checks never run on those changes.
Fix: route all changes through PRs, or accept as a documented solo exception. **Effort: S**

### 🟢 LOW (selection — full list in agent outputs)

- **L1 · `routes/api.py` = 405 lines, `db/users.py` = 407 lines · Confidence 9** — both past the documented 400-line split trigger (ARCH-L5 fired). Split `api.py` into `api_health/api_ml/api_seizures/api_glucose`; extract token/consent queries from `users.py`. **Effort: M**
- **L2 · `compute_spo2_trend` cyclomatic complexity C=15 · `ml-service/src/models/spo2_metrics.py:4` · Confidence 8** — exceeds warn threshold 10; extract apnea-flag + trend-slope branches. **Effort: S**
- **L3 · `/api/metrics` requires session auth · `api/src/main.py:184` · Confidence 7** — scrapers/uptime probes can't read golden-signal metrics; also `psutil.cpu_percent(interval=None)` returns 0.0 on first call. Expose on internal-only unauthenticated path or document as human-only. **Effort: S**
- **L4 · Python `fail_under = 75` below standard 80 · 3× `pyproject.toml` · Confidence 7** — within the 70-80% band but under the rule's explicit 80; raise if actual coverage already exceeds it. **Effort: S**
- **L5 · No SBOM generation on release · `ci.yml` (absent) · Confidence 6** — add `syft … -o cyclonedx-json`; low urgency (no release process yet). **Effort: S**
- **L6 · `db/pool.py:53` pool sizing hardcoded (max_size=5) · Confidence 6** — not env-configurable; minor for single-process solo. **Effort: S**

### ⚪ COMPLIANCE REMINDERS (not security defects)

- **OBS-L3 (documented):** Sentry error-rate + p95/CPU/mem alert rules are manual dashboard config and not codified. Per the project's own note this is **PFLICHT before public release**. Alert thresholds per `app-rules.md → Error Handling`: error rate > 1%, p95 > 2s, CPU/mem > 80%.
- **Email-verify / account-deletion tokens** are stateless `itsdangerous` signed payloads (24h), not single-use — a leaked link is replayable until expiry. Acceptable for verify; consider a stored single-use nonce for the deletion confirmation. (Low, Confidence 7)

---

## Documentation drift — propose updating CLAUDE.md

Three documented statements no longer match the repo and should be corrected (the skill flags new/outdated exceptions):

| CLAUDE.md claim | Reality | Action |
|---|---|---|
| **OBS-L1**: "Uptime Kuma läuft als Compose-Service (make up startet es automatisch)" + Monitoring block "Loki + Promtail (make up startet beides automatisch)" | No such services in `docker-compose.yml` | Add services **or** mark as "geplant, nicht deployed" (see H1) |
| **ARCH-M3**: "traefik/traefik.yml enthält certificatesResolvers.letsencrypt … Zertifikate werden automatisch geholt ✅" | No `traefik/` dir, no proxy service, `--profile standalone` matches nothing | Implement standalone proxy **or** remove target + correct doc (see H2) |
| **CICD-M3**: "Branch Protection nicht erzwingbar (privates Repo, Gratis-Plan); Direktpushes technisch möglich" | A `main` ruleset IS active (pull_request + required_status_checks + non_fast_forward, empty bypass) | Update doc — branch protection **is** enforced now; the real gap is incomplete required checks (H3), not absence of protection |

---

## Recommended fix order

1. **Security/process first:** H3 (wire `ci-ok` as required check — S), M1 (reset TTL → 900s — S), M3 (native secret scanning if plan allows — S).
2. **Operational truth:** H1 + H2 — decide deploy reality, then either add services or fix the docs (M each). M4 verify.
3. **Tests:** M2 (widen JS coverage scope — M), L4 (raise fail_under to 80 — S).
4. **Refactors:** L1 (split api.py/users.py — M), L2 (spo2 complexity — S), L6.
5. **Cosmetics/compliance:** L3, L5, OBS-L3 alert config before public release.

---

## What is genuinely strong (verified, no action)

- **Security (ASVS L2): 🟢** — CSP nonce + `strict-dynamic`, full security-header set, bcrypt(12) timing-safe + user-enum defense, account lockout (V17), httpOnly/secure/sameSite=Lax sessions, CSRF tokens (`hmac.compare_digest`), 100% parameterized SQL, **IDOR protection verified at the data-access layer** (`id = $1 AND user_id = $2`), per-service least-privilege DB roles (V24), Fernet-encrypted Garmin tokens, env validation crashes at startup.
- **Docker/12-Factor:** multi-stage builds, digest-pinned `python:3.14-slim`, non-root `appuser`, HEALTHCHECK + resource limits + log rotation on every service, `127.0.0.1` binding, named volumes, **proper SIGTERM/graceful shutdown in all 3 services**.
- **Tests:** healthy pyramid (~898 unit/integration + 46 E2E), every security/GDPR-critical path covered incl. lockout, reset-replay, **real-DB IDOR E2E**, password_hash-exclusion in export.
- **CI/CD:** semgrep (`--error`) + trivy (`exit-code 1`) + bandit + pip-audit + gitleaks all gated, Renovate (not Dependabot), SHA-pinned actions, 3× frozen uv.lock, squash-only + delete-branch-on-merge.
- **Observability:** structlog JSON + UTC, per-request `request_id` + `X-Request-ID`, PII hashed before logging, Sentry (`send_default_pii=False`) in all services, `/health` + `/ready` (DB + migration check), `pip-audit` clean (0 CVEs).

---
*Created with AI assistance (Claude Code + dev-best-practices plugin).
Findings are to be verified — not a substitute for manual penetration testing.*
