# Architecture Review Report — PulseBase

Stack: FastAPI · TimescaleDB (PG16) · 3 Python-Services (api/sync/ml) · APScheduler · Docker Compose · Flyway
Scope: Komponenten-/Allokations-Struktur + Inter-Service-Kopplung (Modul-Struktur nur sekundär)
Datum: 2026-06-06
Grounding: CMU 17-633 (Bass/Clements/Kazman), Martin Fowler Patterns

---

## Vorbemerkung — Bewertungsrahmen (ATAM Schritt 1–2)

Ein Architektur-Review bewertet **nicht gegen ein Lehrbuch-Ideal**, sondern gegen die
tatsächlichen Quality-Attribute-Prioritäten. Da kein expliziter Treiber genannt wurde,
sind die Prioritäten **[Schlussfolgerung]** aus dem System abgeleitet (bitte korrigieren,
falls falsch — die Severities hängen daran):

| Priorität | Quality Attribute | Begründung (abgeleitet) |
|-----------|-------------------|--------------------------|
| 1 | **Modifiability** | Solo-Entwickler, hohe Velocity nötig, viele bewusste KISS-Entscheidungen dokumentiert |
| 2 | **Security / Privacy** | DSGVO-sensible Gesundheitsdaten, Epilepsie/Glukose → besonders schützenswerte Kategorie (Art. 9) |
| 3 | **Operational Simplicity** | Single-Host (Mac mini = Prod), kein DevOps-Team, kein Broker/Mesh |
| 4 | Availability | Persönliche Daily-Batch-App; kurzer Ausfall unkritisch, kein SLA |
| 5 | Performance | Daily-Sync-Kadenz; Latenz im Minutenbereich akzeptabel |

**Konsequenz für dieses Review:** Mehrere klassische „Distributed-Monolith"-Vorwürfe sind
hier **bewusste, korrekte Trade-offs** (siehe Non-Risks). Die Findings konzentrieren sich
auf die Stellen, wo die gewählte Struktur den **eigenen** Prioritäten (v.a. Privacy + stille
Korrektheits-/Reliability-Lücken) zuwiderläuft.

---

## Identifizierte Architektur-Struktur (CMU 17-633 — Component & Connector)

PulseBase ist ein **Multi-Prozess-System mit Shared-Database-Integration**:

```
            ┌──────────┐   sync_requested=true    ┌───────────────┐
   Browser ─► api      ├─────────(DB-Spalte)──────► (Polling 1 min) │
            │ (FastAPI)│                            │ sync-service   │
            └────┬─────┘                            └──────┬─────────┘
                 │ liest ml_predictions                    │ ml_requested=true
                 │                                         ▼ (DB-Spalte)
            ┌────▼──────────────── TimescaleDB ────────────────────┐
            │  EINE Schema-Instanz · EINE Rolle (garmin_app)        │
            └────▲──────────────────────────────────────────────────┘
                 │ schreibt ml_predictions          ┌───────────────┐
                 └──────────────────────────────────┤ ml-service     │
                                  (Polling 2 min)    │ (Polling)      │
                                                     └───────────────┘
```

