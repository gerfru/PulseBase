# Production Hardening

Checkliste und Referenz für den Betrieb von PulseBase als gehosteter Service.
Status-Symbole: ✅ erledigt · 🔧 in Arbeit · 📋 geplant · ⏳ langfristig

---

## 1. Release-Blocker

| # | Was | Status | Datei |
|---|-----|--------|-------|
| 1 | Session-Fixation: `request.session.clear()` vor Login | ✅ | api/src/main.py |
| 2 | Account-Enumeration: Dummy-bcrypt wenn User nicht existiert | ✅ | api/src/main.py |
| 3 | CDN entfernen: Chart.js, Leaflet, Tailwind self-hosted | ✅ | api/src/static/vendor/ |
| 4 | Docker Image Pinning: Semver+Digest + Renovate | ✅ | docker-compose.yml, renovate.json |

### Fix 1 — Session-Fixation

```python
# api/src/main.py — Login-Route
user_id = user["id"]
request.session.clear()           # verhindert Session-Fixation
request.session["user_id"] = str(user_id)
```

Gleiche Änderung im Register-Endpoint.

### Fix 2 — Account-Enumeration (Timing-Angriff)

Wenn User nicht existiert, wird bcrypt nie aufgerufen → Response ~300ms schneller →
Angreifer kann gültige E-Mails enummerieren.

```python
# Modul-Level Konstante (einmal beim App-Start berechnet, nicht pro Request)
DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode()

# Login-Route:
user = await get_user_by_email(email)
password_hash = user.get("password_hash") if user else DUMMY_HASH
valid = verify_password(password, password_hash)
if not user or not valid:
    return ... {"error": "E-Mail oder Passwort falsch."}
```

### Fix 3 — CDN → Self-hosted

Herunterladen und in `api/src/static/vendor/` ablegen:

```bash
# Chart.js
curl -o api/src/static/vendor/chart.umd.min.js \
  https://cdn.jsdelivr.net/npm/chart.js@4.4.8/dist/chart.umd.min.js

# Leaflet
curl -o api/src/static/vendor/leaflet.min.js \
  https://unpkg.com/leaflet@1.9.4/dist/leaflet.js
curl -o api/src/static/vendor/leaflet.min.css \
  https://unpkg.com/leaflet@1.9.4/dist/leaflet.css

# Tailwind (CDN-Bundle, bis Phase 5 Tailwind CLI fertig ist)
curl -o api/src/static/vendor/tailwind.cdn.js \
  https://cdn.tailwindcss.com
```

Templates updaten: `/static/vendor/...` statt CDN-URLs.

CSP in `api/src/main.py` bereinigen — `cdn.jsdelivr.net`, `unpkg.com`, `cdn.tailwindcss.com`
aus `script-src` und `style-src` entfernen.

### Fix 4 — Docker Image Pinning

State of the Art: **Semver-Tag + SHA256-Digest** + **Renovate** für automatische Updates.

```bash
# Aktuellen Digest ermitteln:
docker pull timescale/timescaledb:2.17.2-pg16
docker inspect --format='{{index .RepoDigests 0}}' timescale/timescaledb:2.17.2-pg16
```

```yaml
# docker-compose.yml
image: timescale/timescaledb:2.17.2-pg16@sha256:<digest>
image: flyway/flyway:11.8.2@sha256:<digest>
# Public-Overlay (docker-compose.public.yml):
image: caddy:2.10-alpine@sha256:<digest>
```

**renovate.json** (Projekt-Root):
```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"],
  "pinDigests": true,
  "docker-compose": {
    "enabled": true
  },
  "packageRules": [
    {
      "matchDepTypes": ["devDependencies"],
      "matchUpdateTypes": ["patch"],
      "automerge": true
    }
  ]
}
```

GitHub App aktivieren: https://github.com/apps/renovate → Install auf dem Repo.
Renovate erstellt danach automatisch PRs wenn neue Image-Versionen oder Digests erscheinen.

---

## 2. GDPR / Rechtliches

EU-Pflichten: DSGVO (seit 2018), BFSG/EU Accessibility Act (seit Juni 2025).

### 2.1 Pflichtdokumente (vor erstem fremden User)

- **Datenschutzerklärung** (`/privacy`): Welche Daten, Zweck, Speicherdauer, Drittanbieter
  (Garmin Connect API, LibreLink API), Recht auf Auskunft/Löschung/Export, Kontakt, Cookie-Hinweis
- **Nutzungsbedingungen** (`/terms`): Haftungsausschluss (keine medizinische Beratung!),
  Mindestalter 16 (DSGVO Art. 8), Konsequenzen bei Missbrauch
