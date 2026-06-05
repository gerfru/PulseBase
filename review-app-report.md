# PulseBase — App Review Report

**Datum:** 2026-06-05
**Stack:** FastAPI + Python 3.14 | TimescaleDB PG16 | asyncpg | Jinja2 + Chart.js | scikit-learn | Docker Compose | GitHub Actions | uv
**Regelquelle:** Plugin-Rules (`essential-rules.md`, `app-rules.md`, `github-rules.md`, `architecture-rules.md`)
**ASVS-Level:** L2 (Auth + sensible Gesundheitsdaten + DSGVO)
**Dokumentierte Ausnahmen übernommen:** ARCH-M2/L2/L3/L5, CICD-M3/M4, OBS-L1/L2/L3, QUAL-M2, TEST-L1/L4

---

## Achsenübersicht

| Achse | Ampel | #Critical | #High | Wichtigste verletzte Regel |
|---|:---:|:---:|:---:|---|
| Architektur & 12-Factor | 🟡 | 0 | 0 | 12-Factor #11: structlog auf stderr statt stdout |
| Security (ASVS L2) | 🔴 | 0 | 1 | ASVS 2.1.1: bcrypt ohne Längenlimit; CSRF auf unauthenticated POSTs |
| Code-Qualität | 🔴 | 0 | 2 | Race Condition auf Metrik-Countern; Fernet-Null-Pfad |
| Tests & Zuverlässigkeit | 🟡 | 0 | 1 | Cookie-Security-Flags nicht assertiert; Branch-Coverage fehlt |
| CI/CD & Delivery | 🟡 | 0 | 0 | Renovate platformAutomerge wirkungslos; e2e-Secret-Guard fehlt |
| Observability & Betrieb | 🟡 | 0 | 0 | Sentry nicht in sync/ml aktiv; Garmin-Fehler stumm auf WARNING |

---

## Alle Befunde (sortiert nach Severity)

### HIGH

| # | Titel | Datei:Zeile | Achse | Conf | Verletzte Regel | Fix | Aufwand |
|---|---|---|---|---|---|---|---|
| H1 | bcrypt DoS: Passwort ohne `max_length` | `api/src/routes/auth.py:57,139,318` + `account.py:42` | Security | 9 | app-rules → Auth: Rate Limiting + Input-Validierung; ASVS 2.1.1 | `password: str = Form(max_length=128)` an allen 4 Stellen | S |
| H2 | Race Condition: Metrik-Counter ohne Lock gelesen | `api/src/main.py:96,187-189` | Qualität | 8 | architecture-rules → Testing; concurrent reads ohne `async with _metrics_lock` | Lese-Zugriff in `app_metrics()` unter `_metrics_lock` verschieben; `_error_requests += 1` im `except`-Block | S |
| H3 | Fernet-Null-Pfad speichert Token im Klartext | `sync-service/src/main.py:157,167,206,229,238` | Qualität | 7 | app-rules → Environment & Secrets; `if settings.fernet_key else blob` bypassed defensive layer | `else`-Pfade durch `raise RuntimeError("FERNET_KEY required")` ersetzen | S |
| H4 | Session-Cookie: SameSite/Secure nicht unit-assertiert | `api/tests/test_auth.py` (~Z.966) | Tests | 9 | app-rules → Auth: Sessions httpOnly/secure/sameSite=Lax | `assert "samesite=lax" in ...` und `assert "secure" in ...` ergänzen | S |

---

### MEDIUM

#### Security

