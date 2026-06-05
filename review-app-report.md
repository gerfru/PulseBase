# PulseBase — App Evaluation Report (Eval 7)

**Datum:** 2026-06-05
**Stack:** FastAPI + Python 3.14 · TimescaleDB PG16 · Docker Compose · Chart.js/Vitest
**Services:** api · sync-service · ml-service
**Regelquelle:** Dev-Best-Practices Plugin (essential/app/github/architecture-rules.md)
**ASVS-Level:** L2 (Auth + Gesundheitsdaten + DSGVO)
**Dokumentierte Ausnahmen (nicht gemeldet):** ARCH-M2, ARCH-L2, ARCH-L3, ARCH-L5, CICD-M3, CICD-M4, QUAL-M2, OBS-L1, OBS-L2, OBS-L3
**False Positives ausgeschlossen:** CSP `style-src 'unsafe-inline'` (in CLAUDE.md explizit erlaubt)

---

## Achsen-Übersicht

| Achse | Ampel | #Critical | #High | Wichtigste verletzte Regel |
|---|---|---|---|---|
| Architektur & 12-Factor | 🟡 Gelb | 0 | 2 | architecture-rules.md → Disposability (stop_grace_period, /tmp Sentinels) |
| Security (ASVS L2) | 🟡 Gelb | 0 | 1 | app-rules.md → Token Invalidation vor Passwort-Update |
| Code-Qualität | 🔴 Rot | 1 | 3 | app-rules.md → Error Handling (sync_libre_user, FERNET_KEY-Duplikation, fehlende Input-Validation) |
| Tests & Zuverlässigkeit | 🟡 Gelb | 0 | 0 | architecture-rules.md → kritische Pfade ~100% (`configure_sentry`, `_sync_activities` Boundary) |
| CI/CD & Delivery | 🟢 Grün | 0 | 0 | github-rules.md → bandit exit-code [zu verifizieren] |
| Observability & Betrieb | 🟡 Gelb | 0 | 0 | app-rules.md → Strukturiertes Logging (backfill_energy.py) · Saturation-Signal fehlt |

---

## Alle Befunde (nach Severity sortiert)

### CRITICAL (1)

