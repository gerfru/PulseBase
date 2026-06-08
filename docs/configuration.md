# Configuration Reference

Alle Umgebungsvariablen aller drei Services. Jede Variable wird beim App-Start validiert (Pydantic `BaseSettings`) — die App crasht sofort wenn eine Pflicht-Variable fehlt.

Dateien liegen unter `env/`. Vorlagen: `env/.env.example`, `env/.env.app.example`, `env/.env.api.example`, `env/.env.sync.example`, `env/.env.ml.example`.

---

## Übersicht: Welche Datei für welchen Service

| Datei | Geladen von | Enthält |
|-------|-------------|---------|
| `env/.env` | db, flyway | Admin-DB-Credentials, HOST_IP |
| `env/.env.app` | api, sync-service, ml-service | Per-Service-DB-Credentials (`DB_APP_*`, `DB_SYNC_*`, `DB_ML_*`), FERNET_KEY, SENTRY_DSN |
| `env/.env.api` | api | SESSION_SECRET, RESEND_*, APP_BASE_URL, TRIMP_* |
| `env/.env.sync` | sync-service | SYNC_INTERVAL_HOURS, SYNC_LOOKBACK_DAYS, SYNC_DAILY_DAYS |
| `env/.env.ml` | ml-service | ML_INFER_HOUR, ML_TRAIN_WEEKDAY, MODEL_DIR |

> **Warum diese Trennung?** Admin-Credentials (`DB_USER`/`DB_PASSWORD`) sind nur für Flyway-Migrationen nötig. App-Services bekommen je eine eigene Least-Privilege-Rolle (V24): api liest `DB_APP_*` (breit), sync-service liest `DB_SYNC_*`, ml-service liest `DB_ML_*` — alle mit eng-granulierten Rechten. Damit sind Admin-Creds nie im Prozess-Environment von api/sync/ml sichtbar (H-11).
> `SENTRY_DSN` steht zentral in `env/.env.app` und wird von allen drei Services gelesen.

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
| `HOST_IP` | string | — | `your-domain.com` | Hostname/Domain des Servers (Heim-Routing). Öffentliche Domain für `make up-public` steht in `env/.env.public` als `PUBLIC_DOMAIN`. |

---

## `env/.env.app` — App-Services (api, sync-service, ml-service)

Enthält die minimalen Credentials für App-Services. Kein Admin-Zugriff — nur Least-Privilege-User.

### Datenbank — Per-Service-Rollen (Least Privilege, V24)

Jeder App-Service bekommt eine eigene DB-Rolle. Alle sechs Werte stehen in `env/.env.app`, weil sie sowohl die Flyway-Platzhalter (Rollen-Anlage) als auch die Container speisen.

| Variable | Typ | Pflicht | Default | Gelesen von | Beschreibung |
|----------|-----|---------|---------|-------------|--------------|
| `DB_APP_USER` | string | ✓ | — | api | App-User (breit: SELECT/INSERT/UPDATE/DELETE, Auth, Account-Löschung) |
| `DB_APP_PASSWORD` | string | ✓ | — | api | Passwort des App-Users |
| `DB_SYNC_USER` | string | ✓ | — | sync-service | Least-Privilege-Rolle für den Sync-Service |
| `DB_SYNC_PASSWORD` | string | ✓ | — | sync-service | Passwort der Sync-Rolle |
| `DB_ML_USER` | string | ✓ | — | ml-service | Read-only Health + write `ml_predictions` |
| `DB_ML_PASSWORD` | string | ✓ | — | ml-service | Passwort der ML-Rolle |

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

