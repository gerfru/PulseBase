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

Backups laufen als **Container im Stack** (Service `backup`, [`backup/`](../backup/)) — kein
Host-Cron, kein Docker-Socket: der Container verbindet sich übers interne Netz mit `db` und
führt täglich [`scripts: backup.sh`](../backup/backup.sh) aus (`pg_dump -Fc` → **age**-Verschlüsselung
→ Retention → optional rclone-Offsite). Single Source — diese Doku dupliziert das Skript nicht.

**Einrichtung:**

1. age-Keypair auf einer **vertrauenswürdigen Offsite-Maschine** erzeugen (nicht auf dem VPS):
   `age-keygen -o pulsebase-backup.key`.
2. `env/.env.backup` anlegen (`cp env/.env.backup.example env/.env.backup`), `AGE_RECIPIENT`
   auf den `age1…`-Public-Key setzen, optional `RCLONE_REMOTE`/`BACKUP_HOUR`. `make secure-env`.
3. Den **privaten** Key (`pulsebase-backup.key`) offsite/im Passwortmanager verwahren — nur
   fürs Restore. Verschlüsselte Backups landen im Named Volume `backups`.

- `-Fc` = komprimiert, selektiv restorefähig; erfasst alle TimescaleDB-Hypertables.
- **age** (X25519/ChaCha20-Poly1305): nur der Public-Key liegt am Server → ein kompromittierter
  Server kann eigene Backups **nicht entschlüsseln**. Privater Key bleibt offsite.
- **Backups testen** (Regel „test backups"): monatlich `make restore-test` (liest den privaten
  Key-Pfad aus `AGE_IDENTITY` in `env/.env.backup`) — entschlüsselt den neuesten Backup und
  restored ihn **TimescaleDB-korrekt** (`timescaledb_pre_restore()` → `pg_restore` ohne `-j`
  → `timescaledb_post_restore()`) in eine Wegwerf-DB und prüft die User-Zahl.
- **Offsite (3-2-1):** `RCLONE_REMOTE` in `env/.env.backup` setzen; das rclone-Remote muss im
  Image konfiguriert sein. Bucket-Keys restriktiv.

## Monitoring (externe SaaS-Dienste)

- **Sentry** (Errors): `SENTRY_DSN` real setzen (api in `.env.api`, sync+ml in `.env.app`).
  Issues sind automatisch mit `release=<pyproject-Version>` getaggt (z.B. `1.0.0`) →
  Regressionen lassen sich einer Version zuordnen. Alert-Rules siehe Runbook unten.
- **Logs**: Vector-Sidecar shippt die stdout-JSON-Logs an Better Stack
  (`BETTERSTACK_SOURCE_TOKEN` in `env/.env.public`). Alternativ Axiom — Sink in
  `vector.public.toml` tauschen.
- **Uptime**: UptimeRobot-Monitore auf `https://app.example.com/health` **und** `/ready`
  (erkennt DB-down). Alert → E-Mail/Telegram.

### Sentry-Alert-Runbook (OBS-L3 — Pflicht vor Public-Launch)

Im Sentry-Projekt unter **Alerts → Create Alert Rule** drei Regeln anlegen (die drei
goldenen Signale, die Sentry abdecken kann):

| # | Typ | Bedingung | Zeitfenster | Aktion |
|---|---|---|---|---|
| 1 | Metric Alert (Error Rate) | `failure_rate()` der Transaktionen **> 1%** | 10 min | E-Mail/Slack |
| 2 | Metric Alert (Latenz) | `p95(transaction.duration)` **> 2000 ms** | 10 min | E-Mail |
| 3 | Issue Alert (neuer Fehler) | „A new issue is created" | sofort | E-Mail |

Schritt-für-Schritt für Regel 1/2: Alerts → Create Alert → **Metric Alert** → Dataset
*Transactions* → Function `failure_rate()` bzw. `p95(transaction.duration)` →
Threshold wie oben → Environment `production` → Owner/Notification setzen.
Regel 3: **Issue Alert** → „When a new issue is created" → Notify.

**Ehrliche Grenze:** Die vierte Schwelle aus den Regeln (CPU/Mem **> 80%**, Saturation)
hat **keinen automatischen Sentry-Pfad** — Sentry kennt keine Host-Metriken. Die Werte
sind via `GET /api/metrics` (psutil: `memory_mb`, `cpu_percent`) abrufbar, aber ein
Auto-Alert darauf braucht Prometheus/Grafana oder einen Better-Stack-Log-Monitor (deckt
sich mit OBS-L3 in CLAUDE.md). Als pragmatische Brücke: UptimeRobot-Keyword-Monitor auf
`/api/metrics` oder ein Better-Stack-Alert auf eine geloggte Sättigungswarnung.

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
