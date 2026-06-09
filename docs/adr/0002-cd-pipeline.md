# ADR-0002: Continuous-Delivery-Pipeline — Architektur skizziert, Einführung bewusst vertagt

## Status
Deferred — 2026-06-09 (kein Code; Ziel-Architektur dokumentiert, Trigger definiert. Ersetzt das CICD-M4-Stichwort)

## Context

PulseBase wird heute **manuell** deployt: alle vier Services (`api`, `sync-service`,
`ml-service`, `backup`) werden via `build:`-Direktive **lokal auf dem Zielserver** gebaut
([`docker-compose.yml`](../../docker-compose.yml) Z.70/107/143/182), und der Rollout ist ein
einzelnes `make up` (`docker compose up -d --build`, [`Makefile`](../../Makefile)). Es gibt
**keine Container-Registry**, **keinen `docker push`** und **keinen Deploy-/CD-Job** in der
CI — `.github/workflows/ci.yml` endet nach Build, Test und Image-Scan (Trivy baut lokal, pusht
nicht). Ein Rollback erfolgt heute implizit über `git revert` + erneutes `make up`.

Das ist als **CICD-M4** in CLAUDE.md als bewusste Tech-Debt vermerkt. Dieser ADR hält die
Architektur-Entscheidung fest, damit sie nachvollziehbar und auffindbar ist — statt nur als
Stichwort zu existieren — und definiert den Auslöser, ab dem sich der Bau lohnt.

**Auslösender Kontext:** PulseBase ist für einen öffentlichen Release vorgesehen. Eine CD-Pipeline
verspricht dort kürzere Lead Time und verlässlichere Deploys (DORA), kostet aber Setup
(Registry, Secrets, Rollback-Mechanik). Bei aktuell **einem Server, einem Entwickler und
seltenen Deploys** ist offen, ob dieser Nutzen die Komplexität rechtfertigt.

## Decision Drivers

* **Deployment-Frequenz / Lead Time (DORA):** Eine CD-Pipeline zahlt sich ein, wenn häufig
  deployt wird; bei seltenen, manuellen Releases bleibt der Nutzen marginal.
* **Change Failure Rate / MTTR (DORA):** Automatisiertes Health-Gate + definierter Rollback
  senken das Risiko fehlerhafter Deploys — relevant erst, wenn Deploys nicht mehr einzeln
  beaufsichtigt werden.
* **Single-Server / Solo-Betrieb (Gegendruck):** Ein Zielserver, ein Entwickler, kein
  Multi-Environment — `make up` (~30 s, beaufsichtigt) ist heute ausreichend und risikoarm.
* **Voraussetzungen fehlen:** Ohne Container-Registry gibt es kein versioniertes Artefakt, das
  ein Deploy-Schritt ziehen oder ein Rollback referenzieren könnte.
* **Security:** Ein Auto-Deploy braucht einen langlebigen SSH-/Registry-Credential in GitHub —
  zusätzliche Angriffsfläche, die nur bei echtem Nutzen vertretbar ist.

## Considered Options

* **Option A — Manuelles `make up` / `make up-public` (Status quo)**
* **Option B — Push-basierte CD: GitHub Actions → ghcr.io → SSH-Pull → Health-Gate → Rollback**
* **Option C — Pull-basierte GitOps (Watchtower / Argo-ähnlich auf dem Server)**

## Decision Outcome

Chosen option: **Option A bleibt — Einführung von Option B vertagt.** Bei einem Server, einem
Entwickler und seltenen Deploys überwiegt der Setup- und Wartungsaufwand (Registry, SSH-Secret,
`build:`→`image:`-Umstellung, Image-Retention) den DORA-Nutzen. Option B ist als **Ziel-Architektur**
skizziert (siehe Implementierungs-Skizze), damit sie bei Erreichen eines Triggers ohne erneute
Grundsatz-Diskussion umgesetzt werden kann.

