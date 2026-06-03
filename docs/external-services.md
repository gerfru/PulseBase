# External Services Setup

PulseBase nutzt drei externe Dienste die einmalig konfiguriert werden müssen.
Zwei davon (Sentry, UptimeRobot) sind kostenlos im Standardumfang.

---

## 1. Let's Encrypt / ACME — TLS-Zertifikate

**Was:** Automatische, kostenlose TLS-Zertifikate via Let's Encrypt. Nur relevant
für den **standalone-Modus** (`make up-standalone`) mit Traefik. Beim Betrieb mit
homelab-gateway übernimmt Caddy die TLS-Terminierung.

**Voraussetzungen:**
- Domain zeigt per A-Record auf die öffentliche IP des Servers
- Port 80 und 443 sind auf dem Server erreichbar (Router-Portweiterleitung)

**Setup:**

1. `ACME_EMAIL` in `env/.env` eintragen:
   ```
   ACME_EMAIL=deine@email.com
   ```
   Let's Encrypt schickt Ablauf-Benachrichtigungen an diese Adresse (90 Tage TTL,
   automatische Erneuerung durch Traefik ab 30 Tage vor Ablauf).

2. Berechtigungen der `acme.json`-Datei sicherstellen (einmalig nach `git clone`):
   ```bash
   chmod 600 traefik/acme/acme.json
   ```
   Traefik verweigert den Start wenn die Datei zu offen ist.

3. Standalone-Stack starten:
   ```bash
   make up-standalone
   ```
   Beim ersten Start holt Traefik das Zertifikat automatisch (HTTP-01 Challenge
   auf Port 80). Danach ist `https://your-domain.com` mit gültigem Zertifikat
   erreichbar.

**Troubleshooting:**
```bash
make logs-standalone     # Traefik-Logs — zeigt ACME-Fehler sofort
```
Häufige Fehler: Domain zeigt noch auf falsche IP, Port 80 nicht erreichbar,
`acme.json` hat falsche Permissions (braucht exakt `600`).

---

## 2. Sentry — Error Tracking

**Was:** Sentry fängt unbehandelte Exceptions und `logger.error()`-Aufrufe ab,
benachrichtigt sofort per E-Mail und zeigt Stack Trace, User-Context und
Request-Details. Ohne Sentry merkst du Fehler erst wenn User sich melden.

**Kosten:** Kostenlos bis 5.000 Errors/Monat (Sentry Free Plan).

**Setup:**

1. Account erstellen: [sentry.io](https://sentry.io) → New Project → Python → FastAPI

2. DSN kopieren (Format: `https://xxx@oNNNNNN.ingest.sentry.io/NNNNNNN`)

3. In `env/.env.api` eintragen:
   ```
   SENTRY_DSN=https://xxx@oNNNNNN.ingest.sentry.io/NNNNNNN
   ```
   Der API-Service initialisiert Sentry automatisch beim Start wenn `SENTRY_DSN`
   gesetzt ist. Sync-Service und ML-Service haben eigene Sentry-Initialisierung
   (gleiche DSN, unterschiedliche `server_name`).

4. Alert Rules im Sentry-Dashboard konfigurieren:
   - **Issues → Alerts → Create Alert Rule**

   | Alert | Bedingung | Empfehlung |
   |---|---|---|
   | Neuer Issue | First seen | Sofort per E-Mail |
   | Error Rate | >5 Events / 10 min | E-Mail |
   | Regression | Issue taucht nach Fix wieder auf | E-Mail |

5. Testen:
   ```bash
   make logs-dashboard   # Zeigt "sentry.initialized" beim API-Start
   ```

**Hinweis:** `send_default_pii=False` ist gesetzt — keine personenbezogenen Daten
(E-Mail, IP, Session) werden an Sentry gesendet.

---

## 3. Uptime Kuma — Uptime-Monitoring (self-hosted)

**Was:** Uptime Kuma überwacht deine App-Endpunkte intern im Docker-Netz und
benachrichtigt bei Ausfall. Im Gegensatz zu UptimeRobot braucht es keinen
Internetzugriff auf den Server — ideal für Homelab und self-hosted Setups.

**Kosten:** Kostenlos, self-hosted.

**Setup:**

Uptime Kuma läuft bereits als Compose-Service (`make up` startet es automatisch).

1. Dashboard öffnen: [http://localhost:3001](http://localhost:3001)
   (oder via SSH-Tunnel von einem anderen Gerät)

2. Beim ersten Start Admin-Account anlegen (nur einmalig).

3. **Add New Monitor:**
   - Monitor Type: `HTTP(s)`
   - Friendly Name: `PulseBase API`
   - URL: `http://api:8000/health`
     *(interner Docker-Hostname — kein Internetzugriff nötig)*
   - Heartbeat Interval: `60` Sekunden

4. Optional — zweiter Monitor für DB-Readiness:
   - Friendly Name: `PulseBase Ready`
   - URL: `http://api:8000/ready`
   - Erkennt auch DB-Verbindungsprobleme und fehlgeschlagene Migrations

5. Notification konfigurieren:
   - Settings → Notifications → Add Notification
   - Unterstützt E-Mail, Telegram, Discord, Slack, ntfy und viele mehr
   - Den Notification-Channel beim Monitor unter "Notifications" zuweisen

**Was `/health` vs. `/ready` unterscheidet:**
- `/health` → App läuft (kein DB-Call) — primärer Uptime-Monitor
- `/ready` → App + DB + Migrations OK — für Deployment-Verification

---

## Checkliste vor Public Release

- [ ] `HOST_IP` in `env/.env` auf echte Domain gesetzt
- [ ] `ACME_EMAIL` in `env/.env` eingetragen
- [ ] `chmod 600 traefik/acme/acme.json` ausgeführt (einmalig nach `git clone`)
- [ ] `SENTRY_DSN` in `env/.env.api` eingetragen
- [ ] `make up` gestartet, Uptime Kuma unter `http://localhost:3001` konfiguriert
- [ ] `make up-standalone` gestartet, `https://your-domain.com` im Browser geprüft
