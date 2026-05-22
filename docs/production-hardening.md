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
image: traefik:v3.3.4@sha256:<digest>
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
  (Garmin Connect API, LibreLink API), Recht auf Auskunft/Löschung/Export, Kontakt
- **Nutzungsbedingungen** (`/terms`): Haftungsausschluss (keine medizinische Beratung!),
  Mindestalter 18, Konsequenzen bei Missbrauch
- **Impressum** (DE/AT-Pflicht): Name, Adresse, Kontakt-E-Mail

Gesundheitsdaten fallen unter Art. 9 DSGVO ("besondere Kategorien") →
explizite, informierte Einwilligung bei Registrierung erforderlich (Checkbox mit Link zur
Datenschutzerklärung, nicht vorausgewählt).

### 2.2 Technische GDPR-Features

| Feature | Endpoint | Status |
|---------|----------|--------|
| Konto löschen (alle Daten) | `DELETE /account` | 📋 |
| Daten exportieren (JSON) | `GET /account/export` | 📋 |
| E-Mail-Verifikation | Nach Register → Bestätigungs-Mail | ✅ |
| Passwort-Reset | `POST /auth/reset-request` + Token-Mail | ✅ |

**Konto-Löschung — umfasst (atomar in einer Transaktion):**
`users`, `activities`, `activity_records`, `daily_summary`, `sleep_sessions`,
`hrv_daily`, `ml_predictions`, `seizure_events`, `glucose_readings` +
Token-Files in `/app/tokens/{user_id}/`

### 2.3 Verarbeitungsverzeichnis (internes Dokument, kein UI)

| Datenart | Quelle | Zweck | Speicherdauer | Drittland? |
|----------|--------|-------|---------------|-----------|
| Garmin Aktivitätsdaten | Garmin Connect API | Analyse, Dashboard | bis Konto-Löschung | Nein (EU-Hosting) |
| Garmin Gesundheitsdaten (HRV, Schlaf) | Garmin Connect API | Analyse, ML | bis Konto-Löschung | Nein |
| Glukosedaten | LibreLink API | Analyse | bis Konto-Löschung | Nein |
| Login-Session | Starlette SessionMiddleware | Auth | 14 Tage inaktiv | Nein |
| Garmin Auth-Token | Docker Volume (verschlüsselt, siehe 3.5) | Sync | bis Garmin-Konto getrennt | Nein |

---

## 3. Security-Features Backlog

### 3.1 Password-Reset-Flow ✅

Implementiert via stateless `itsdangerous.URLSafeTimedSerializer` (kein DB-Schema-Change,
1-Stunde TTL, HMAC-signiert mit `SESSION_SECRET`). E-Mail-Versand via Resend (3.000 Mails/Mo kostenlos).

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
APP_BASE_URL=https://garmin.home.lab
```

### 3.2 Per-Service Secrets Isolation ✅

Jeder Service lädt nur die Secrets, die er tatsächlich braucht (Least-Privilege).
Umsetzung via native Docker Compose `env_file`-Listen — kein extra Tooling, kein Code-Change.

| File | Service | Enthält |
|------|---------|---------|
| `env/.env` | alle | DB_USER/PASSWORD, DB_APP_USER/PASSWORD, HOST_IP |
| `env/.env.api` | api | SESSION_SECRET, HTTPS_ONLY, TRIMP_*, RESEND_*, APP_BASE_URL |
| `env/.env.sync` | sync-service | SYNC_HOUR, SYNC_LOOKBACK_DAYS, SYNC_DAILY_DAYS |
| `env/.env.ml` | ml-service | ML_INFER_HOUR |

Dateiberechtigungen: `make secure-env` setzt `chmod 600` auf alle Secret-Files.

Verifikation:
```bash
docker exec garmin-sync env | grep SESSION_SECRET   # → leer
docker exec garmin-api env | grep SESSION_SECRET    # → vorhanden
```

### 3.3 E-Mail-Verifikation bei Registrierung ✅

Migration `V18__email_verification.sql` ergänzt `email_verified_at TIMESTAMPTZ`; bestehende
User werden per Backfill sofort verifiziert.

Ablauf: Register → Token-Mail → `/auth/verify/{token}` → `email_verified_at` setzen.
Login sperrt nicht-verifizierte Accounts (klare Fehlermeldung + Resend-Link `/auth/resend-verify`).
Gleiches Token-System wie Password-Reset (anderer Salt → kein Token-Reuse), 24h TTL.
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

### 3.6 Garmin Token Encryption at Rest

**Aktuell:** Plaintext-Token-Files im Docker-Volume.

**Fix (kurzfristig):** Fernet-Verschlüsselung mit Key aus Env:
```python
from cryptography.fernet import Fernet
# Einmalig: FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
# → in .env + .env.example ergänzen
fernet = Fernet(settings.fernet_key.encode())
encrypted = fernet.encrypt(token_data.encode())   # Schreiben
decrypted = fernet.decrypt(encrypted_data).decode()  # Lesen
```

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
Traefik v3 ←── TLS-Terminierung, HTTPS-Redirect, Let's Encrypt automatisch
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
ufw allow 80/tcp    # HTTP → Traefik → Redirect zu HTTPS
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
docker exec garmin-db pg_dump -U garmin garmin | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Token-Volume (verschlüsselt — Fernet ist Pflicht bevor dieser Backup nützlich ist)
docker run --rm \
  -v garmin_garmin-tokens:/data:ro \
  -v "$BACKUP_DIR:/backup" \
  busybox tar czf "/backup/tokens_$DATE.tar.gz" /data

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
| **UptimeRobot** | Uptime-Check auf `/health` | Account + Monitor erstellen | Free (50 Monitore) |
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
# 1. Backup machen (Pflicht!)
make backup   # oder manuell: docker exec garmin-db pg_dump -U garmin garmin | gzip > backup.sql.gz

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
| **Isolieren** | Traefik-Label `traefik.enable=false` setzen → `make dashboard` |
| **Sessions invalidieren** | `SESSION_SECRET` rotieren → `make dashboard` (alle Logins sofort ungültig) |
| **Passwörter** | Alle User per Mail informieren, Reset-Links senden |
| **Logs sichern** | `docker logs garmin-api > incident_$(date +%Y%m%d).log` bevor Container neu gestartet |
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
- [ ] Datenschutzerklärung live unter `/privacy`
- [ ] Nutzungsbedingungen live unter `/terms`
- [ ] Impressum live (Footer oder `/imprint`)
- [x] Einwilligungs-Checkbox bei Registrierung (DSGVO Art. 9) + Consent-Audit-Log (user_consents)
- [ ] Gesundheitsdaten-Disclaimer auf Dashboard ("Keine medizinische Beratung")

### Pre-Release: Infrastruktur
- [ ] Server in EU (Hetzner Nürnberg oder Helsinki)
- [ ] Cloudflare DNS eingerichtet, Origin-IP nicht öffentlich
- [ ] Automatische Backups laufen, Restore einmal getestet
- [ ] Sentry eingebunden, Test-Exception versendet
- [ ] UptimeRobot Monitor für `/health` aktiv
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
- [ ] Fernet-Verschlüsselung für Token-Volume aktiv
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
