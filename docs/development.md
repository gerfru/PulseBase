# Developer Guide

Lokale Entwicklung, Tests, CI/CD und Debugging für PulseBase.

---

## Voraussetzungen

| Tool | Version | Zweck |
|------|---------|-------|
| Docker + Compose | ≥ 27 | Services, DB, Caddy (public) |
| Python | 3.12+ | API, Sync, ML (lokal) |
| uv | aktuell | Python Package Manager |
| Node.js | 22 LTS | JS-Tests (Vitest) |
| npm | aktuell | JS-Dependencies |

---

## Ersteinrichtung

```bash
# 1. Env-Files aus Vorlagen erstellen
cp env/.env.example env/.env
cp env/.env.app.example env/.env.app  # DB_APP_USER, DB_APP_PASSWORD, FERNET_KEY
cp env/.env.api.example env/.env.api
cp env/.env.sync.example env/.env.sync
cp env/.env.ml.example env/.env.ml

# 2. Secrets generieren (SESSION_SECRET, FERNET_KEY, DB-Passwörter)
make gen-secrets
# → SESSION_SECRET → env/.env.api (min. 32 Zeichen)
# → FERNET_KEY    → env/.env.app (gilt für api, sync-service und ml-service)
# → DB_APP/SYNC/ML_PASSWORD → env/.env.app
# → druckt ausserdem den age-keygen-Hinweis für Backups (env/.env.backup)

# 3. Dateiberechtigungen absichern
make secure-env

# 4. Pre-commit Hooks installieren
pip install pre-commit
pre-commit install

# 5. DB starten + Migrationen ausführen
make migrate

# 6. Alle Services starten
make up
```

Für lokalen Betrieb: `make setup` zeigt die vollständige Schritt-für-Schritt-Anleitung.

---

## Services neustarten nach Code-Änderungen

```bash
make dashboard    # api/src/** geändert
make sync         # sync-service/src/** geändert
make analytics    # ml-service/src/** geändert
make up           # alles auf einmal
```

---

## Datenbank

```bash
make migrate      # Flyway-Migrationen ausführen (V1–V31)
make db           # psql-Shell öffnen
make db SQL="SELECT ..." # SQL direkt ausführen
```

Migrationen liegen unter `db/migrations/V*.sql`. Niemals manuell SQL auf Prod.

---

## Backups

