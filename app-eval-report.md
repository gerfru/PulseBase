# PulseBase — App Evaluation Report

**Datum:** 2026-06-05
**Stack:** FastAPI 0.136 · Python 3.14 · TimescaleDB/PG16 · structlog · Sentry · Docker Compose
**Services:** api · sync-service · ml-service
**ASVS-Level:** L2 (Gesundheitsdaten, DSGVO, Epilepsie-Modus)
**Team:** Solo
**Regelquelle:** Dev-Best-Practices Plugin (essential/app/github/architecture-rules.md)
**Dokumentierte Ausnahmen:** ARCH-M2, ARCH-L2, ARCH-L3, ARCH-L5, CICD-M3, CICD-M4, QUAL-M2, OBS-L2

---

## Ampel-Übersicht

| Achse | Ampel | #Critical | #High | #Medium | #Low | Wichtigste verletzte Regel |
|---|---|---|---|---|---|---|
| Architektur & 12-Factor | 🟡 Gelb | 0 | 1 | 2 | 2 | 12-Factor IV Disposability (ml-service SIGTERM) |
| Security (ASVS L2) | 🟢 Grün | 0 | 0 | 1 | 2 | app-rules.md → Auth ("Fail Closed") |
| Code-Qualität | 🟢 Grün | 0 | 0 | 2 | 10 | Datei-Schwellwert 400 Z., Logging-Inkonsistenz |
| Tests & Zuverlässigkeit | 🟡 Gelb | 0 | 0 | 4 | 4 | JS-Datentransformationslogik komplett ungetestet |
| CI/CD & Delivery | 🟡 Gelb | 0 | 0 | 3 | 3 | github-rules.md → Secret Scanning (3. Schicht fehlt) |
| Observability & Betrieb | 🟡 Gelb | 0 | 0 | 0 | 4 | /api/metrics ungeschützt, Sentry ohne Environment-Tags |

**Gesamtbild: 🟡 Gelb** — Keine kritischen Schwachstellen. Fundament (CSP nonce, SQL parameterisiert, Auth-Layering, Multi-Stage Docker, CI-Pipeline) ist solid. 4 Achsen gelb wegen je 1–4 behabbarer Einzellücken. Keine Critical-Befunde.

---

## Konsolidierte Befundliste (nach Severity sortiert)

### HIGH

| # | Titel | Datei:Zeile | Severity | Conf. | Verletzte Regel | Fix | Aufwand |
|---|---|---|---|---|---|---|---|
| H-01 | ml-service SIGTERM-Handler nach blockierendem Initial-Run registriert | `ml-service/src/main.py:215` | High | 9 | architecture-rules.md → Docker (Disposability) | SIGTERM-Handler vor `await run_all_users()` registrieren; Initial-Run in `asyncio.create_task` wrappen (analog sync-service) | M |

### MEDIUM

