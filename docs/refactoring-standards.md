# Refactoring Standards

Verbindliche Regeln für jeden Refactor in diesem Projekt. Ergänzt die allgemeinen
Regeln in [`claude/app-rules.md`](../claude/app-rules.md) und
[`CLAUDE.md`](../CLAUDE.md).

---

## 1. Structure & Length

- **Dateien > 500 Zeilen** in logische Module aufteilen (Feature-Schnitt, nicht technisch).
- **Eine Funktion = eine Verantwortung** (Single Responsibility Principle).
- **Max. Funktionslänge: 30–50 Zeilen.** Längere Funktionen sind ein Refactor-Signal.
- Lange Dateien werden als Package reorganisiert: Ordner + `__init__.py` mit Re-Exports
  → keine Breaking Changes an Import-Stellen.

### Beispiel — db.py aufteilen

```
src/db.py  →  src/db/
               ├── __init__.py   # from .users import *; from .activities import *; …
               ├── pool.py
               ├── users.py
               └── activities.py
```

---

## 2. Naming & Readability

- Namen beschreiben **was** das Objekt ist / tut, nicht wie es implementiert ist.
- Private Hilfsfunktionen: führender Unterstrich `_helper()`.
- Tote Code-Blöcke (auskommentierter Code, nie aufgerufene Funktionen) vollständig
  entfernen — kein „für später" stehen lassen.
- Kommentare nur, wenn **Warum** nicht aus dem Code hervorgeht: versteckter Constraint,
  nicht-offensichtliche Invariante, Workaround für konkreten Bug.
- Keine Kommentare, die beschreiben **was** der Code tut — das leisten die Namen.
- Docstrings nur bei nicht-offensichtlicher Logik: Schwellwerte, Heuristiken,
  mathematische Formeln. Format: ein prägnanter Satz + Parameter/Return wenn nötig.

---

## 3. Security

- **Keine Klartext-Secrets** im Code (Passwörter, API-Keys, Tokens).
  Alle Credentials aus Umgebungsvariablen lesen (Pydantic `BaseSettings`).
- `eval`, `exec`, `subprocess.shell=True` mit User-Input sind verboten.
- Shell-Kommandos nie mit User-Input zusammenbauen; Argumente als Liste übergeben.
- SQL ausschließlich mit Prepared Statements / parametrisierten Queries (`$1`, `$2`…).
- Dynamische SQL-Tabellennamen nur gegen Allowlist validieren und mit
  `# nosec B608` + Kommentar kennzeichnen.
- Credentials dürfen nicht in Log-Nachrichten erscheinen (auch nicht in Debug-Level).

---

## 4. Error Handling

- **Kein bloßes `except:` oder `except Exception:`** ohne spezifischen Grund.
  Fange die engstmögliche Exception-Klasse.
- Wenn ein breiter `except Exception` unvermeidbar ist (z. B. Plugin-Code, externer
  Client): Logging mit `logger.warning("… %s", exc)` und Kommentar warum.
- Leere `except`-Blöcke sind verboten — mindestens `logger.debug` oder `pass` mit
  Begründung.
- Fehler an System-Grenzen (API-Eingabe, externer Service) mit spezifischer Exception
  wrappen und re-raisen; interne Fehler propagieren lassen.

### Beispiel

```python
# Falsch
except Exception:
    self._client.login()

# Richtig
except (OSError, RuntimeError) as exc:
    logger.warning("token login failed (%s), retrying", exc)
    self._client.login()
```

---

## 5. Standards & Consistency

- Formatierung durch **ruff** (PEP 8, max. 88 Zeichen). Nie manuell anpassen.
- Type Hints auf allen public Funktionen (Parameter + Return).
- Ungenutzte Imports entfernen (ruff meldet F401).
- Import-Reihenfolge: stdlib → third-party → local (ruff-isort erzwingt das).
- Kein gemischtes Deutsch/Englisch in Identifier-Namen; Log-Nachrichten können
  Deutsch bleiben (bestehende Konvention).
- Pydantic-Modelle für alle strukturierten Inputs an API-Grenzen.

---

## Output-Format nach jedem Refactor

Jeder Refactor-Commit liefert:

1. **Refactored Code** — geänderte Dateien im Diff (keine Inline-Doku nötig).
2. **Summary of Changes** — Kurzliste: welche Datei/Funktion, was geändert, warum.
3. **Flagged Issues** — Punkte, die manuellen Review brauchen (DB-Migrationen,
   nosec-Markierungen, Breaking Changes an externen Schnittstellen).

### Beispiel-Summary

```
api/src/db.py → db/ Package (8 Module)
  - pool.py: Connection-Pool-Management ausgelagert
  - seizures.py: get_seizure_risk() in 7 _check_*()-Hilfsfunktionen decomponiert
  - __init__.py: alle public functions re-exportiert → keine Import-Änderung

Flagged:
  - db/seizures.py:_check_missed_spo2(): Schwellwert 0.5 heuristisch — validieren
```

---

## Checkliste vor PR

```
[ ] Keine Datei > 500 Zeilen
[ ] Keine Funktion > 50 Zeilen
[ ] Kein bloßes except Exception ohne Logging + Kommentar
[ ] Kein auskommentierter Code
[ ] ruff check . && ruff format --check . grün
[ ] mypy src/ --ignore-missing-imports grün
[ ] bandit -r src/ -q grün
[ ] alle Tests grün (make test)
```