Der `backup`-Service ([`backup/`](../backup/)) läuft als Container im Stack und sichert die DB
täglich verschlüsselt (`pg_dump -Fc` → age → Retention → optional rclone). Details:
[security.md §9.6](security.md) · [deployment-public.md](deployment-public.md#backups-health-pii-pflicht).

```bash
make backup        # Backup sofort auslösen (One-Off; sonst täglich via Container-Loop)
make restore-test  # neuesten Backup TimescaleDB-korrekt in Wegwerf-DB restoren + prüfen
                   # (Key-Pfad aus AGE_IDENTITY in env/.env.backup)
```

Der CI-Job **`backup-smoke`** (Required) baut das Backup-Image und beweist die Kette
`pg_dump → age → decrypt → pre/post_restore → pg_restore` gegen eine seed-Test-DB.

---

## Test-Architektur

PulseBase hat vier Teststufen:

```
api/tests/
├── conftest.py              Shared fixtures + make_session() Helper
├── test_auth.py             Login, Register, Password-Reset, E-Mail-Verifikation
├── test_account.py          Account-Löschung, Daten-Export (DSGVO)
├── test_api.py              JSON-Endpunkte: Activities, Sleep, HRV, ML, ...
├── test_api_endpoints.py    Auth-Schutz aller API-Routen (require_user)
├── test_pages.py            HTML-Seiten (Dashboard, Settings, Metrics, ...)
├── test_db.py               DB-Hilfsfunktionen + Readiness-Score-Logik
├── test_coverage.py         Randfälle: Crypto, Fernet-Key, TRIMP, Garmin/Libre-Links
├── test_training_load.py    Banister TRIMP-Modell (_trimp + build_training_load)
├── test_garmin_client.py    GarminClient Token-Handling
├── test_libre_client.py     LibreLinkUp-Client
└── e2e/
    ├── conftest.py          Playwright-Fixtures (browser_context, page, authenticated_page,
    │                          clean_register_email, registered_test_user, unverified_test_user,
    │                          reset_test_user, epilepsy_test_user, session_secret)
    ├── create_ci_user.py    Test-User in garmin_test-DB anlegen
    ├── test_smoke.py        Browser-Smoke-Tests gegen lokalen Stack (Port 8001)
    ├── test_auth_flows.py   Register, E-Mail-Verify, Passwort-Reset (Token aus DB injiziert)
    └── test_static_pages.py Öffentliche Seiten (Privacy/Terms/Imprint/Accessibility) + Epilepsie

sync-service/tests/
├── test_mapper.py           Garmin-Daten-Mapper (Activity, Sleep, HRV, ...)
├── test_libre_mapper.py     LibreLink-Daten-Mapper
├── test_libre_client.py     LibreLinkUp-Client (Token-Login, API-Fehler)
├── test_repository.py       TimescaleRepository (asyncpg Roundtrips)
├── test_main.py             Orchestrierung + Retry-Logik
├── test_crypto.py           Fernet Encrypt/Decrypt + Token-Dir-Serialisierung (inkl. Path-Traversal)
└── test_garmin_client.py    GarminClient Token-Login, Fallback, save_token, None-Defaults

ml-service/tests/
└── test_models.py           ML-Modelle (Readiness, Anomaly, Correlation, ...)
```

### Mock-Strategie

- **DB-Zugriff**: `get_pool` wird per `unittest.mock.AsyncMock` gemockt — kein echter DB-Zugriff in Unit-Tests
- **Auth**: `require_user` wird in Route-Tests direkt gemockt (`patch("src.routes.*.require_user", ...)`)
- **Externe APIs**: Garmin-Client und Libre-Client werden per MagicMock ersetzt
- **Session-Cookie**: `make_session(client, user_id=1)` aus `tests/conftest.py` erzeugt einen signierten Starlette-Session-Cookie für den Test-Client
- **E2E**: Echter Browser (Playwright/Chromium) gegen laufenden Docker-Stack, kein Mocking

### Wichtig: Patch-Pfad bei `require_user`

```python
# Richtig — am Import-Ort patchen:
patch("src.routes.account.require_user", AsyncMock(return_value=TEST_USER))

# Falsch — am Definitions-Ort patchen (hat keinen Effekt):
patch("src.deps.require_user", ...)
```

---

## Tests ausführen

### Alle Unit-Tests (ohne Docker)

```bash
make test
# entspricht:
cd api         && .venv/bin/pytest tests/ -v --ignore=tests/e2e
cd sync-service && .venv/bin/pytest tests/ -v
cd ml-service  && .venv/bin/pytest tests/ -v
```

### Mit Coverage-Report (Terminal + HTML)

```bash
make test-coverage
# → HTML-Report: api/htmlcov/index.html
```

### JS-Tests (Vitest)

```bash
make test-js           # einmalig
make test-js-coverage  # mit Coverage-Report (api/coverage/index.html)
```

Vitest testet zwölf Dateien aus `coverage.include`: die sechs Utility-Module (`chart-utils.js`, `dashboard-utils.js`, `dashboard-nav.js`, `dashboard-status.js`, `epilepsy.js`, `onboarding.js`) plus die sechs reinen Render-Module (`metrics-ml.js` und seit Wave 16 PR-D `metrics-energy/readiness/sleep/garmin/activity.js`) (Schwellen: ≥95% Statements/Branches/Lines, ≥90% Functions; erreicht: Statements 99.7 / Branches 95.07 / Functions 98.25 / Lines 100). Verbleibende Branch-Lücken sind Chart.js-Tick-Callbacks (von der gemockten Chart-Lib nie aufgerufen) — kein 100%-Ziel. `dashboard-hero.js` hat Unit-Tests für `heroRecommendation()`, ist aber bewusst aus `coverage.include` ausgeschlossen — DOM-schwere Funktionen (`buildHeroCard`, `buildMlTabs`) via Playwright E2E (TEST-L3, dokumentierte Ausnahme). `colors.js` ist nicht in `coverage.include`, hat aber einen eigenen WCAG-Kontrast-Guard (`tests/js/colors.test.js`): jede Chart-Datenfarbe muss in hellem und dunklem Theme ≥ 3:1 erfüllen.

### E2E-Tests (Playwright)

```bash
make test-e2e
# 1. make test-build  → baut api-Test-Image (ohne laufenden Stack zu belasten)
# 2. make test-env-up → startet Test-Stack auf Port 8001 (--wait-timeout 120)
# 3. Erzeugt Test-User, führt Chromium-Tests durch
# 4. make test-env-down → stoppt Stack (mit docker rm -f Fallback)
```

E2E-Credentials (lokal):
```
TEST_EMAIL    = e2e@pulsebase.test
TEST_PASSWORD = E2eLocalTest1!
```

Die E2E-Suite enthält ein **axe-core-Accessibility-Gate** (`tests/e2e/test_a11y.py`, `axe-playwright-python`): es scannt die kritischen Seiten in **hellem und dunklem** Theme und blockiert bei Violations der Stufen `critical`/`serious`; zusätzlich wird der Fokus-Indikator-Kontrast (WCAG 1.4.11) gemessen. Auth läuft per injiziertem Session-Cookie (rate-limit-sicher). Datenlastige Detailseiten (`/activity/{id}`) sind mit `@requires_data` markiert und brauchen geseedete Garmin-Daten.

Voll-Läufe als ein Kommando:
```bash
make test-all          # Unit + E2E + JS-/py-Coverage (ohne Seed)
make test-all-seeded   # zusätzlich Prod→Test-Seed + CI_HAS_DATA=true (inkl. @requires_data)
make test-e2e-seeded   # nur die E2E mit echten Daten
```

Wichtig: `authenticated_page` ist session-scoped — alle Tests teilen eine Browser-Page mit Auth-Cookie (1 Login pro Run). Jeder Test muss explizit zur Ziel-URL navigieren. Tests die einen komplett unauthentifizierten Context brauchen, müssen wie `test_account_export_unauthenticated_redirects_to_login` einen isolierten Browser öffnen (eigener `async with async_playwright()` Block).

### Einzelne Testdatei

```bash
cd api && .venv/bin/pytest tests/test_auth.py -v
cd api && .venv/bin/pytest tests/test_auth.py::test_login_success_redirects -v
```

---

## Coverage-Ziele

| Service | Aktuell | Minimum (CI) | Ziel |
|---------|---------|--------------|------|
| api (Python) | ~99% | 70% | 100% |
| api (JS) | 100% Lines / ~96% Branches / ~94% Functions (6 Dateien) | 95% Stmts/Branches/Lines, 90% Functions | — |
| sync-service | ~97%+ | 70% | 70%+ |
| ml-service | ~80%+ | 80% | 80%+ |

Die JS-Schwelle (95% Statements/Branches/Lines, 90% Functions) gilt für die zwölf gemessenen Module (6 Utility + 6 Render). `dashboard-hero.js` und die DOM-/fetch-lastigen Loader sind bewusst ausgeschlossen (TEST-L3). sync-service: CI-Gate auf 70% angehoben (W13 R3, M-79). ml-service: CI-Gate auf 80% angehoben (W10 R2, M-61).

---

## Pre-commit Hooks

Reihenfolge beim Commit:

1. **gitleaks** — Secret-Scan (kein Commit wenn Secrets im Diff)
2. **pre-commit-hooks** — trailing whitespace, YAML/JSON/TOML-Validierung, `no-commit-to-branch` (blockiert direkten Push auf `main`)
3. **bandit** — SAST: Security-Check für `api/src/`, `sync-service/src/`, `ml-service/src/`
4. **semgrep** — SAST (`p/python` + `p/owasp-top-ten`) für `api/src/`, `sync-service/src/`, `ml-service/src/`
5. **ruff** — Python Lint + Auto-Fix
6. **ruff-format** — Python Formatting
7. **detect-secrets** — Baseline-Check gegen `.secrets.baseline`
8. **biome** — JS Lint + Format für `api/src/static/`
9. **mypy-api** — Type Check `api/src/`
10. **mypy-sync** — Type Check `sync-service/src/`
11. **mypy-ml** — Type Check `ml-service/src/`

Hooks manuell auf allen Dateien ausführen:

```bash
pre-commit run --all-files
```

---

## CI/CD Pipeline

Alle Jobs laufen bei jedem PR. Pipeline schlägt bei jedem roten Job fehl. Global `permissions: contents: read` (Least Privilege).

| Job | Tool | Was wird geprüft |
|-----|------|-----------------|
| `lint` | ruff | Python Lint + Format-Check |
| `js-lint` | Biome 2.x | JS Lint + Format-Check (`api/src/static/`) |
| `security` | gitleaks + pip-audit + bandit + semgrep | Secrets, bekannte Vulns, SAST, cross-file Taint |
| `typecheck` | mypy | alle 3 Services mit `--explicit-package-bases` |
| `test` | pytest + pytest-cov | Unit-Tests aller 3 Services mit Coverage-Schwellen |
| `js-test` | Vitest | JS Unit-Tests mit Coverage (95% Stmts/Branches/Lines, 90% Functions) |
| `e2e` | Playwright + axe-core | Smoke-Tests + Accessibility-Gate (light/dark) gegen docker-compose.test.yml (Port 8001) |
| `trivy` | trivy | Docker-Image-Scan (CRITICAL + HIGH → exit 1) |

### CI schlägt fehl — häufige Ursachen

**`typecheck` schlägt fehl:**
```bash
# Lokal reproduzieren:
cd api && mypy src/ --ignore-missing-imports --explicit-package-bases
cd sync-service && mypy src/ --ignore-missing-imports --explicit-package-bases
cd ml-service && mypy src/ --ignore-missing-imports --explicit-package-bases
```

**`test` schlägt fehl (Coverage):**
```bash
make test-coverage   # → api/htmlcov/index.html zeigt nicht abgedeckte Zeilen
```

**`security` → bandit:**
```bash
bandit -r api/src/ sync-service/src/ ml-service/src/ -q
```

**`security` → semgrep:**
```bash
semgrep --config p/python --config p/owasp-top-ten .
```

**`trivy` schlägt fehl:**
```bash
docker build -t pulsebase-api:local api/
trivy image --severity CRITICAL,HIGH --ignore-unfixed pulsebase-api:local
```

---

## Neuen Test schreiben

### Python Unit-Test (api)

```python
# api/tests/test_meinefeature.py
from unittest.mock import AsyncMock, patch
from tests.conftest import TEST_USER

async def test_mein_endpoint_returns_200(client):
    with patch("src.routes.api.require_user", AsyncMock(return_value=TEST_USER)):
        with patch("src.routes.api.get_meine_daten", AsyncMock(return_value=[])):
            r = await client.get("/api/meine-route")
    assert r.status_code == 200
```

### Session-Cookie setzen (für Routen mit require_user)

```python
from tests.conftest import make_session

def test_mit_session(client):
    make_session(client, user_id=1)
    # client sendet jetzt einen signierten Session-Cookie mit user_id=1
```

### False Positives bei detect-secrets vermeiden

```python
env_overrides = {
    "DB_PASSWORD": "test",  # pragma: allowlist secret
    "SESSION_SECRET": "a" * 32,  # pragma: allowlist secret  — min. 32 Zeichen
}
```

---

## Tailwind CSS neu bauen

Nach Änderungen an HTML-Templates oder `api/src/static/input.css`:

```bash
make tailwind-build
# → api/src/static/tailwind.min.css wird aktualisiert (committen!)
```

---

## Befehlsübersicht (kanonisch)

Vollständige Referenz aller `make`-Targets — die README verlinkt hierher.

### Betrieb

| Befehl | Beschreibung |
|--------|--------------|
| `make up` | Images bauen + alle Services starten (braucht Reverse Proxy auf dem `proxy`-Netz, z. B. homelab-gateway) |
| `make up-public` | Öffentliche Instanz: gebündeltes Caddy + Let's Encrypt (kein homelab-gateway nötig) — siehe [deployment-public.md](deployment-public.md) |
| `make down` | Services stoppen |
| `make clean` | Services stoppen + Volumes + verwaiste Container entfernen |
| `make reset` | ⚠ Volumes löschen + DB komplett neu aufsetzen (**löscht alle User!**) |
| `make status` | Container-Status |

### Code-Änderungen übernehmen

| Befehl | Beschreibung |
|--------|--------------|
| `make dashboard` | API (Dashboard) neu bauen + starten — nach Änderungen in `api/src/` |
| `make analytics` | ML-/Analytics-Service neu bauen + starten — nach Änderungen in `ml-service/src/` |
| `make sync` | Sync-Service **neu bauen + starten** — nach Änderungen in `sync-service/src/` |
| `make tailwind-build` | Tailwind CSS neu bauen — nach Template-/`input.css`-Änderungen (Output committen!) |

### Sync & Daten

| Befehl | Beschreibung |
|--------|--------------|
| `make trigger-sync` | Garmin-Sync **sofort anfordern** (kein Rebuild — der laufende sync-service verarbeitet es binnen 1 Minute) |
| `make backfill-energy` | Energie-Scores rückwirkend neu berechnen |
| `make backfill-battery` | `body_battery_custom` mit aktuellem Modell neu berechnen (löscht alte Predictions zuerst) |

> **`make sync` vs. `make trigger-sync`:** `make sync` baut den Container neu (für Code-Änderungen, löst dabei einen Backfill-Sync aus). Für „jetzt einmal Daten holen" ohne Rebuild ist **`make trigger-sync`** das richtige Target.

### Datenbank-Befehle

| Befehl | Beschreibung |
|--------|--------------|
| `make migrate` | Flyway-Migrationen ausführen (V1–V31) |
| `make db` | psql-Shell öffnen |
| `make db SQL="SELECT ..."` | SQL direkt ausführen |

### Setup & Secrets

| Befehl | Beschreibung |
|--------|--------------|
| `make setup` | Schritt-für-Schritt-Einrichtungsanleitung anzeigen |
| `make gen-secrets` | SESSION_SECRET (→ `.env.api`), FERNET_KEY + DB-Rollen-Passwörter (→ `.env.app`) generieren |
| `make secure-env` | `chmod 600` auf alle `env/`-Dateien (inkl. `.env.app`) |
| `make add-host` | `pulsebase.local` in `/etc/hosts` eintragen (lokaler Betrieb) |

### Logs

| Befehl | Beschreibung |
|--------|--------------|
| `make logs-dashboard` | API-Logs live |
| `make logs-sync` | Sync-Service-Logs live |
| `make logs-analytics` | ML-Service-Logs live |
| `make logs-all` | Alle Logs zusammen |

### Tests

| Befehl | Beschreibung |
|--------|--------------|
| `make test` | Unit-Tests aller 3 Services (kein Docker nötig) |
| `make test-coverage` | Coverage-Report aller 3 Services (Terminal + HTML) |
| `make test-js` / `make test-js-coverage` | JS-Unit-Tests (Vitest) |
| `make test-e2e` | Playwright-E2E (inkl. axe-Accessibility-Gate) gegen Test-Stack auf Port 8001 (baut + startet + stoppt automatisch) |
| `make test-e2e-seeded` | wie `test-e2e`, aber mit Prod→Test-Seed + `CI_HAS_DATA=true` (inkl. `@requires_data`) |
| `make test-all` / `make test-all-seeded` | Voll-Lauf als ein Kommando (Unit + E2E + JS-/py-Coverage), optional mit Daten-Seed |
