# Configuration Reference

Alle Umgebungsvariablen aller drei Services. Jede Variable wird beim App-Start validiert (Pydantic `BaseSettings`) — die App crasht sofort wenn eine Pflicht-Variable fehlt.

Dateien liegen unter `env/`. Vorlagen: `env/.env.example`, `env/.env.api.example`, `env/.env.sync.example`.

---

## Übersicht: Welche Datei für welchen Service

| Datei | Geladen von |
|-------|-------------|
| `env/.env` | api, sync-service, db, flyway |
| `env/.env.api` | api |
| `env/.env.sync` | sync-service |
| `env/.env.ml` | ml-service |

---

## `env/.env` — Shared (alle Services + DB)

### Datenbank — Admin-User

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `DB_USER` | string | ✓ | — | PostgreSQL-Admin-User (Flyway-Migrationen) |
| `DB_PASSWORD` | string | ✓ | — | Passwort des Admin-Users |

### Datenbank — App-User (Least Privilege)

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `DB_APP_USER` | string | ✓ | — | App-User (SELECT/INSERT/UPDATE/DELETE only) |
| `DB_APP_PASSWORD` | string | ✓ | — | Passwort des App-Users |

### Verschlüsselung

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `FERNET_KEY` | string | ✓ | — | 32-Byte URL-safe base64-Key für Fernet-Verschlüsselung der Garmin/Libre-Tokens. Leerer Wert → Startup-Crash. Gleicher Wert in `env/.env` und `env/.env.sync`. |

Generieren:
```bash
make gen-secrets
# oder:
python3 -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

### Sonstiges

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `HOST_IP` | string | — | `garmin.home.lab` | Hostname (wird in `docker-compose.yml` als Traefik-Rule verwendet) |

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
| `APP_BASE_URL` | string | — | `https://garmin.home.lab` | Basis-URL für Links in Reset-Mails. Muss öffentlich erreichbar sein. |

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
| `SYNC_HOUR` | int | — | `6` | Stunde (UTC) für den täglichen Garmin-Sync (0–23). Libre-Sync läuft alle 5 Minuten unabhängig davon. |
| `SYNC_LOOKBACK_DAYS` | int | — | `30` | Wie viele Tage beim initialen Backfill (erster Sync nach Account-Verknüpfung) geholt werden |
| `SYNC_DAILY_DAYS` | int | — | `2` | Wie viele Tage beim täglichen Sync und beim manuellen Sync-Button nachgeladen werden |

*(FERNET_KEY kommt aus `env/.env` — muss identisch mit dem API-Wert sein)*

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

| Variable | env/.env | env/.env.api | env/.env.sync | env/.env.ml |
|----------|----------|--------------|---------------|-------------|
| `DB_USER` | ✓ | — | — | — |
| `DB_PASSWORD` | ✓ | — | — | — |
| `DB_APP_USER` | ✓ | — | — | — |
| `DB_APP_PASSWORD` | ✓ | — | — | — |
| `FERNET_KEY` | ✓ | — | ✓ (gleicher Wert!) | — |
| `HOST_IP` | ✓ | — | — | — |
| `DB_HOST` | — | default `db` | default `db` | default `db` |
| `DB_PORT` | — | default `5432` | default `5432` | default `5432` |
| `DB_NAME` | — | default `garmin` | default `garmin` | default `garmin` |
| `SESSION_SECRET` | — | ✓ | — | — |
| `HTTPS_ONLY` | — | default `true` | — | — |
| `TRIMP_LOOKBACK_DAYS` | — | default `7` | — | — |
| `TRIMP_FORECAST_DAYS` | — | default `7` | — | — |
| `RESEND_API_KEY` | — | optional `""` | — | — |
| `RESEND_FROM_EMAIL` | — | default | — | — |
| `APP_BASE_URL` | — | default | — | — |
| `SENTRY_DSN` | — | optional `""` | optional `""` | optional `""` |
| `SYNC_HOUR` | — | — | default `6` | — |
| `SYNC_LOOKBACK_DAYS` | — | — | default `30` | — |
| `SYNC_DAILY_DAYS` | — | — | default `2` | — |
| `ML_INFER_HOUR` | — | — | — | default `7` |
| `ML_TRAIN_WEEKDAY` | — | — | — | default `6` |
| `MODEL_DIR` | — | — | — | default `/app/models` |

---

## Secrets generieren

```bash
make gen-secrets
```

Gibt aus:
- `SESSION_SECRET` → in `env/.env.api` eintragen
- `FERNET_KEY` → in `env/.env` **und** `env/.env.sync` eintragen (gleicher Wert!)

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