| # | Titel | Datei:Zeile | Severity | Conf. | Verletzte Regel | Fix | Aufwand |
|---|---|---|---|---|---|---|---|
| M-01 | `/api/metrics` unauthentifiziert — Betriebsdaten ohne Session | `api/src/main.py:176` | Medium | 9 | app-rules.md → Authentication ("Fail Closed") | `Depends(require_user)` hinzufügen | S |
| M-02 | promtail Docker Socket ohne `:ro` | `docker-compose.yml:240` | Medium | 9 | architecture-rules.md → Docker Security | `/var/run/docker.sock:/var/run/docker.sock:ro` | S |
| M-03 | Loki / Promtail / Uptime-Kuma Images ohne Digest-Pin | `docker-compose.yml:212,235,259` | Medium | 8 | architecture-rules.md → Docker (Base Images mit Digest pinnen) | `docker inspect --format '{{index .RepoDigests 0}}'` ausführen und `@sha256:…` ergänzen | S |
| M-04 | `dashboard-loaders.js` (556 Zeilen) komplett ohne Unit-Tests | `api/src/static/dashboard-loaders.js` | Medium | 8 | architecture-rules.md → Testing (Datentransformationen Prio 2) | Pure Hilfsfunktionen extrahieren + Vitest-Tests; Datei in coverage `include` aufnehmen | L |
| M-05 | `activity.js` (445 Zeilen) ungetestet, `innerHTML` mit API-Daten | `api/src/static/activity.js:126,247,273` | Medium | 8 | app-rules.md → DOM XSS + Testing | Logik-Teile extrahieren + testen; in coverage `include` aufnehmen | M |
| M-06 | E2E session-scoped `authenticated_page` Fixture — Zustandsabhängigkeit | `api/tests/e2e/conftest.py:33` | Medium | 7 | architecture-rules.md → Testing (keine Test-Interdependenz) | State-mutierende Tests (theme-toggle, period-nav) in eigenen Browser isolieren | M |
| M-07 | semgrep pre-commit als `language: system` — kein Autom. Install | `.pre-commit-config.yaml:43` | Medium | 8 | github-rules.md → Pre-Commit Hooks / Security Scanning | Zu `language: python` + `additional_dependencies: [semgrep==1.164.0]` wechseln | S |
| M-08 | GitHub native Secret Scanning / Push Protection nicht aktiviert | GitHub Settings | Medium | 7 | github-rules.md → Secret Scanning ("3 Schichten: Pre-commit, CI, GitHub-nativ") | GitHub → Settings → Code Security → Secret Scanning + Push Protection aktivieren | S |
| M-09 | Renovate pep621 automerge trifft auch Prod-Dependencies (kein `matchDepTypes: dev`) | `.github/renovate.json` | Medium | 8 | github-rules.md → Dependency Management (devDeps patch Automerge) | `matchDepTypes: ["dev"]` in pep621-patch-Regel ergänzen oder Ausnahme dokumentieren | S |
| M-10 | `inference_models.py` überschreitet 400-Zeilen-Schwellwert (404 Z.) | `ml-service/src/inference_models.py:1` | Medium | 9 | Qualitätsschwellwert (Datei >400 Zeilen) | In `inference_energy.py` + `inference_recovery.py` aufteilen oder CLAUDE.md-Ausnahme dokumentieren | M |
| M-11 | `_assign_pattern_labels` — doppelte `stabil_hoch`-Zuweisung, Logik unklar | `ml-service/src/models/battery_pattern.py:90` | Medium | 7 | Qualitätsschwellwert (Verschachtelung, Logikfehler-Risiko) | In explizite `_classify_cluster()`-Funktion mit klaren Guards extrahieren + Unit-Test | M |
| M-12 | Vitest coverage-include erfasst `dashboard-hero.js` nicht | `api/vitest.config.js:12` | Medium | 9 | github-rules.md → Testing (Coverage-Konfiguration) | `'src/static/dashboard-hero.js'` zur `include`-Liste hinzufügen | S |

### LOW

