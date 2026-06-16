# Security Design: KI-Wochen-Insights

Date: 2026-06-16
Grundlage: [ADR-0003](adr/0003-ai-weekly-insights.md) · [Data-Design](design-data-ai-insights.md)
Baut auf bestehender Posture auf: [security.md](security.md), [ADR-0001](adr/0001-per-service-db-roles.md), [dpia.md](dpia.md)

Fokus: die **neue Angriffsfläche**, die das KI-Feature einführt. Bestehende Controls
(Session-Auth, Fernet-Credentials, Per-Service-Rollen, CSRF, CSP, TLS/HSTS, 3-Schichten-Authz)
werden **vorausgesetzt und wiederverwendet**, nicht neu erfunden.

---

## Phase 0 — Kontext

| Frage | Antwort |
|---|---|
| Was macht das Feature? | Verbalisiert wöchentliche Gesundheits-Kennzahlen via LLM zu segment-spezifischem Text |
| Sensible Daten | **Gesundheitsdaten (DSGVO Art. 9):** HRV, Glukose, Trainingslast |
| Nutzer | Consumer (Hobby), B2B-nah (Health-Pro/Trainer), Profi+Staff; geplant multi-mandantenfähig, public |
| Deployment | Self-hosted, Mac mini **ist** Prod; lokales Modell Default, Cloud-LLM nur Opt-in |
| Bedrohungslage | Öffentliches Internet; opportunistisch + finanziell motiviert; **kein** Nation-State im Scope |
| Compliance | DSGVO (Art. 9/22/32), **EU AI Act** (Transparenz), vgl. bestehende DPIA |

---

## Phase 1 — Threat Model (neue Komponenten)

### Assets

| Asset | Klassifikation | Impact bei Kompromittierung |
|---|---|---|
| Gesundheits-Kennzahlen im Prompt | Art. 9 (besonders) | DSGVO-Verstoß, Reputations-/Haftungsschaden |
| Generierter Insight-Text (pro User) | Art. 9 (verkettbar via user_id) | wie oben |
| LLM-Logs/Traces (falls Prompt geloggt) | Art. 9 | wie oben — **oft übersehener Speicher** |
| Evidenz-Katalog | Integrität | falsche medizinische Aussagen → Haftung |
| Lokaler Inference-Endpoint | Verfügbarkeit/Integrität | DoS auf Prod, manipulierte Ausgaben |

### Trust Boundaries (neu)

1. **App ↔ LLM** — Gesundheitsdaten überqueren die Grenze zum Modell. Lokal = innerhalb
   Homelab; **Cloud-Opt-in = verlässt Homelab** (kritischste neue Grenze).
2. **Untrusted Daten-Felder ↔ Prompt** — Garmin/Libre-stammende Werte fließen über das
   Insight-Objekt in den Prompt (Prompt-Injection-Vektor).
3. **LLM-Output ↔ Nutzer/DB** — ungeprüfter Text darf nicht zum Nutzer (Halluzination).
4. **Inference-Server ↔ Netzwerk** — neuer Port/Prozess auf dem Mac mini.

### STRIDE — Top-Risiken (gerankt)

