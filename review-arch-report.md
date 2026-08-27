# Architecture Review Report — PulseBase

Stack: Python (FastAPI / asyncio) · TimescaleDB · Docker Compose
Scope: Full codebase · graphify-out knowledge graph (3 786 nodes, 8 554 edges, 207 communities)
Date: 2026-08-26

---

## Overall Assessment

🟡 **Solid foundation with deliberate trade-offs — two areas need attention before adding the next feature or team member.**

The three-service split (api / sync-service / ml-service) is well-motivated and consistently executed. Security and domain boundaries are clearly thought through (ADR-0001, ADR-0003). The main architectural risks are: inter-service coupling through DB-level signalling, and growing implementation duplication that will compound with every new feature.

---

## Findings

### 🟠 HIGH (2)

---

### 🟠 Finding 1: Database Used as Message Bus

**Category:** Coupling — Shared Database IPC
**Location:** `sync-service/src/sync_runner.py` → `users.ml_requested` · `users.sync_requested` · `ml-service/src/db/users_ml.py` · `api/src/db/users.py`

**What:** All inter-service communication is mediated by boolean flags on the `users` table. After a Garmin sync the sync-service writes `ml_requested = true`; the ML-service polls this column every 2 minutes. The API writes `sync_requested = true`; the sync-service polls it every 1 minute.

**Why it matters:** This is the "Shared Database as Message Broker" anti-pattern (Fowler: *IntegrationDatabase*). It has three compounding problems:

1. **Tight schema coupling.** The `users` table now owns both identity data and inter-service control flow. Every service that reads or writes these flags must be updated when the signalling protocol changes. Adding a fourth service (e.g. a notification service) means yet another consumer polling the same row.
2. **Bounded latency floor.** Maximum trigger latency is the poll interval (1–2 min). There is no way to reduce it below that without tightening the poll, which increases DB load proportionally.
3. **No back-pressure or queue semantics.** If the ML-service is down for 10 minutes, all `ml_requested` flags accumulate silently. When it recovers, it processes a burst with no ordering guarantee and no visibility into queue depth.

The current scale (personal tracker, single host) makes this manageable. But the next logical feature — a push notification when ML insights are ready — would require a third poller or a duplicate mechanism.

**Recommendation:** Introduce a lightweight event channel between services. For the current single-host deployment a PostgreSQL `LISTEN/NOTIFY` channel is the lowest-friction upgrade: sync-service `NOTIFY ml_channel, user_id` after sync; ML-service `LISTEN ml_channel`. This eliminates polling latency, removes the `ml_requested` flag from the `users` table, and provides a natural queue abstraction. The `sync_requested` flag for the API → sync flow can be replaced the same way.

**ADR needed:** Yes. This decision directly constrains how new services integrate. The current choice was implicit; making it explicit (and recording the trade-off against LISTEN/NOTIFY or a proper queue) will save the next developer significant time.

