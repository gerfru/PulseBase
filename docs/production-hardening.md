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
| E-Mail-Verifikation | Nach Register → Bestätigungs-Mail | 📋 |
| Passwort-Reset | `POST /auth/reset-request` + Token-Mail | 📋 |

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

### 3.1 Password-Reset-Flow

```sql
-- Neue Migration: VXX__password_reset.sql
CREATE TABLE password_reset_tokens (
    token       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at  TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '1 hour',
    used_at     TIMESTAMPTZ
);
```

```
POST /auth/reset-request  → Token generieren, Mail senden (Resend/Postmark Free Tier)
GET  /auth/reset/{token}  → Formular anzeigen (Token-Validierung)
POST /auth/reset/{token}  → Passwort setzen, Token als used markieren
```

E-Mail senden via `aiosmtplib` (SMTP) oder Transactional E-Mail API:
- **Resend** — 3.000 Mails/Mo kostenlos, einfachste API
- **Postmark** — 100 Mails/Mo kostenlos, besonders gute Deliverability

### 3.2 E-Mail-Verifikation bei Registrierung

```sql
-- In users-Tabelle ergänzen:
ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMPTZ;
```

Ablauf: Register → Token-Mail → `/auth/verify/{token}` → `email_verified_at` setzen.
Login sperren bis verifiziert (klare Fehlermeldung + Resend-Link).
Gleiches Token-System wie Password-Reset.

### 3.3 Account-Lockout (ergänzendes Brute-Force-Schutz)

Aktuell: IP-basiertes Rate Limiting via slowapi. Zusätzlich account-basiert:

```sql
ALTER TABLE users ADD COLUMN failed_login_attempts INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN locked_until TIMESTAMPTZ;
```

Logik: Nach 10 Fehlversuchen → 15min Sperre. Sperre zurücksetzen bei erfolgreichem Login.
Vorteil: schützt auch gegen verteilte Angriffe von verschiedenen IPs auf ein Konto.

### 3.4 Audit-Logging

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

### 3.5 Garmin Token Encryption at Rest

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
- [ ] Session-Fixation-Fix (`request.session.clear()` vor Login)
- [ ] Account-Enumeration-Schutz (Dummy-bcrypt)
- [ ] CDN-URLs entfernt, alle Assets unter `/static/vendor/`
- [ ] Docker Images auf Semver+Digest gepinnt
- [ ] `renovate.json` erstellt, GitHub App aktiviert

### Pre-Release: Legal
- [ ] Datenschutzerklärung live unter `/privacy`
- [ ] Nutzungsbedingungen live unter `/terms`
- [ ] Impressum live (Footer oder `/imprint`)
- [ ] Einwilligungs-Checkbox bei Registrierung (DSGVO Art. 9)
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
- [ ] Password-Reset-Flow live
- [ ] E-Mail-Verifikation bei Registrierung
- [ ] Account-Löschung (`DELETE /account`) live
- [ ] Daten-Export (`GET /account/export`) live
- [ ] Fernet-Verschlüsselung für Token-Volume aktiv
- [ ] Account-Lockout nach Fehlversuchen

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
