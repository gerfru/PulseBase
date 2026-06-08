# Public-SaaS-Deployment

Anleitung für eine **öffentliche Instanz** von PulseBase (Nutzer registrieren sich
über eine öffentliche Domain). Gehostet als Single-VPS-SaaS mit gebündeltem
**Caddy** (automatisches Let's-Encrypt-TLS) und externem Monitoring.

> Heim-Betrieb (homelab-gateway, nur im Tailnet erreichbar) ist hiervon getrennt
> und unverändert: dort `make up`. Diese Anleitung gilt **nur** für `make up-public`.

## Architektur

```
Internet ──▶ Caddy (:80/:443, Let's Encrypt) ──▶ api:8000 (internal-Netz)
                                                   ├─ db (TimescaleDB, nur 127.0.0.1)
                                                   ├─ sync-service
                                                   └─ ml-service
             Vector ──▶ Better Stack/Axiom (Logs)
             Sentry (Errors)   UptimeRobot (Uptime)
```

Das Overlay `docker-compose.public.yml` entkoppelt `api` vom externen `proxy`-Netz
des homelab-gateway (per `networks: !override`) und ergänzt **Caddy** + **Vector**.

Beteiligte Dateien: `docker-compose.public.yml`, `Caddyfile.public`,
`vector.public.toml`, `env/.env.public`.

## Voraussetzungen (in dieser Reihenfolge!)

1. **DNS:** A-Record (und ggf. AAAA) `app.example.com` → öffentliche VPS-IP.
   Prüfen: `dig +short app.example.com`. **Muss vor dem ersten Start stehen** —
   ACME HTTP-01 schlägt sonst fehl.
2. **Firewall:** eingehend TCP **80 + 443** (und UDP 443 für HTTP/3) auf `0.0.0.0`.
   DB-Port 5433 bleibt loopback-only (Basis-Compose) — nicht öffnen.
3. **Docker + Compose v2** auf dem VPS.

## Einrichtung

```bash
# 1) Env-Dateien
cp env/.env.public.example env/.env.public      # PUBLIC_DOMAIN, ACME_EMAIL, Log-Token
make gen-secrets                                # SESSION_SECRET / FERNET_KEY / DB-Passwörter
#   → SESSION_SECRET in env/.env.api, FERNET_KEY + DB_* in env/.env.app eintragen

# 2) env/.env.api für die öffentliche Instanz
#   HTTPS_ONLY=true
#   APP_BASE_URL=https://app.example.com
#   TRUSTED_PROXY_CIDRS=["172.30.0.0/16","127.0.0.1/32"]   # internal-Subnetz (gepinnt im Overlay)
#   RESEND_API_KEY=...  RESEND_FROM_EMAIL=noreply@app.example.com   (echte Reset-Mails)
#   SENTRY_DSN=...

make secure-env                                 # chmod 600 inkl. env/.env.public

# 3) Merge prüfen (api ohne proxy-Netz, caddy publisht 80/443)
make config-public

# 4) (Empfohlen) Erst mit ACME-Staging testen: in Caddyfile.public die acme_ca-Zeile
#    einkommentieren → make up-public → Zertifikat ok? → Zeile wieder auskommentieren.

# 5) Start
make up-public
```

### TRUSTED_PROXY_CIDRS bestimmen

Das `internal`-Netz ist im Overlay fest auf `172.30.0.0/16` gepinnt — Caddy sitzt
dort. Setze deshalb `TRUSTED_PROXY_CIDRS=["172.30.0.0/16","127.0.0.1/32"]`. Bei
falschem CIDR greift Rate-Limiting auf der Caddy-IP statt der echten Client-IP.

## Backups (Health-PII, Pflicht)

Täglicher Host-Cron auf dem VPS (`crontab -e`):

```bash
30 3 * * * docker exec pulsebase-db pg_dump -U garmin -Fc garmin \
  > /srv/backups/garmin-$(date +\%F).dump 2>>/srv/backups/backup.log && \
  find /srv/backups -name 'garmin-*.dump' -mtime +14 -delete && \
  rclone copy /srv/backups remote:pulsebase-backups --max-age 24h
```

- `-Fc` = komprimiert, parallel-restorefähig. Offsite-Bucket **verschlüsselt**, Keys restriktiv.
- **Backups testen** (Regel „test backups"): monatlich `make restore-test` —
  restored den neuesten Dump in eine Wegwerf-DB und prüft die User-Zahl.

## Monitoring (externe SaaS-Dienste)

- **Sentry** (Errors): `SENTRY_DSN` real setzen (api in `.env.api`, sync+ml in `.env.app`).
  Alert-Rules: neuer Issue sofort; Error-Rate >1% / 10min; p95 >2s (Pflicht vor Launch, OBS-L3).
- **Logs**: Vector-Sidecar shippt die stdout-JSON-Logs an Better Stack
  (`BETTERSTACK_SOURCE_TOKEN` in `env/.env.public`). Alternativ Axiom — Sink in
  `vector.public.toml` tauschen.
- **Uptime**: UptimeRobot-Monitore auf `https://app.example.com/health` **und** `/ready`
  (erkennt DB-down). Alert → E-Mail/Telegram.

## Verifikation (Go-Live-Check)

```bash
curl -sI https://app.example.com/health            # HTTP/2 200
echo | openssl s_client -connect app.example.com:443 -servername app.example.com 2>/dev/null \
  | openssl x509 -noout -issuer                     # issuer = Let's Encrypt
curl -sI http://app.example.com/                    # 308 → https
curl -sI https://app.example.com/ | grep -ci strict-transport-security   # 1 (nur App, Caddy doppelt nicht)
```

- Register-Flow live testen → Reset-Mail kommt an (Resend + APP_BASE_URL ok).
- Rate-Limiting von zwei externen IPs → getrennte Buckets (TRUSTED_PROXY_CIDRS ok).
- Logs erscheinen in Better Stack/Axiom (<1 min); UptimeRobot `/health`+`/ready` grün.
- `make restore-test` grün.

## Scharfe Kanten

- **ACME braucht DNS + Ports 80/443 zuerst.** Let's-Encrypt-Prod-Limit: 5 gleiche
  Zertifikate/Woche → erst mit Staging testen.
- **`caddy-data`-Volume muss persistieren** (Zertifikate + ACME-Account). **Niemals**
  `docker compose down -v` / `make clean` auf der Public-Instanz.
- **Auf dem VPS nur `make up-public`**, nie `make up` (verlangt das nicht existierende
  `proxy`-Netz und würde api doppelt anhängen).
- **Single VPS = Single Point of Failure.** RTO = Restore-aus-Backup-Zeit.

## CI

Der CI-Job **`deploy-public-smoke`** validiert dieses Setup bei jedem PR: er rendert
die gemergte Public-Config (api ohne `proxy`-Netz), fährt Caddy HTTP-only über
`docker-compose.public.ci.yml` hoch und prüft das Routing `Caddy → api` via
`http://localhost:8080/health`. Echtes ACME/TLS wird bewusst nur hier manuell getestet.