**Zentrale Beobachtung:** Die drei Services kommunizieren **ausschließlich über die geteilte
Datenbank**. Es gibt keine HTTP-/RPC-Aufrufe zwischen ihnen. Die „Orchestrierung" läuft über
boolesche Flag-Spalten (`sync_requested`, `ml_requested`) auf der `users`-Tabelle, die im
Intervall gepollt werden (DB-als-Message-Queue). Das ist Fowlers
[IntegrationDatabase](https://martinfowler.com/bliki/IntegrationDatabase.html)-Muster.

---

## Gesamtbewertung

🟡 — **Solide, bewusst pragmatische Architektur für den Solo-/Self-Hosted-Kontext mit zwei
realen Schwachstellen:** (1) eine geteilte DB-Rolle ohne Least-Privilege trotz Art.-9-Daten,
und (2) ein „fail-and-forget"-Trigger-Mechanismus, der bei Fehlern still Daten/Requests
verwirft. Beides ist behebbar ohne Architektur-Umbau.

---

## Findings

### 🟠 High (2)

---

### 🟠 HIGH Finding: Eine geteilte DB-Rolle für drei Services — kein Least Privilege
**Kategorie:** Coupling / Quality Attribute (Security)
**Location:** `db/migrations/V7__app_user.sql` · alle drei Services (`env/.env.app`)

**What:** Alle drei Services verbinden sich mit derselben Rolle `garmin_app`, die
`SELECT, INSERT, UPDATE, DELETE` auf **allen** Tabellen besitzt (inkl. Default-Privileges für
künftige Tabellen).

**Why it matters:** Die App-eigene Regel lautet „Least Privilege DB User" (app-rules.md,
Datenbank-Sektion) und es geht um Art.-9-Gesundheitsdaten (HRV, Schlaf, Epilepsie-Anfälle,
Glukose). Tatsächlich braucht aber:
- **ml-service** nur *lesend* Health-Tabellen + *schreibend* `ml_predictions` — niemals
  `DELETE` auf `users` oder `user_tokens`.
- **sync-service** *schreibend* Health-/Activity-Tabellen — niemals Zugriff auf
  `password_hash` o.ä.
- nur **api** braucht den breiten Zugriff (Auth, Account-Löschung).

Ein kompromittierter ml-service (verarbeitet untrusted Garmin-Payloads über scikit-learn/
numpy-Deserialisierung) hat heute volle DELETE-Rechte auf die Nutzertabelle und Lesezugriff
auf Fernet-verschlüsselte Tokens. Das verletzt das Defense-in-Depth-Prinzip „Auth am Data
Access Layer" auf Infrastruktur-Ebene. Es ist zugleich eine **Modifiability**-Verbesserung:
explizite Grants dokumentieren, welcher Service welche Tabelle berührt.

**Recommendation:** Drei Rollen einführen — `pulse_api` (breit), `pulse_sync`
(Health/Activity write, kein Auth-Spaltenzugriff), `pulse_ml` (Health read, `ml_predictions`
write). Per-Service-Credentials in `env/.env.sync` / `env/.env.ml` statt der geteilten
`env/.env.app`. Spalten-Level-Grants oder Views für die Auth-sensiblen Spalten.

**ADR needed:** Ja — „Per-Service-DB-Rollen vs. eine geteilte App-Rolle" ist ein nicht-
offensichtlicher Security/Operability-Trade-off (mehr Rollen = mehr Migrations-Komplexität),
den ein künftiger Leser hinterfragen würde.

**Reference:** CMU 17-633 — Security Tactics (Limit Access); OWASP ASVS V1.4; Fowler
SharedDatabase.

---

### 🟠 HIGH Finding: „Fail-and-forget"-Trigger — Flags werden auch bei Fehler gelöscht
**Kategorie:** Anti-Pattern (Implicit Interface Coupling) / Quality Attribute (Reliability)
**Location:** `sync-service/src/main.py:278,295` · `ml-service/src/main.py:152-154`

**What:** Sowohl `process_sync_requests` als auch `run_on_request` löschen das Request-Flag
im `finally`-Block — also **auch wenn der Sync bzw. die Inferenz mit einer Exception
fehlschlägt** (`mark_sync_done` / `mark_ml_done` im `finally`, `set_ml_requested` ebenfalls).

**Why it matters:** Drei konkrete Konsequenzen:
1. **Stiller Daten-Verlust bei manuellem Trigger:** Klickt ein Nutzer „Sync jetzt"
   (`sync_requested=true`) und der Garmin-Call schlägt fehl, wird das Flag konsumiert,
   ohne Retry und ohne dass der Nutzer eine Fehlermeldung sieht — die nächste Chance ist
   das geplante Intervall.
2. **ML läuft auf fehlgeschlagenem Sync:** `set_ml_requested` steht im `finally` *nach*
   dem Sync — d.h. ein **fehlgeschlagener** Sync triggert trotzdem die ML-Inferenz, die
   dann auf veralteten/unvollständigen Daten rechnet. Das ist ein Korrektheits-Smell in
   einer Pipeline, deren Output medizinnahe Scores sind.
