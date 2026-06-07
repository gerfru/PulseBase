<div align="center">

# 🫀 PulseBase

**Your fitness data. Your server. Your rules.**

A privacy-first, self-hosted dashboard that turns your Garmin &amp; Libre data
into ML-grade health insights — running entirely on your own machine.

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![TimescaleDB](https://img.shields.io/badge/TimescaleDB-PostgreSQL%2016-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-ML-F7931E?style=flat-square&logo=scikitlearn&logoColor=white)
![Self-hosted](https://img.shields.io/badge/Self--hosted-Privacy--first-10B981?style=flat-square)

[Quickstart](#-quickstart) · [Features](#-whats-inside) · [Docs](#-documentation) · [Security](#-security-at-a-glance)

</div>

<!--
📸 Drop a hero screenshot here once you have one — this is the single biggest
   visual upgrade. Recommended right below the header, e.g.:
<p align="center">
  <img src="docs/screenshot-dashboard.png" width="820" alt="PulseBase dashboard">
</p>
-->

---

> *Your Garmin data lives in someone else's cloud.*
> *Your sleep, your heart rate, your recovery — measured by a watch on **your** wrist,
> then rented back to you behind a login you don't control.*

**PulseBase takes it back.**

One `make up`, and every heartbeat syncs to a dashboard on **your** server — with the kind
of ML insights Garmin never surfaces, optional continuous glucose alongside it, and passwords
that are **never stored**. No cloud. No subscription. No data broker in the middle.

> 🔒 **Self-hosted by design.** PulseBase runs entirely on hardware you control. Your health
> data never leaves your server, and Garmin/LibreLinkUp passwords are wiped from memory the
> moment a token is obtained.

---

## ✨ Why PulseBase

- 🔒 **Privacy by architecture, not by promise** — runs entirely on your machine. Garmin and
  LibreLinkUp passwords are wiped from memory the moment a token is obtained; only a
  Fernet-encrypted token is ever persisted.
- 🧠 **Insights, not just charts** — anomaly detection, sleep→HRV correlation, a Random Forest
  readiness model, body-battery clustering and more turn raw samples into "what does this *mean*?"
- 🩺 **Honest about its own limits** — every metric ships an EN 62366-inspired disclosure:
  intended use, limitations, time horizon, evidence level. No black-box scores.
- 🧬 **More than Garmin shows you** — energy triptych (physical / autonomic / cognitive),
  ACWR, training monotony, running economy, SpO₂ trends, and an optional epilepsy seizure diary
  with a rule-based risk indicator.
- 🐳 **One command to run it** — Docker Compose, self-service registration, multi-user. No admin.

---

## 📦 What's inside

### Data sync

- Automatic Garmin Connect sync (activities, sleep, HRV, body battery, stress)
- Optional continuous glucose via LibreLinkUp (Libre 3, every 5 min)

### The dashboard

- Slate/Emerald instrument-panel UI — tabbed (Training / Verlauf / Erholung), dark + light mode
- Unified *Tagesstatus* hero: Oura-style readiness arc with HRV/sleep/pulse contributors,
  energy triptych (Physisch / Autonom / Kognitiv), vitals strip
- Time navigation (← →) across all charts — browse any historical period
- Activity detail pages with GPS map (Leaflet), HR/pace/elevation/cadence charts

### The intelligence

- ML insights with dedicated detail pages: anomaly detection (resting HR + SpO₂ + stress
  Z-score), sleep→HRV Pearson correlation, Random Forest readiness, body-battery K-Means
  patterns, ACWR, training monotony, running economy, sleep consistency, SpO₂ trend, and more
- 👍 / 👎 item-level feedback on every ML insight
- Metrics overview (`/metrics`) — all 21 metrics as tiles with colour-coded evidence badges
  (Meta-Analysis / Replicated / Model), each linked to a searchable `/help` methodology page

### Built for real use

- Central settings page (Garmin + LibreLinkUp in one place), self-service registration
- DSGVO/GDPR data export + account deletion, accessibility statement (BFSG)
- Optional epilepsy seizure diary with rule-based risk indicator (6 biomarker heuristics)

---

## 🚀 Quickstart

> 💡 **No reverse proxy yet?** Use `make up-standalone` — it ships a bundled Traefik with automatic
> HTTPS, so you can go from clone to dashboard without any extra infrastructure.

```bash
cp env/.env.example env/.env              # HOST_IP, ACME_EMAIL (standalone only)
cp env/.env.app.example env/.env.app      # DB roles + FERNET_KEY  → make gen-secrets
cp env/.env.api.example env/.env.api      # SESSION_SECRET (≥32 chars) + APP_BASE_URL
cp env/.env.sync.example env/.env.sync
cp env/.env.ml.example env/.env.ml

make up                 # build + start everything (needs a reverse proxy on the proxy network)
# → https://your-domain.com/register
# → https://your-domain.com/garmin/link
make trigger-sync       # pull your Garmin data now (no rebuild — runs within a minute)
# → https://your-domain.com/dashboard
```

**Running a homelab?** Start [homelab-gateway](https://github.com/gerfru/homelab-gateway) first,
then `make up`.

→ Full walkthrough: **[docs/setup.md](docs/setup.md)**

---

## 📚 Documentation

Pick your depth:

| | |
|---|---|
| 🧒 **[ELI5](docs/eli5.md)** | The whole system explained like you're five |
| 🚀 **[Setup Guide](docs/setup.md)** | Complete installation walkthrough |
| ⚙️ **[Configuration](docs/configuration.md)** | Every env var, per service |
| 🛠️ **[Developer Guide](docs/development.md)** | Local dev, tests, CI/CD — and the full `make` command reference |
| 🏛️ **[Architecture](docs/architecture.md)** | Services, data paths, network setup |
| 🗄️ **[Database](docs/database.md)** | Schema, hypertables, real column names |
| 🔌 **[API Reference](docs/api.md)** | Every endpoint with request/response format |
| 🤖 **[ML Deep Dive](docs/ml-deep-dive.md)** | Algorithms, formulas, thresholds, training pipeline |
| ⚡ **[Energy Metrics](docs/energy-metrics.md)** | The physical / autonomic / cognitive scores in detail |
| 🔐 **[Security](docs/security.md)** | Threat model, auth layers, crypto, headers |
| 🏗️ **[Production Hardening](docs/production-hardening.md)** | Going live: secrets, backups, monitoring |
| 🌐 **[External Services](docs/external-services.md)** | Let's Encrypt, Sentry, Uptime Kuma setup |
| 🧭 **[Design Decisions](docs/design-decisions.md)** | Why no Grafana, no ORM, no JWT, Caddy vs Traefik |
| 📋 **[ADRs](docs/adr/)** | Architecture Decision Records |

---

## 🔐 Security at a glance

Self-hosting your health data only helps if the app itself is hard to break into. PulseBase
ships with rate-limited auth + account lockout, email verification, CSRF protection, bcrypt
password hashing, signed httpOnly session cookies, Fernet-encrypted Garmin/Libre tokens,
least-privilege per-service DB roles, a strict nonce-based CSP, and SAST/SCA/container scanning
in CI (bandit · semgrep · pip-audit · Trivy).

→ Full threat model and controls: **[docs/security.md](docs/security.md)**

---

## 🧱 Stack

FastAPI · TimescaleDB (PostgreSQL 16) · Docker Compose · Chart.js · scikit-learn · Tailwind CSS

Three services — `api` (dashboard), `sync-service` (Garmin/Libre ingest), `ml-service`
(analytics) — behind a reverse proxy. No Grafana, no ORM, no JWT, no framework on the frontend.
See **[Design Decisions](docs/design-decisions.md)** for the why.

---

<div align="center">
<sub>Built for people who'd rather own their health data than rent it back.</sub>
</div>