- **Impressum** (DE/AT-Pflicht): Name, Adresse, Kontakt-E-Mail
- **Barrierefreiheitserklärung** (`/accessibility`): Pflicht nach BFSG (in Kraft seit 28. Juni 2025).
  [Name]/[E-Mail]-Platzhalter füllen.

Gesundheitsdaten fallen unter Art. 9 DSGVO ("besondere Kategorien") →
explizite, informierte Einwilligung bei Registrierung erforderlich (Checkbox mit Link zur
Datenschutzerklärung, nicht vorausgewählt).

### 2.2 Technische GDPR-Features

| Feature | Endpoint | Status |
|---------|----------|--------|
| Konto löschen (alle Daten) | `POST /account/delete` | ✅ |
| Daten exportieren (JSON) | `GET /account/export` | ✅ |
| E-Mail-Verifikation | Nach Register → Bestätigungs-Mail | ✅ |
| Passwort-Reset | `POST /auth/reset-request` + Token-Mail | ✅ |

**Konto-Löschung — umfasst (atomar in einer Transaktion):**
`users`, `activities`, `activity_records`, `daily_summary`, `sleep_sessions`,
`hrv_daily`, `ml_predictions`, `seizure_events`, `glucose_readings` +
`user_tokens`-Einträge (ON DELETE CASCADE — Garmin/Libre Fernet-Tokens werden mitgelöscht)

### 2.3 Verarbeitungsverzeichnis (internes Dokument, kein UI)

| Datenart | Quelle | Zweck | Speicherdauer | Drittland? |
|----------|--------|-------|---------------|-----------|
| Garmin Aktivitätsdaten | Garmin Connect API | Analyse, Dashboard | bis Konto-Löschung | Nein (EU-Hosting) |
| Garmin Gesundheitsdaten (HRV, Schlaf) | Garmin Connect API | Analyse, ML | bis Konto-Löschung | Nein |
| Glukosedaten | LibreLink API | Analyse | bis Konto-Löschung | Nein |
| Login-Session | Starlette SessionMiddleware | Auth | 14 Tage inaktiv | Nein |
| Garmin Auth-Token + LibreLink Token | user_tokens DB-Tabelle (Fernet-verschlüsselt, V20) | Sync | bis Konto getrennt | Nein |

---

## 3. Security-Features Backlog

### 3.1 Password-Reset-Flow ✅

Implementiert **DB-backed** (`api/src/auth_tokens.py`): `secrets.token_urlsafe(32)` → SHA-256-Hash
→ via `save_reset_token` in der DB abgelegt, Validierung per DB-Lookup. 1-Stunde TTL (`_RESET_MAX_AGE = 3600`).
(Nur E-Mail-Verify und Account-Delete nutzen stateless `itsdangerous.URLSafeTimedSerializer`, HMAC-signiert
mit `SESSION_SECRET`.) E-Mail-Versand via Resend (3.000 Mails/Mo kostenlos).

```
GET  /auth/reset-request  → Formular anzeigen
POST /auth/reset-request  → Token generieren, Mail senden (non-leaking: immer 200)
GET  /auth/reset/{token}  → Formular anzeigen (Token-Validierung, 400 wenn ungültig/abgelaufen)
POST /auth/reset/{token}  → Passwort setzen, Redirect zu /login?reset=1
```

Konfiguration in `env/.env.api`:
```bash
RESEND_API_KEY=re_...          # leer lassen = Reset-Link nur im Log (kein Mailversand)
RESEND_FROM_EMAIL=onboarding@resend.dev
APP_BASE_URL=https://your-domain.com
```

### 3.2 Per-Service Secrets Isolation ✅

Jeder Service lädt nur die Secrets, die er tatsächlich braucht (Least-Privilege).
Umsetzung via native Docker Compose `env_file`-Listen — kein extra Tooling, kein Code-Change.

| File | Service | Enthält |
|------|---------|---------|
| `env/.env` | db, flyway | DB_USER/PASSWORD (Admin), HOST_IP |
| `env/.env.app` | api, sync, ml | FERNET_KEY + Per-Service-DB-Rollen (V24): `DB_APP_*` (nur api), `DB_SYNC_*` (nur sync), `DB_ML_*` (nur ml) |
| `env/.env.api` | api | SESSION_SECRET (min. 32 Zeichen), HTTPS_ONLY, TRIMP_*, RESEND_*, APP_BASE_URL, TRUSTED_PROXY_CIDRS, SENTRY_DSN, LOG_LEVEL |
| `env/.env.sync` | sync-service | SYNC_INTERVAL_HOURS, SYNC_LOOKBACK_DAYS, SYNC_DAILY_DAYS, SENTRY_DSN, LOG_LEVEL |
| `env/.env.ml` | ml-service | ML_INFER_HOUR, ML_TRAIN_WEEKDAY, SENTRY_DSN, LOG_LEVEL |

