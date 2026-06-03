# PulseBase — Erklärt wie für ein Kind

Kein technisches Vorwissen nötig. Dieses Dokument erklärt das gesamte System so,
dass es jeder verstehen kann.

Für die technische Tiefe: [ml-deep-dive.md](ml-deep-dive.md) und [architecture.md](architecture.md).

---

## Was ist PulseBase überhaupt?

Stell dir vor, du hast eine Garmin-Uhr am Handgelenk und einen Blutzuckersensor im Arm.
Beide messen ständig Dinge über deinen Körper — Puls, Schlaf, Stress, Energie, Blutzucker.
Aber die Daten liegen auf den Servern von Garmin und Abbott, und du siehst nur das,
was deren Apps dir zeigen.

PulseBase holt diese Daten auf deinen eigenen Server zu Hause und zeigt sie dir
so, wie du es möchtest. Keine Cloud, kein Drittanbieter analysiert deine Gesundheitsdaten.
Alles gehört dir, läuft bei dir.

---

## Die drei Dienste — Wer macht was?

PulseBase besteht aus drei Diensten, die gleichzeitig laufen und miteinander reden.

### 1. Der Postbote (Sync-Service)

Der Sync-Service ist wie ein Postbote, der jeden Morgen um eine feste Uhrzeit
bei Garmin klingelt und alle neuen Daten abholt:

- Wie viele Schritte hast du gestern gemacht?
- Wie war dein Schlaf?
- Wie hoch war dein Ruhepuls?
- Wie hat sich deine Body Battery über den Tag verändert?

Für den Blutzuckersensor läuft derselbe Postbote alle **5 Minuten** — weil
Glukosewerte sich schnell ändern und möglichst aktuell sein sollen.

### 2. Das Schaufenster (API + Dashboard)

Die API ist wie ein Schaufenster: Sie nimmt die Daten aus der Datenbank und
zeigt sie dir schön aufbereitet im Browser an. Das Dashboard mit seinen
Grafiken und Karten läuft vollständig in deinem Browser — der Server schickt
nur die Zahlen, den Rest zeichnet dein Browser selbst.

### 3. Der Forscher (ML-Service)

Der ML-Service ist wie ein stiller Forscher im Hintergrund. Jeden Morgen
schaut er sich deine Daten an und stellt Fragen:

- Ist dein Ruhepuls, SpO2 oder Stresslevel heute ungewöhnlich?
- Wie fit wirst du morgen wahrscheinlich sein?
- Hängt dein Schlaf mit deinem HRV-Wert zusammen?
- Welches Energiemuster hattest du heute?
- Wie viel Trainingsbelastung trägst du gerade (ACWR)?
- Wie regelmäßig sind deine Schlafzeiten?
- Wie schnell erholt sich deine HRV nach dem Training?

Einmal pro Woche (sonntags) trainiert er seine lernenden Modelle neu — mit deinen
neuesten Daten, damit die Vorhersagen immer besser werden. Alle anderen Analysen
sind regelbasierte Berechnungen ohne Trainingsbedarf.

---

## Deine Daten — Was wird gespeichert?

| Was | Woher | Wie oft |
|-----|-------|---------|
| Schritte, Kalorien, Stress | Garmin | Täglich |
| Ruhepuls | Garmin | Täglich |
| Body Battery (alle 5 min) | Garmin | Täglich |
| Schlaf (Dauer, Phasen, Score) | Garmin | Täglich |
| HRV (Herzratenvariabilität) | Garmin | Täglich |
| Trainingszustand | Garmin | Täglich |
| Aktivitäten + GPS-Route | Garmin | Täglich |
| Blutzucker (Libre 3) | LibreLinkUp | Alle 5 min |

Alle Daten sind nach Benutzer getrennt — du siehst nur deine eigenen Werte.

---

## Passwörter — Warum werden sie nicht gespeichert?

**Die Idee mit dem Türschlüssel:**

Stell dir vor, du gibst jemandem einmalig deinen Hausschlüssel, damit er
eine Kopie macht. Danach brauchst du ihm den Originalschlüssel nie wieder geben —
er hat ja die Kopie.

Genau so funktioniert das hier: Beim ersten Verbinden gibst du einmalig dein
Garmin-Passwort ein. PulseBase meldet sich damit bei Garmin an und bekommt
einen **Token** zurück — das ist die "Schlüsselkopie". Das Token wird gespeichert,
das Passwort sofort aus dem Speicher gelöscht.

Ab dann verwendet PulseBase nur noch das Token — dein Passwort wird nie auf
einer Festplatte abgelegt, nie in einer Datenbank gespeichert, nie geloggt.

Dasselbe gilt für den LibreLinkUp-Account (Blutzucker).

**Was ist ein Token?**
Ein Token ist eine lange, zufällige Zeichenkette, die beweist, dass du einmal
korrekt angemeldet warst. Sie sieht aus wie:
`eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...`
Ohne dein Passwort zu kennen, kann PulseBase damit trotzdem Daten abrufen.

---

## ML — Was der Computer analysiert

Der ML-Service führt täglich viele Analysen durch. Hier sind die wichtigsten in einfacher Sprache:

### Analyse 1: Ist dein Puls heute ungewöhnlich?

Der Computer schaut sich deinen Ruhepuls der letzten 30 Tage an und berechnet:
Was ist dein "normaler" Wert? Wie viel schwankt er normalerweise?