| # | Titel | Datei:Zeile | Conf | Verletzte Regel | Fix | Aufwand |
|---|---|---|---|---|---|---|
| M1 | CSRF-Token fehlt auf `reset-request` und `resend-verify` | `api/src/routes/auth.py:197-215,237-252` | 8 | app-rules → Auth: ASVS 4.2.2 | CSRF-Token in GET-Formular einbetten, im POST prüfen (`verify_csrf_token()`) | M |
| M2 | Reset-Token auf 16 Hex-Zeichen (64 Bit) truncated | `api/src/routes/auth.py:264,288` | 8 | app-rules → Auth: ASVS 2.5.6 | `[:16]` entfernen → voller SHA-256-Hex (256 Bit) | S |
| M3 | Form-Felder ohne `max_length`: name, garmin/libre-creds | `auth.py:137` + `garmin.py:44-45` + `libre.py:35-36` | 8 | app-rules → Input-Validierung: ASVS 5.1.3 | `Form(max_length=320)` für Emails, `Form(max_length=128)` für Passwörter | S |
| M4 | `/account/export` ohne `Cache-Control: no-store` | `api/src/routes/account.py:70-73` | 8 | app-rules → Caching + ASVS 8.3.4 | `headers={"Cache-Control": "no-store"}` in JSONResponse | S |

#### Architektur

| # | Titel | Datei:Zeile | Conf | Verletzte Regel | Fix | Aufwand |
|---|---|---|---|---|---|---|
| M5 | `structlog.WriteLoggerFactory` schreibt auf stderr | `api/src/logging_config.py:42` + sync + ml (je Z.41-42) | 9 | 12-Factor #11: Logs auf stdout | `WriteLoggerFactory(file=sys.stdout)` in allen 3 Services | S |

#### Code-Qualität

| # | Titel | Datei:Zeile | Conf | Verletzte Regel | Fix | Aufwand |
|---|---|---|---|---|---|---|
| M6 | `dispatch()`-Methoden + Route-Handler ohne Return-Typen | `api/src/main.py:35,73,103,174,179,184,194` | 9 | Typisierung-Schwellwert | `-> Response`, `-> dict[str, Any]`, `-> AsyncIterator[None]` ergänzen | S |
| M7 | `_run_body_battery()` mit 11 Parametern | `ml-service/src/inference_models.py:183` | 9 | Komplexität: >6 Parameter | Parameter in `BodyBatteryInputs`-Dataclass bündeln | M |
| M8 | Dreifach duplizierter `sentry_sdk.init()`-Block | `api/main.py:134` + `sync/main.py:331` + `ml/main.py:211` | 9 | Duplikation >3% | `configure_sentry(settings)` in `logging_config.py` pro Service | M |
| M9 | `register()` / `_validate_register_form()` mit je 9 Parametern | `api/src/routes/auth.py:90,135` | 8 | Komplexität: >6 Parameter | `RegisterFormData`-Dataclass oder Pydantic-Modell | M |

#### Tests

| # | Titel | Datei:Zeile | Conf | Verletzte Regel | Fix | Aufwand |
|---|---|---|---|---|---|---|
| M10 | Referrer-Policy und voller HSTS-Wert nicht assertiert | `api/tests/test_api.py:41` | 8 | architecture-rules → Testing; app-rules → Security Headers | `referrer-policy` und `max-age=31536000; includeSubDomains` in Header-Test ergänzen | S |
| M11 | Branch-Coverage nicht konfiguriert (alle 3 Services) | `api/pyproject.toml` + sync + ml | 9 | architecture-rules → Testing: 60-70% Branches | `branch = true` unter `[tool.coverage.run]` in allen 3 `pyproject.toml` | S |
| M12 | JS-Coverage schließt `dashboard-hero.js` (398 LOC) und `dashboard-loaders.js` (556 LOC) aus | `api/vitest.config.js:11-17` | 8 | github-rules → Testing | Beide in `coverage.include` aufnehmen oder mit Begründung dokumentieren | M |
| M13 | `_sync_activities` ohne Unit-Test (kritischer Datenpfad) | `sync-service/tests/test_sync_logic.py` | 8 | architecture-rules → Testing: API Endpoints Priorität 1 | Tests nach Muster `TestSyncDay` ergänzen (happy path + Fehlerbehandlung) | M |
| M14 | `ml-service/tests/test_db.py` ohne Testfunktionen | `ml-service/tests/test_db.py` | 8 | architecture-rules → Testing: Data-Transformationen Priorität 2 | `save_prediction` + `get_yesterday_prediction` mit AsyncMock-Pool testen | M |
| M15 | `/api/metrics` nicht in Auth-Guard-Parametrize | `api/tests/test_api.py:113-148` | 7 | app-rules → Auth an 3 Schichten | Endpunkt in Liste ergänzen + Verhalten dokumentieren (public/protected) | S |
| M16 | E2E `authenticated_page`-Fixture session-scoped — Zustandslecks möglich | `api/tests/e2e/conftest.py:35-44` | 7 | architecture-rules → Testing: keine Test-Interdependenz | `scope="function"` oder explizites `page.goto()` am Testanfang | M |

