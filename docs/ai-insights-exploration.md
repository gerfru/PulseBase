# AI Insights — Ideenfindung & Architektur-Exploration

> Status: **Exploration / Brainstorming** — verdichtet in [ADR-0003](adr/0003-ai-weekly-insights.md) (Proposed)
> Datum: 2026-06-15
> Kontext: Soll PulseBase ein KI-gestütztes Insight-Feature bekommen? Welche
> Technologie, welcher Ansatz — und was ist aus Kundensicht das Beste?

---

## 1. Konzept: Was ist ein "Agent"?

- **LLM** = sehr kluges Gehirn ohne Hände. Text rein → Text raus. Kein Gedächtnis,
  keine Aktionen.
- **Agent** = LLM + **Tools** (Funktionen, die es aufrufen darf) + **Loop**
  (mehrere Runden denken→handeln→beobachten) + **Memory**.
- **Reason–Act-Loop**: Agent entscheidet selbst, *welches* Tool er *wann* nutzt
  und verkettet Schritte.
- **Multi-Agent**: Leader-Worker-Muster — ein Leader zerlegt die Aufgabe, verteilt
  sie an spezialisierte Worker, sammelt Ergebnisse ein.
- **Agent-Framework** (z.B. AgentScope) = fertige Infrastruktur drumherum:
  Loop, Tool-System, Sandbox (isolierte Ausführung), Permission-System,
  Observability/Studio, Multi-Agent-Koordination.

---

## 2. Agent-Framework-Landschaft (Stand 2026)

| Framework | Herkunft | Charakter / Stärke |
|---|---|---|
| **AgentScope** | Alibaba (akademisch) | Agent-Oriented Programming, native Sandbox + Permissions, verteilt |
| **LangGraph** | LangChain | Stateful Graphen, reifste Produktion, Observability (LangSmith) |
| **CrewAI** | CrewAI Inc. | Rollenbasierte Teams, niedrigste Einstiegshürde |
| **AutoGen** | Microsoft | Konversierende Agenten — *im Maintenance-Mode* |
| **Microsoft Agent Framework** | Microsoft | Nachfolger von AutoGen + Semantic Kernel, Enterprise/.NET |
| **OpenAI Agents SDK** | OpenAI | Leichtgewichtig, OpenAI-nativ |
| **Claude Agent SDK** | Anthropic | Leichtgewichtig, Claude-nativ |
| **Google ADK** | Google | GCP-nativ, A2A-Discovery, Vertex-Deployment |
| **Pydantic AI** | Pydantic | Type-Safety & Testing first (oft *mit* anderen kombiniert) |
| **smolagents** | Hugging Face | Minimalistisch, "Code-Agents", Sandbox, model-agnostisch |
| **Letta** (ex-MemGPT) | Letta | Spezialist für persistentes Gedächtnis |
| **LlamaIndex / Haystack** | — | Daten-/RAG-zentriert |
| **Dify / n8n** | — | Low-Code / visuelle Workflows |
| **Mastra** | — | TypeScript-Welt, full-stack Agenten |

> Einschätzungen aus aktuellen Vergleichsartikeln (2026), **nicht selbst gebenchmarkt**.

---

## 3. Direktduell: AgentScope vs. LangGraph

**Grundphilosophie:**
- **LangGraph = Workflow als Landkarte.** Du zeichnest vorher einen Graphen
  (Knoten = Schritte, Kanten = Übergänge). Ablauf explizit & vorhersehbar.
- **AgentScope = Agenten als selbstständige Objekte.** Agenten kooperieren,
  entscheiden mehr selbst. Ablauf emergenter.

> Faustregel: **LangGraph kontrolliert den Weg, AgentScope vertraut den Agenten.**

| Dimension | AgentScope | LangGraph |
|---|---|---|
| Modell | Agenten als first-class Objekte (async) | State-Machine-Graph |
| State | Implizit über Agent-Memory (In-Mem/Redis/SQL) | Explizites Schema (TypedDict/Pydantic), Checkpointing |
| Multi-Agent | Eingebaut (MsgHub, A2A-Protokoll) | Manuell per Graph-Komposition |
| Sandbox | **Nativ** (Docker + VNC) + Permissions | Keine native — externe Lösung nötig |
| Observability | OpenTelemetry-nativ + Studio | LangSmith (stark) |
| Lernkurve | ~20 min, async-Wissen | 30 min+, Graph-Denken |
| Ökosystem | jünger (~46K Stars) | riesig (LangChain 97K+) |
| Sprachen | Python | Python **& TypeScript** |
| Reife | jünger, akademisch | am meisten battle-tested |

