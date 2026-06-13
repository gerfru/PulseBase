.PHONY: network up up-public down-public logs-public config-public restore-test backup down clean reset dashboard analytics sync trigger-sync logs-dashboard logs-analytics logs-sync logs-all status migrate db gen-secrets setup add-host setup-user backfill-energy backfill-records tailwind-build test test-env-up test-env-down test-seed test-user test-e2e test-e2e-seeded test-all test-all-seeded test-coverage test-js test-js-coverage secure-env

DC := docker compose --env-file env/.env --env-file env/.env.app
# Public SaaS deployment (bundled Caddy + Let's Encrypt). The overlay decouples
# api from the home gateway's external `proxy` network. See docs/deployment-public.md.
DC_PUBLIC := docker compose --env-file env/.env --env-file env/.env.app -f docker-compose.yml -f deploy/docker-compose.public.yml

# E2E Test-Credentials (lokal, kein echter Account)
TEST_EMAIL  ?= e2e@pulsebase.test
TEST_PASSWORD ?= E2eLocalTest1!  # pragma: allowlist secret

network:
	docker network inspect proxy >/dev/null 2>&1 || docker network create proxy

up: network
	$(DC) up -d --build

# ── Public SaaS instance (bundled Caddy + Let's Encrypt on PUBLIC_DOMAIN) ──────
up-public: ## Öffentliche Instanz starten (eigenes Caddy + Let's Encrypt)
	@test -f env/.env.public || { echo "FEHLER: env/.env.public fehlt — cp env/.env.public.example env/.env.public und ausfüllen"; exit 1; }
	$(DC_PUBLIC) up -d --build

down-public:
	$(DC_PUBLIC) down

logs-public:
	$(DC_PUBLIC) logs -f caddy

config-public: ## Gemergte Public-Config rendern (Sanity-Check: api ohne proxy-Netz)
	$(DC_PUBLIC) config

down:
	$(DC) down

clean:
	$(DC) down -v --remove-orphans

reset:
	$(DC) down --remove-orphans
	docker volume rm garmin-dev_timescale-data garmin-dev_garmin-tokens 2>/dev/null || true
	@echo "=== Volumes geloescht — Datenbank wird neu aufgesetzt ==="
	$(DC) up flyway
	$(DC) up -d --build

dashboard: network
	$(DC) build api && $(DC) up -d api

analytics: network
	$(DC) build ml-service && $(DC) up -d ml-service

sync: network
	$(DC) build sync-service && $(DC) up -d --force-recreate sync-service

trigger-sync: ## Garmin-Sync für alle aktiven User anfordern (sync-service verarbeitet binnen 1 Minute)
	$(DC) exec -T db psql -U garmin_app -d garmin \
	  -c "UPDATE users SET sync_requested = true WHERE garmin_linked = true AND is_active = true;"
	@echo "Sync angefordert — läuft binnen 1 Minute. Fortschritt: make logs-sync"

logs-dashboard:
	$(DC) logs -f api

logs-analytics:
	$(DC) logs -f ml-service

logs-sync:
	$(DC) logs -f sync-service

logs-all:
	$(DC) logs -f

migrate: network
	$(DC) up flyway

backfill-energy:
	$(DC) exec ml-service python /app/src/backfill_energy.py

backfill-records: ## Fetch GPS/HR records from Garmin for all activities without records
	$(DC) exec sync-service python /app/src/backfill_records.py

backfill-battery: ## Force-recompute body_battery_custom with new model (deletes old predictions first)
	$(DC) exec db psql -U garmin_app garmin \
	  -c "DELETE FROM ml_predictions WHERE model = 'body_battery_custom';"
	$(DC) exec ml-service python /app/src/backfill_energy.py

status:
	$(DC) ps

db: network
	if [ -n "$(SQL)" ]; then \
		$(DC) exec -T db psql -U garmin_app -d garmin -c "$(SQL)"; \
	elif [ -t 0 ]; then \
		$(DC) exec db psql -U garmin_app -d garmin; \
	else \
		$(DC) exec -T db psql -U garmin_app -d garmin; \
	fi

gen-secrets:
	@echo "In env/.env.api eintragen:"
	@echo "SESSION_SECRET=$$(openssl rand -hex 32)"
	@echo ""
	@echo "In env/.env.app eintragen (shared — wird von api + sync gelesen):"
	@echo "FERNET_KEY=$$(python3 -c 'import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
	@echo ""
	@echo "Per-Service-DB-Rollen (V24) — ebenfalls in env/.env.app:"
	@echo "DB_APP_PASSWORD=$$(openssl rand -hex 24)"
	@echo "DB_SYNC_PASSWORD=$$(openssl rand -hex 24)"
	@echo "DB_ML_PASSWORD=$$(openssl rand -hex 24)"
	@echo ""
	@echo "Backup-Verschlüsselung — age-Keypair auf einer VERTRAUENSWÜRDIGEN"
	@echo "Offsite-Maschine erzeugen (NICHT auf dem Server):"
	@echo "  age-keygen -o pulsebase-backup.key"
	@echo "  → 'Public key: age1…' als AGE_RECIPIENT in env/.env.backup"
	@echo "  → Datei pulsebase-backup.key NUR offsite/Passwortmanager (für Restore)"

