# ADR-0001: Per-Service-Datenbankrollen mit Least Privilege statt einer geteilten App-Rolle

## Status
Accepted — 2026-06-06 (implementiert in `db/migrations/V24__per_service_roles.sql`, PR-1)

## Context

PulseBase besteht aus drei separat deployten Services (`api`, `sync-service`, `ml-service`),
die ausschließlich über eine geteilte TimescaleDB integrieren. Aktuell verbinden sich **alle
drei** mit derselben DB-Rolle `garmin_app`, definiert in
[`db/migrations/V7__app_user.sql`](../../db/migrations/V7__app_user.sql):

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "${DB_APP_USER}";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "${DB_APP_USER}";
```

Die Rolle hat damit Voll-DML auf **allen** bestehenden und **künftigen** Tabellen. Das
Credential liegt in der geteilten `env/.env.app` und wird von allen drei Services geladen.

**Auslösender Kontext:** PulseBase ist nicht nur Solo-self-hosted, sondern für einen
**öffentlichen, multi-mandantenfähigen Release** vorgesehen (vgl. CLAUDE.md: „Pflicht vor
Public-Release-Launch", „Public Release"). Das verschiebt die Quality-Attribute-Prioritäten:
**Security/Privacy wird zur höchsten Priorität**, weil dann Gesundheitsdaten vieler Nutzer
(DSGVO Art. 9 — HRV, Schlaf, Epilepsie-Anfälle, Glukose) über eine öffentlich erreichbare
Oberfläche exponiert sind.

## Decision Drivers

* **DSGVO Art. 9 / Art. 32 (Public, Multi-Tenant):** Besonders schützenswerte Daten vieler
  Nutzer erfordern technische Maßnahmen nach Stand der Technik — Least Privilege auf
  Datenbankebene ist eine Standardanforderung (OWASP ASVS V1.4 / V4.1).
* **Defense in Depth / Blast-Radius-Begrenzung:** `ml-service` deserialisiert und verarbeitet
  *untrusted* externe Payloads (Garmin/Libre) über numpy/scikit-learn. Ein kompromittierter
  ml-Prozess hat heute `DELETE` auf `users` und Lesezugriff auf `user_tokens`
  (Fernet-Ciphertext) — obwohl er fachlich nur Health-Tabellen liest und `ml_predictions`
  schreibt.
* **Eigene Projektregel:** app-rules.md fordert explizit „Least Privilege DB User".
* **Modifiability/Lesbarkeit:** Scoped Grants dokumentieren maschinenlesbar, welcher Service
  welche Tabelle berührt — ein Onboarding- und Audit-Vorteil.
* **Operational Simplicity (Gegendruck):** Solo-Betrieb, ein Prod-Server, Flyway als einziges
  Schema-Werkzeug — die Lösung darf die Migrations-/Secret-Verwaltung nicht überkomplizieren.

## Considered Options

* **Option A — Eine geteilte App-Rolle (Status quo)**
* **Option B — Drei Per-Service-Rollen mit tabellengenauen Grants**
* **Option C — Option B + PostgreSQL Row-Level Security (RLS) für Mandanten-Isolation**

## Decision Outcome

Chosen option: **Option B — drei Per-Service-Rollen**, weil es den Blast-Radius eines
kompromittierten Service auf das fachlich Notwendige begrenzt und die eigene Least-Privilege-
Regel erfüllt, ohne die Solo-Betriebs-Einfachheit nennenswert zu belasten (drei Grant-Blöcke
in einer Migration, drei Credentials in den bereits existierenden per-Service-Env-Files).

RLS (Option C) adressiert ein **anderes** Problem — Mandanten-Isolation *innerhalb* einer
Rolle — und wird hier **bewusst abgegrenzt**: relevant für Public-Multi-Tenant, aber als
eigene Entscheidung (Folge-ADR) zu treffen, weil sie alle Queries und das App-User-Design
betrifft. Option B ist Voraussetzung und unabhängig davon korrekt.

### Rollen-Zuschnitt

| Rolle | Zweck | Grants (Richtwert) |
|-------|-------|--------------------|
| `pulse_api` | Web-/Auth-/Account-Layer | SELECT/INSERT/UPDATE/DELETE auf `users`, `user_consents`, `user_tokens`, Health-/Activity-/Seizure-/Glucose-Tabellen, **SELECT** auf `ml_predictions` |
| `pulse_sync` | Garmin/Libre-Ingest | SELECT/INSERT/UPDATE auf Health-/Activity-/Glucose-Tabellen; UPDATE nur auf Trigger-/Token-Spalten von `users` (via Spalten-Grant oder View); **kein** Zugriff auf `password_hash` |
| `pulse_ml` | Inferenz | **SELECT** (read-only) auf Health-/Activity-Tabellen; INSERT/UPDATE/DELETE nur auf `ml_predictions`; UPDATE nur auf `ml_requested`/`last_ml_at` von `users` |

Auth-sensible Spalten (`password_hash`, `failed_login_attempts`, `locked_until`) werden
`pulse_sync`/`pulse_ml` über Spalten-Level-Grants bzw. dedizierte Views entzogen — `users` hat
heute gemischte Auth- und Trigger-Spalten (siehe verwandtes Finding zum Split von
[`api/src/db/users.py`](../../api/src/db/users.py)).

### Positive Consequences

* Kompromittierter ml-/sync-Prozess kann weder Nutzer löschen noch Passwort-Hashes lesen.
* Grants sind Selbst-Dokumentation des Service→Tabelle-Zugriffs (Audit/Onboarding).
* Erfüllt OWASP ASVS V4.1 / DSGVO Art. 32 für den Public-Release.
* Saubere Vorbereitung für eine spätere RLS-Entscheidung (Option C / Folge-ADR).

### Negative Consequences (akzeptierte Trade-offs)

* Drei Credentials statt einem → `env/.env.sync` und `env/.env.ml` bekommen je eigene
  `DB_*`-Variablen; `make gen-secrets` und die Settings-Validierung sind anzupassen.
* Neue Tabellen erfordern bewusste Grant-Pflege pro Rolle (kein „GRANT ALL" mehr) — gewollt,
  aber zusätzlicher Schritt in jeder Migration mit neuer Tabelle.
* Spalten-Level-Grants/Views erhöhen die Migrations-Komplexität gegenüber dem Status quo.

## Pros and Cons of the Options

### Option A — Eine geteilte App-Rolle (Status quo)
* ✅ Maximale Betriebs-Einfachheit (ein Credential, „GRANT ALL", keine Grant-Pflege)
* ❌ Verletzt Least Privilege und die eigene app-rules.md-Regel
* ❌ Kompromittierter ml-/sync-Prozess hat DELETE auf `users` + Lesezugriff auf Token-Tabelle
* ❌ Unter Public-Multi-Tenant nicht ASVS-/Art.-32-konform

### Option B — Drei Per-Service-Rollen
* ✅ Blast-Radius pro Service begrenzt; Least Privilege erfüllt
* ✅ Selbst-dokumentierender Zugriff; ASVS-/DSGVO-konform
* ✅ Nutzt die bereits existierenden per-Service-Env-Files
* ❌ Grant-Pflege pro neuer Tabelle; drei Credentials zu verwalten

### Option C — Option B + Row-Level Security
* ✅ Zusätzlich harte Mandanten-Isolation *innerhalb* einer Rolle
* ✅ Stärkster Schutz für echtes Public-Multi-Tenant
* ❌ Betrifft alle Queries + App-User-Kontext (`SET app.current_user`) — großer Eingriff
* ❌ Eigene, unabhängige Entscheidung — sollte nicht mit der Rollentrennung vermischt werden

## Implementierungs-Skizze (nicht normativ)

* Neue Migration `V24__per_service_roles.sql`: `pulse_sync`, `pulse_ml` anlegen (Muster wie
  V7, `NOINHERIT`, Passwort via Flyway-Placeholder); tabellengenaue Grants; `pulse_api`
  als Nachfolger von `garmin_app` behalten oder umbenennen.
* `ALTER DEFAULT PRIVILEGES` pro Rolle gezielt setzen statt pauschal.
* `env/.env.sync` / `env/.env.ml`: eigene `DB_APP_USER`/`DB_APP_PASSWORD`; `config.py` der
  jeweiligen Services liest sie bereits über Pydantic-Settings.
* `make gen-secrets` um zwei Passwörter erweitern; Doku in CLAUDE.md (Env-Files-Sektion).
* Umstellung ist abwärtskompatibel ausrollbar: neue Rollen anlegen → Services umstellen →
  `garmin_app`-Grants zuletzt einschränken.

## Supersession trigger

Revisit, wenn: (a) echte Mandanten-Isolation auf Zeilenebene nötig wird → Folge-ADR für RLS
(Option C); oder (b) ein Service auf ein eigenes Schema/eine eigene DB migriert (entfällt die
geteilte Rolle ganz).

## References

* OWASP ASVS 5.0 — V1.4 (Access Control Architecture), V4.1 (General Access Control)
* DSGVO Art. 9 (besondere Kategorien), Art. 32 (Sicherheit der Verarbeitung)
* CMU 17-633 — Security Tactics: *Limit Access*, *Limit Exposure*
* Martin Fowler — [IntegrationDatabase](https://martinfowler.com/bliki/IntegrationDatabase.html)
* PostgreSQL — [Privileges](https://www.postgresql.org/docs/16/ddl-priv.html),
  [Row Security Policies](https://www.postgresql.org/docs/16/ddl-rowsecurity.html)
* Review-Finding #1 — [`review-arch-report.md`](../../review-arch-report.md)