Dateiberechtigungen: `make secure-env` setzt `chmod 600` auf alle Secret-Files.

Verifikation:
```bash
docker exec pulsebase-sync env | grep SESSION_SECRET   # → leer
docker exec pulsebase-api env | grep SESSION_SECRET    # → vorhanden
```

### 3.3 E-Mail-Verifikation bei Registrierung ✅

Migration `V18__email_verification.sql` ergänzt `email_verified_at TIMESTAMPTZ`; bestehende
User werden per Backfill sofort verifiziert.

Ablauf: Register → Token-Mail → `/auth/verify/{token}` → `email_verified_at` setzen.
Login sperrt nicht-verifizierte Accounts (klare Fehlermeldung + Resend-Link `/auth/resend-verify`).
Verify-Token nutzt stateless `itsdangerous.URLSafeTimedSerializer` (Salt `email-verify`, 24h TTL) —
anders als der DB-backed Password-Reset-Token (siehe 3.1).
Resend-Endpoint non-leaking (immer 200), Rate Limit 3/h.

### 3.4 Account-Lockout ✅

IP-basiertes Rate Limiting (slowapi) + konto-basierter Lockout (OWASP-konform, Schwellenwert 3–5).

```sql
-- V17__account_lockout.sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts SMALLINT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;
```

Logik: 5 Fehlversuche → 15min Sperre + Resend-E-Mail an Nutzer. Sperre zurücksetzen bei
erfolgreichem Login. Auto-Unlock nach Ablauf (kein manueller Eingriff).

**DoS-Hinweis:** Fixer Lockout kann vom Angreifer ausgenutzt werden (gezieltes Sperren fremder Konten).
Mitigation: E-Mail-Benachrichtigung informiert echten Nutzer sofort; `locked_until` läuft automatisch ab.

### 3.5 Audit-Logging

Events die geloggt werden sollten:
- Login (success/fail, IP, User-Agent)
- Passwort-Änderung, E-Mail-Änderung
- Garmin/Libre Account verknüpft/getrennt
- Konto-Löschung initiiert

**KISS-Implementierung:** Strukturierte Log-Zeilen mit `structlog` (kein Schema-Change):
```python
structlog.get_logger().info("auth.login.success", user_id=user_id, ip=ip)
structlog.get_logger().warning("auth.login.fail", email=email, ip=ip)
```

**Alternativ (auditierbar):** Tabelle `audit_log(id BIGSERIAL, user_id INT, event TEXT, ip INET, ua TEXT, created_at TIMESTAMPTZ)`.

### 3.6 Garmin & LibreLink Token Encryption at Rest ✅

**Implementiert:** Tokens werden Fernet-verschlüsselt als `BYTEA` in der DB gespeichert (`user_tokens`-Tabelle, V20-Migration). Kein Docker-Volume mehr nötig.

**Architektur:**
- `FERNET_KEY` in `env/.env.app` (shared — von api via `api/src/db/pool.py` und von sync via `sync-service/src/config.py` gelesen; ml-service hat keinen FERNET_KEY) (32-byte URL-safe base64)
- Generieren: `make gen-secrets`
- Startup-Validation: API und Sync-Service crashen beim Start wenn `FERNET_KEY` fehlt oder leer ist (Pydantic `ValidationError` — kein Plaintext-Fallback mehr). ValueError wenn Key-Format ungültig.
- `ON DELETE CASCADE` — Token wird beim Konto-Löschen automatisch mitgelöscht
- Transparente Migration: bestehende Token-Files werden beim ersten Sync in die DB migriert

**Kein permanenter Token-Pfad mehr:** Garmin- und Libre-Tokens werden beim Link-Flow ausschließlich in einem `tempfile.TemporaryDirectory()` geschrieben und dann Fernet-verschlüsselt in der DB gespeichert. Der Klartext-Token existiert nie dauerhaft auf Disk.

**Langfristig:** ⏳ Garmin OAuth2 via Garmin Health API Developer Program — dann kein
Passwort und kein Token mehr auf eigenen Servern.

---

## 4. Hosting-Architektur