secure-env:
	chmod 600 env/.env env/.env.app env/.env.api env/.env.sync env/.env.ml
	@test -f env/.env.public && chmod 600 env/.env.public || true
	@test -f env/.env.backup && chmod 600 env/.env.backup || true

# ── Backup sofort ausführen (One-Off; sonst täglich via Backup-Container-Loop) ─
backup:
	$(DC) run --rm backup /scripts/backup.sh

# ── Backup-Restore-Test (Regel "test backups") ───────────────────────────────
# Entschlüsselt den neuesten Backup (age) + restored ihn TimescaleDB-korrekt
# (pre/post_restore, kein -j) in eine Wegwerf-DB und prüft die User-Zahl.
# Key-Pfad kommt aus env/.env.backup (AGE_IDENTITY=); überschreibbar via Variable.
restore-test:
	@key="$${AGE_IDENTITY:-$$(sed -n 's/^AGE_IDENTITY=//p' env/.env.backup 2>/dev/null)}"; \
	test -n "$$key" || { echo "FEHLER: AGE_IDENTITY in env/.env.backup setzen (Pfad zum privaten age-Key)"; exit 1; }; \
	$(DC) run --rm -v "$$key:/age.key:ro" -e AGE_IDENTITY=/age.key backup /scripts/restore.sh latest restore_check; \
	echo "→ Restore-Test OK"

setup:
	@echo "=== Erstmalige Einrichtung ==="
	@echo ""
	@echo "Schritt 1 — Session Secret generieren:"
	@echo "  make gen-secrets"
	@echo "  → Wert in env/.env.api eintragen"
	@echo ""
	@echo "Schritt 2 — Domain konfigurieren:"
	@echo "  env/.env:     HOST_IP=<deine-domain>"
	@echo "  env/.env.api: APP_BASE_URL=https://<deine-domain>"
	@echo "  Standalone/lokal: HOST_IP=pulsebase.local + Hosts-Eintrag via make add-host"
	@echo ""
	@echo "Schritt 3 — Datenbank migrieren:"
	@echo "  make migrate"
	@echo ""
	@echo "Schritt 4 — Starten:"
	@echo "  make up         (Heim: hinter homelab-gateway / Caddy-Tailscale)"
	@echo "  make up-public  (öffentliche Instanz: eigenes Caddy + Let's Encrypt — siehe docs/deployment-public.md)"
	@echo ""
	@echo "Schritt 5 — Registrieren und Garmin verknüpfen:"
	@echo "  https://<deine-domain>/register"
	@echo "  https://<deine-domain>/garmin/link"

add-host:
	@grep -q "pulsebase.local" /etc/hosts && echo "pulsebase.local ist bereits eingetragen." || (echo "127.0.0.1 pulsebase.local" | sudo tee -a /etc/hosts && echo "pulsebase.local hinzugefügt.")

setup-user:
	@echo "Neuen User anlegen:"
	@echo "  https://<deine-domain>/register"
	@echo "Garmin verknüpfen:"
	@echo "  https://<deine-domain>/garmin/link"

tailwind-build:
	@echo "=== Tailwind CLI Build ==="
	@OS=$$(uname -s | tr '[:upper:]' '[:lower:]' | sed 's/darwin/macos/'); \
	ARCH=$$(uname -m | sed 's/x86_64/x64/;s/aarch64/arm64/'); \
	curl -fsSL "https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.19/tailwindcss-$$OS-$$ARCH" \
	  -o /tmp/tailwindcss-cli && chmod +x /tmp/tailwindcss-cli && \
	cd api && /tmp/tailwindcss-cli -c tailwind.config.js \
	  -i src/static/input.css \
	  -o src/static/tailwind.min.css \
	  --minify
	@echo "Done: api/src/static/tailwind.min.css"

test: ## Unit + Integration aller 3 Services (kein Docker nötig)
	cd api && .venv/bin/pytest tests/ -v --ignore=tests/e2e
	cd sync-service && .venv/bin/pytest tests/ -v
	cd ml-service && .venv/bin/pytest tests/ -v

test-build: ## api-Test-Image bauen (ohne Stack zu starten)
	$(DC) -f deploy/docker-compose.test.yml build api-test

test-env-up: ## Test-Stack auf Port 8001 starten (Image muss bereits gebaut sein — make test-build)
	$(DC) -f deploy/docker-compose.test.yml up -d --wait --wait-timeout 120