| ID | Achse | Titel | Datei:Zeile | Conf | Verletzte Regel | Fix | Aufwand |
|---|---|---|---|---|---|---|---|
| C-01 | CQ | `sync_libre_user`: `RuntimeError` nicht gefangen — kein exc_info-Logging | [sync-service/src/main.py:224](sync-service/src/main.py#L224) | 9 | app-rules.md → Error Handling: Fail Fast, Exc-Info-Logging | `try/except RuntimeError` um `LibreAuthError` hinaus, `logger.error(..., exc_info=True)` | S |

---

### HIGH (6)

| ID | Achse | Titel | Datei:Zeile | Conf | Verletzte Regel | Fix | Aufwand |
|---|---|---|---|---|---|---|---|
| H-01 | SEC | Reset-Token wird erst nach `update_password()` invalidiert (Token-Replay-Fenster) | [api/src/routes/auth.py:347](api/src/routes/auth.py#L347) | 9 | app-rules.md → Authentication: Token-Invalidation vor Passwort-Update | `clear_reset_token(user_id)` **vor** `update_password()` aufrufen | S |
| H-02 | CQ | FERNET_KEY-Null-Guard 3× dupliziert | [sync-service/src/main.py:161](sync-service/src/main.py#L161) | 8 | architecture-rules.md → Code Quality: Duplikation | `_require_fernet_key(settings)` Helper mit `raise RuntimeError` extrahieren | S |
| H-03 | CQ | Keine Input-Validierung auf `/api/glucose` Query-Params | [api/src/routes/api.py:317](api/src/routes/api.py#L317) | 8 | app-rules.md → Input-Validierung an Systemgrenzen | `Query(ge=1, le=90)` auf `days`/`hours`-Params | S |
| H-04 | CQ | `_sync_date_range`: kein Top-Level-Exception-Handler für `_sync_activities` | [sync-service/src/main.py:141](sync-service/src/main.py#L141) | 7 | app-rules.md → Error Handling: Fail Fast, exc_info | `try/except` um `_sync_activities()`-Aufruf mit strukturiertem `logger.error` | M |
| H-05 | ARCH | `/api/metrics` Lese-Zugriff auf `_active_requests`/`_error_requests` ohne Lock | [api/src/main.py:68](api/src/main.py#L68) | 8 | architecture-rules.md → 12-Factor: Stateless (Race Condition auf Lese-Pfad) | `async with _metrics_lock:` auch im `app_metrics()`-Handler | S |
| H-06 | ARCH | `stop_grace_period` (90s/60s) kürzer als mögliche `scheduler.shutdown(wait=True)` Laufzeit | [docker-compose.yml:121](docker-compose.yml#L121) | 8 | architecture-rules.md → Disposability: Graceful Shutdown | Grace Period auf 120s erhöhen oder `wait=False` | S |

---

### MEDIUM (18)

| ID | Achse | Titel | Datei:Zeile | Conf | Verletzte Regel | Fix | Aufwand |
|---|---|---|---|---|---|---|---|
| M-01 | SEC | Reset-/Verify-Token in GET-URL (Access Logs, Referrer) | [api/src/routes/auth.py:229](api/src/routes/auth.py#L229) | 8 | app-rules.md → Authentication: A07:2021 Token-Übertragung | Dokumentieren als bekanntes Risiko oder POST-Migration | M |
| M-02 | SEC | `GET /auth/reset/{token}` schreibt Session-State (ASVS 4.11.2 Idempotenz) | [api/src/routes/auth.py:278](api/src/routes/auth.py#L278) | 7 | app-rules.md → Authentication: Idempotente GETs | Session-Write in POST-Handler verschieben | M |
| M-03 | SEC | Token-Reuse-Race: `session.pop()` nicht atomar mit Passwort-Update | [api/src/routes/auth.py:310](api/src/routes/auth.py#L310) | 8 | app-rules.md → Authentication: Token-Invalidation (atomar) | `clear_reset_token()` und `update_password()` in einer DB-Transaktion | M |
| M-04 | ARCH | `/tmp`-Sentinels für Healthcheck: veralten bei Container-Start vor erstem Scheduler-Tick | [sync-service/src/main.py:349](sync-service/src/main.py#L349) | 9 | architecture-rules.md → Docker: Health Checks | Sentinel beim Service-Start schreiben (vor APScheduler-Start) oder `start_period` erhöhen | S |
| M-05 | ARCH | DB-Verbindung vor SIGTERM-Handler-Registrierung aufgebaut | [sync-service/src/main.py:335](sync-service/src/main.py#L335) | 7 | architecture-rules.md → Disposability: Signal-Handler zuerst | Signal-Handler vor `await repo.init()` registrieren | S |
| M-06 | CI | `bandit -q` ohne explizites `--exit-code 1` [zu verifizieren] | [.github/workflows/ci.yml:96](.github/workflows/ci.yml#L96) | 8 | github-rules.md → SAST: bandit exit-code 1 | `bandit ... -q --exit-code 1` | S |
| M-07 | CQ | `_validate_register_form`: 9 Positional-Parameter (Schwelle: 7) | [api/src/routes/auth.py:90](api/src/routes/auth.py#L90) | 8 | architecture-rules.md → Code Quality: Funktion-Parameter | Als Pydantic `BaseModel` analog zu `SeizureBody`/`ProfileBody` | M |
| M-08 | CQ | `hrv_hist: list` / `sleep_h: list` ohne Generics | [ml-service/src/inference_models.py:146](ml-service/src/inference_models.py#L146) | 7 | architecture-rules.md → Code Quality: Typisierung | `list[float \| None]` / `list[dict[str, Any]]` | S |
| M-09 | CQ | `json.loads(raw)` ohne `try/except JSONDecodeError` auf Libre-Token | [sync-service/src/main.py:245](sync-service/src/main.py#L245) | 7 | app-rules.md → Error Handling: Fail Fast | `try/except json.JSONDecodeError` mit `logger.error(..., exc_info=True)` | S |
| M-10 | CQ | `user_id` in Libre-Token-Pfad nicht gegen Path-Traversal validiert | [sync-service/src/main.py:227](sync-service/src/main.py#L227) | 6 | app-rules.md → Input-Validierung: kein User-Input in Paths | `int(user["id"])` sicherstellen (DB-Wert → kein Traversal-Risiko, aber defensiv dokumentieren) | S |
| M-11 | TEST | `configure_sentry()` vollständig ungetestet | api/tests/ | 9 | architecture-rules.md → Tests: kritische Pfade ~100% | `test_configure_sentry_disabled_when_no_dsn()` + `test_configure_sentry_initialized()` | M |
| M-12 | TEST | CSRF-Bypass-Fixture deckt nicht alle Mutations-Routen ab | [api/tests/conftest.py:67](api/tests/conftest.py#L67) | 8 | architecture-rules.md → Tests: kritische Auth-Pfade | Fixture auf alle Routen mit CSRF-Prüfung ausweiten | M |
| M-13 | TEST | `fail_under` inkonsistent: api=70, sync=70, ml=80 | api/pyproject.toml | 8 | architecture-rules.md → Tests: Coverage-Soll 70–80% | Auf 75 vereinheitlichen oder Abweichung dokumentieren | S |
| M-14 | TEST | Reset-Flow: Session-Marker bei abgelaufenem Token im zweiten POST nicht getestet | [api/tests/test_auth.py:323](api/tests/test_auth.py#L323) | 7 | architecture-rules.md → Tests: kritische Auth-Pfade ~100% | `test_reset_password_session_reused_after_expiry()` ergänzen | M |
| M-15 | TEST | `_sync_activities`: Boundary-Cases fehlen (empty map_records, exception in map_activity) | [sync-service/tests/test_sync_logic.py:159](sync-service/tests/test_sync_logic.py#L159) | 6 | architecture-rules.md → Tests: kritische Datenpfade ~100% | 2 zusätzliche Test-Cases in `TestSyncActivities` | M |
| M-16 | OBS | `backfill_energy.py` nutzt `logging.basicConfig` statt structlog | [ml-service/src/backfill_energy.py:18](ml-service/src/backfill_energy.py#L18) | 8 | app-rules.md → Logging: Strukturiert (JSON), structlog | `configure_logging()` aus `logging_config` importieren | S |
| M-17 | OBS | Background-Worker (sync/ml) ohne HTTP-Health-Endpunkte (nur /tmp-Sentinel) | sync-service/src/main.py | 7 | app-rules.md → Deployment: `/health` Liveness | Als akzeptiertes Pattern dokumentieren oder minimalen HTTP-Server hinzufügen | M |
| M-18 | OBS | Saturation-Signal (CPU/Memory) nicht getrackt | [api/src/main.py:98](api/src/main.py#L98) | 8 | app-rules.md → Observability: Vier goldene Signale | `psutil` Memory/CPU in `/api/metrics` ergänzen | S |

---

### LOW (13)

| ID | Achse | Titel | Datei:Zeile | Conf | Fix | Aufwand |
|---|---|---|---|---|---|---|
| L-01 | SEC | Email-Hash `[:12]` in Login-Logs (Rainbow-Table-angreifbar) | [api/src/deps.py:45](api/src/deps.py#L45) | 7 | Nur `user_id` loggen, Email-Hash entfernen | S |
| L-02 | SEC | Session-Secret ohne Entropy-Prüfung (32× `a` wäre gültig) | api/src/deps.py (Settings) | 7 | Warnung wenn Entropy niedrig | S |
| L-03 | SEC | Garmin/Libre-Passwort nach `connect()` nicht aus RAM entfernt | [api/src/routes/garmin.py:73](api/src/routes/garmin.py#L73) | 8 | Als bekannte Python-Einschränkung dokumentieren | S |
| L-04 | SEC | Account-Deletion ohne Soft-Delete / Bestätigungs-E-Mail | [api/src/routes/account.py:37](api/src/routes/account.py#L37) | 7 | Optional: E-Mail-Bestätigung oder 24h-Soft-Delete | L |
| L-05 | SEC | `require_user()` prüft kein `email_verified_at` | [api/src/deps.py](api/src/deps.py) | 8 | `WHERE ... AND email_verified_at IS NOT NULL` in `get_user_by_id()` | S |
| L-06 | ARCH | Externes `proxy`-Netzwerk nicht dokumentiert | [docker-compose.yml:185](docker-compose.yml#L185) | 6 | Kommentar + `make create-proxy-network` Ziel | S |
| L-07 | ARCH | ML-Model-Volume: Root-erstelltes Volume → Permission-Fehler für `appuser` | [ml-service/Dockerfile:13](ml-service/Dockerfile#L13) | 6 | Startup-Skript `mkdir -p && chown appuser` | S |
| L-08 | CQ | `save_prediction + logger.info`-Muster 6× wiederholt | [ml-service/src/inference_models.py:69](ml-service/src/inference_models.py#L69) | 7 | `_save_and_log()` Helper | S |
| L-09 | CQ | Response-Union-Rückgabetypen ohne `response_model=None` dokumentiert | [api/src/routes/api.py:61](api/src/routes/api.py#L61) | 6 | Kommentar oder Union-Typ entfernen | S |
| L-10 | TEST | E2E-Fixtures nutzen statische E-Mails (Duplicate-Key bei abgebrochenem Lauf) | [api/tests/e2e/conftest.py:226](api/tests/e2e/conftest.py#L226) | 8 | UUID-Suffix auf Test-E-Mails | S |
| L-11 | TEST | Mail-Exception-Tests: 3 near-identische Blöcke statt `@pytest.mark.parametrize` | [api/tests/test_auth.py:374](api/tests/test_auth.py#L374) | 7 | `@pytest.mark.parametrize("mail_fn, endpoint", [...])` | S |
| L-12 | OBS | `apt-get upgrade` ohne `--no-install-recommends` in sync/ml Dockerfiles | [sync-service/Dockerfile:11](sync-service/Dockerfile#L11) | 7 | `apt-get upgrade -y --no-install-recommends` | S |
| L-13 | OBS | `/health` ohne DB-Check — Unterschied zu `/ready` nicht dokumentiert | [api/src/main.py:177](api/src/main.py#L177) | 6 | Inline-Kommentar: "Liveness only — DB check is in /ready" | S |

---

## Fix-Reihenfolge

### Sofort — Security & Correctness

1. **H-01** Reset-Token vor `update_password()` invalidieren
2. **M-03** Token-Reuse-Race: DB-Transaktion für clear+update
3. **H-05** `/api/metrics` Lese-Lock ergänzen
4. **C-01** `sync_libre_user` try/except mit exc_info
5. **H-03** Query-Param-Validierung auf `/api/glucose`
6. **L-05** `require_user()`: `email_verified_at IS NOT NULL`

### Kurzfristig — Stabilität & Qualität

1. **H-06** `stop_grace_period` auf 120s erhöhen
2. **M-04** `/tmp`-Sentinel beim Service-Start schreiben
3. **M-05** Signal-Handler vor `repo.init()` registrieren
4. **H-02** FERNET_KEY-Guard als Helper extrahieren
5. **H-04** `_sync_date_range` Exception-Handler
6. **M-09** `json.loads` try/except
7. **M-16** `backfill_energy.py` → structlog
8. **M-18** Saturation-Signal in `/api/metrics` (psutil)

### Mittelfristig — Test-Coverage & Housekeeping

1. **M-11** `configure_sentry()` Tests
2. **M-13** `fail_under` vereinheitlichen (75)
3. **M-12** CSRF-Fixture Vollständigkeit
4. **M-15** `_sync_activities` Boundary-Cases
5. **M-07** Register-Form als Pydantic BaseModel
6. **L-01** Email-Hash aus Logs entfernen
7. **L-10** E2E-Fixtures UUID-Suffix
8. **L-12** `--no-install-recommends` in Dockerfiles

---

## Statistik

| | Gesamt | SEC | ARCH | CQ | TEST | CI | OBS |
|---|---|---|---|---|---|---|---|
| Critical | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| High | 6 | 1 | 2 | 3 | 0 | 0 | 0 |
| Medium | 18 | 3 | 2 | 4 | 5 | 1 | 3 |
| Low | 13 | 5 | 2 | 2 | 2 | 0 | 2 |
| **Total** | **38** | **9** | **6** | **10** | **7** | **1** | **5** |

---

6 parallele Subagenten · Regelquelle: plugin rules/ · ASVS L2 · 2026-06-05
