.PHONY: up down clean reset logs logs-sync logs-all sync status migrate db gen-secrets setup add-host setup-user restart-api build-api

up:
	docker compose up -d --build

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

logs:
	docker compose logs -f api

logs-sync:
	docker compose logs -f sync-service

logs-all:
	docker compose logs -f

migrate:
	docker compose up flyway

sync:
	docker compose restart sync-service

status:
	docker compose ps

db:
	docker compose exec db psql -U $${DB_USER} -d garmin

restart-api:
	docker compose restart api

build-api:
	docker compose build api && docker compose up -d api

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