3. **Implizite, undokumentierte Schnittstelle:** Der Vertrag zwischen den Services ist die
   Semantik zweier boolescher Spalten. Es gibt kein explizites Schema (AsyncAPI/Doc), keine
   Idempotenz-Garantie und keinen Status für „failed".

**Mitigation (Fairness):** Der tägliche `ml_infer_hour`-Cron in ml-service ist ein
Sicherheitsnetz — eine ausgefallene Inferenz wird am nächsten Tag nachgeholt. Das senkt die
Schwere, behebt aber nicht (1) [die UX-Lücke des stillen manuellen Fehlschlags] und (2)
[ML-Lauf auf Bad-Data]. **[Schlussfolgerung]**, basierend auf dem `finally`-Kontrollfluss.

**Recommendation:** Flag nur bei **Erfolg** löschen; bei Fehler entweder behalten (mit
Retry-Zähler-Spalte `sync_attempts` gegen Endlos-Loops) oder einen Fehlerstatus persistieren,
den `/api/sync-status` an die UI surface. `set_ml_requested` aus dem `finally` in den
Erfolgspfad verschieben, damit ML nicht auf fehlgeschlagenem Sync läuft.

**ADR needed:** Nein (Implementierungs-Detail des Trigger-Mechanismus) — aber den
Trigger-Vertrag selbst (siehe ADR-Empfehlung unten) dokumentieren.

**Reference:** CMU 17-633 — Availability Tactics (Retry, Exception Handling);
Fowler Implicit-Interface-Coupling.

---

### 🟡 Medium (3)

---

### 🟡 MEDIUM Finding: Byte-identisches `crypto.py` in api/ und sync-service/
**Kategorie:** Coupling (Shared Kernel / Copy-Paste)
**Location:** `api/src/crypto.py` ≡ `sync-service/src/crypto.py` (diff = leer)

**What:** Die Fernet-Verschlüsselungslogik (Token-Encrypt/Decrypt, `serialize/restore_token_dir`)
ist in zwei Services byte-identisch dupliziert. CLAUDE.md dokumentiert die GarminClient-
Duplikation bewusst (QUAL-M2), erwähnt aber `crypto.py` nicht explizit.

**Why it matters:** Bei Datenmappern ist Duplikation tolerierbar; bei **Krypto** erhöht sie
das Risiko: Ein Sicherheits-Fix (z.B. Key-Rotation-Logik, ein gepatchter Deserialisierungs-
pfad) muss diszipliniert an zwei Stellen identisch angewandt werden — ein klassischer
Drift-Vektor. Die beiden GarminClients sind bereits divergiert (`diff` zeigt Unterschiede),
was belegt, dass Duplikate hier real auseinanderlaufen.

**Recommendation:** `crypto.py` als kleinste sinnvolle shared-Einheit zuerst extrahieren
(`shared/pulse_crypto/` als path-dependency in beiden `pyproject.toml`). Crypto ist der
ideale Kandidat, weil winzig, stabil und sicherheitskritisch — der Docker-Build-Context-
Aufwand (das dokumentierte Gegenargument zu QUAL-M2) ist hier minimal.

**ADR needed:** Nein — Erweiterung der bestehenden QUAL-M2-Notiz reicht; explizit `crypto.py`
mit höherer Priorität als den GarminClient nennen.

**Reference:** Fowler — Shared Kernel vs. Inappropriate Intimacy; DRY für Sicherheitscode.

---

### 🟡 MEDIUM Finding: ml-service als God-Orchestrator
**Kategorie:** Cohesion
**Location:** `ml-service/src/main.py` (importiert ~20 Inferenz-Funktionen) · `inference_models.py` (335 LOC, orchestriert 8 Modelle)

**What:** `main.py` zieht ~20 Funktionen aus vier Inferenz-Modulen zusammen und `run_inference`
ruft sie teils via `asyncio.gather`, teils sequentiell. Die Orchestrierungs-Logik (welches
Modell, in welcher Reihenfolge, mit welchen vorgeladenen Features) konzentriert sich in einer
Datei.