**Trade-off in einem Satz:**
- LangGraph = max. Kontrolle & Reife, dafür mehr Boilerplate + Multi-Agent selbst bauen.
- AgentScope = Multi-Agent + Sandbox geschenkt + mehr Autonomie, dafür kleineres
  Ökosystem & weniger Produktions-Track-Record.

---

## 4. Der Perspektivwechsel: Was ist aus KUNDENSICHT das Beste?

**Erkenntnis:** Die Framework-Wahl ist für Kunden **komplett unsichtbar**. Was zählt,
steht davor.

### Zielgruppen-Bedürfnisse

| Segment | Will… | Toleranz für AI-Fehler | Verkaufsargument |
|---|---|---|---|
| **Hobby-Sportler** | einfache, motivierende Insights | mittel | Bequemlichkeit, Klartext |
| **Health-Pros / Trainer** | belastbare, **begründbare** Aussagen für Klienten | **sehr niedrig** (Haftung) | Nachvollziehbarkeit + Evidenz |
| **Profi-Sportler (+ Staff)** | Tiefe, Trends, Rohdaten, freies Nachfragen | **null** | Präzision & Experten-Interpretation |

**Gemeinsamer Nenner & größtes Risiko: Vertrauen.** Eine erfundene Gesundheitszahl
ist bei Hobby-Nutzern ärgerlich, bei Health-Pros & Profis geschäftsschädigend.

---

## 5. Getroffene Entscheidungen

> Ergebnis der Ideenfindung — Richtungsentscheidung, noch keine finale ADR.

1. **Eine Engine für alle Segmente** — gemeinsamer deterministischer Kern,
   Präsentation pro Segment unterschiedlich. Nicht dreimal bauen.
2. **Vertrauen / keine Halluzination zuerst** — höchste Priorität.

### Leitprinzip

> **Zahlen kommen aus Code, Worte kommen aus dem LLM.**

---

## 6. Ziel-Architektur: 3 Schichten

```
┌───────────────────────────────────────────────────────────┐
│  3) PRÄSENTATIONS-SCHICHT  (pro Segment unterschiedlich)  │
│     Hobby: kurz & motivierend                             │
│     Pro/Trainer: + Zahlen + Evidenz + Export              │
│     Profi: + Rohdaten + freies Nachfragen                 │
└───────────────────────────▲───────────────────────────────┘
                            │ nur Tonlage/Tiefe, NICHT Inhalt
┌───────────────────────────┴───────────────────────────────┐
│  2) ERKLÄR-SCHICHT  (LLM)                                 │
│     formuliert · ordnet ein · koppelt an Evidenz          │
│     darf NIEMALS rechnen oder Werte erfinden              │
└───────────────────────────▲───────────────────────────────┘
                            │ bekommt fertige, geprüfte Zahlen
┌───────────────────────────┴───────────────────────────────┐
│  1) FAKTEN-SCHICHT  (bestehender Code, deterministisch)   │
│     get_glucose_stats · get_ml_insights · training_load   │
│     + evidence_catalog.json                               │
│     → liefert ein striktes "Insight-Objekt"               │
└───────────────────────────────────────────────────────────┘
```

### Das "Insight-Objekt" (Vertrauens-Vertrag)

Schicht 1 produziert für *alle* Segmente dasselbe strukturierte Objekt:

```python
WeeklyInsight(
    metrics=[
        Metric(name="HRV",  value=58, unit="ms", change_pct=-4.1, trend="stabil"),
        Metric(name="Glukose-CV", value=28, unit="%", change_pct=+2.0, trend="leicht↑"),
        Metric(name="Trainingslast", value=412, unit="TSS", change_pct=+18, trend="↑"),
    ],
    flags=["training_load_spike"],                       # deterministisch erkannt
    evidence=["acwr_injury_risk", "glucose_variability"],# Keys aus evidence_catalog.json
)
```

Das LLM bekommt **nur dieses Objekt** + Auftrag "formuliere, erfinde nichts,
nenne die Evidenz".

### Halluzination technisch erzwingen (3 Riegel)

1. **Strukturierter Input** — LLM bekommt nur das Insight-Objekt, keinen Rohdaten-
   Zugriff zum Schätzen.
2. **Zahlen-Whitelist / Post-Check** — nach der Antwort prüft Code: kommt jede
   genannte Zahl im Insight-Objekt vor? Wenn nein → verwerfen/neu generieren.
   (Der stärkste, oft übersehene Riegel.)
3. **Evidenz-Pflicht** — Empfehlungen nur aus `evidence_catalog.json`, keine
   freien medizinischen Ratschläge.

---

## 7. Framework-Konsequenz & nächste Schritte

- Für "Vertrauen first + prüfbarer Ablauf" ist der **LangGraph-artige, kontrollierte
  Pfad** die richtige Basis für die Wochen-Insight (Schicht 1+2). Für die reine
  Wochen-Insight reicht streng genommen sogar ein **simpler, kontrollierter Tool-Loop**.