| # | Titel | Datei:Zeile | Conf. | Fix | Aufwand |
|---|---|---|---|---|---|
| L-01 | Uptime-Kuma ohne Healthcheck-Block | `docker-compose.yml:258` | 8 | `healthcheck: { test: wget localhost:3001, interval: 30s }` ergänzen | S |
| L-02 | api Lifespan: DB-Pool bei Shutdown nicht geschlossen | `api/src/main.py:116` | 7 | `await pool.close()` nach `yield` im Lifespan | S |
| L-03 | `dashboard-loaders.js` — `a.id` in `data-id` ohne explizites Cast | `api/src/static/dashboard-loaders.js:18` | 7 | `data-id="${Number(a.id)}"` | S |
| L-04 | `metrics.js` — `result.value`/`result.sub` via innerHTML ohne esc() | `api/src/static/metrics.js:39` | 7 | `textContent` statt `innerHTML` wo kein HTML nötig; sonst DOMPurify | S |
| L-05 | `backfill.py` nutzt `logging.getLogger` + f-strings statt structlog | `ml-service/src/backfill.py:195,201` | 9 | `structlog.get_logger(__name__)` + Key-Value-Stil | S |
| L-06 | Fehlende Return-Typ-Annotation `_load_user_records` | `api/src/db/users.py:355` | 8 | `-> list[dict]` + `conn: asyncpg.Connection` | S |
| L-07 | Fehlende `-> float` Annotation auf innerer `hour()`-Funktion | `ml-service/src/models/battery_pattern.py:19` | 7 | `-> float` ergänzen | S |
| L-08 | `_clamp` innere Funktion dupliziert `_clip()` aus energy_metrics | `ml-service/src/models/readiness.py:144` | 7 | Auf Modul-Ebene heben oder aus energy_metrics importieren | S |
| L-09 | 5 `_run_anomaly_*` Aufrufe laufen sequentiell, könnten parallel laufen | `ml-service/src/main.py:69` | 8 | `await asyncio.gather(...)` | M |
| L-10 | Logik-Duplikat: Readiness-Gewichtung in api und ml-service | `api/src/db/health.py:165` | 6 | Parity-Test hinzufügen der beide Implementierungen vergleicht | S |
| L-11 | `_run_body_battery()` hat 11 Parameter | `ml-service/src/inference_models.py:280` | 7 | `BodyBatteryInputs` Dataclass einführen | S |
| L-12 | `sync-service/main.py` nähert sich 400-Zeilen-Schwelle (372 Z.) | `sync-service/src/main.py:1` | 7 | Token-Migration-Logik auslagern bei nächster Erweiterung | S |
| L-13 | `api/src/db/users.py` nähert sich 400-Zeilen-Schwelle (393 Z.) | `api/src/db/users.py:1` | 7 | Split in `users_auth.py` + `users_data.py` bei nächster Erweiterung | S |
| L-14 | asyncio_default_test_loop_scope fehlt in sync/ml pyproject.toml | `sync-service/pyproject.toml` | 8 | `asyncio_default_fixture_loop_scope = "session"` ergänzen | S |
| L-15 | `test_sync_activities` in test_sync_logic.py und test_main.py doppelt | `sync-service/tests/` | 9 | Eine Klasse entfernen (test_sync_logic.py bevorzugt) | S |
| L-16 | `test_libre_link_has_rate_limit_decorator` testet nur Route-Existenz | `api/tests/test_coverage.py:633` | 7 | Source-Check auf `'5/hour'` analog zu Garmin-Test ergänzen | S |
| L-17 | Kein Test für `/api/metrics` Endpoint | `api/src/routes/` | 6 | In Auth-Guard-Parameterliste aufnehmen (oder als öffentlich dokumentieren) | S |
| L-18 | Renovate Automerge ohne explizite `requiredStatusChecks` | `.github/renovate.json` | 6 | `platformAutomerge: true` oder Status Checks referenzieren | S |
| L-19 | `test`-Job läuft parallel zu `lint` (kein `needs: lint`) | `ci.yml:255` | 7 | `typecheck` um `needs: lint` ergänzen, oder als Speed-Tradeoff dokumentieren | S |
| L-20 | `.dockerignore` ohne `.mypy_cache/` und `.ruff_cache/` (sync, ml) | `sync-service/.dockerignore`, `ml-service/.dockerignore` | 8 | `.mypy_cache/` + `.ruff_cache/` ergänzen | S |
| L-21 | Uptime Kuma Monitor auf `/health` statt `/ready` — DB-Ausfall unerkannt | `docs/external-services.md:122` | 8 | Zweiten Monitor auf `/ready` konfigurieren | S |
| L-22 | Sentry ohne `environment` und `release` Tags | `api/src/main.py:131` | 7 | `environment=os.getenv("APP_ENV", "production")` + `release=os.getenv("APP_VERSION")` | S |
| L-23 | Alert-Schwellen für Latenz/Ressourcen nicht automatisiert durchgesetzt | `monitoring/` | 7 | Loki Alert-Rules konfigurieren, oder als Ausnahme analog OBS-L2 in CLAUDE.md dokumentieren | M |

---

## Empfohlene Fix-Reihenfolge

### Sofort (Security & Betrieb, alle S<30min)
1. **M-01** — `/api/metrics` mit `require_user` sichern
2. **M-02** — promtail Docker Socket `:ro` setzen
3. **M-03** — Loki/Promtail/Uptime-Kuma Images Digest-pinnen
4. **M-07** — semgrep pre-commit zu `language: python` migrieren
5. **M-08** — GitHub native Secret Scanning aktivieren
6. **L-05** — backfill.py auf structlog umstellen
7. **L-21** — Uptime Kuma zweiten Monitor auf `/ready` konfigurieren
8. **L-22** — Sentry environment + release Tags ergänzen