**Why it matters:** Niedrige Schwere, weil sauber benannt und (noch) überschaubar. Aber jede
neue Metrik berührt `main.py` (Import + gather-Liste) — afferente Kopplung auf die Orchestrator-
Datei wächst linear mit der Modell-Anzahl. Bei der Geschwindigkeit, mit der hier Modelle
hinzukommen (21 Metriken), ist das ein vorhersehbarer Reibungspunkt.

**Recommendation:** Eine Registry/Liste von Inferenz-Schritten (`INFERENCE_STEPS = [...]`) statt
hartkodierter gather-Aufrufe; `main.py` iteriert darüber. Neue Metrik = ein Listen-Eintrag,
keine Orchestrator-Änderung (Defer-Binding-Tactic).

**ADR needed:** Nein.

**Reference:** CMU 17-633 — Modifiability Tactics (Defer Binding, Plugin/Registry).

---

### 🟡 MEDIUM Finding: Dateien nähern sich dem dokumentierten 400-LOC-Trigger
**Kategorie:** Tech Debt / Cohesion
**Location:** `api/src/db/users.py` (407 LOC) · `api/src/routes/auth.py` (359) · `api/src/routes/api.py` (338)

**What:** `db/users.py` hat den selbstgesetzten 400-Zeilen-Trigger (ARCH-L2/ARCH-L5)
bereits **überschritten** (407), `routes/api.py` (338) und `auth.py` (359) nähern sich.

**Why it matters:** Die CLAUDE.md definiert 400 LOC explizit als Refactoring-Trigger. `users.py`
vermischt mehrere Verantwortlichkeiten (CRUD, Consent, Export/Löschung, Sync-Flags, ML-Flags) —
das ist mehr ein Kohäsions- als ein Größen-Problem: die Sync-/ML-Flag-Queries (`set_sync_requested`,
`get_ml_status`) gehören thematisch nicht zu „User-CRUD".

**Recommendation:** `users.py` entlang Verantwortlichkeit splitten: `users.py` (CRUD/Auth-Felder),
`consents.py`, `account_lifecycle.py` (Export/Löschung), `triggers.py` (sync/ml-Flags). Letzteres
macht zugleich den Trigger-Vertrag aus Finding #2 explizit lokalisierbar.

**ADR needed:** Nein — der eigene dokumentierte Trigger ist erreicht; einfach ausführen.

**Reference:** CMU 17-633 — Increase Cohesion (Split Module).

---

### 🔵 Low / ⚪ Info (3)

---

### 🔵 LOW Finding: Keine Resilienz-Tactic für externe Garmin/Libre-Calls
**Kategorie:** Quality Attribute (Availability)
**Location:** `sync-service/src/garmin/client.py`, `libre/client.py`

**What:** Sync-Aufrufe gegen Garmin Connect / LibreLinkUp haben keinen Circuit Breaker und
kein Retry-mit-Backoff; ein Fehler wird geloggt und der User übersprungen.

**Why it matters:** Bei Availability-Priorität 4 ist das vertretbar. Garmin Connect ist aber
bekannt für transiente Auth-/Rate-Limit-Fehler — ein einfaches Retry-mit-Backoff würde die
Erfolgsrate ohne Architektur-Änderung erhöhen. Verstärkt Finding #2 (Fehler = Tagesausfall).

**Recommendation:** Tenacity-Retry (exponential backoff, 3 Versuche) um die externen Calls;
Zusammenspiel mit dem „nur bei Erfolg Flag löschen" aus Finding #2.

**Reference:** CMU 17-633 — Availability (Retry, Circuit Breaker).

---

### 🔵 LOW Finding: Trigger-Vertrag der Spalten ist undokumentiert
**Kategorie:** Anti-Pattern (Implicit Interface)
**Location:** `db/migrations/V6`, `V10` (nur `ALTER TABLE`, keine Vertragsdoku)

