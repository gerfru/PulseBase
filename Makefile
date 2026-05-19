.PHONY: network up up-standalone down clean reset dashboard analytics sync logs-dashboard logs-analytics logs-sync logs-all status migrate db gen-secrets setup add-host setup-user backfill-energy tailwind-build

network:
	docker network inspect proxy >/dev/null 2>&1 || docker network create proxy

up: network
	docker compose up -d --build

up-standalone: network
	docker compose --profile standalone up -d --build

down:
	docker compose down

clean:
	docker compose down -v --remove-orphans

reset:
	docker compose down --remove-orphans
	docker volume rm garmin-dev_timescale-data garmin-dev_garmin-tokens 2>/dev/null || true
	@echo "=== Volumes geloescht — Datenbank wird neu aufgesetzt ==="
	docker compose up flyway
	docker compose up -d --build

dashboard: network
	docker compose build api && docker compose up -d api

analytics: network
	docker compose build ml-service && docker compose up -d ml-service

sync: network
	docker compose build sync-service && docker compose up -d --force-recreate sync-service

logs-dashboard:
	docker compose logs -f api

logs-analytics:
	docker compose logs -f ml-service

logs-sync:
	docker compose logs -f sync-service

logs-all:
	docker compose logs -f

migrate:
	docker compose up flyway

backfill-energy:
	docker compose exec ml-service python /app/src/backfill_energy.py

status:
	docker compose ps

db:
	@export $$(grep -v '^#' .env | xargs) 2>/dev/null; \
	if [ -n "$(SQL)" ]; then \
		docker compose exec -T db psql -U $${DB_APP_USER} -d garmin -c "$(SQL)"; \
	elif [ -t 0 ]; then \
		docker compose exec db psql -U $${DB_APP_USER} -d garmin; \
	else \
		docker compose exec -T db psql -U $${DB_APP_USER} -d garmin; \
	fi

gen-secrets:
	@echo "Folgende Werte in .env eintragen:"
	@echo ""
	@echo "SESSION_SECRET=$$(openssl rand -hex 32)"
	@echo ""
	@echo "RSA Key wird nicht mehr benötigt."

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
