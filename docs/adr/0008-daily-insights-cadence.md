# ADR-0008: Insights-Bericht taeglich um 05:00 Wiener Zeit

## Status

Accepted. Ersetzt die bedarfsgetriebene Generierung und den manuellen
Regenerierungsendpunkt aus [ADR-0007](0007-unified-insights-report.md).
Der Aufbau des einzelnen Berichts, seine geprueften Fakten und das optionale
lokale LLM mit deterministischem Fallback bleiben erhalten.

## Kontext

Ein Seitenaufruf loeste bislang die Generierung aus. Ein expliziter POST konnte
denselben Zeitraum erneut berechnen. Bei mehreren API-Prozessen oder einem
Neustart war eine In-Memory-Task nicht dauerhaft. Die ML-Inferenz soll nach
erfolgreichen Syncs unabhaengig laufen; der Insights-Bericht benoetigt dagegen
einen festen Zeitpunkt und nur die zu diesem Zeitpunkt verfuegbaren Werte.

## Entscheidung

- APScheduler plant um 05:00 `Europe/Vienna` einen Auftrag je aktivem Nutzer mit
  verknuepfter Garmin- oder Libre-Quelle ein. `period_end` ist gestern in Wien;
  das Berichtsfenster umfasst die sieben abgeschlossenen lokalen Kalendertage.
  Sommer- und Winterzeit werden ueber die Zeitzone behandelt, nicht ueber einen
  festen UTC-Offset.
- Die Migration V37 speichert pro `(user_id, period_end)` einen dauerhaften
  Auftrag. `ON CONFLICT DO NOTHING`, `FOR UPDATE SKIP LOCKED`, begrenzte
  Wiederholungen und Lease-Recovery ermoeglichen mehrere API-Prozesse und
  Neustarts. Ein Advisory-Lock am gespeicherten Bericht verhindert ein
  Ueberschreiben. Die Queue enthaelt keine Gesundheitsdaten oder Berichtstexte;
  Fehlercodes und Logs enthalten keine exception message.
- `GET /api/insights` liest nur: fuer den Zielzeitraum einen fertigen Bericht
  oder dessen Jobstatus (`pending`, `failed`, `stale`) mit dem letzten frueheren,
  fertigen Bericht samt dessen tatsaechlichem Zeitraum. Die Browseransicht
  aktualisiert um 05:00 und pollt nur waehrend `pending`. Der manuelle
  `POST /api/insights/regenerate` und sein Button entfallen. API und Browser
  muessen gemeinsam ausgerollt werden; externe Verbraucher sind nicht verifiziert.
- Bereits angelegte Jobs duerfen nach einem Neustart fertiggestellt werden.
  War der Scheduler um 05:00 vollstaendig ausgefallen, wird fuer diesen Tag
  kein neuer Job nachtraeglich angelegt. Spaetere Syncs aendern einen
  veroeffentlichten Bericht nicht. `INSIGHTS_DAILY_ENABLED=false` stoppt
  Scheduler und Worker fuer einen Rollback, nicht die Leseansicht.
- 05:00 ist der Zeitpunkt der Einplanung, kein Datenbank-Snapshot. Der Worker
  liest die Quellen bei der Bearbeitung des jeweiligen Nutzers; spaeter
  verarbeitete Jobs koennen daher Werte beruecksichtigen, die erst nach 05:00
  synchronisiert wurden. Ein exakt auf 05:00 eingefrorener Datenstand wuerde
  eine gesonderte Snapshot-Persistenz erfordern und ist nicht umgesetzt.
- Die vorhandene `ml_requested`-Queue bleibt: nach jedem erfolgreichen Sync
  wird ML angestossen (dicht folgende Auftraege koennen koaleszieren).
  Die unabhaengige taegliche ML-Inferenz fuer andere Ansichten bleibt ebenfalls.
  Der 05:00-Bericht verwendet die vorhandenen ML-Werte; eine rueckwirkende
  Berechnung fehlender ML-Werte fuer gestern ist nicht vorgesehen.

## Folgen und Pruefung

Pro Nutzer und Zielzeitraum wird nur ein fertiger Bericht publiziert; technische
Wiederholungen koennen auftreten. Ein fehlgeschlagener oder verpasster Tageslauf
laesst den letzten fertigen Bericht sichtbar, ohne dessen Datum als aktuell
auszugeben. Migration und Grants sind vor dem API-Release im Teststack zu
pruefen. UTC-Termin, Sommer-/Winterzeit, Retry/Recovery, API-Zustaende und
Frontend-Darstellung sind durch gezielte Tests abzudecken.
