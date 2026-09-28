# ADR-0007: Einen strukturierten Insights-Bericht statt Segmenttexten erzeugen

## Status

Accepted — 2026-09-28

Die bedarfsgetriebene Generierung und manuelle Regenerierung wurden durch
[ADR-0008](0008-daily-insights-cadence.md) ersetzt; Aufbau und Safety-Gates
dieser Entscheidung bleiben gueltig.

Ersetzt ausschließlich die Drei-Segmente-Präsentation aus [ADR-0003](0003-ai-weekly-insights.md). Das rollierende Sieben-Tage-Fenster aus [ADR-0004](0004-rolling-window-cadence.md), die deterministische Berechnung der Kennzahlen und die bestehenden Datenschutz- und Safety-Invarianten bleiben bestehen.

## Context

Die bisherigen Varianten Hobby, Pro und Profi verwendeten dieselben Fakten. Insbesondere beim deterministischen Fallback unterschied sich die Auswertung hauptsächlich im Hinweistext. Die Nutzeransicht soll stattdessen einen einzigen, ausführlicheren und übersichtlich gegliederten Bericht bieten. Die bisherigen Segmenttexte sind nur ein regenerierbarer Cache, keine Quelldaten.

## Decision Drivers

- Ein verständlicher Bericht ohne Auswahl nahezu gleicher Varianten.
- Zahlen aus dem deterministischen Faktenkern; das optionale LLM formuliert nur die Einordnung.
- Nachvollziehbare Abschnitte auch ohne verfügbares oder erfolgreiches LLM.
- Der Output-Post-Check bleibt Voraussetzung für die Auslieferung von Modelltext.
- Keine neue Datenbankmigration nur für den Wechsel eines Cache-Formats.

## Considered Options

1. Drei Textvarianten beibehalten und nur die Auswahl aus der UI entfernen: einfache Oberfläche, aber doppelte Generierung und ein irreführender API-Vertrag bleiben.
2. Eine Auswertung mit festem Aufbau erzeugen: ein Text pro Zeitfenster; klare Vertragsänderung, aber bisherige Texte müssen neu generiert werden.

## Decision

Option 2: Pro Nutzer und `period_end` entsteht genau ein Bericht. Er enthält die Abschnitte `Zusammenfassung`, `Kennzahlen`, `Einordnung` und `Hinweis` in dieser Reihenfolge. Der Hinweis wird bei Modelltext deterministisch angehängt; fehlt ein Abschnitt oder schlägt ein bestehender Safety-Check fehl, greift nach begrenzten Versuchen der gegliederte Fallback. Der Prompt fordert mehrere vollständige Sätze und für jede vorhandene Kennzahl eine eigene Zeile. Der Fallback enthält ausschließlich aus den geprüften Fakten abgeleitete Werte, Trends und vorhandene Niveau-Bänder; er behauptet keine Ursachen.

Die bisherige Prompting-only-Architektur bleibt: keine Internet-Recherche und kein Transfer persönlicher Kennzahlen an Suchdienste. Das lokale LLM bleibt optional; der identifierfreie Prompt ist nicht anonymisiert. Die konfigurierbare Modelladresse und eine mögliche externe Übertragung sind weiterhin gesondert abzusichern (siehe [Sicherheitsdesign](../design-secure-ai-insights.md)).

### Schnittstelle und Cache

`GET /api/insights` liefert für `status: ready` genau ein `text`-Objekt mit `body`, `generator` und `model_id`, keine `texts`-Map mehr. `POST /api/insights/regenerate` erneuert diesen Bericht. Ein `segment`-Query-Parameter wird abgewiesen. API und Browser müssen daher zusammen ausgerollt werden; für andere Clients ist die Änderung inkompatibel. In diesem Repository wurde nur der Browser als Verbraucher gefunden; weitere externe Verbraucher sind nicht verifiziert.

Die bestehenden Tabellen bleiben erhalten: `weekly_insights` speichert die Kennzahlen, `weekly_insight_texts` einen Text mit dem technischen Cache-Schlüssel `report`. Ohne `report`-Zeile ist ein alter Drei-Segmente-Eintrag ein Cache-Miss und wird beim nächsten Aufruf neu erzeugt. Beim atomaren Speichern des Berichts werden ältere Segmenttexte desselben Nutzers und Zeitraums gelöscht, damit auch nach einem Rollback keine veralteten Texte neben neuen Zahlen stehen; das alte System kann den Cache dann bei Bedarf neu generieren. Es gehen keine Quelldaten verloren. Die Generierung bleibt vorerst bedarfsgetrieben; eine Vorabberechnung nach Daten-Sync ist nicht Bestandteil dieser Entscheidung.

## Consequences and Verification

- Weniger UI- und Generierungsvarianten sowie genau eine aktive Textversion pro Zeitfenster.
- Ein längerer LLM-Text kann mehr Inferenzzeit benötigen; ein Modell, das die Struktur nicht einhält, führt zum Fallback.
- Bestehende Cache-Texte erscheinen nicht automatisch im neuen Format und werden beim ersten Aufruf neu erstellt.
- Tests für API-Vertrag, Cache, Safety-Gate, Zahlen mit gegenläufigen Trends und HTML-Escaping prüfen den Wechsel. Reale Inferenzqualität und Inferenzdauer sind damit noch nicht gemessen.
- Dauerhafte Hintergrundjobs und Frische nach Daten-Sync sind in [ADR-0008](0008-daily-insights-cadence.md) entschieden; eine technisch erzwungene interne Inference-Adresse bleibt offen (siehe [Sicherheitsdesign](../design-secure-ai-insights.md)).