```
Internet
    ↓
Cloudflare (Free) ←── DNS, DDoS-Schutz, WAF-Basis, Origin-IP verstecken
    ↓
Hetzner VPS CX21 (5 €/Mo, Nürnberg oder Helsinki = EU-Hosting)
    ↓
Caddy 2 (make up-public) ←── TLS-Terminierung, HTTPS-Redirect, Let's Encrypt automatisch
    ↓
FastAPI API ←── Container-intern auf Port 8000
    ↓
TimescaleDB ←── internes Docker-Netz only, nie direkt exponiert
```

**Warum Cloudflare davor:**
- DDoS-Schutz ohne Konfigurationsaufwand (auch Free-Tier blockt volumetrische Angriffe)
- Origin-Server-IP ist unsichtbar → direkter Angriff am Edge abgeblockt
- `CF-Connecting-IP`-Header weiterleiten, damit `X-Forwarded-For` in `_get_real_ip()` korrekt bleibt
- Rate Limiting auf Edge zusätzlich zu slowapi

**Server-Grundsetup (einmalig nach Provisionierung):**
```bash
# Automatische Security-Updates
apt install unattended-upgrades -y
dpkg-reconfigure --priority=low unattended-upgrades

# Fail2Ban (SSH + HTTP Brute-Force)
apt install fail2ban -y

# UFW Firewall
ufw allow 22/tcp    # SSH (besser: anderen Port wählen)
ufw allow 80/tcp    # HTTP → Caddy → Redirect zu HTTPS (+ ACME HTTP-01)
ufw allow 443/tcp   # HTTPS
ufw --force enable

# SSH härten: PasswordAuthentication no, PermitRootLogin no in /etc/ssh/sshd_config
```

---

## 5. Betrieb & Wartung

### 5.1 Backup-Strategie

**KISS:** Cron-Job auf dem Host (außerhalb Docker, überlebt Container-Neustart).

```bash
# /etc/cron.d/pulsebase-backup
0 3 * * * root /opt/pulsebase/scripts/backup.sh >> /var/log/pulsebase-backup.log 2>&1
```

```bash
#!/bin/bash
# /opt/pulsebase/scripts/backup.sh
set -euo pipefail
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/pulsebase/backups"
mkdir -p "$BACKUP_DIR"

# PostgreSQL-Dump
docker exec pulsebase-db pg_dump -U garmin garmin | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Offsite-Upload (Backblaze B2, rclone konfigurieren: rclone config → b2)
rclone copy "$BACKUP_DIR" b2:pulsebase-backups --include "*$DATE*"

# Lokale Rotation (14 Tage)
find "$BACKUP_DIR" -name "*.gz" -mtime +14 -delete

echo "Backup $DATE fertig."
```

**Offsite-Storage:** Backblaze B2 — 10 GB kostenlos, danach ~0,006 $/GB/Mo.

**Restore-Test:** Monatlich — Dump in Test-Container einspielen und API-Aufruf verifizieren.

### 5.2 Monitoring

| Tool | Zweck | Einrichtung | Kosten |
|------|-------|-------------|--------|
| **Sentry** | Exceptions, Error-Tracking | `sentry-sdk[fastapi]` in requirements | Free (5k Events/Mo) |
| **UptimeRobot** | Uptime-Check auf `/ready` | Account + Monitor erstellen | Free (50 Monitore) |
| **Better Stack** | Log-Aggregation (strukturiert) | `structlog` HTTP-Sink | Free (1 GB/Mo) |

**Sentry minimal einbinden:**
```python
# api/src/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, integrations=[FastApiIntegration()])
```

`SENTRY_DSN` in `.env.example` ergänzen, optional in `.env` setzen.

### 5.3 Dependency-Updates

Renovate (nach Einrichten von `renovate.json`, s. Fix 4) verwaltet alles:
- pip-Pakete (`pyproject.toml`)
- Docker-Image-Digests (`docker-compose.yml`)
- GitHub Actions (`ci.yml`)

Strategie: devDeps Patch → Automerge. Major → manueller Review. Docker → Digest-Update = Automerge, Tag-Update = manuell.

**⚠️ Sonderfall TimescaleDB-Upgrades:**
Ein reines Image-Tag-Update reicht nicht — PostgreSQL lädt die `.so`-Library der alten
Version aus den Datenbankdateien und startet nicht, wenn die neue Image-Version nicht passt.

Ablauf für ein TimescaleDB-Minor-Upgrade (z.B. 2.26.4 → 2.27.x):
```bash
# 1. Backup machen (Pflicht!) — es gibt KEIN `make backup`-Target, manuell:
docker exec pulsebase-db pg_dump -U garmin garmin | gzip > backup.sql.gz

# 2. Image in docker-compose.yml auf neue Version + Digest updaten

# 3. DB-Container neu starten
docker compose up -d db

# 4. Extension updaten
make db SQL="ALTER EXTENSION timescaledb UPDATE;"

# 5. Verify
make db SQL="SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"
```