- Ein **AgentScope-artiger Agent** wird erst für das Profi-Feature "frag deine Daten
  frei" gebraucht — und holt Daten auch dort nur über dieselbe Fakten-Schicht.
- **Wichtigste Erkenntnis:** Schicht 1 (Insight-Objekt + Evidenz-Kopplung) ist
  framework-unabhängig und der eigentliche Wert. Das Framework kommt erst bei
  Schicht 2/3.

### Vorgeschlagene Reihenfolge

1. **Schicht 1 bauen:** `WeeklyInsight`-Schema + deterministische Sammel-/Flag-Funktion
   gegen bestehende `db/`-Funktionen. Kein LLM, voll testbar.
2. **Zahlen-Post-Check** als kleine Guard-Funktion.
3. **Schicht 2:** einfacher, kontrollierter LLM-Aufruf, der das Objekt verbalisiert
   (3 Präsentations-Modi).
4. **Später:** Profi-"frag-frei"-Agent obendrauf.

---

## 8. Umgang mit den offenen Risiken (machbar gemacht)

> Drei der vier Lücken werden **strukturell** gelöst (erzwingen statt hoffen),
> passend zum Leitprinzip. Eval folgt als eigener Schritt (siehe 8.4).

### 8.1 Datenschutz — durch Architektur, nicht durch Policy

Hebel ist schon da: **Nur das `Insight-Objekt` verlässt Schicht 1** — aggregierte
Metriken, keine Rohzeitreihen, kein Name, keine User-ID.

- **Default = lokales Modell** (z.B. Ollama auf dem Mac mini). Nichts verlässt das
  Homelab → DSGVO Art. 9 (Gesundheitsdaten) löst sich auf, statt vertraglich
  verwaltet zu werden. Passt zur self-hosted-Philosophie; Latenz/Qualität für die
  kurze, strukturierte Wochen-Insight unkritisch.
- **Cloud-API nur als Opt-in**, dann mit Pseudonymisierung *vor* dem Prompt
  (Identifier raus, nur Metriken). Bewusste Entscheidung pro Deployment, nie Default.
- **Im Schema verankert:** `WeeklyInsight` enthält **nie** einen Identifier — als
  harte Regel **plus Test**, der genau das prüft. Datenschutz wird testbar, nicht
  nur dokumentiert.

### 8.2 Regulatorik — Scope-Grenze als Code

Ziel: nicht in die Medizinprodukte-Ecke rutschen. Die `evidence_catalog.json`-Pflicht
(Riegel 3) ist dafür das Werkzeug — konsequent genutzt:

- **Harte Grenze:** LLM darf *einordnen und auf Evidenz verweisen*, aber **keine**
  individualisierte Handlungsanweisung erzeugen ("nimm X", "trainiere morgen nicht").
  Empfehlungstexte kommen **ausschließlich** aus kuratierten `evidence_catalog`-
  Einträgen, nicht aus freier LLM-Formulierung.
- **Disclaimer + Tonalität pro Segment** in der Präsentationsschicht: Hobby =
  "Hinweis, kein medizinischer Rat"; Health-Pro = "Entscheidungsunterstützung,
  fachliche Bewertung beim Profi". Gehört genau in die Schicht, die nur Tonlage
  variiert — entschärft zugleich die Haftungsfrage aus der Zielgruppen-Tabelle.

### 8.3 Halluzination — Post-Check härten (3 Stufen)

Der String-Match aus Riegel 2 ist zu löchrig (paraphrasierte/gerundete/abgeleitete
Zahlen). Härtung in drei Stufen, einfach → streng:

1. **Zahl-Extraktion + Normalisierung:** alle zahlartigen Tokens ("58", "58 ms",
   "-4 %") ziehen, normalisieren, gegen die erlaubte Menge aus dem `Insight-Objekt`
   prüfen (kleine Rundungs-Toleranz). Jede Zahl ohne Deckung → verwerfen/regenerieren.
2. **Qualitative Zahlwörter verbieten:** "knapp 60", "fast ein Fünftel", "etwa die
   Hälfte" umgehen jeden Ziffern-Check. Per Prompt untersagen **und** per Blocklist
   nachprüfen. Lieber "58 ms" als "knapp 60".
3. **Stärkster Riegel — Slot-Template statt Freitext:** Code baut den Satz mit fixen
   Zahl-Slots (`HRV {hrv} ms, {trend}`), das LLM formuliert nur die Prosa drumherum
   und kann die Slots nicht anfassen. Dann *kann* strukturell keine Zahl erfunden
   werden, statt es hinterher zu prüfen. Für begrenzte Satzmuster realistisch.