#### CI/CD

| # | Titel | Datei:Zeile | Conf | Verletzte Regel | Fix | Aufwand |
|---|---|---|---|---|---|---|
| M17 | PR-Size-Check nicht in `e2e`-`needs`-Gate | `ci.yml:202` | 9 | github-rules → PR-Größe < 400 LOC | `check-pr-size` zu `needs:` beim e2e-Job ergänzen | S |
| M18 | Renovate `platformAutomerge: false` macht Automerge wirkungslos | `renovate.json:5` | 8 | github-rules → Renovate devDeps patch Automerge | `"platformAutomerge": true` setzen | S |
| M19 | `e2e`-Job: leere Secrets ohne Fail-Guard | `ci.yml:237,248` | 8 | github-rules → CI: reproduzierbar | `if [ -z "$TEST_EMAIL" ] || [ -z "$TEST_PASSWORD" ]; then exit 1; fi` vor Script | S |

#### Observability

| # | Titel | Datei:Zeile | Conf | Verletzte Regel | Fix | Aufwand |
|---|---|---|---|---|---|---|
| M20 | Garmin-Sync-Fehler als `WARNING` — nicht in Sentry sichtbar | `sync-service/src/main.py:68,84,96,108,120,132` | 9 | app-rules → Error Tracking: Sentry | `logger.warning` → `logger.error(exc_info=True)` bei per-Metrik-Sync-Fehlern | S |
| M21 | Sentry-DSN leer in sync- und ml-Service | `env/.env.sync` + `env/.env.ml` | 9 | app-rules → Monitoring-Minimum: Sentry | `SENTRY_DSN` in `env/.env.app` zentralisieren (alle 3 Services) | S |

---

### LOW (Auswahl — hohe Confidence oder unmittelbarer Fix)

| # | Titel | Datei:Zeile | Achse | Conf | Fix | Aufwand |
|---|---|---|---|---|---|---|
| L1 | `activity.js`: `econRow()` interpoliert ohne `esc()` in `innerHTML` | `api/src/static/activity.js:198-202` | Security | 7 | `esc(label)`, `esc(val)`, `esc(sub)` verwenden | S |
| L2 | DB-Index fehlt auf `password_reset_token_hash` | `api/src/db/users.py:284-290` | Security | 7 | `CREATE INDEX IF NOT EXISTS idx_users_reset_token ON users(password_reset_token_hash) WHERE ... IS NOT NULL` als V23-Migration | S |
| L3 | `ml-service` Sentinel `/tmp/ml_alive` nur bei Inferenz (1×/Tag) geschrieben | `ml-service/src/main.py:172` | Architektur | 8 | Sentinel in separatem Heartbeat-Loop (alle 30s) aktualisieren — Healthcheck schlägt sonst nach 2 min fehl | S |
| L4 | `docker-compose.yml`: Uptime Kuma / Loki / Promtail fehlen (laut CLAUDE.md erwartet) | `docker-compose.yml` | Architektur | 9 | Services ergänzen oder dokumentieren dass sie in separatem Stack laufen | M |
| L5 | `docker-compose.test.yml`: kein `tmpfs` für db-test | `docker-compose.test.yml:3` | Architektur | 8 | `tmpfs: /var/lib/postgresql/data` ergänzen (schnell, kein Cleanup) | S |
| L6 | `api/src/db/users.py` nähert sich 400-Zeilen-Grenze (399 Z.) | `api/src/db/users.py` | Qualität | 9 | Split-Trigger dokumentieren: bei nächstem Feature Auth-Queries in `users_auth.py` | S |
| L7 | `main()` in sync-service und ml-service >50 Zeilen | `sync-service/src/main.py:318` + `ml-service/src/main.py:202` | Qualität | 9 | Startup-Sequenz in Hilfsfunktion auslagern | S |
| L8 | PR-Size `grep -cP` zählt `+++`-Diff-Header mit | `ci.yml:31` | CI/CD | 8 | `grep -cP '^\+(?!\+\+)'` (oder portable `grep -cE '^\+[^+]'`) | S |
| L9 | Renovate ignoriert `loki`/`promtail`/`uptime-kuma` ohne Ablaufdatum | `renovate.json:6` | CI/CD | 7 | `description`-Feld mit Begründung ergänzen | S |
| L10 | `request_id` auf 8 Zeichen (32 Bit) gekürzt — Kollision möglich | `api/src/main.py:77` | Observability | 6 | Vollständige UUID oder mindestens 12 Zeichen verwenden | S |