### Error Tracking (shared)

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `SENTRY_DSN` | string | — | `""` | DSN von [sentry.io](https://sentry.io). Leer = Sentry deaktiviert. Zentral hier gesetzt und von api, sync-service und ml-service gelesen. |

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
| `DB_POOL_MIN` | int | — | `1` | asyncpg-Pool `min_size`. Defaults entsprechen den bisherigen Hardcodes. |
| `DB_POOL_MAX` | int | — | `5` | asyncpg-Pool `max_size`. Hochsetzen bei mehreren uvicorn-Workern. |

*(DB_APP_USER, DB_APP_PASSWORD kommen aus `env/.env.app`)*

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
| `APP_BASE_URL` | string | — | `""` (Pydantic-Default leer) | Basis-URL für Links in Reset-Mails. Muss öffentlich erreichbar sein. Die Beispieldatei `env/.env.api.example` setzt `https://your-domain.com` als Platzhalter. |

### Proxy & Rate Limiting

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `TRUSTED_PROXY_CIDRS` | list[str] | — | `["127.0.0.1/32"]` | CIDR-Bereiche der vertrauenswürdigen Proxies für `X-Forwarded-For`-Auswertung. Docker-Netz: `["172.23.0.0/16","127.0.0.1/32"]`. Falsche Konfiguration bricht IP-basiertes Rate Limiting. |

*(SENTRY_DSN kommt aus `env/.env.app` — zentral für alle drei Services)*

---

## `env/.env.sync` — Sync-Service

### Datenbankverbindung

Wie API — `DB_HOST`, `DB_PORT`, `DB_NAME` (mit denselben Defaults). `DB_SYNC_USER`, `DB_SYNC_PASSWORD` kommen aus `env/.env.app` (eigene Least-Privilege-Rolle, V24).

### Sync-Timing

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `SYNC_INTERVAL_HOURS` | int | — | `2` | Polling-Intervall in Stunden für den Garmin-Sync. Libre-Sync läuft alle 5 Minuten unabhängig davon. |
| `SYNC_LOOKBACK_DAYS` | int | — | `30` | Wie viele Tage beim initialen Backfill (erster Sync nach Account-Verknüpfung) geholt werden |
| `SYNC_DAILY_DAYS` | int | — | `2` | Wie viele Tage pro Interval-Run nachgeladen werden |

*(FERNET_KEY und SENTRY_DSN kommen aus `env/.env.app` — gemeinsam für alle App-Services)*

### Token-Speicherort

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `TOKEN_BASE_DIR` | path | — | `/app/tokens` | Basisverzeichnis für die (Fernet-verschlüsselten) Garmin-Login-Tokens pro User |

---

## `env/.env.ml` — ML-Service

### Datenbankverbindung

`DB_HOST`, `DB_PORT`, `DB_NAME` (mit denselben Defaults). `DB_ML_USER`, `DB_ML_PASSWORD` kommen aus `env/.env.app` (eigene Least-Privilege-Rolle, V24).

> Hinweis: ml-service nutzt nur seine eigene ML-Rolle (read-only Health + write `ml_predictions`), nicht den Admin-User (kein `DB_USER` / `DB_PASSWORD` nötig).

### ML-Scheduler

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `ML_INFER_HOUR` | int | — | `7` | Stunde (UTC) für die tägliche Inferenz (Predictions für alle User) |
| `ML_TRAIN_WEEKDAY` | int | — | `6` | Wochentag für das wöchentliche Re-Training (0 = Montag, 6 = Sonntag) |

### Modell-Speicherort

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `MODEL_DIR` | path | — | `/app/models` | Verzeichnis für gespeicherte scikit-learn-Modelle (joblib-Format) |

*(SENTRY_DSN kommt aus `env/.env.app` — zentral für alle drei Services)*

---

## `env/.env.public` — Public SaaS (nur `make up-public`)

Nur für die öffentliche Instanz (gebündeltes Caddy + Vector). Nicht im Heim-Betrieb nötig.
Vollständiger Runbook: [deployment-public.md](deployment-public.md).

| Variable | Typ | Pflicht | Default | Beschreibung |
|----------|-----|---------|---------|--------------|
| `PUBLIC_DOMAIN` | string | ✓ (public) | — | Öffentliche Domain für Caddy/Let's Encrypt. A-Record muss vor dem Start stehen. |
| `ACME_EMAIL` | string | ✓ (public) | — | Kontakt-Mail für Let's Encrypt. |
| `BETTERSTACK_SOURCE_TOKEN` | string | — | `""` | Source-Token für Log-Shipping via Vector an Better Stack (alternativ Axiom). |

> Zusätzlich für die öffentliche Instanz in `env/.env.api`: `HTTPS_ONLY=true`,
> `APP_BASE_URL=https://<domain>`, `TRUSTED_PROXY_CIDRS=["172.30.0.0/16","127.0.0.1/32"]`
> (gepinntes `internal`-Subnetz des Overlays).

---

## Vollständige Variablen-Matrix

| Variable | env/.env | env/.env.app | env/.env.api | env/.env.sync | env/.env.ml |
|----------|----------|--------------|--------------|---------------|-------------|
| `DB_USER` | ✓ | — | — | — | — |
| `DB_PASSWORD` | ✓ | — | — | — | — |
| `HOST_IP` | ✓ | — | — | — | — |
| `DB_APP_USER` | — | ✓ | — | — | — |
| `DB_APP_PASSWORD` | — | ✓ | — | — | — |
| `DB_SYNC_USER` | — | ✓ | — | — | — |
| `DB_SYNC_PASSWORD` | — | ✓ | — | — | — |
| `DB_ML_USER` | — | ✓ | — | — | — |
| `DB_ML_PASSWORD` | — | ✓ | — | — | — |
| `FERNET_KEY` | — | ✓ | — | — | — |
| `SENTRY_DSN` | — | optional `""` | — | — | — |
| `DB_HOST` | — | — | default `db` | default `db` | default `db` |
| `DB_PORT` | — | — | default `5432` | default `5432` | default `5432` |
| `DB_NAME` | — | — | default `garmin` | default `garmin` | default `garmin` |
| `SESSION_SECRET` | — | — | ✓ | — | — |
| `HTTPS_ONLY` | — | — | default `true` | — | — |
| `TRIMP_LOOKBACK_DAYS` | — | — | default `7` | — | — |
| `TRIMP_FORECAST_DAYS` | — | — | default `7` | — | — |
| `RESEND_API_KEY` | — | — | optional `""` | — | — |
| `RESEND_FROM_EMAIL` | — | — | default | — | — |
| `APP_BASE_URL` | — | — | default `""` (Beispiel: URL) | — | — |
| `TRUSTED_PROXY_CIDRS` | — | — | default | — | — |
| `SYNC_INTERVAL_HOURS` | — | — | — | default `2` | — |
| `SYNC_LOOKBACK_DAYS` | — | — | — | default `30` | — |
| `SYNC_DAILY_DAYS` | — | — | — | default `2` | — |
| `TOKEN_BASE_DIR` | — | — | — | default `/app/tokens` | — |
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
sed -i "s|^FERNET_KEY=.*|FERNET_KEY=$(python3 -c '...')|" env/.env.app
```

In Unit-Tests (`api/tests/conftest.py`) werden Env-Variablen via `os.environ.setdefault()` mit Test-Werten gesetzt — bevor `src.main` importiert wird.
