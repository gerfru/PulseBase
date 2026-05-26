.PHONY: network up up-standalone down clean reset dashboard analytics sync logs-dashboard logs-analytics logs-sync logs-all status migrate db gen-secrets setup add-host setup-user backfill-energy tailwind-build test test-env-up test-env-down test-seed test-e2e test-coverage secure-env

DC := docker compose --env-file env/.env

network:
	docker network inspect proxy >/dev/null 2>&1 || docker network create proxy

up: network
	$(DC) up -d --build

up-standalone: network
	$(DC) --profile standalone up -d --build

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

logs-dashboard:
	$(DC) logs -f api

logs-analytics:
	$(DC) logs -f ml-service

logs-sync:
	$(DC) logs -f sync-service

logs-all:
	$(DC) logs -f

migrate:
	$(DC) up flyway

backfill-energy:
	$(DC) exec ml-service python /app/src/backfill_energy.py

backfill-battery: ## Force-recompute body_battery_custom with new model (deletes old predictions first)
	$(DC) exec db psql -U garmin_app garmin \
	  -c "DELETE FROM ml_predictions WHERE model = 'body_battery_custom';"
	$(DC) exec ml-service python /app/src/backfill_energy.py

status:
	$(DC) ps

db:
	@export $$(grep -v '^#' env/.env | xargs) 2>/dev/null; \
	if [ -n "$(SQL)" ]; then \
		$(DC) exec -T db psql -U $${DB_APP_USER} -d garmin -c "$(SQL)"; \
	elif [ -t 0 ]; then \
		$(DC) exec db psql -U $${DB_APP_USER} -d garmin; \
	else \
		$(DC) exec -T db psql -U $${DB_APP_USER} -d garmin; \
	fi

gen-secrets:
	@echo "Folgende Werte in env/.env.api eintragen:"
	@echo ""
	@echo "SESSION_SECRET=$$(openssl rand -hex 32)"
	@echo "FERNET_KEY=$$(python3 -c 'import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
	@echo ""
	@echo "FERNET_KEY auch in env/.env.sync eintragen (gleicher Wert)."

secure-env:
	chmod 600 env/.env env/.env.api env/.env.sync env/.env.ml

setup:
	@echo "=== Erstmalige Einrichtung ==="
	@echo ""
	@echo "Schritt 1 — Session Secret generieren:"
	@echo "  make gen-secrets"
	@echo "  → Wert in .env eintragen"
	@echo ""
	@echo "Schritt 2 — garmin.local in hosts eintragen:"
	@echo "  Windows (Admin-PowerShell):"
	@echo "    Add-Content C:\\Windows\\System32\\drivers\\etc\\hosts '127.0.0.1 garmin.local'"
	@echo "  Linux / Mini PC:"
	@echo "    make add-host"
	@echo ""
	@echo "Schritt 3 — Datenbank migrieren:"
	@echo "  make migrate"
	@echo ""
	@echo "Schritt 4 — Starten:"
	@echo "  make up"
	@echo ""
	@echo "Schritt 5 — Registrieren und Garmin verknüpfen:"
	@echo "  https://garmin.local/register"
	@echo "  https://garmin.local/garmin/link"

add-host:
	@grep -q "garmin.local" /etc/hosts && echo "garmin.local ist bereits eingetragen." || (echo "127.0.0.1 garmin.local" | sudo tee -a /etc/hosts && echo "garmin.local hinzugefügt.")

setup-user:
	@echo "Neuen User anlegen:"
	@echo "  https://garmin.local/register"
	@echo "Garmin verknüpfen:"
	@echo "  https://garmin.local/garmin/link"

tailwind-build:
	@echo "=== Tailwind CLI Build ==="
	@OS=$$(uname -s | tr '[:upper:]' '[:lower:]'); \
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

test-env-up: ## Test-Stack auf Port 8001 starten
	$(DC) -f docker-compose.test.yml up -d --wait

test-env-down: ## Test-Stack stoppen
	$(DC) -f docker-compose.test.yml down

test-seed: ## Live-DB (garmin) → Test-DB (garmin_test) kopieren (test-env-up vorher)
	docker exec garmin-db pg_dump \
	  -U $$(grep ^DB_USER env/.env | cut -d= -f2) garmin \
	  | docker exec -i garmin-db-test psql \
	  -U $$(grep ^DB_USER env/.env | cut -d= -f2) garmin_test

test-e2e: ## Playwright E2E gegen Test-Stack (test-env-up + test-seed vorher)
	cd api && .venv/bin/playwright install chromium --with-deps --quiet
	cd api && .venv/bin/pytest tests/e2e/ -v

test-coverage: ## Coverage-Report (Terminal + HTML unter api/htmlcov/index.html)
	cd api && .venv/bin/pytest tests/ --ignore=tests/e2e \
	  --cov=src --cov-report=term-missing --cov-report=html:htmlcov
	@echo "→ open api/htmlcov/index.html"