test-env-down: ## Test-Stack stoppen
	docker compose -f deploy/docker-compose.test.yml down 2>/dev/null || true
	docker rm -f pulsebase-db-test pulsebase-flyway-test pulsebase-api-test 2>/dev/null || true

test-seed: ## Live-DB (garmin) → Test-DB (garmin_test) kopieren — Test-Stack muss laufen (make test-env-up)
	@docker ps --format '{{.Names}}' | grep -qx pulsebase-db-test || { \
	  echo "FEHLER: Test-DB 'pulsebase-db-test' läuft nicht — zuerst 'make test-build && make test-env-up' (oder nutze 'make test-e2e-seeded')"; exit 1; }
	docker exec pulsebase-db pg_dump \
	  -U $$(grep ^DB_USER env/.env | cut -d= -f2) garmin \
	  | docker exec -i pulsebase-db-test psql \
	  -U $$(grep ^DB_USER env/.env | cut -d= -f2) garmin_test

test-user: ## Test-User in garmin_test anlegen — reicht für E2E
	cd api && TEST_EMAIL=$(TEST_EMAIL) TEST_PASSWORD=$(TEST_PASSWORD) DB_PORT=5434 \
	  DB_USER=$$(grep ^DB_USER ../env/.env | cut -d= -f2) \
	  DB_PASSWORD=$$(grep ^DB_PASSWORD ../env/.env | cut -d= -f2) \
	  .venv/bin/python tests/e2e/create_ci_user.py

test-e2e: ## Playwright E2E — alles automatisch, Stack wird auch bei Fehler gestoppt
	$(MAKE) test-build
	$(MAKE) test-env-up
	$(MAKE) test-user && \
	  api/.venv/bin/playwright install chromium --with-deps && \
	  ( cd api && TEST_EMAIL=$(TEST_EMAIL) TEST_PASSWORD=$(TEST_PASSWORD) .venv/bin/pytest tests/e2e/ -v ); \
	  EXIT=$$?; $(MAKE) test-env-down; exit $$EXIT

test-e2e-seeded: ## Wie test-e2e, aber mit echten Garmin-Daten (Prod→Test) + CI_HAS_DATA=true (inkl. @requires_data)
	# Hinweis: @requires_data-Tests brauchen einen User MIT Daten — ggf.
	#   make test-e2e-seeded TEST_EMAIL=<dein-Konto> TEST_PASSWORD=<...>
	# Der Default-Test-User (e2e@pulsebase.test) hat keine Aktivitäten.
	$(MAKE) test-build
	$(MAKE) test-env-up
	$(MAKE) test-seed
	$(MAKE) test-user && \
	  api/.venv/bin/playwright install chromium --with-deps && \
	  ( cd api && CI_HAS_DATA=true TEST_EMAIL=$(TEST_EMAIL) TEST_PASSWORD=$(TEST_PASSWORD) .venv/bin/pytest tests/e2e/ -v ); \
	  EXIT=$$?; $(MAKE) test-env-down; exit $$EXIT

test-all: ## Voll-Lauf (ohne Seed): Unit + E2E + JS-Coverage + Coverage — ein Kommando
	$(MAKE) test
	$(MAKE) test-e2e
	$(MAKE) test-js-coverage
	$(MAKE) test-coverage

test-all-seeded: ## Voll-Lauf MIT Garmin-Daten: Unit + seeded-E2E + JS-Coverage + Coverage
	$(MAKE) test
	$(MAKE) test-e2e-seeded
	$(MAKE) test-js-coverage
	$(MAKE) test-coverage

test-coverage: ## Coverage-Report aller 3 Services (Terminal + HTML unter */htmlcov/index.html)
	@echo "── api ─────────────────────────────────────────────────────────"
	cd api && .venv/bin/pytest tests/ --ignore=tests/e2e \
	  --cov=src --cov-report=term-missing --cov-report=html:htmlcov
	@echo "── sync-service ─────────────────────────────────────────────────"
	cd sync-service && .venv/bin/pytest tests/ \
	  --cov=src --cov-report=term-missing --cov-report=html:htmlcov
	@echo "── ml-service ───────────────────────────────────────────────────"
	cd ml-service && .venv/bin/pytest tests/ \
	  --cov=src --cov-report=term-missing --cov-report=html:htmlcov
	@echo ""
	@echo "HTML-Reports:"
	@echo "  → open api/htmlcov/index.html"
	@echo "  → open sync-service/htmlcov/index.html"
	@echo "  → open ml-service/htmlcov/index.html"

test-js: ## JS Unit Tests (Vitest)
	cd api && npm test

test-js-coverage: ## JS Coverage-Report (api/coverage/index.html)
	cd api && npm run test:coverage
	@echo "→ open api/coverage/index.html"