| # | STRIDE | Bedrohung | L×I | Score | Priorität |
|---|---|---|---|---|---|
| 1 | T/Spoofing-of-data | **Halluzinierte Gesundheitszahl** erreicht Nutzer → Haftung/Safety | 3×3 | **9** | 🔴 CRITICAL |
| 2 | I | **Health-Daten-Egress** zum Cloud-LLM (bei Opt-in), ggf. außerhalb EU | 2×3 | **6** | 🟠 HIGH |
| 3 | I | **Health-Daten in LLM-Logs** (ADR sagt „Prompt loggen") | 3×2 | **6** | 🟠 HIGH |
| 4 | E/I | **BOLA** — User A liest Insight von User B | 2×3 | **6** | 🟠 HIGH |
| 5 | D | **Inference-DoS** auf dem Mac mini (Prod) durch erzwungene Regenerierung | 2×2 | **4** | 🟠 HIGH |
| 6 | T/I | **Prompt-Injection** über untrusted Daten-/Evidenz-Felder | 2×2 | **4** | 🟠 HIGH |
| 7 | S/T | **Inference-Server exponiert / Modell-Supply-Chain** (Weights, Port) | 2×2 | **4** | 🟠 HIGH |
| 8 | I | **Output-PII-Leak** — Modell halluziniert/echo't einen Identifier in den Text | 1×2 | **2** | 🟡 MEDIUM |

**Erläuterung der Top-3:**

- **#1 (CRITICAL)** ist realistisch, weil LLMs strukturell halluzinieren; der Impact ist
  hoch, weil eine falsche Gesundheitszahl bei Health-Pros/Profis geschäftsschädigend ist.
  Ohne Control könnte das Modell eine plausible, aber falsche Zahl ausgeben, die ein Trainer
  seinem Klienten weitergibt. → Das **gesamte Post-Check-Gate** aus ADR-0003 ist *die* Antwort
  hierauf; dieses Design bestätigt es als wichtigste Maßnahme.
- **#2 (HIGH)** ist nur bei Cloud-Opt-in real, dann aber ein Art.-9-Transfer an einen
  Auftragsverarbeiter. Ohne Control: Gesundheitsdaten bei einem Drittanbieter, evtl.
  Drittland, ohne AVV.
- **#3 (HIGH)** ist real, weil die ADR „Prompt + Response loggen" empfiehlt — der Prompt
  *ist* der Gesundheitsdatensatz. Ohne Control verlagert man Art.-9-Daten unbemerkt in
  ein schwächer geschütztes Log-System.

---

## Phase 2 — Architektur & Security Controls

### C1 — Output-Integritäts-Gate (gegen #1, CRITICAL)

- **Was:** Der Post-Check aus ADR-0003 als *fail-secure* Gate vor Auslieferung **und** vor
  Persistierung: Number-Grounding (binär 100 %), Evidence-Grounding, Trend-Richtung,
  Disclaimer-Präsenz, Identifier-Scan. Fail → max. 2 Regenerationen → **deterministisches
  Fallback-Template**.
- **Warum:** „Fail Secure" — wenn das LLM nicht beweisbar treu ist, liefert das System einen
  geprüften, zahlen-treuen Standardtext statt zu raten.
- **Limitation:** schützt **nicht** gegen einen falschen Wert *im Insight-Objekt selbst*
  (Schicht-1-Bug). → Schicht 1 braucht eigene Unit-Tests (siehe Data-Design).

### C2 — Daten-Lokalität & Egress-Kontrolle (gegen #2)

- **Was:** Lokales Modell ist Default; Cloud nur als **explizites Opt-in pro Deployment**.
  Bei Cloud: AVV/DPA verpflichtend, EU-Region, TLS 1.3 in Transit, Pseudonymisierung vor
  dem Prompt, dokumentiert in der DPIA.
- **Warum:** Datenminimierung & Datensouveränität (Privacy by Design). Lokal = kein Transfer,
  kein Auftragsverarbeiter, kein Drittland-Problem.
- **Limitation — ehrlich:** Pseudonymisierung macht die Daten **nicht** zu Nicht-Art.-9-Daten.
  HRV/Glukose-Werte bleiben Gesundheitsdaten, auch ohne Namen. Pseudonymisierung senkt das
  Breach-Risiko des Verarbeiters, hebt die Art.-9-Pflichten **nicht** auf.

### C3 — Log-/Telemetrie-Minimierung (gegen #3)

- **Was:** **Rohen Prompt/Response NICHT loggen.** Stattdessen loggen: Metriken-*Keys* (nicht
  Werte), `catalog_version`, `model_id`, Post-Check-Ergebnis (pass/fail je Riegel),
  Regenerations-Zahl, Latenz, Token-Count. Für Debugging optional ein **opt-in, kurzlebiger**
  Voll-Trace, dann im selben Art.-9-Schutzniveau (Zugriffsschutz, Retention, Löschscope).
- **Warum:** Korrigiert den Daten­minimierungs-Konflikt in ADR-0003. Die Observability-Ziele
  (Regenerations-Rate als Frühwarnsignal) werden **ohne** Health-Payload erreicht.
- **Referenz:** GDPR Art. 32; Logging-Pattern „what NOT to log".

> **Aktion:** ADR-0003 Observability-Punkt entsprechend präzisieren (Prompt/Response → Metadaten).

### C4 — Autorisierung / BOLA (gegen #4)

- **Was:** Insight-Endpoints scopen **immer** per Session-`user_id`; `user_id` wird **nie**
  vom Client akzeptiert. Wiederverwendung des bestehenden 3-Schichten-Authz + BOLA-Musters
  aus [security.md](security.md) §4.2. DB-Reads `WHERE user_id = <session>`.
- **Warum:** Verhindert objektbezogene Rechteausweitung auf fremde Gesundheits-Insights.
- **Limitation:** greift nur, wenn jeder neue Endpoint das Muster einhält → Code-Review-Pflicht.

### C5 — Generierungs-Ratelimit & Isolation (gegen #5)

- **Was:** Generierung **batch/scheduled**, nicht synchron pro Request; Concurrency-Cap +
  Queue; Rate-Limit auf manuell ausgelöste Regenerierung; Timeout + Circuit-Breaker um den
  Inference-Call. Da der Mac mini Prod **ist**: Inference-Last gegen die übrige App isolieren
  (eigener Prozess/Container mit CPU-Limit).
- **Warum:** Eine teure LLM-Last darf nicht die Kern-App (Sync/API) auf demselben Host
  aushungern (Availability).
- **Limitation:** schützt nicht vor einem generell überlasteten Host → Kapazitätsplanung nötig.

### C6 — Prompt-Injection-Eindämmung (gegen #6)

- **Was:** Strukturierter Input ist die primäre Verteidigung — das Insight-Objekt ist
  Enums + Zahlen, **kein** freier User-Text. Verbleibende Freitext-Felder (Evidenz-Texte =
  kuratiert/trusted; künftige Daten-Felder) als **Daten** klar delimitieren, nicht als
  Instruktion. Output-Gate (C1) fängt Folgen ab.
- **Warum:** v1-Injection-Fläche ist *by design* winzig. Wichtig wird das beim Wachsen des
  Objekts und **kritisch in v2 (Agent)** — dort eigener Threat-Pass.
- **Limitation:** „Markieren als Daten" ist kein harter Schutz; die echte Absicherung ist,
  dass kein untrusted Freitext in den Prompt gelangt.

### C7 — Inference-Server-Härtung (gegen #7)

- **Was:** Inference-Endpoint **nur auf localhost** binden (keine Netzwerk-Exposition);
  Modell-Weights pinnen + Checksum/Signatur verifizieren; Prozess unter least-privilege
  (eigene Service-Rolle, kein DB-Schreibrecht außer auf die zwei Insight-Tabellen).
- **Warum:** Neuer Prozess = neue Angriffsfläche; localhost-Bind nimmt die Netzwerk-Exposition
  komplett raus (Economy of Mechanism).
- **Referenz:** Least Privilege (ADR-0001-Muster).

### C8 — Persistenz im Art.-9-Schutzniveau (Querschnitt)

- **Was:** `weekly_insights` + `weekly_insight_texts` erben das bestehende Health-Tabellen-
  Schutzniveau: Per-Service-Grants (nur Insight-Service schreibt, ADR-0001), `ON DELETE
  CASCADE` von `users(id)` für DSGVO-Löschung, Encryption-at-rest-Posture wie übrige Health-Daten.
- **Warum:** Der generierte Text ist via `user_id` verkettbar → Art. 9, gleiche Pflichten.

---

## Phase 3 — Crypto Plan

Überwiegend Wiederverwendung; das Feature führt **kein neues Krypto-Primitiv** ein, außer:

| Use Case | Algorithmus | Key-Management | Begründung |
|---|---|---|---|
| Transit zum Cloud-LLM (nur Opt-in) | TLS 1.3 | Provider-Zertifikat, Pinning optional | Standard für Daten in Transit |
| Pseudonymisierung (nur Cloud-Opt-in) | **HMAC-SHA256**(secret, user_id) | Secret in bestehender Secret-Verwaltung, getrennt von Daten | Konsistent + nicht umkehrbar ohne Key; ermöglicht keine Re-Identifikation beim Verarbeiter |
| At-Rest (Insight-Tabellen) | bestehende DB-/Disk-Encryption-Posture | wie Health-Tabellen | Konsistenz, kein Sonderweg |
| Modell-Integrität | SHA-256-Checksum der Weights | Checksum in Repo/Deploy gepinnt | Supply-Chain-Integrität (C7) |

> Kein neues Schlüsselmaterial für v1-Lokalbetrieb. Das HMAC-Pseudonymisierungs-Secret
> entsteht **nur**, wenn Cloud-Opt-in aktiviert wird.

---

## Phase 4 — Auth & Authorization Design

Keine Änderung am Auth-Modell — bestehende **Session-basierte Auth** (security.md §3) gilt.
Für das Feature relevant:

- **Authentifizierung:** unverändert (Server-side Sessions, Account-Lockout, CSRF Double-Submit).
- **Autorisierung:** Insight-Endpoints = `require_user` + Scoping per Session-`user_id`
  (C4). Health-Pro/Profi-Segmente sind **Präsentations**-Varianten, **keine** Rollen mit
  Mehr-Rechten auf fremde Daten — wichtig: Segment ≠ Berechtigung zum Lesen anderer Nutzer.
- **Separation of Duties:** Insight-Generierungs-Service hat eine eigene DB-Rolle mit
  Schreibrecht **nur** auf die zwei Insight-Tabellen + Leserecht auf die Health-Quelltabellen
  (ADR-0001-konform).

---

## Compliance Notes

> [Nicht verifiziert] Die folgenden regulatorischen Einordnungen sind keine Rechtsberatung.
> Sie sind als [Schlussfolgerung] zu lesen und vor dem Public-Release rechtlich zu bestätigen.

### DSGVO

| Pflicht | Status | Lücke |
|---|---|---|
| Art. 9 (besondere Kategorien) | adressiert via Lokal-Default + Schutzniveau (C2/C8) | Cloud-Opt-in braucht AVV + DPIA-Update |
| Art. 22 (automatisierte Entscheidung) | **[Schlussfolgerung]** vermutlich nicht einschlägig — Insight ist *informativ*, keine rechtliche/erheblich beeinträchtigende Wirkung | rechtlich bestätigen; Profi-Klienten-Kontext prüfen |
| Art. 32 (TOMs) | Log-Minimierung (C3), Least-Privilege (C7/C8) | C3 erfordert ADR-Korrektur |
| Art. 17 (Löschung) | `ON DELETE CASCADE` deckt Insight-Tabellen | Logs/Traces in Löschscope aufnehmen |
| Datenminimierung | Objekt ohne Identifier; Metadaten-Logging | — |

### EU AI Act

- **[Schlussfolgerung] Risikoklasse:** v1 ist vermutlich **kein** Hochrisiko-System nach Annex III
  (keine medizinische Diagnose/Entscheidung; informatives Wellness-Feature, „Worte aus dem LLM,
  keine individualisierten Handlungsanweisungen"). **Aber:** die Gesundheitsnähe + Health-Pro-
  Nutzung verlangt eine bewusste, dokumentierte Einstufung — nicht aus dem Bauch.
- **Transparenzpflicht (Art. 50):** KI-generierter Text **muss als solcher gekennzeichnet** sein.
  Die DPIA nennt das bereits (Art.-52-Verweis) → in der Präsentationsschicht (Schicht 3) je
  Segment umsetzen. Deckt sich mit dem Disclaimer-Guard.
- **Abgrenzung Medizinprodukt (MDR):** sobald das Feature *diagnostiziert* oder *individuelle
  medizinische Empfehlungen* gibt, droht MDR-Relevanz. Der Regulatorik-Guard (Empfehlungen nur
  aus `evidence_catalog`, keine individualisierten Anweisungen) hält bewusst Abstand. **Diese
  Grenze ist die wichtigste Compliance-Invariante.**

---

## Security-Invarianten (müssen immer gelten)

1. Kein ungeprüfter LLM-Text erreicht Nutzer **oder** DB (Post-Check-Gate, fail-secure).
2. Das Insight-Objekt im Prompt enthält **nie** einen Identifier (dreifach erzwungen, Data-Design).
3. Roher Health-Prompt/Response wird **nicht** in Standard-Logs gespeichert.
4. Gesundheitsdaten verlassen das Homelab **nur** bei explizitem Cloud-Opt-in mit AVV.
5. Insight-Reads sind **immer** per Session-`user_id` gescopet (kein Client-`user_id`).
6. KI-generierter Text ist im UI **als KI-generiert gekennzeichnet** (AI-Act Art. 50).

---

## Assumptions & Open Questions

- **[Nicht verifiziert]** EU-AI-Act- & Art.-22-Einstufung: rechtlich zu bestätigen vor Public-Release.
- Welcher Service hostet die Inference (eigener Container? ml-service?) — bestimmt Rolle/Isolation (C5/C7).
- Retention der opt-in Voll-Traces (C3): Dauer? Wer hat Zugriff?
- Cloud-Opt-in: konkreter Anbieter + EU-Region + AVV-Verfügbarkeit noch offen.

---

## Setup Todos

- [ ] Post-Check-Gate fail-secure vor Auslieferung **und** Persistierung verdrahten (C1)
- [ ] ADR-0003 Observability-Punkt korrigieren: Prompt/Response → Metadaten (C3)
- [ ] Logging-Filter: Health-Payload nie in Standard-Logs; opt-in Trace separat (C3)
- [ ] Insight-Endpoints: Scoping-Test „User A kann User B nicht lesen" (C4, BOLA)
- [ ] Generierungs-Ratelimit + Concurrency-Cap + Inference-Isolation (C5)
- [ ] Inference nur localhost-Bind; Modell-Weights-Checksum (C7)
- [ ] Per-Service-Grant für Insight-Service (ADR-0001-konform, C8)
- [ ] DPIA-Update + EU-AI-Act-Einstufung dokumentieren; Art.-50-Kennzeichnung im UI
- [ ] Logs/Traces in den DSGVO-Löschscope aufnehmen

## Next Steps (priorisiert)

1. **C1 + Invariante 1** — das CRITICAL-Risiko zuerst: Post-Check-Gate fail-secure.
2. **C3 + ADR-Korrektur** — Log-Minimierung, bevor irgendein LLM-Call geloggt wird (sonst
   entsteht sofort ein Art.-9-Logspeicher).
3. **C4-Scoping-Test** — BOLA, sobald ein Insight-Endpoint existiert.
4. **C5/C7** — bei Aufsetzen des lokalen Inference-Servers.
5. **Compliance** — DPIA-Update + rechtliche Einstufung vor Public-Release.
6. **v2 (Agent):** eigener Threat-Pass — Prompt-Injection & Excessive Agency werden dann CRITICAL.