Option C wird **bewusst abgegrenzt**: Pull-basiertes Auto-Update auf dem Server entkoppelt zwar
GitHub vom Server, bringt aber unbeaufsichtigte Deploys ohne explizites Health-Gate und eine
eigene Komponente auf dem Server — für einen Single-Server-Solo-Betrieb mehr Risiko als Nutzen.

### Positive Consequences

* Keine zusätzliche Angriffsfläche (kein langlebiger SSH-/Registry-Credential in GitHub).
* Keine neue Infrastruktur zu betreiben; `make up` bleibt nachvollziehbar und beaufsichtigt.
* Die Architektur-Entscheidung ist dokumentiert und auffindbar — der spätere Bau ist vorgezeichnet.

### Negative Consequences (akzeptierte Trade-offs)

* Deploy bleibt ein manueller Schritt mit kurzer beaufsichtigter Downtime (`make up`).
* Kein automatisches Health-Gate / kein Ein-Klick-Rollback — beides liegt in der Hand des Operators.
* DORA-Metriken (Lead Time, CFR, MTTR) werden nicht automatisiert verbessert.

## Pros and Cons of the Options

### Option A — Manuelles `make up` (Status quo)
* ✅ Null Setup, null neue Angriffsfläche, voll nachvollziehbar
* ✅ Passt zu Single-Server/Solo/seltene-Deploys
* ❌ Manuell, kurze Downtime, kein Auto-Health-Gate / Auto-Rollback

### Option B — Push-CD (ghcr.io → SSH → Health-Gate → Rollback)
* ✅ Kurze Lead Time, reproduzierbare versionierte Artefakte, definierter Rollback
* ✅ Explizites Health-Gate vor Traffic-Umschaltung
* ❌ Setup: Registry, `image:`-Pin, SSH-Secret, Image-Retention
* ❌ Langlebiger Deploy-Credential in GitHub = zusätzliche Angriffsfläche

### Option C — Pull-GitOps (Watchtower/Argo-artig)
* ✅ Server zieht selbst, kein eingehender SSH-Zugriff von GitHub nötig
* ❌ Unbeaufsichtigte Deploys ohne explizites Health-Gate
* ❌ Zusätzliche dauerhaft laufende Komponente auf dem Single-Server

## Implementierungs-Skizze (nicht normativ)

Die Ziel-Architektur für Option B, falls ein Trigger erreicht wird:

* **Registry:** ghcr.io; `docker-compose.yml` von `build:` auf `image: ghcr.io/…:<tag>` umstellen
  (lokaler Build bleibt für Dev via Override). CI baut + pusht je Service ein per-Commit-Tag
  (z. B. `sha-<short>`) und ein `latest`.
* **Deploy-Job (nach `ci-ok`):** GitHub Actions → SSH auf den VPS → `docker compose pull && up -d`
  mit gepinntem Tag.
* **Health-Gate:** nach `up -d` auf `/ready` pollen (analog `deploy-public-smoke`); bei Fehler
  Abbruch + Rollback auf das vorherige Image-Tag.
* **Rollback:** vorheriges Tag in der Registry behalten (Image-Retention) → `docker compose up -d`
  mit altem Tag.
* **Secrets:** VPS-SSH-Key als GitHub-Secret (least-privilege Deploy-User), ghcr.io-Token.

## Supersession trigger

Revisit (Option B bauen), wenn **eines** zutrifft: (a) eine **zweite Umgebung** (Staging) entsteht;
(b) **häufige Deploys** den manuellen Schritt zum Engpass machen; (c) das **Team > 1** wird;
(d) eine **SLA**/On-Call-Anforderung definierte MTTR/Rollback verlangt.

## References

* CICD-M4 (CLAUDE.md) — bisheriges Stichwort, von diesem ADR abgelöst
* [`docs/deployment-public.md`](../deployment-public.md) — aktueller manueller Deploy-Pfad
* Forsgren/Humble/Kim — *Accelerate* (DORA: Deployment Frequency, Lead Time, CFR, MTTR)
* Humble/Farley — *Continuous Delivery*
* [ADR-0001](0001-per-service-db-roles.md) — Vorlage/Struktur dieses ADR