**What:** Die Inter-Service-Schnittstelle = vier Spalten (`sync_requested`, `last_sync_at`,
`ml_requested`, `last_ml_at`). V10 hat einen erklärenden Kommentar, V6 nicht. Es existiert
kein Dokument, das den Lebenszyklus „wer setzt, wer löscht, was bei Fehler" beschreibt.

**Recommendation:** Kurzer Abschnitt in `docs/` oder ein ADR (siehe unten), der den
Flag-Lebenszyklus als expliziten Vertrag beschreibt.

**Reference:** Fowler — explicit contracts statt implicit interface coupling.

---

### ⚪ INFO Finding: Explizit anzuerkennende Non-Risks (ATAM Schritt 7)

Gute Entscheidungen, die **bewusst beibehalten** werden sollten — kein Handlungsbedarf:

- **Shared-Database-Integration ist hier korrekt.** Für Solo + Single-Host wäre ein
  Message-Broker (Kafka/RabbitMQ) Resume-Driven-Development. Die DB als Integrationspunkt ist
  die operativ einfachste Wahl. *Der Mangel ist nicht die geteilte DB, sondern die geteilte
  Rolle (Finding #1) und der Fail-Modus (Finding #2) — beides ohne Broker behebbar.*
- **Kein Service-Layer (ARCH-M2), keine API-Versionierung (ARCH-L3), kein OTel (OBS-L2)** —
  korrekt gegen die Quality-Attribute-Prioritäten begründet; der dokumentierte Tech-Debt-
  Register *ist selbst* eine ATAM-Non-Risk-Dokumentation und vorbildlich.
- **Deployment-Allokation:** Ports auf `127.0.0.1` gebunden, Netz-Segmentierung
  (`internal`/`proxy`), Resource-Limits + Healthchecks pro Service, gepinnte Image-Digests,
  Flyway als One-Shot mit `service_completed_successfully`-Gate. Solide.
- **Token-Sicherheit:** Garmin-Passwörter nie gespeichert, nur Fernet-verschlüsselte Tokens
  (V20) — gute Security-by-Design-Entscheidung.

---

## Statistik

| Severity | Anzahl |
|----------|--------|
| 🔴 Critical | 0 |
| 🟠 High | 2 |
| 🟡 Medium | 3 |
| 🔵 Low | 2 |
| ⚪ Info | 1 |

---

## Top 3 Sofortmaßnahmen

1. **Trigger-Fail-Modus fixen (Finding #2)** — `set_ml_requested` aus dem `finally` in den
   Erfolgspfad; Flag nur bei Erfolg löschen. Kleinster Diff, größte Korrektheits-Wirkung,
   stoppt ML-Läufe auf fehlgeschlagenem Sync.
2. **Per-Service-DB-Rollen (Finding #1)** — `pulse_ml` (read-only Health + write
   `ml_predictions`) zuerst, da ml-service untrusted Payloads verarbeitet und heute DELETE auf
   `users` hätte. Größter Privacy-Gewinn pro Aufwand.
3. **`crypto.py` extrahieren (Finding #3)** — als `shared/pulse_crypto/` path-dependency,
   bevor die zwei Kopien (wie die GarminClients) divergieren.

---

## ADR-Empfehlungen

| ADR | Titel | Warum dokumentieren |
|-----|-------|---------------------|
| **ADR-A** | „Per-Service-DB-Rollen statt einer geteilten App-Rolle" | Nicht-offensichtlicher Security/Operability-Trade-off (Finding #1); Default-Privileges-Verhalten muss erklärt sein |
| **ADR-B** | „Shared-Database mit Flag-Polling als Inter-Service-Trigger" | Bewusste Wahl gegen Message-Broker; Flag-Lebenszyklus + Fehlersemantik als expliziter Vertrag (Findings #2, #7) — ein künftiger Leser fragt garantiert „warum kein Queue?" |

Beide ADRs kann ich im MADR-Format (`docs/adr/`) ausformulieren — sag Bescheid.

---

*Erstellt mit KI-Unterstützung (Claude Code + dev-best-practices Plugin).
Findings sind zu verifizieren — kein Ersatz für manuelle Architektur-Reviews.*