> Mindeststandard: **1 + 2**. Stufe **3** anstreben, sobald die Satzmuster stabil sind.

### 8.4 Eval — Schicht 2 absichern

Schicht 1 ist über Unit-Tests gegen `db/` voll testbar. Schicht 2 (LLM-Verbalisierung)
braucht eine eigene Eval, sonst ist jeder Prompt-/Modell-Wechsel ein Blindflug.

> **Kerngedanke: Safety und Quality sind zwei getrennte Tracks.** Safety wird
> deterministisch geprüft und muss **100 %** bestehen (hart, CI-blockierend).
> Quality (Ton, Lesbarkeit) wird weicher mit Schwellwerten bewertet. Niemals
> vermischen — sonst verwässert ein subjektiver Ton-Score die Halluzinations-Garantie.

**Track A — Deterministische Checks (kein LLM, höchster ROI):**

- **Number-Grounding:** jede Zahl in der Ausgabe ∈ `Insight-Objekt` (= Post-Check
  aus 8.3, hier als Eval-Assertion).
- **Zahlwort-Blocklist:** keine "knapp 60"/"fast ein Fünftel" (8.3 Stufe 2).
- **Evidence-Grounding:** jede Empfehlung referenziert einen gültigen
  `evidence_catalog`-Key; keine freie Empfehlung.
- **Trend-Richtung:** sagt die Prosa "verbessert", obwohl `change_pct` in die
  Gegenrichtung zeigt? Deterministisch prüfbar — fängt die subtilste, gefährlichste
  Fehlklasse.
- **Disclaimer-Präsenz** pro Segment (8.2).
- **Kein-Identifier-Leak** (8.1) — PII-Scan der Ausgabe.
- **Coverage:** alle geflaggten Metriken kommen vor; keine erfundenen Flags.

**Track B — LLM-as-Judge (nur fürs Subjektive, getrennt vom Safety-Gate):**

- Ton passt zum Segment (Hobby motivierend vs. Pro sachlich-knapp), Klarheit,
  kein Widerspruch, keine Leer-Aussage.
- Judge mit **stärkerem Modell** als der Generator, fixierte Judge-Prompts, und der
  Judge selbst gegen ein kleines human-gelabeltes Set validiert (sonst misst man
  Rauschen mit Rauschen).

**Golden-Set (Datengrundlage für beide Tracks):**

- Kuratierte `Insight-Objekte`, geprüft auf erwartete *Eigenschaften* (nicht exakte
  Strings — zu brüchig).
- Edge Cases: Trainingslast-Spike, fehlende Werte (CGM-Lücke), alle Trends stabil,
  widersprüchliche Signale (HRV ↓ *und* Last ↓), Extremwerte, leere Woche.

**Adversariale Schicht (klein, wertvoll):**

- Hallucination-Stress: knifflige Objekte, prüfen ob der Post-Check hält.
- Injection über Datenfelder: Inhalt aus Metrik-/Evidenz-Feldern darf nicht als
  Instruktion wirken (geringes Risiko bei rein strukturiertem Objekt, aber billig).

**Regression-Gate (Mechanik):**

- Läuft bei **jedem Prompt-/Modell-Wechsel**; Modellversion **pinnen** (stilles
  Provider-Update = Regression).
- Pass-Kriterium: Safety-Track = 100 %, Quality-Track ≥ Schwelle.
- Metriken: Halluzinations-Rate, Evidence-Grounding-Rate, Judge-Pass-Rate und
  **Regenerations-Rate** (wie oft erzwingt der Post-Check einen Retry — hoher Wert
  = Frühwarnsignal für einen schlechten Prompt, nicht für eine zu strenge Eval).

**Bewusst weggelassen:** Referenz-Metriken (BLEU/ROUGE) — für freie Verbalisierung
wenig aussagekräftig, erzeugen nur Pseudo-Präzision.

**Reihenfolge (spiegelt Schicht-1-vor-Schicht-2):**

1. **Track A + Golden-Set** — die eigentliche Versicherung, billig, CI-tauglich,
   deckt das Haftungsrisiko.
2. **Track B + Adversariales** — Ausbaustufe.

---

## Anhang: Referenzen (Recherche 2026)

- Turing — Top 6 AI Agent Frameworks 2026
- Firecrawl — Best open source agent frameworks 2026
- SOTAAZ — AgentScope vs LangGraph vs CrewAI
- OpenAgents — CrewAI vs LangGraph vs AutoGen 2026
- Morph — AI Agent Frameworks 2026 + Claude Agent SDK
- Fast.io — 8 Best Python AI Agent Frameworks 2026
- AgentScope Repo: https://github.com/agentscope-ai/agentscope