---

## Fix-Reihenfolge

### Sofort — Security + kritischer Betrieb (alle S-Aufwand außer M1)

1. **H1** — `Form(max_length=128)` an 4 Stellen (`auth.py`, `account.py`)
2. **M3** — `max_length` auf name/garmin/libre-Felder
3. **M4** — `Cache-Control: no-store` auf `/account/export`
4. **H2** — Metrik-Counter unter Lock lesen + `_error_requests` im `except`-Block
5. **H3** — Fernet-Null-Pfad durch `raise RuntimeError` ersetzen
6. **M21** — `SENTRY_DSN` in `.env.app` zentralisieren
7. **M20** — Garmin-Sync `logger.warning` → `logger.error`
8. **L3** — `ml_alive`-Sentinel im Heartbeat-Loop schreiben
9. **H4** — SameSite/Secure in `test_auth.py` assertieren
10. **M11** — `branch = true` in allen 3 `pyproject.toml`
11. **M10** — Referrer-Policy + HSTS-Vollwert in Header-Test
12. **M17** — `check-pr-size` in `e2e`-`needs` aufnehmen
13. **M18** — `platformAutomerge: true` in `renovate.json`
14. **M19** — Secret-Guard in e2e-Job
15. **M5**  — `WriteLoggerFactory(file=sys.stdout)` in allen 3 logging_configs

### Mittelfristig — Qualität + Tests

16. **M1**  — CSRF auf reset-request + resend-verify
17. **M2**  — Reset-Token-Hash nicht truncaten
18. **M13** — `_sync_activities` Unit-Tests
19. **M14** — `ml-service/tests/test_db.py` Testfunktionen ergänzen
20. **M8**  — `sentry_sdk.init()` in Helper-Funktion konsolidieren
21. **M6**  — Return-Typen auf Middleware-Dispatcher ergänzen
22. **M9**  — `RegisterFormData`-Dataclass
23. **M7**  — `BodyBatteryInputs`-Dataclass
24. **M15** — `/api/metrics` in Auth-Guard-Parametrize
25. **M16** — E2E-Fixture `scope="function"` oder explizite `page.goto()`

### Langfristig — Architektur

26. **M12** — JS-Coverage für dashboard-hero/loaders aktivieren
27. **L4**  — Uptime Kuma / Loki / Promtail in `docker-compose.yml` aufnehmen
28. **M12** — uv-Workspace + shared `logging_config`-Package einrichten

---

## Vorgeschlagene neue CLAUDE.md-Ausnahmen

Keine neuen Ausnahmen empfohlen — alle identifizierten Lücken sind behebbar und sollten nicht dauerhaft dokumentiert werden.

---

## pip-audit Ergebnis

Alle drei Services (api, sync-service, ml-service): **keine bekannten CVEs** zum Prüfzeitpunkt.

## Container-Hygiene

Alle drei Dockerfiles bestehen den vollständigen Review: Multi-Stage ✅ · Digest-Pins ✅ · non-root User (`appuser`) ✅ · `HEALTHCHECK` ✅ · `PYTHONUNBUFFERED=1` ✅