**Reference:** Fowler — [IntegrationDatabase](https://martinfowler.com/bliki/IntegrationDatabase.html) · CMU 17-633 L11 — Component-and-Connector structures: pipe-and-filter vs. shared data style.

---

### 🟠 Finding 2: Garmin API Calls Block the Async Event Loop

**Category:** Quality Attribute — Performance / Availability
**Location:** `sync-service/src/garmin/client.py` → `garmin_call()` · `sync_runner.py` · `backfill_records.py`

**What:** `garmin_call()` uses tenacity's synchronous `Retrying` context manager to call synchronous `garminconnect` library methods directly inside `async` functions. There is no `asyncio.run_in_executor()` wrapper.

```python
# sync-service/src/garmin/client.py
def garmin_call(fn: Callable[[], _T]) -> _T:
    for attempt in Retrying(stop=stop_after_attempt(3), ...):
        with attempt:
            return fn()   # ← blocking call inside async context
```

**Why it matters:** Each Garmin API round-trip (typically 0.5–3 s) holds the event loop hostage. During that window, no other coroutine in the process can run: health-check heartbeats, Libre syncs, and internal async operations are all blocked. This is a textbook violation of the asyncio contract — "never block the event loop" (Python asyncio docs, CMU 17-633 L13 Concurrency tactics). With N users being synced sequentially and multiple Garmin calls per user per day, a scheduled sync run can block the loop for minutes. The Libre sync (every 5 min) may miss its window entirely.

**Recommendation:** Wrap all `garmin_call()` invocations in `asyncio.get_event_loop().run_in_executor(None, fn)`. Since `garminconnect.Garmin` is not thread-safe, instantiate one client per executor call or protect it with a lock. A cleaner long-term solution is to wrap the entire `sync_user()` call in an executor so the loop remains free. This is a one-function change with measurable latency improvement.

**ADR needed:** No. This is a correctness fix, not a trade-off decision.

**Reference:** Python asyncio docs — "Coroutines and Tasks" · CMU 17-633 L10 — Performance tactic: *Introduce Concurrency*.

---

### 🟡 MEDIUM (4)

---

### 🟡 Finding 3: GarminClient Duplicated Across Services

**Category:** Cohesion — Code Duplication
**Location:** `api/src/garmin/client.py` · `sync-service/src/garmin/client.py`

**What:** Two nearly identical `GarminClient` classes exist in separate services. They share the same constructor signature, the same method set (`connect`, `get_activities`, `get_sleep`, `get_hrv`, …), and differ only in the `connect()` branch: the API version handles fresh password login (for initial account linking); the sync-service version is token-only.

**Why it matters (CMU 17-633):** This is the *Inappropriate Intimacy* pattern at the code level. When Garmin changes its API (versioned endpoints, new auth flow, rate-limit headers), the fix must be applied in two places, owned by potentially different developers. The graph confirms this: `GarminClient` is a high-betweenness-centrality node bridging five communities — any change radiates widely. The divergence between the two implementations will grow over time.

**Recommendation:** Extract a shared `garmin` package as a proper Python package installable by both services (e.g. `packages/garmin/`). The `GarminClient` class can accept a `token_only: bool` flag to select the login path. Both services add it as an editable or vendored dependency. This is the *Shared Kernel* pattern used correctly: explicit contract, single point of change, tested independently.

**ADR needed:** Yes. The decision to duplicate vs. share has long-term consequences for release coupling.

**Reference:** DDD — Shared Kernel · Fowler — [MonolithFirst](https://martinfowler.com/bliki/MonolithFirst.html) (shared libraries as an intermediate step).

---

### 🟡 Finding 4: TimescaleRepository is a God Object

**Category:** Cohesion — God Object / Large Class
**Location:** `sync-service/src/repositories/timescale.py`

**What:** `TimescaleRepository` implements six abstract base classes (`ActivityRepository`, `ActivityRecordRepository`, `DailySummaryRepository`, `SleepRepository`, `HRVRepository`, `IntradayRepository`) plus token management and user coordination (`set_ml_requested`, `mark_sync_done`, `get_sync_requested_users`). The result is a single class with >25 public methods spanning every data domain in the sync-service.

**Why it matters:** The abstract base classes (a good design!) are rendered ineffective by combining all their implementations in one class. Test setup must mock the entire interface even for tests that only exercise one domain. The class has 56 graph edges — it is the fourth most-connected node in the entire codebase. Changes to the HRV schema require touching the same file as changes to the Garmin token storage. The user-coordination methods (`set_ml_requested`) mix infrastructure signalling into the data repository, which leaks the DB-as-message-bus coupling directly into the repository.

**Recommendation:** The existing ABC structure is the right direction — take it one step further. Create separate concrete classes for each domain (`ActivityTimescaleRepo`, `SleepTimescaleRepo`, …) each implementing their respective ABC. `TimescaleRepository` can remain as a facade that composes them, or be deleted entirely. Separately, move `set_ml_requested` / `mark_sync_done` into a dedicated `UserSyncStateRepository` to separate data from control flow.

**ADR needed:** No. This is internal refactoring; it does not change service contracts.

**Reference:** CMU 17-633 — Increase Cohesion tactic: *Split Module*. Fowler — *Decompose Conditional* / *Extract Class*.

---

### 🟡 Finding 5: ML-Service Has No Repository Abstraction

**Category:** Cohesion — Inconsistent Architecture Style
**Location:** `ml-service/src/db/` (~20 files with direct `asyncpg` calls)

**What:** The sync-service has a clean repository pattern with abstract base classes and a single `TimescaleRepository` implementation. The ML-service has ~20 separate `db/*.py` files, each with naked `asyncpg` calls via a module-global `_pool` variable. There is no abstract interface, no repository class, and no indirection.

**Why it matters:** The `get_pool()` function in the ML-service has 77 graph edges, making it the most-connected node in the entire codebase — a textbook God Node. Every ML-service module imports it directly. If the DB layer needs to change (different driver, connection middleware, transaction wrapping), every file must change. Unit tests for ML models must patch `db.pool._pool` — a private implementation detail. Contrast with the sync-service, where tests mock a `TimescaleRepository` instance at the interface boundary.

**Recommendation:** Introduce a `MLDataRepository` ABC in the ML-service mirroring the sync-service pattern. Group the 20 DB functions into 3–4 domain repositories (`ActivityMLRepo`, `HealthMLRepo`, `UserMLRepo`, `PredictionRepo`). This immediately reduces the fan-out from `get_pool()` and makes the ML models unit-testable without database mocks.

**ADR needed:** No. Align with the already-established sync-service pattern.

**Reference:** CMU 17-633 — *Encapsulate* modifiability tactic. The Stable Dependencies Principle: domain logic should not depend on infrastructure details.

---

### 🟡 Finding 6: No Circuit Breaker for External Service Calls

**Category:** Quality Attribute — Availability
**Location:** `sync-service/src/garmin/client.py` → `garmin_call()` · `sync-service/src/libre/client.py`

**What:** `garmin_call()` retries 3 times with exponential backoff per call. There is no circuit breaker: if Garmin's API is consistently unavailable (maintenance window, rate-limiting), every scheduled sync run for every user will exhaust 3 retries before giving up. The LibreLink client has no retry at all.

**Why it matters:** At fleet scale (or with a 2-hour sync interval and many users), a 1-hour Garmin outage generates `3 × N_users × M_api_calls_per_sync` wasted HTTP requests. More importantly, the absence of a circuit breaker means there is no fast-fail: each blocked call holds the event loop (see Finding 2) or occupies an executor thread for the full retry budget. A circuit breaker would open after the first N failures and immediately return an error to all subsequent callers until the Garmin API recovers, reducing waste by 10–50× during outages.

**Recommendation:** Add tenacity's `retry_if_exception_type` combined with a shared `CircuitBreaker` state (e.g. `pybreaker` or a simple counter + cooldown). Open the breaker after 3 consecutive failures; reset after 60 seconds. Apply the same pattern to the LibreLink client.

**ADR needed:** No. Standard reliability pattern with no controversial trade-offs.

**Reference:** Fowler — [CircuitBreaker](https://martinfowler.com/bliki/CircuitBreaker.html) · CMU 17-633 L10 — Availability tactic: *Fault Prevention*.

---

### 🔵 LOW / ⚪ INFO (4)

---

### 🔵 Finding 7: Logging and Sentry Config Triplicated Across Services

**Category:** Cohesion — Code Duplication
**Location:** `api/src/logging_config.py` · `sync-service/src/logging_config.py` · `ml-service/src/logging_config.py`

**What:** All three services contain structurally identical `configure_logging()` and `configure_sentry()` functions. The Sentry `_release()` helper that reads the version from `pyproject.toml` is copied verbatim. Any change to the logging format (adding a field, changing the processor chain) must be applied three times.

**Recommendation:** Extract to a shared `pulsebase_observability` package installable by all services. One change, one test suite, one changelog entry.

**ADR needed:** No.

---

### 🔵 Finding 8: Vendored Chart.js Bloats Repository and Graph

**Category:** Tech Debt — Dependency Management
**Location:** `api/src/static/vendor/chart.umd.min.js`

**What:** A minified Chart.js bundle (~200 KB) is committed to the repository as a static vendor file. This generated 4 large graph communities (0, 1, 2, 3) totalling 375+ nodes of minified identifiers — roughly 10% of the entire graph — obscuring real architecture signals.

**Recommendation:** Serve Chart.js via CDN with a `<link integrity="sha384-…">` Subresource Integrity hash. Or manage it via `pnpm` and bundle it at build time. Remove from git history with `git filter-repo`. The integrity hash provides the same security guarantee as a vendored file.

**ADR needed:** No.

---

### ⚪ Finding 9: Garmin Token Ownership Mixed into Data Repository

**Category:** Cohesion — Separation of Concerns
**Location:** `sync-service/src/repositories/timescale.py` → `get_user_token` / `save_user_token`

**What:** Fernet-encrypted Garmin/Libre tokens are managed by `TimescaleRepository` alongside activity and health data. Token operations are security-sensitive and have different access requirements from health data.

**Recommendation:** Extract to a `TokenRepository` ABC + implementation. This makes it possible to apply different connection-level permissions and audit logging to token access without affecting the data path.

**ADR needed:** No — but worth noting in the existing ADR-0001 (per-service DB roles) as a future refinement.

---

### ⚪ Finding 10: Single-Host Deployment Limits Independent Scaling

**Category:** Quality Attribute — Scalability (accepted trade-off)
**Location:** `docker-compose.yml` · `deploy/docker-compose.public.yml`

**What:** All services are deployed on a single host via Docker Compose. The sync and ML services cannot be scaled horizontally without migrating to an orchestrator (Kubernetes, Nomad).

**Why this is an Info, not a risk:** For a personal health tracker with one user or a small number of users, single-host deployment is the correct choice — simpler, cheaper, fewer failure modes. The architecture does not make this harder to change later (services are already separated into independent containers). This is a deliberate trade-off that should be documented.

**Recommendation:** Record this in an ADR as an explicit decision: "We use Docker Compose on a single host until horizontal scaling becomes necessary." This prevents a future developer from introducing Kubernetes complexity prematurely.

**ADR needed:** Yes (record the accepted trade-off explicitly).

---

## Statistics

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 2 |
| 🟡 Medium | 4 |
| 🔵 Low | 2 |
| ⚪ Info | 2 |

---

## What the Architecture Gets Right (Non-Risks)

These decisions are explicitly good and worth preserving:

- **ADR-0001 (Per-Service DB Roles):** Least-privilege by default. Each service has its own DB role with scoped permissions. This correctly addresses the shared-database trade-off.
- **ADR-0003 (AI Trust Contract):** "Numbers from code, words from LLM" is an architecturally sound guardrail. The post-check gate, evidence catalog, and hallucination guard form a proper safety layer.
- **Repository Pattern in Sync-Service:** Abstract base classes + single concrete implementation is clean and testable. The ML-service should match it.
- **SIGTERM Graceful Shutdown:** All three services register signal handlers before blocking work. Docker Compose `make down` responds immediately.
- **Fernet Token Encryption at Rest:** Correct use of symmetric encryption for credential storage with proper key validation on startup.
- **GDPR Two-Step Account Deletion:** Email-confirmation-gated deletion with a pending state is the right UX and compliance pattern.
- **Health Servers on All Services:** TCP health servers allow Docker healthchecks without HTTP overhead.

---

## Top 3 Immediate Actions

1. **Wrap `garmin_call()` in `run_in_executor`** — 30-minute change, immediate improvement to Libre sync reliability. The event loop blocking is a correctness issue, not a future risk.

2. **Replace `ml_requested` polling with PostgreSQL `LISTEN/NOTIFY`** — Eliminates the 2-minute latency floor and removes inter-service coupling from the `users` schema. Estimated effort: 1–2 days. Write the ADR first.

3. **Introduce a `MLDataRepository` ABC in the ML-service** — Aligns with the already-proven sync-service pattern. Enables proper unit testing of ML models without asyncpg patches. Estimated effort: 1 day.

---

## ADR Recommendations

| Decision | Priority | Rationale |
|----------|----------|-----------|
| `ADR-0005`: Inter-Service Event Channel (LISTEN/NOTIFY vs. Queue vs. DB Flags) | High | Non-obvious trade-off; constrains how a 4th service integrates |
| `ADR-0006`: Single-Host Docker Compose as Deployment Model | Medium | Prevents premature K8s migration; documents scalability boundary |
| Update `ADR-0001`: Extract Token Repository | Low | Token access patterns differ from health data; worth noting for future role refinement |

---

*Created with AI assistance (GitHub Copilot + dev-best-practices plugin).
Graph source: graphify-out/graph.json (3 786 nodes, 8 554 edges).
Findings are to be verified against the current codebase — not a substitute for manual architecture reviews.*