Dann vergleicht er den heutigen Wert damit. Das Ergebnis heißt **z-Score**.

- **z = 0** → heute genau wie immer
- **z = +1** → heute etwas höher als normal (passiert oft, kein Grund zur Sorge)
- **z = +2** → heute deutlich höher als normal (passiert an ~5% aller Tage)
- **z = +3** → heute stark erhöht — möglicher Hinweis auf Stress, Krankheit oder Überbelastung

Wenn z über 2,0 liegt, wird der Tag als "Anomalie" markiert (rot im Dashboard).

### Analyse 2: Wie fit wirst du morgen sein?

Der Computer hat gelernt, wie sich dein Schlaf-Score und Ruhepuls auf
deinen nächsten Tag auswirken. Er hat dafür Hunderte deiner vergangenen
Tage angeschaut und Muster gefunden.

Das Ergebnis ist der **Readiness-Score** — eine Zahl von 0 bis 100:

- **80–100** → Top-Form, intensive Einheiten kein Problem
- **50–79** → Gut erholt, moderates Training passt
- **0–49** → Erholung empfohlen, lieber ruhig angehen

Das ist keine Magie — der Computer macht nichts anderes als das, was ein
Trainer auch tun würde: Muster aus der Vergangenheit auf die Zukunft übertragen.

### Analyse 3: Hängen Schlaf und HRV zusammen?

**HRV** (Herzratenvariabilität) ist ein Maß dafür, wie gut sich dein
Nervensystem erholt hat. Ein hoher HRV-Wert am Morgen ist ein gutes Zeichen.

Der Computer untersucht: Ist dein HRV am nächsten Morgen tatsächlich höher,
wenn du gut geschlafen hast? Das Ergebnis heißt **r-Wert** und liegt zwischen
-1 und +1:

- **r = +1** → Perfekter Zusammenhang: immer wenn Schlaf gut, ist HRV auch hoch
- **r = 0** → Kein Zusammenhang: Schlaf und HRV haben bei dir nichts miteinander zu tun
- **r = -1** → Gegenteiliger Zusammenhang (wäre ungewöhnlich)

Dasselbe wird auch für Schlaf→Ruhepuls und Body Battery→Ruhepuls berechnet.

### Analyse 4: Welches Energiemuster hattest du heute?

Deine Body Battery zeigt über den Tag, wie viel Energie du hattest.
Der Computer gruppiert alle deine Tage in drei Muster:

- **Stabil hoch** — Morgens gut gestartet, abends noch viel übrig
- **Erholung** — Mittleres Niveau, normaler Alltag
- **Erschöpft** — Stark abgefallen, viele Belastungsspitzen

Das Muster wird täglich als kleiner Status-Chip im Tagesstatus-Hero angezeigt.
Die Detail-Seite (`/metrics/battery-pattern`) zeigt die Feature-Aufschlüsselung für den aktuellen Tag.

---

## Blutzucker (Libre 3)

Der Libre 3 ist ein Sensor, der kontinuierlich den Blutzucker misst —
alle paar Minuten einen neuen Wert, 24 Stunden am Tag.

Die Werte werden in **mg/dL** (Milligramm pro Deziliter) angegeben.
Normalbereich für Nicht-Diabetiker: ca. 70–140 mg/dL.

**Was bedeuten die Trend-Pfeile?**

| Pfeil | Bedeutung | Was passiert |
|-------|-----------|--------------|
| ↓↓ | Fällt schnell | Blutzucker sinkt stark |
| ↓ | Fällt | Blutzucker sinkt |
| → | Stabil | Kein starker Trend |
| ↑ | Steigt | Blutzucker steigt |
| ↑↑ | Steigt schnell | Blutzucker steigt stark |

**Hypo** = Blutzucker zu niedrig (unter ~70 mg/dL) — kann gefährlich sein.
**Hoch** = Blutzucker zu hoch (über ~180 mg/dL) — Hinweis auf starke Mahlzeit oder Insulinbedarf.

PulseBase ist kein Medizinprodukt und gibt keine medizinischen Empfehlungen.
Die Werte dienen ausschließlich der persönlichen Übersicht.

---

## Einstellungen & Accounts

Die Einstellungsseite (`/settings`) zeigt auf einen Blick:

- **Account** — Dein Name und deine E-Mail-Adresse
- **Garmin Connect** — Verbunden oder nicht; Button zum Verbinden oder Trennen
- **LibreLinkUp** — Verbunden oder nicht; Button zum Verbinden oder Trennen

**Was passiert beim Trennen?**

Beim Trennen von LibreLinkUp werden **alle gespeicherten Glukosewerte** aus
der Datenbank gelöscht — inklusive historischer Daten. Der verschlüsselte Token
in der Datenbank wird ebenfalls gelöscht. Das kann nicht rückgängig gemacht werden.

Beim Trennen von Garmin bleiben die bereits synchronisierten Aktivitäts- und
Gesundheitsdaten erhalten — nur neue Syncs werden gestoppt.

---

## Multi-User

PulseBase unterstützt mehrere Benutzer auf demselben Server. Jeder Benutzer
kann sich selbst registrieren (`/register`) und seinen eigenen Garmin-Account
sowie seinen eigenen LibreLinkUp-Account verknüpfen.

Alle Daten sind strikt nach Benutzer-ID getrennt — ein Benutzer sieht
niemals die Daten eines anderen.
