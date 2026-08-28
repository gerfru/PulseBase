# ADR-0005: PostgreSQL-Work-Queue als Inter-Service-Kanal

## Status

Accepted — 2026-08-28

Related: [Architecture concept](0005-architecture-concept.md)

## Context

API, sync-service und ml-service brauchen zwei asynchrone Arbeitsaufträge:

- API → sync-service: `sync_requested`
- sync-service → ml-service: `ml_requested`

Die ursprünglichen Boolean-Flags in `users` sind dauerhaft, koppeln den Kanal aber an das
Nutzermodell und benötigen Polling. Reines PostgreSQL `LISTEN/NOTIFY` reduziert die Latenz,
ist jedoch keine dauerhafte Queue: Ein nicht verbundener Listener erhält keine Notification.

V34 führte deshalb `service_events` als dauerhafte Queue ein und verwendete `NOTIFY` nur als
Wake-up. Während der Migration wurden Flag und Event teilweise in getrennten Statements ohne
gemeinsame Transaktion geschrieben. Außerdem konnte der partielle Unique Index einen neuen
Auftrag verwerfen, wenn derselbe Auftrag gerade `processing` war.

Die Einträge sind Arbeitsaufträge zur Konvergenz auf den neuesten Nutzerzustand. Sie sind
kein unveränderliches Domain-Eventlog und mehrere gleichartige Anforderungen dürfen
zusammengefasst werden.

## Decision Drivers

- Kein Verlust bestätigter Arbeit bei Prozessabsturz oder Listener-Unterbrechung.
- Niedrige Latenz für manuell ausgelöste Synchronisation.
- At-least-once-Verarbeitung mit idempotenten Fachoperationen.
- Wenig zusätzliche Betriebsinfrastruktur im bestehenden Single-Host-System.
- Least-Privilege-Zugriff und keine Gesundheitsdaten oder Secrets im Payload.
- Späterer Brokerwechsel ohne Änderung der Fachlogik.

## Considered Options

1. Boolean-Flags plus Polling.
2. Nur `LISTEN/NOTIFY`.
3. PostgreSQL-Work-Queue plus `LISTEN/NOTIFY`.
4. Dedizierter Broker wie NATS JetStream, RabbitMQ oder SQS.
5. Replaybares Eventlog über Kafka oder Redpanda.

## Decision Outcome

Gewählt wird **Option 3: PostgreSQL-Work-Queue plus `LISTEN/NOTIFY`**.

### Zustellung

- `service_events` ist die dauerhafte Source of Truth.
- `LISTEN/NOTIFY` ist ausschließlich ein Best-effort-Wake-up.
- Jeder Consumer drainiert beim Start und spätestens alle 30 Sekunden.
- Claims erfolgen atomar mit `FOR UPDATE SKIP LOCKED` und einer Processing-Lease.
- Die Zustellgarantie ist at-least-once. Sync-Schreiboperationen und ML-Predictions müssen
  deshalb wiederholbar sein; ML-Predictions verwenden bereits Upserts.

### Atomare Producer

Fachzustand und Enqueue werden auf derselben Connection in einer expliziten Transaktion
geschrieben. Offene Aufträge werden per `ON CONFLICT` zusammengefasst.

Der Operator-Pfad `make trigger-sync` erzeugt Flag und Queue-Auftrag in einem atomaren
PostgreSQL-Statement.

### Coalescing und Retrigger

Pro `(event_type, user_id)` existiert höchstens ein offener Auftrag. Jeder Enqueue erhöht
`generation`. Beim Claim kopiert der Consumer diesen Wert nach `claimed_generation`.

- `generation = claimed_generation`: Abschluss setzt den Auftrag auf `completed`.
- `generation > claimed_generation`: Während der Verarbeitung kam neue Arbeit hinzu;
  Abschluss setzt denselben Auftrag wieder auf `pending`.

Damit wird ein Retrigger nicht verworfen und derselbe Nutzer wird nicht parallel verarbeitet.

### Fehler und Betrieb

