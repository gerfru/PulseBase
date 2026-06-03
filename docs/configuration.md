# Configuration Reference

Alle Umgebungsvariablen aller drei Services. Jede Variable wird beim App-Start validiert (Pydantic `BaseSettings`) — die App crasht sofort wenn eine Pflicht-Variable fehlt.

Dateien liegen unter `env/`. Vorlagen: `env/.env.example`, `env/.env.api.example`, `env/.env.sync.example`.

---

## Übersicht: Welche Datei für welchen Service

| Datei | Geladen von | Enthält |
|-------|-------------|---------|
| `env/.env` | db, flyway | Admin-DB-Credentials, HOST_IP |
| `env/.env.app` | api, sync-service, ml-service | App-DB-Credentials, FERNET_KEY |
| `env/.env.api` | api | SESSION_SECRET, RESEND_*, APP_BASE_URL, SENTRY_DSN, TRIMP_* |
| `env/.env.sync` | sync-service | SYNC_INTERVAL_HOURS, SYNC_LOOKBACK_DAYS, SYNC_DAILY_DAYS, SENTRY_DSN |
| `env/.env.ml` | ml-service | ML_INFER_HOUR, ML_TRAIN_WEEKDAY, MODEL_DIR, SENTRY_DSN |

> **Warum diese Trennung?** Admin-Credentials (`DB_USER`/`DB_PASSWORD`) sind nur für Flyway-Migrationen nötig. App-Services bekommen ausschließlich `DB_APP_USER`/`DB_APP_PASSWORD` mit eingeschränkten Rechten (SELECT/INSERT/UPDATE/DELETE). Damit sind Admin-Creds nie im Prozess-Environment von api/sync/ml sichtbar (H-11).

---

## `env/.env` — DB + Flyway only

Wird **nur** von `db` und `flyway` geladen. App-Services (api/sync/ml) sehen diese Datei nicht.

### Datenbank — Admin-User

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `DB_USER` | string | ✓ | — | PostgreSQL-Admin-User (nur für Flyway-Migrationen) |
| `DB_PASSWORD` | string | ✓ | — | Passwort des Admin-Users |

### Sonstiges

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `HOST_IP` | string | — | `your-domain.com` | Hostname/Domain (wird in `docker-compose.yml` als Traefik-Rule verwendet) |

---

## `env/.env.app` — App-Services (api, sync-service, ml-service)

Enthält die minimalen Credentials für App-Services. Kein Admin-Zugriff — nur Least-Privilege-User.

### Datenbank — App-User

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `DB_APP_USER` | string | ✓ | — | App-User (SELECT/INSERT/UPDATE/DELETE only, kein DDL) |
| `DB_APP_PASSWORD` | string | ✓ | — | Passwort des App-Users |

### Verschlüsselung

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `FERNET_KEY` | string | ✓ | — | 32-Byte URL-safe base64-Key für Fernet-Verschlüsselung der Garmin/Libre-Tokens. Leerer Wert → Startup-Crash. Gleicher Wert für alle App-Services. |

Generieren:
```bash
make gen-secrets
# oder:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## `env/.env.api` — API-Service

### Session & Sicherheit

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `SESSION_SECRET` | string | ✓ | — | Signierungsschlüssel für Starlette SessionMiddleware. Min. 32 Zeichen, zufällig. Rotation invalidiert alle aktiven Sessions. |
| `HTTPS_ONLY` | bool | — | `true` | `true` → Cookies nur über HTTPS (`secure=True`). Auf `false` setzen für lokale Entwicklung ohne TLS. |

### Datenbankverbindung

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `DB_HOST` | string | — | `db` | PostgreSQL-Hostname (Docker-Service-Name) |
| `DB_PORT` | int | — | `5432` | PostgreSQL-Port |
| `DB_NAME` | string | — | `garmin` | Datenbankname |

*(DB_USER, DB_PASSWORD, DB_APP_USER, DB_APP_PASSWORD kommen aus `env/.env`)*

### Training-Load Forecast

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `TRIMP_LOOKBACK_DAYS` | int | — | `7` | Wie viele Tage der historische ATL/CTL-Verlauf im Dashboard angezeigt wird |
| `TRIMP_FORECAST_DAYS` | int | — | `7` | Wie viele Tage die ATL-Abklingkurve in die Zukunft projiziert wird |

### E-Mail (Password-Reset via Resend)

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `RESEND_API_KEY` | string | — | `""` | API-Key von [resend.com](https://resend.com). Leer = kein Mail-Versand, Reset-Link erscheint nur im Log. |
| `RESEND_FROM_EMAIL` | string | — | `onboarding@resend.dev` | Absender-Adresse. Eigene Domain nach Verifizierung in Resend eintragen. |
| `APP_BASE_URL` | string | — | `https://your-domain.com` | Basis-URL für Links in Reset-Mails. Muss öffentlich erreichbar sein. |

