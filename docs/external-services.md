# External Services Setup

PulseBase nutzt drei externe Dienste die einmalig konfiguriert werden müssen.
Zwei davon (Sentry, UptimeRobot) sind kostenlos im Standardumfang.

---

## 1. Let's Encrypt / ACME — TLS-Zertifikate (Public SaaS)

**Was:** Automatische, kostenlose TLS-Zertifikate via Let's Encrypt. Relevant für den
**Public-SaaS-Modus** (`make up-public`) mit gebündeltem **Caddy**. Im Heim-Betrieb
(`make up`) übernimmt das Caddy des homelab-gateway die TLS-Terminierung.

**Voraussetzungen:**
- Domain zeigt per A-Record auf die öffentliche IP des Servers (vor dem ersten Start!)
- Port 80 und 443 sind auf dem Server erreichbar (Firewall / Portweiterleitung)

**Setup (Kurzform — vollständiger Runbook: [deployment-public.md](deployment-public.md)):**

1. `env/.env.public` anlegen und `PUBLIC_DOMAIN` + `ACME_EMAIL` setzen:
   ```bash
   cp env/.env.public.example env/.env.public
   # PUBLIC_DOMAIN=app.example.com
   # ACME_EMAIL=deine@email.com
   ```
   Caddy holt das Zertifikat beim ersten Request automatisch (HTTP-01) und erneuert es
   selbstständig. Die Zertifikate liegen im persistenten Volume `caddy-data` (niemals
   mit `down -v` löschen → Let's-Encrypt-Rate-Limit).

2. Starten:
   ```bash
   make up-public
   ```
   Tipp: zuerst mit der ACME-Staging-CA testen (Zeile in `deploy/Caddyfile` einkommentieren),
   um das Prod-Rate-Limit (5 gleiche Zertifikate/Woche) nicht zu treffen.

**Troubleshooting:**
```bash
make logs-public     # Caddy-Logs — zeigt ACME-Fehler sofort
```
Häufige Fehler: Domain zeigt noch auf falsche IP, Port 80/443 nicht erreichbar.

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

## 3. Uptime-Monitoring

PulseBase bündelt **kein** eigenes Uptime-Monitoring. Je nach Modus:

**Heim (`make up`):** Uptime Kuma läuft **zentral im homelab-gateway** (eigenes Repo),
erreichbar über `status.home.lab` bzw. die Tailscale-IP. Dort einen Monitor anlegen:
- Monitor Type: `HTTP(s)`
- URL: `http://pulsebase-api:8000/health` (interner Docker-Hostname im `proxy`-Netz)
- Heartbeat Interval: `60` s
- Optional zweiter Monitor auf `http://pulsebase-api:8000/ready` (erkennt DB/Migrations-Probleme)

**Public SaaS (`make up-public`):** externes **UptimeRobot** (kostenlos) gegen die
öffentlichen Endpunkte:
- `https://<domain>/health` (primärer Uptime-Monitor)
- `https://<domain>/ready` (App + DB + Migrations)
- Notification → E-Mail/Telegram

**Was `/health` vs. `/ready` unterscheidet:**
- `/health` → App läuft (kein DB-Call) — primärer Uptime-Monitor
- `/ready` → App + DB + Migrations OK — für Deployment-Verification

---

## Checkliste vor Public Release

- [ ] `env/.env.public` angelegt: `PUBLIC_DOMAIN` + `ACME_EMAIL` gesetzt
- [ ] DNS-A-Record auf VPS-IP, Ports 80/443 offen (vor dem ersten Start)
- [ ] `env/.env.api`: `HTTPS_ONLY=true`, `APP_BASE_URL`, `TRUSTED_PROXY_CIDRS`
- [ ] `SENTRY_DSN` in `env/.env.app` eingetragen + Alert-Rules konfiguriert (OBS-L3)
- [ ] `BETTERSTACK_SOURCE_TOKEN` (Logs) gesetzt, UptimeRobot-Monitore auf `/health` + `/ready`
- [ ] `make up-public` gestartet, `https://<domain>` mit gültigem Let's-Encrypt-Cert geprüft
- [ ] Backup-Cron + `make restore-test` eingerichtet

Vollständiger Runbook: [deployment-public.md](deployment-public.md).