- Transiente Fehler verwenden exponentiellen Backoff mit Jitter, gedeckelt auf 15 Minuten.
- Nach fünf Versuchen wechselt ein Auftrag nach `failed`.
- Eine neuere Generation reaktiviert auch einen währenddessen fehlgeschlagenen Lauf sofort.
- Abgelaufene Processing-Leases werden wieder auf `pending` gesetzt.
- Fehlgeschlagene Aufträge können kontrolliert auf `pending` zurückgesetzt werden.
- Strukturierte Snapshots enthalten Queue-Tiefe, laufende und fehlgeschlagene Aufträge sowie
  das Alter des ältesten wartenden Auftrags.
- `completed`-Einträge werden nach 30 Tagen gelöscht.
- `last_error` ist auf 2000 Zeichen begrenzt; Payloads enthalten nur Schema-Version,
  Correlation-ID und Ursache, keine Tokens oder Gesundheitsmesswerte.

### Berechtigungen

Row-Level Security begrenzt die Queue:

- API erzeugt `sync_requested` und liest beide Auftragstypen für Statusanzeigen.
- sync-service konsumiert `sync_requested` und erzeugt `ml_requested`.
- ml-service konsumiert `ml_requested`.
- Consumer dürfen nur abgeschlossene eigene Aufträge im Rahmen der Retention löschen.

### Rollout und Legacy-Flags

`SYNC_EVENT_CONSUMER_ENABLED` und `ML_EVENT_CONSUMER_ENABLED` sind standardmäßig aktiv.
Bei `false` läuft der jeweilige Legacy-Poller als Rollback-Pfad; beide Pfade laufen nie
parallel.

Die Spalten `users.sync_requested` und `users.ml_requested` bleiben in diesem Release als
Expand/Contract-Kompatibilität erhalten. Sie sind nicht mehr die Statusquelle der API.
Entfernung, Poller-Löschung und Reconciliation-Löschung erfolgen erst nach einer beobachteten
Produktionsperiode in einer späteren Migration. Dadurch bleibt ein Rollback auf das vorherige
Application-Image nach V36 möglich.

## Consequences

Positiv:

- Bestätigte Arbeit überlebt Neustarts und Listener-Ausfälle.
- Manuelle Aufträge starten normalerweise ohne Polling-Latenz.
- Retrigger während laufender Arbeit geht nicht verloren.
- Kein zusätzlicher stateful Broker muss betrieben und gesichert werden.
- Queue-Eigentum ist auf Datenbankebene erzwungen.

Negativ:

- Queue-Last und fachliche Last teilen sich PostgreSQL.
- At-least-once verlangt idempotente Handler.
- Die Legacy-Flags existieren vorübergehend als zweites technisches Signal.
- Es gibt keine unabhängigen Consumer-Gruppen oder langfristige Event-Historie.

## Revisit Triggers

Ein dedizierter Broker wird neu bewertet, sobald mindestens eine Bedingung eintritt:

- mehrere Produktionshosts oder horizontal skalierte Consumer;
- mehrere unabhängige Consumer-Gruppen für dasselbe unveränderliche Event;
- geordnetes Replay oder langfristige Eventhistorie als Produktanforderung;
- messbarer negativer Einfluss der Queue auf die OLTP-Datenbank;
- Queue-Durchsatz oder Backlog-Recovery verletzt ein vereinbartes SLO;
- Producer verwenden getrennte Datenbanken und können nicht mehr atomar enqueueen.

Dann wird pro Producer-Datenbank eine Transactional Outbox mit Relay zu einem dauerhaften
Broker bevorzugt. NATS JetStream ist der erste Kandidat für einen kleinen selbstgehosteten
Betriebsumfang; Kafka ist nur bei einem echten Stream-/Replay-/Durchsatzbedarf gerechtfertigt.

## Validation

- Vollständige Flyway-Migration auf leerer TimescaleDB.
- Upgrade V35 → V36 mit einem bereits laufenden `processing`-Auftrag.
- Unit-Tests für atomare Producer, Claim, Generation-Retrigger, Retry, Listener-Wake-up,
  ineligible Nutzer und Rollback-Poller.
- Service-Suites für API, sync-service und ml-service.

## References

- [PostgreSQL `LISTEN`](https://www.postgresql.org/docs/current/sql-listen.html)
- [PostgreSQL `NOTIFY`](https://www.postgresql.org/docs/current/sql-notify.html)
- [PostgreSQL `SELECT`](https://www.postgresql.org/docs/current/sql-select.html)
- [Transactional Outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