Für **Major-Upgrades** (z.B. pg16 → pg17) ist ein `pg_upgrade` oder Dump+Restore nötig —
nie nur das Image tauschen.

### 5.4 Incident Response (Minimalplan)

| Schritt | Aktion |
|---------|--------|
| **Isolieren** | `make down-public` (oder den `caddy`-Service stoppen) → App vom Netz nehmen |
| **Sessions invalidieren** | `SESSION_SECRET` rotieren → `make dashboard` (alle Logins sofort ungültig) |
| **Passwörter** | Alle User per Mail informieren, Reset-Links senden |
| **Logs sichern** | `docker logs pulsebase-api > incident_$(date +%Y%m%d).log` bevor Container neu gestartet |
| **Analyse** | Logs + Audit-Log auf ungewöhnliche Events durchsuchen |

---

## 6. Release-Checkliste

### Pre-Release: Code
- [x] Session-Fixation-Fix (`request.session.clear()` vor Login)
- [x] Account-Enumeration-Schutz (Dummy-bcrypt)
- [x] CDN-URLs entfernt, alle Assets unter `/static/vendor/`
- [x] Docker Images auf Semver+Digest gepinnt
- [x] `renovate.json` erstellt, GitHub App aktiviert

### Pre-Release: Legal
- [ ] Datenschutzerklärung live unter `/privacy` (Route ✅, Inhalt: [Name]/[E-Mail] Platzhalter füllen)
- [ ] Nutzungsbedingungen live unter `/terms` (Route ✅, Inhalt: [Name]/[E-Mail] Platzhalter füllen)
- [ ] Impressum live unter `/imprint` (Route ✅, Inhalt: [Name]/[Adresse] Platzhalter füllen)
- [x] Barrierefreiheitserklärung live unter `/accessibility` (BFSG seit Juni 2025, Footer-Link vorhanden)
- [x] Einwilligungs-Checkboxen bei Registrierung: Gesundheitsdaten (Art. 9) + Nutzungsbedingungen + Altersbestätigung ≥16 (Art. 8) + Consent-Audit-Log (user_consents, V19)
- [x] Gesundheitsdaten-Disclaimer auf Dashboard (dashboard.html:171)

### Pre-Release: Infrastruktur
- [ ] Server in EU (Hetzner Nürnberg oder Helsinki)
- [ ] Cloudflare DNS eingerichtet, Origin-IP nicht öffentlich
- [ ] Automatische Backups laufen, Restore einmal getestet
- [ ] Sentry eingebunden, Test-Exception versendet
- [ ] UptimeRobot Monitor für `/ready` aktiv
- [ ] SSH Passwort-Auth deaktiviert, nur Key-Auth

### Launch
- [ ] HTTPS erzwungen (HSTS aktiv) ✅ via SecurityHeadersMiddleware
- [ ] Status-Page öffentlich (UptimeRobot Public Page, kostenlos)
- [ ] Kontakt-E-Mail in Datenschutzerklärung + Impressum

### Post-Launch (erste 4 Wochen)
- [x] Password-Reset-Flow live
- [x] E-Mail-Verifikation bei Registrierung
- [x] Account-Löschung (`POST /account/delete`) live (DSGVO Art. 17, ASVS V2.4.1 Passwort-Bestätigung)
- [x] Daten-Export (`GET /account/export`) live (DSGVO Art. 20, ohne password_hash)
- [x] Fernet-Verschlüsselung für Token-Storage aktiv (DB, V20)
- [x] Account-Lockout nach Fehlversuchen

---

## Anhang: Verifikation der Release-Blocker

```bash
# Session-Fixation: Cookie vor und nach Login vergleichen
# → Browser DevTools → Application → Cookies → session-Wert muss sich ändern

# Account-Enumeration Timing-Test (bcrypt ~300ms — beide sollten gleich dauern)
time curl -s -X POST https://deinedomain.com/login \
  -d "email=nonexistent@example.com&password=test" -c /tmp/c1.txt
time curl -s -X POST https://deinedomain.com/login \
  -d "email=existinguser@example.com&password=wrongpass" -c /tmp/c2.txt

# CDN: Keine externen Script-Loads in der Browser-Console
# DevTools → Network → filter "cdn.jsdelivr.net" → sollte leer sein

# Docker Digest-Pinning
grep "sha256" docker-compose.yml | wc -l  # > 0 erwartet
```