### Kurzfristig (Architektur & Tests, M<2h)
9. **H-01** — ml-service SIGTERM-Handler vor Initial-Run registrieren
10. **M-11** — `_assign_pattern_labels` Logik in `_classify_cluster()` extrahieren + Unit-Test
11. **M-06** — E2E state-mutierende Tests isolieren
12. **M-05** — activity.js: Logik extrahieren + coverage
13. **L-09** — Anomalie-Ausführung parallelisieren (`asyncio.gather`)

### Mittelfristig (Qualität & Coverage, L>2h)
14. **M-04** — dashboard-loaders.js: testbare Utilities extrahieren
15. **M-10** — inference_models.py aufteilen
16. **M-09** — Renovate pep621 matchDepTypes präzisieren

### Kosmetik / Watch-Liste (Low, S<30min je)
L-01, L-02, L-03, L-04, L-06–L-08, L-10–L-16, L-18–L-20, L-23

---

## Nicht als Befund gewertete dokumentierte Ausnahmen

| ID | Ausnahme | Begründung |
|---|---|---|
| ARCH-M2 | Kein Service-Layer (Routes → DB direkt) | Solo-Projekt, route-spezifische Logik |
| ARCH-L2 | Technisch-basierte `db/`-Struktur | Dateien <200 Z., Solo-Entwickler |
| ARCH-L3 | Kein `/api/v1/` Prefix | Keine externen Consumer |
| ARCH-L5 | `routes/api.py` flat (~340 Z.) | Unter 400-Schwelle, dokumentiert |
| CICD-M3 | Branch Protection nicht erzwingbar | Privates Repo, Gratis-Plan |
| CICD-M4 | Kein automatisierter CD-Step | Single-Server-Deployment |
| QUAL-M2 | GarminClient in api/ und sync-service/ dupliziert | Shared-Package würde Build-Context-Änderungen erfordern |
| OBS-L2 | Kein OpenTelemetry | Single-Server, Loki+Sentry ausreichend |

---

## Positive Befunde (explizit bestätigt, kein Befund)

- **CSP**: Nonce-basiert mit `'strict-dynamic'` auf allen `<script>`-Tags — Gold-Standard
- **SQL**: 100% Prepared Statements mit asyncpg `$n`-Platzhaltern, kein String-Interpolation-Risiko
- **Auth-Layering**: `require_user` konsistent auf allen `/api/*` und Pages-Routen
- **CSRF**: `hmac.compare_digest` auf allen state-mutierenden Form-Routes
- **Account-Lockout**: 5 Fehlversuche → 15 min, Dummy-Hash gegen Timing-Angriff
- **Session-Cookies**: `httpOnly`, `secure`, `sameSite=lax` korrekt konfiguriert
- **structlog**: JSON-Format, UTC-Timestamps, `request_id` per Request, keine Secrets geloggt
- **Sentry**: `send_default_pii=False`, FastAPI-Integration, ERROR/CRITICAL über structlog-Processor
- **Multi-Stage Docker**: Alle 3 Dockerfiles mit Builder + Runtime + Digest-gepinntem Base Image
- **Non-root User**: Alle Dockerfiles erstellen und nutzen `appuser`
- **SIGTERM sync-service**: Handler korrekt vor Initial-Sync registriert (abbrechbar)
- **Actions gepinnt**: Alle `uses:` auf Commit-Digest + Tag-Kommentar
- **Trivy**: Alle 3 Images mit `exit-code: 1`, `CRITICAL,HIGH`, `ignore-unfixed: true`
- **Renovate**: `pinDigests: true`, sinnvolle Automerge-Strategie, Dashboard-Issue
- **Coverage**: 338 API + 179 Sync + 274 ML + 35 E2E Tests — klare Pyramidenform
- **Kritische Pfade getestet**: Auth, Lockout, CSRF, DSGVO-Export/Delete, Seizure-Events vollständig
- **Resource Limits**: Alle Services mit `deploy.resources.limits` (Memory + CPU)
- **Log-Rotation**: Alle Services mit `max-size`/`max-file` konfiguriert
