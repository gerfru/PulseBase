# Developer Guide

Lokale Entwicklung, Tests, CI/CD und Debugging für PulseBase.

---

## Voraussetzungen

| Tool | Version | Zweck |
|------|---------|-------|
| Docker + Compose | ≥ 27 | Services, DB, Traefik |
| Python | 3.12+ | API, Sync, ML (lokal) |
| uv | aktuell | Python Package Manager |
| Node.js | 22 LTS | JS-Tests (Vitest) |
| npm | aktuell | JS-Dependencies |

---

## Ersteinrichtung

```bash
# 1. Env-Files aus Vorlagen erstellen
cp env/.env.example env/.env
cp env/.env.api.example env/.env.api
cp env/.env.sync.example env/.env.sync
cp env/.env.ml.example env/.env.ml   # falls noch nicht vorhanden: DB_APP_USER + DB_APP_PASSWORD setzen

# 2. Secrets generieren (SESSION_SECRET + FERNET_KEY)
make gen-secrets
# → Ausgabe in env/.env.api (SESSION_SECRET) und env/.env + env/.env.sync (FERNET_KEY) eintragen

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

Für den Homelab-Betrieb via `garmin.home.lab`: `make setup` zeigt die vollständige Schritt-für-Schritt-Anleitung.

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
make migrate      # Flyway-Migrationen ausführen (V1–V20+)
make db           # psql-Shell öffnen
make db SQL="SELECT ..." # SQL direkt ausführen
```

Migrationen liegen unter `db/migrations/V*.sql`. Niemals manuell SQL auf Prod.

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
    ├── conftest.py          Playwright-Fixtures (browser_context, page, authenticated_page)
    ├── create_ci_user.py    Test-User in garmin_test-DB anlegen
    └── test_smoke.py        Browser-Smoke-Tests gegen lokalen Stack (Port 8001)

sync-service/tests/
└── test_mapper.py           Garmin-Daten-Mapper (Activity, Sleep, HRV, ...)

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

Vitest testet vier Utility-Dateien: `chart-utils.js`, `dashboard-utils.js`, `dashboard-nav.js`, `dashboard-status.js` (Threshold: ≥65% Lines, ≥70% Functions). DOM-schwere Dateien (Loaders, Hero) und interne Poll-Funktionen werden durch Playwright E2E abgedeckt.

### E2E-Tests (Playwright)

```bash
make test-e2e
# startet Docker-Stack auf Port 8001, erzeugt Test-User, führt Chromium-Tests durch, stoppt Stack
```

E2E-Credentials (lokal):
```
TEST_EMAIL    = e2e@pulsebase.test
TEST_PASSWORD = E2eLocalTest1!
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
| api (JS) | ~68% Lines / ~74% Functions | 65% Lines / 70% Functions | 80%+ |
| sync-service | ~20% | 20% | 70%+ |
| ml-service | ~19% | 15% | 70%+ |

Die JS-Schwelle (65/70) gilt für die vier getesteten Utility-Dateien. Interne Poll-Funktionen in `dashboard-status.js` sind von Unit-Tests ausgenommen (Playwright-E2E). Die niedrigen Schwellen für sync/ml sind bewusste Einstiegswerte — sie steigen wenn Mapper-, Repository- und Modell-Tests ergänzt werden.

---

## Pre-commit Hooks

Reihenfolge beim Commit:

1. **gitleaks** — Secret-Scan (kein Commit wenn Secrets im Diff)
2. **pre-commit-hooks** — trailing whitespace, YAML/JSON/TOML-Validierung, `no-commit-to-branch` (blockiert direkten Push auf `main`, `dev`, `master`)
3. **ruff** — Python Lint + Auto-Fix
4. **ruff-format** — Python Formatting
5. **bandit** — SAST: Security-Check für `api/src/`, `sync-service/src/`, `ml-service/src/`
6. **detect-secrets** — Baseline-Check gegen `.secrets.baseline`
7. **biome** — JS Lint + Format für `api/src/static/`
8. **mypy-api** — Type Check `api/src/`
9. **mypy-sync** — Type Check `sync-service/src/`
10. **mypy-ml** — Type Check `ml-service/src/`

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
| `js-test` | Vitest | JS Unit-Tests mit Coverage (65% Lines / 70% Functions) |
| `e2e` | Playwright | Smoke-Tests gegen docker-compose.test.yml (Port 8001) |
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
docker build -t garmin-api:local api/
trivy image --severity CRITICAL,HIGH --ignore-unfixed garmin-api:local
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
    "SESSION_SECRET": "test-secret",  # pragma: allowlist secret
}
```

---

## Tajllwind CSS neu bauen

Nach Änderungen an HTML-Templates oder `api/src/static/input.css`:

```bash
make tailwind-build
# → api/src/static/tailwind.min.css wird aktualisiert (committen!)
```

---

## Nützliche Make-Befehle

```bash
make logs-dashboard   # API-Logs live
make logs-sync        # Sync-Service-Logs live
make logs-analytics   # ML-Service-Logs live
make logs-all         # Alle Logs zusammen
make status           # Container-Status
make sync             # Garmin-Sync sofort auslösen (nicht auf 6 Uhr warten)
make gen-secrets      # SESSION_SECRET + FERNET_KEY generieren
make secure-env       # chmod 600 auf alle env/-Dateien
make reset            # ⚠ Volumes löschen + DB komplett neu aufsetzen (löscht alle User!)
```
