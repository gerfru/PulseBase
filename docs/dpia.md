# Datenschutz-Folgenabschätzung (DPIA)

**Gemäß Art. 35 DSGVO**

> **Status:** Vorlage — vor erstem Mehrbenutzerbetrieb ausfüllen und archivieren.

---

## 1. Verantwortlicher

| Feld | Wert |
|------|------|
| Name / Organisation | _[ausfüllen]_ |
| Adresse | _[ausfüllen]_ |
| E-Mail | _[ausfüllen]_ |
| Datenschutzbeauftragter (falls ernannt) | _[ausfüllen oder „nicht ernannt (§ 38 BDSG)"]_ |

---

## 2. Beschreibung der Verarbeitungstätigkeit

PulseBase ist eine selbst gehostete Gesundheits- und Fitness-Tracking-Anwendung.
Sie aggregiert Garmin-Gerätedaten (Herzfrequenz, HRV, Schlaf, Aktivitäten, GPS-Tracks)
und optionale Glukosedaten (LibreLink) für persönliche Analyse und ML-gestützte Prognosen.

**Zweck:** Persönliches Gesundheitsmonitoring und Trainingsoptimierung.

**Rechtsgrundlage:** Art. 9 Abs. 2 lit. a DSGVO (ausdrückliche Einwilligung für besondere
Kategorien personenbezogener Daten — Gesundheitsdaten).

---

## 3. Verarbeitete Datenkategorien

| Kategorie | Beispiele | Art. 9-Daten? |
|-----------|-----------|--------------|
| Identifikationsdaten | E-Mail, Name | Nein |
| Körperdaten | Herzfrequenz, HRV, SpO₂, Schlaf-Score, Stresswert | **Ja** |
| Aktivitätsdaten | Aktivitätstyp, Dauer, Distanz, Kalorienverbrauch | Ja (indirekt) |
| GPS-Daten | Koordinaten (gerundet auf 4 Dezimalstellen, ~11 m) | Ja (indirekt) |
| Glukosedaten | Blutzucker-Trends (LibreLink, optional) | **Ja** |
| Epilepsie-Tagebuch | Anfallszeiten, Typen, Schweregrade (optional) | **Ja** |
| Systemdaten | IP-Hash (Consent-Log), Session-Token | Nein |
| ML-Prognosen | Readiness-Score, Anomalie-Flags | Ja (abgeleitet) |

---

## 4. GPS-Verarbeitung

Garmin-Trackpunkte enthalten GPS-Koordinaten mit bis zu 7 Dezimalstellen (~1 cm Genauigkeit),
die Wohnort oder Arbeitsort offenlegen können.

**Maßnahme (Datenminimierung, Art. 5 Abs. 1 lit. c):** Koordinaten werden bei der Speicherung
auf 4 Dezimalstellen (~11 m) gerundet. Bestehende Daten wurden per Migration V29 bereinigt.
Diese Genauigkeit reicht für Kartenvisualisierungen aus.

---

## 5. Drittdienstleister

| Dienst | Zweck | Datenübertragung | Rechtsgrundlage |
|--------|-------|-----------------|-----------------|
| Garmin Connect API | Aktivitäts- und Gesundheitsdaten abrufen | OAuth-Token | Art. 6 Abs. 1 lit. a |
| Abbott LibreLink (optional) | Glukosedaten | Direkte Verbindung | Art. 9 Abs. 2 lit. a |
| Resend | Transaktions-E-Mails (Verifikation) | E-Mail-Adresse | Art. 6 Abs. 1 lit. b |
| Sentry (optional) | Fehlermonitoring | Stack Traces (keine Gesundheitsdaten) | Art. 6 Abs. 1 lit. f |
| Better Stack (optional) | Uptime-Monitoring | HTTP-Status, keine Nutzdaten | Art. 6 Abs. 1 lit. f |

---

## 6. Betroffenenrechte

| Recht | Umsetzung |
|-------|-----------|
| Auskunft (Art. 15) | Auf Anfrage via E-Mail; Account-Export geplant |
| Berichtigung (Art. 16) | Profil-Einstellungen unter `/settings` |
| Löschung (Art. 17) | Account-Löschung löscht alle Nutzdaten; Consent-Audit-Log pseudonymisiert (V30) |
| Einschränkung (Art. 18) | Auf Anfrage via E-Mail |
| Datenübertragbarkeit (Art. 20) | _[geplant / noch nicht implementiert]_ |
| Widerspruch (Art. 21) | Garmin-Verknüpfung unter `/settings` trennbar |

---

## 7. Automatisierte Entscheidungsfindung (Art. 22)

PulseBase verwendet ML-Prognosen (Readiness-Score, Anomalie-Erkennung). Diese dienen
ausschließlich informativen Zwecken und führen zu **keinen automatisierten Entscheidungen**
mit rechtlicher oder ähnlich erheblicher Wirkung. Der Nutzer trifft alle Entscheidungen selbst.

EU AI Act Art. 52: Prognosen sind als KI-generiert gekennzeichnet (Disclaimer im UI).

---

## 8. Risikobewertung

| Risiko | Eintrittswahrsch. | Schwere | Maßnahme |
|--------|------------------|---------|----------|
| Unbefugter Zugriff auf Gesundheitsdaten | Mittel | Hoch | HTTPS-only, bcrypt-Passwörter, Session-Tokens |
| Datenverlust | Niedrig | Hoch | Tägliche verschlüsselte Backups |
| GPS-Adress-Rückschluss | Mittel | Mittel | 4-Dezimalstellen-Rundung (V29) |
| Consent-Audit-Verlust bei Nutzerlöschung | Niedrig | Mittel | SET NULL statt CASCADE (V30) |
| Modell-Manipulation (ML) | Niedrig | Mittel | SHA-256-Sidecar-Verifikation vor joblib.load |

---

## 9. Technische und organisatorische Maßnahmen (TOMs)

- Verschlüsselung in Transit: TLS 1.2+ (Caddy)
- Verschlüsselung at Rest: _[Festplattenverschlüsselung des Hosts aktivieren]_
- Passwort-Hashing: bcrypt (cost 12)
- Session-Sicherheit: HttpOnly, Secure, SameSite=Lax Cookies
- Rate Limiting: Login-Lockout nach 5 Fehlversuchen
- CSP: `style-src 'nonce-…'`, keine `unsafe-inline`
- Secrets: `.env`-Dateien, nicht im Git-Repository
- Backup: tägliche Postgres-Dumps, AES-verschlüsselt

---

## 10. Konsultation der Aufsichtsbehörde

_[Wenn nach Risikoabwägung eine vorherige Konsultation gem. Art. 36 erforderlich: Behörde und Datum eintragen. Andernfalls: „Keine vorherige Konsultation erforderlich."]_

---

## 11. Überprüfung

Diese DPIA ist vor signifikanten Änderungen der Datenverarbeitung zu aktualisieren.

**Letzte Überprüfung:** _[Datum]_
**Nächste geplante Überprüfung:** _[Datum + 12 Monate]_