### Error Tracking

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `SENTRY_DSN` | string | — | `""` | DSN von [sentry.io](https://sentry.io). Leer = Sentry deaktiviert. Format: `https://xxx@sentry.io/...` |

---

## `env/.env.sync` — Sync-Service

### Datenbankverbindung

Wie API — `DB_HOST`, `DB_PORT`, `DB_NAME` (mit denselben Defaults). `DB_USER`, `DB_PASSWORD`, `DB_APP_USER`, `DB_APP_PASSWORD` kommen aus `env/.env`.

### Sync-Timing

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `SYNC_INTERVAL_HOURS` | int | — | `2` | Polling-Intervall in Stunden für den Garmin-Sync. Libre-Sync läuft alle 5 Minuten unabhängig davon. |
| `SYNC_LOOKBACK_DAYS` | int | — | `30` | Wie viele Tage beim initialen Backfill (erster Sync nach Account-Verknüpfung) geholt werden |
| `SYNC_DAILY_DAYS` | int | — | `2` | Wie viele Tage pro Interval-Run nachgeladen werden |

*(FERNET_KEY kommt aus `env/.env.app` — identischer Wert für alle App-Services)*

### Error Tracking (Sync)

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `SENTRY_DSN` | string | — | `""` | DSN von [sentry.io](https://sentry.io). Leer = Sentry deaktiviert. Fehler im Sync-Scheduler landen in Sentry wenn gesetzt. |

---

## `env/.env.ml` — ML-Service

### Datenbankverbindung

`DB_HOST`, `DB_PORT`, `DB_NAME` (mit denselben Defaults). `DB_APP_USER`, `DB_APP_PASSWORD` kommen aus `env/.env`.

> Hinweis: ml-service nutzt nur den App-User, nicht den Admin-User (kein `DB_USER` / `DB_PASSWORD` nötig).

### ML-Scheduler

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `ML_INFER_HOUR` | int | — | `7` | Stunde (UTC) für die tägliche Inferenz (Predictions für alle User) |
| `ML_TRAIN_WEEKDAY` | int | — | `6` | Wochentag für das wöchentliche Re-Training (0 = Montag, 6 = Sonntag) |

### Modell-Speicherort

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `MODEL_DIR` | path | — | `/app/models` | Verzeichnis für gespeicherte scikit-learn-Modelle (joblib-Format) |

### Error Tracking (ML)

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `SENTRY_DSN` | string | — | `""` | DSN von [sentry.io](https://sentry.io). Leer = Sentry deaktiviert. Fehler im ML-Training und Inferenz landen in Sentry wenn gesetzt. |

---

## Vollständige Variablen-Matrix

| Variable | env/.env | env/.env.app | env/.env.api | env/.env.sync | env/.env.ml |
|----------|----------|--------------|--------------|---------------|-------------|
| `DB_USER` | ✓ | — | — | — | — |
| `DB_PASSWORD` | ✓ | — | — | — | — |
| `HOST_IP` | ✓ | — | — | — | — |
| `DB_APP_USER` | — | ✓ | — | — | — |
| `DB_APP_PASSWORD` | — | ✓ | — | — | — |
| `FERNET_KEY` | — | ✓ | — | — | — |
| `DB_HOST` | — | — | default `db` | default `db` | default `db` |
| `DB_PORT` | — | — | default `5432` | default `5432` | default `5432` |
| `DB_NAME` | — | — | default `garmin` | default `garmin` | default `garmin` |
| `SESSION_SECRET` | — | — | ✓ | — | — |
| `HTTPS_ONLY` | — | — | default `true` | — | — |
| `TRIMP_LOOKBACK_DAYS` | — | — | default `7` | — | — |
| `TRIMP_FORECAST_DAYS` | — | — | default `7` | — | — |
| `RESEND_API_KEY` | — | — | optional `""` | — | — |
| `RESEND_FROM_EMAIL` | — | — | default | — | — |
| `APP_BASE_URL` | — | — | default | — | — |
| `SENTRY_DSN` | — | — | optional `""` | optional `""` | optional `""` |
| `SYNC_INTERVAL_HOURS` | — | — | — | default `2` | — |
| `SYNC_LOOKBACK_DAYS` | — | — | — | default `30` | — |
| `SYNC_DAILY_DAYS` | — | — | — | default `2` | — |
| `ML_INFER_HOUR` | — | — | — | — | default `7` |
| `ML_TRAIN_WEEKDAY` | — | — | — | — | default `6` |
| `MODEL_DIR` | — | — | — | — | default `/app/models` |

---

## Secrets generieren

```bash
make gen-secrets
```

Gibt aus:
- `SESSION_SECRET` → in `env/.env.api` eintragen
- `FERNET_KEY` → in `env/.env.app` eintragen (gilt für api, sync-service und ml-service)

Alternativ manuell:
```bash
# SESSION_SECRET
openssl rand -hex 32

# FERNET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Startup-Validierung

Alle drei Services crashen beim Start wenn eine Pflicht-Variable fehlt oder leer ist (Pydantic `ValidationError`). Das ist beabsichtigt — kein stiller Fallback auf unsichere Defaults.

Beispiel:
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
fernet_key
  Value error, FERNET_KEY muss gesetzt sein. [...]
```

---

## CI/CD — Env-Handling

In GitHub Actions werden echte Env-Values über Secrets injiziert. Im E2E-Test-Stack (`docker-compose.test.yml`) werden `SESSION_SECRET` und `FERNET_KEY` dynamisch generiert:

```yaml
sed -i "s|^SESSION_SECRET=.*|SESSION_SECRET=$(openssl rand -hex 32)|" env/.env.api
sed -i "s|^FERNET_KEY=.*|FERNET_KEY=$(python3 -c '...')|" env/.env
```

In Unit-Tests (`api/tests/conftest.py`) werden Env-Variablen via `os.environ.setdefault()` mit Test-Werten gesetzt — bevor `src.main` importiert wird.
