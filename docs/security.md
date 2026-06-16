# PulseBase — Security Reference

Dieses Dokument erklärt **warum** PulseBase welche Sicherheitsmaßnahmen trifft, nicht nur was implementiert ist. Es ist die zentrale Referenz für alle Sicherheitsentscheidungen — von der Entwurfsphase bis zur laufenden Wartung.

**Verwandte Dokumente:**
- [`production-hardening.md`](production-hardening.md) — Deployment-Checkliste und konkrete Befehle
- [`review-open-items.md`](review-open-items.md) — offene Punkte aus den Reviews (App/UX/Style)
- [`architecture.md`](architecture.md) — Systemaufbau und Datenflüsse

---

## 1. Threat Model

### 1.1 Was schützen wir?

PulseBase speichert Gesundheitsdaten. Diese fallen unter **Art. 9 DSGVO** ("besondere Kategorien personenbezogener Daten") und sind damit der höchsten gesetzlichen Schutzklasse zugeordnet.

| Asset | Kritikalität | Beispiel |
|-------|-------------|---------|
| Gesundheitsdaten (HRV, Schlaf, Glukose, Aktivitäten) | Sehr hoch | Epilepsie-Events, HRV-Trends |
| Garmin/LibreLink-Zugangsdaten (Token) | Sehr hoch | Ermöglicht Zugriff auf externen Health-Account |
| Benutzerkonto (E-Mail, Passwort-Hash) | Hoch | Identität, Login-Möglichkeit |
| Session-Token (Cookie) | Hoch | Aktive Sitzung aller Nutzer |
| App-Secrets (SESSION_SECRET, FERNET_KEY) | Sehr hoch | Kompromittierung betrifft alle Nutzer |

### 1.2 Wer greift an?

PulseBase ist eine öffentlich zugängliche Self-Hosted-App mit echten Nutzern. Gesundheitsdaten nach Art. 9 DSGVO erfordern das volle Threat Model — kein reduzierter Homelab-Scope.

| Threat Actor | Motivation | Wahrscheinlichkeit |
|---|---|---|
| Automatisierte Scanner (Shodan, Masscan) | Credential Stuffing, bekannte CVEs ausnutzen | Hoch |
| Opportunistische Angreifer | Niedrig hängende Früchte (schwache Passwörter, Standard-Credentials) | Mittel |
| Gezielte Angreifer | Gesundheitsdaten exfiltrieren, Konto übernehmen | Mittel |
| Supply Chain (kompromittierte Abhängigkeit) | Code-Ausführung im Container | Mittel |
| Physischer Zugriff auf den Server | Daten-Dump, Token-Extraktion | Sehr niedrig |

### 1.3 Angriffsfläche

```
[Internet]
     │
     ▼ 443/tcp (einziger eingehender Vektor)
[Caddy]  ←── homelab-gateway (Heim) oder gebündelt via make up-public (SaaS)
     │
     ▼ HTTP intern
[FastAPI]   ←── [Garmin Connect API] (ausgehend, OAuth-ähnlich mit Token)
     │           [LibreLink API] (ausgehend, Token-Auth)
     │
     ▼ asyncpg
[TimescaleDB]  (nicht exponiert, nur internes Docker-Netz)
```

**Eingehende Angriffsvektoren:**
1. HTTP-Endpunkte (Auth-Bypass, IDOR, Injection, CSRF, XSS)
2. Login-Formulare (Brute Force, Credential Stuffing)
3. File-Upload-ähnliche Eingaben (z.B. Seizure Notes mit Nutzerdaten)

**Ausgehende Risiken:**
1. SSRF durch manipulierte Garmin/Libre-Credentials (kein User-Input in URL-Aufbau — mitigiert)
2. Kompromittierter Upstream (Garmin Connect oder LibreLink) liefert manipulierte Daten

### 1.4 Explizit außerhalb des Scope

- **DDoS:** Mitigation durch Cloudflare/Caddy; kein eigener Schutz implementiert
- **Seitenkanal-Angriffe** auf der Hardware (außerhalb des Software-Scopes)
- **Angriffe nach vollständiger Host-Kompromittierung** (root auf Mac mini)

---

## 2. Datenschutzeinstufung

### 2.1 Datenkategorien und Speicherort

| Datenkategorie | DSGVO-Klasse | Gespeichert in | Schutz |
|---|---|---|---|
| Gesundheitsdaten (Aktivitäten, HRV, Schlaf, Glukose, Anfälle) | Art. 9 (hoch) | TimescaleDB | DB auf internem Netz, kein direkter Zugriff |
| Garmin/LibreLink Auth-Token | Art. 9 indirekt (Zugriff auf Gesundheitsdaten) | `user_tokens`-Tabelle | Fernet-verschlüsselt at rest |
| E-Mail, Passwort-Hash | Art. 6 | `users`-Tabelle | bcrypt, nie Plaintext |
| Session-Cookie | — | Client-Browser | httpOnly, secure, sameSite=Strict, max_age=3600 (1h) |
| Consent-Audit-Log | Art. 5(2) Rechenschaftspflicht | `user_consents`-Tabelle | IP als SHA-256-Hash (keine Reverse-Lookup-Möglichkeit) |
| Strukturierte Logs | — | stdout / Container-Log | Keine PII (E-Mail, IP nie geloggt) |
| ML-Modelle | — | `ml-models`-Volume | Aggregiert, kein Rückschluss auf Individuen |

### 2.2 Datenminimierung (Privacy by Design)

- Garmin-Passwörter werden **nie** gespeichert — nur der nach Login erhaltene Session-Token
- IP-Adressen werden im Consent-Log nur als SHA-256-Hash gespeichert (V21-Migration)
- `export_user_data` schließt `password_hash` explizit aus
- Logs enthalten keine E-Mail-Adressen, keine Passwörter, keine IP-Adressen

---

## 3. Authentication & Session Management

### 3.1 Passwort-Sicherheit

**Warum bcrypt direkt (nicht passlib)?**
passlib ist mit `bcrypt>=4.0` inkompatibel — es würde ohne Fehler einen schwächeren Hash-Algorithmus fallen. bcrypt direkt gibt beim Start einen Fehler wenn die Library-Version nicht unterstützt wird.

```python
# Sicherheitsrelevante Parameter:
bcrypt.hashpw(password.encode(), bcrypt.gensalt())  # gensalt() ohne Argument → Default 12 Rounds
```

- Der Default von `bcrypt.gensalt()` ist `rounds=12`, also 2¹² = 4096 Hash-Iterationen — ~300ms pro Versuch, macht Brute Force unpraktikabel
- Timing-sicherer Vergleich: `bcrypt.checkpw()` ist constant-time (keine timing-basierten Enumeration-Angriffe)

**Warum DUMMY_HASH?**
Ohne Dummy-Hash: Login mit nicht-existierender E-Mail → ~0ms Response (kein bcrypt-Aufruf). Login mit falscher E-Mail bei existierendem User → ~300ms (bcrypt läuft). Angreifer kann E-Mails validieren durch Timing-Messung.

```python
DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode()
# Einmal beim App-Start berechnet, dann immer genutzt wenn User nicht existiert
```

### 3.2 Session-Management

PulseBase nutzt **signierte Cookie-Sessions** (Starlette `SessionMiddleware`) statt JWT.

**Warum kein JWT?**
JWT erfordert Token-Invalidierung (z.B. bei Konto-Kompromittierung) entweder via Datenbank-Lookup (dann verliert man Statelessness) oder via kurze TTL + Refresh-Token-Rotation (erhöhte Komplexität). Für ein Single-Server-Deployment bringt JWT keinen Vorteil.

**Session-Cookie-Eigenschaften** (gesetzt in `api/src/main.py`, `SessionMiddleware`):
- `httpOnly=True` — kein JavaScript-Zugriff (Starlette-Default; reduziert Cookie-Diebstahl via XSS)
- `secure=True` (wenn `HTTPS_ONLY=true`, via `https_only=settings.https_only`) — Cookie nur über HTTPS übertragen
- `sameSite="strict"` — Cookie wird bei Cross-Site-Requests gar nicht mitgesendet (stärker als `lax`)
- `max_age=3600` — Session läuft nach 1 Stunde ab (signiertes Cookie mit eingebettetem Ablauf, kein reines Browser-Session-Cookie)

**Session-Fixation verhindern:**
```python
request.session.clear()           # Alte Session-ID wegwerfen
request.session["user_id"] = ...  # Neue Session beginnen
```
Ohne `clear()` könnte ein Angreifer eine Session-ID in einen Link einbauen, das Opfer damit einloggen lassen und dann die vorbekannte Session-ID nutzen.

### 3.3 Account-Lockout

**Warum konto-basiert statt nur IP-basiert?**
IP-basiertes Rate Limiting (slowapi) schützt gegen volumetrische Brute Force. Konto-basierter Lockout schützt gegen verteilte Angriffe (viele IPs, ein Ziel-Account).

```
5 Fehlversuche → locked_until = NOW() + 15 Minuten
Fehlversuch während Lockout → kein neuer bcrypt-Aufruf (Timing-safe, keine Lockout-Extension)
Erfolgreicher Login → failed_login_attempts = 0
```

**DoS-Gegenmaßnahme:** Der Lockout könnte von einem Angreifer genutzt werden um legitime User auszusperren. Mitigation: E-Mail-Benachrichtigung informiert den echten Nutzer, `locked_until` läuft automatisch ab (kein Admin-Eingriff nötig).

### 3.4 Password-Reset-Flow

**Design-Prinzip: Non-leaking**
`POST /auth/reset-request` antwortet immer mit HTTP 200 und gleicher Message, unabhängig ob die E-Mail-Adresse existiert. Würde der Server differenzieren, könnten Angreifer den Endpunkt zur E-Mail-Enumeration nutzen.

**Token-Design (DB-backed, `api/src/auth_tokens.py`):**
```python
# Reset-Token ist NICHT stateless — Zufallswert wird gehasht in der DB abgelegt
raw = secrets.token_urlsafe(32)
token_hash = hashlib.sha256(raw.encode()).hexdigest()
expires_at = datetime.now(timezone.utc) + timedelta(seconds=900)  # _RESET_MAX_AGE = 15 min
await save_reset_token(user_id, token_hash, expires_at)
# Validierung per DB-Lookup auf den SHA-256-Hash, nicht per HMAC-Signatur
```

- Nur der SHA-256-**Hash** liegt in der DB — ein DB-Leak gibt keine nutzbaren Tokens preis
- 15min TTL (`_RESET_MAX_AGE = 900`) — kurzes Fenster reduziert Risiko bei abgefangener E-Mail
- **Token-Invalidierung nach Verwendung:** Nach erfolgreichem Reset wird der DB-Eintrag entwertet — Replay-Angriffe mit demselben Token schlagen fehl.
- **Alle drei** Token-Typen sind DB-backed single-use (Reset 15 min, E-Mail-Verify 24h, Account-Delete 1h): ein Zufallswert wird gemailt, nur sein SHA-256-Hash + Ablauf wird gespeichert, serverseitig geprüft und bei Verwendung gelöscht (V26 hat Verify/Delete von stateless `itsdangerous` auf DB-backed umgestellt — keine replaybaren Tokens mehr).

### 3.5 Garmin/LibreLink Credential-Handling

Garmin- und LibreLink-Passwörter werden **niemals** gespeichert. Der Flow (identisch für beide Services):
1. User gibt Credentials im `/garmin/link` oder `/libre/link`-Formular ein
2. Client-Library authenticiert sich und erhält einen Session-Token
3. Token wird **ausschließlich in einem `tempfile.TemporaryDirectory()`** geschrieben (kein permanenter Pfad auf Disk)
4. Token-Daten werden Fernet-verschlüsselt und in der DB gespeichert (`user_tokens`-Tabelle, V20)
5. Tempdir (und damit der Klartext-Token) wird beim Verlassen des Context-Managers automatisch gelöscht
6. Credentials sind nach dem Request aus dem Speicher weg

**Fernet-Verschlüsselung:**
```python
from cryptography.fernet import Fernet
f = Fernet(settings.fernet_key)
encrypted = f.encrypt(token_data)   # AES-128-CBC + HMAC-SHA256
decrypted = f.decrypt(encrypted)
```

Fernet bietet authenticated encryption — manipulierte Ciphertext-Blöcke werden erkannt und verworfen. Der `FERNET_KEY` wird beim App-Start validiert; die App crasht mit `ValueError` wenn der Key ungültig oder leer ist.

---

## 4. Autorisierung

### 4.1 Defense in Depth: 3 Schichten

```
Request
  │
  ▼ Schicht 1: SessionMiddleware
  │   └── Prüft ob session["user_id"] existiert
  │       → 401 / Redirect /login wenn nicht
  │
  ▼ Schicht 2: require_user() Dependency (deps.py)
  │   └── Prüft session["user_id"] und lädt den User aus der DB
  │       → NeedsLogin (Redirect /login) wenn Session fehlt oder User nicht existiert
  │       (Die E-Mail-Verifikation wird beim LOGIN erzwungen, nicht pro Request —
  │        siehe auth_helpers._handle_unverified_email)
  │
  ▼ Schicht 3: Data Access Layer (db/*.py)
      └── Jede Query bindet user_id: WHERE user_id = $1
          → BOLA unmöglich — andere User-Daten nicht abrufbar
```

**Warum die 3. Schicht die wichtigste ist:**
Schicht 1 und 2 können durch Fehler im Routing oder durch vergessene `require_user()`-Dependency umgangen werden. Die 3. Schicht ist schwerer zu vergessen, weil jede Query explizit `user_id` als Parameter haben muss.

### 4.2 BOLA (Broken Object Level Authorization)

Gefahr ohne BOLA-Schutz: `GET /api/activities/12345` würde Aktivität 12345 zurückgeben, egal welchem User sie gehört.

Schutz in `api/src/db/activities.py`:
```sql
SELECT * FROM activities WHERE id = $1 AND user_id = $2
```
Beide Parameter müssen passen. Wenn `$2` (eingeloggte User-ID) nicht zum Datensatz passt → `None` zurück → 404.

---

## 5. Transport Security

### 5.1 TLS und HSTS

**TLS:** **Caddy** terminiert TLS mit ACME/Let's Encrypt (Pflicht für öffentliches Deployment). HSTS ist aktiviert (`max-age=31536000; includeSubDomains`) — Browser erzwingen HTTPS nach dem ersten Aufruf.

**Deployment-Optionen:**
- **Heim — homelab-gateway (Caddy):** ACME via HTTP-01/DNS-01 im `homelab-gateway`; nur über Tailscale erreichbar.
- **Public SaaS — `make up-public`:** gebündeltes Caddy holt automatisch ein Let's-Encrypt-Cert für `PUBLIC_DOMAIN` (`deploy/Caddyfile`). Self-signed TLS ist für öffentliches Deployment nicht akzeptabel.

### 5.2 Security Headers

Alle HTTP-Responses enthalten diese Headers (gesetzt in `api/src/main.py`):

| Header | Wert | Schutz gegen |
|---|---|---|
| `Content-Security-Policy` | Nonce-basiert + `'strict-dynamic'` | XSS |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Downgrade-Angriffe, SSL-Stripping |
| `X-Content-Type-Options` | `nosniff` | MIME-Sniffing (IE/Edge-Exploit) |
| `X-Frame-Options` | `DENY` | Clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Referrer-Leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=()` | Browser-Feature-Missbrauch |

**Wave 7 (L-05):** `worker-src 'none'` und `manifest-src 'self'` sind seit Wave 7 in der CSP gesetzt (`api/src/main.py`).

---

## 6. Injection-Schutz

### 6.1 SQL Injection

**Alle** Datenbankzugriffe laufen über asyncpg Prepared Statements:
```python
await conn.fetch("SELECT * FROM activities WHERE user_id = $1", user_id)
```

`$1`, `$2`, usw. sind **Platzhalter für Parameter** — asyncpg trennt SQL-Code von Daten auf Protokollebene. User-Input landet nie im SQL-String. Kein ORM, kein Query Builder — direktes Prepared-Statement-API verhindert versehentliche String-Konkatenation.

### 6.2 DOM XSS

**Risiko:** Seizure Notes, Event-Type-Strings, Metriken-Labels kommen aus der DB (also ursprünglich vom User) und werden in der UI dargestellt.

**Mitigation:** Kein `innerHTML` mit User-Daten. Drei Ansätze je nach Kontext:

```javascript
// 1. Reiner Text → textContent (epilepsy.js, dashboard-utils.js)
element.textContent = userInput;

// 2. String-Werte in HTML-Attributen/Inhalt → esc() (activity.js: statTile, sport_label)
element.innerHTML = `<span>${esc(label)}: ${esc(value)}</span>`;

// 3. Renderer-erzeugte HTML-Struktur → DOMPurify (metrics.js)
element.innerHTML = DOMPurify.sanitize(rendererOutput);

// Verboten:
element.innerHTML = userInput;  // ← XSS
```

### 6.3 Server-Side: Keine Shell-Kommandos mit User-Input

PulseBase startet keine Subprozesse mit User-kontrollierten Parametern. Der einzige externe Call ist die Garmin/LibreLink-Library, die intern HTTP-Requests baut.

---

## 7. CSRF-Schutz

### 7.1 Warum CSRF ein reales Risiko ist

CSRF (Cross-Site Request Forgery) nutzt aus, dass Browser Cookies automatisch mitsenden. Eine bösartige Seite kann einen POST-Request an `https://your-domain.com/account/delete` schicken — der Browser hängt das Session-Cookie an, die App sieht einen "authentifizierten" Request.

**Gefährdete Endpunkte (alle POST-Routen mit State-Change):**
- `/login`, `/register` — Auth-Formulare (L-30, W9)
- `/garmin/link`, `/libre/link` — Verknüpfung externer Accounts
- `/account/delete` — Konto-Löschung
- `/auth/reset` — Passwort-Reset

### 7.2 Double-Submit-Cookie-Pattern

PulseBase implementiert das **Double-Submit-Cookie-Pattern** zusätzlich zum `SameSite=Strict`-Cookie (Defense in Depth — der CSRF-Token-Check hängt nicht allein vom Browser-SameSite-Verhalten ab):

```python
# Generierung (GET-Endpoint):
csrf_token = secrets.token_urlsafe(32)  # Kryptographisch stark
request.session["csrf_token"] = csrf_token
# Token im HTML-Formular als <input type="hidden">

# Validierung (POST-Endpoint):
session_token = request.session.get("csrf_token")
form_token = form_data.get("csrf_token")
if not session_token or not hmac.compare_digest(session_token, form_token):
    raise HTTPException(status_code=403)
```

`hmac.compare_digest()` statt `==` verhindert Timing-Angriffe auf den Token-Vergleich.

**Warum zusätzlich zum `sameSite=strict`-Cookie:**
Der Session-Cookie ist auf `sameSite=strict` gesetzt (`api/src/main.py`) — Browser senden ihn bei Cross-Site-Requests gar nicht mit. Der serverseitige Double-Submit-Token bleibt als zweite, browser-unabhängige Schicht bestehen, falls ein Browser SameSite nicht korrekt durchsetzt.

---

## 8. Input-Validierung

### 8.1 Schema-Validierung mit Pydantic

Alle API-Eingaben werden an der System-Grenze gegen Pydantic-Schemas validiert:

```python
class SeizureBody(BaseModel):
    notes: str = Field(default="", max_length=1000)  # Ohne max_length: DoS durch riesige Payloads
    severity: int = Field(ge=1, le=10)
    trigger: str = Field(max_length=100)
```

Pydantic wirft `ValidationError` (→ HTTP 422) bevor der Handler-Code ausgeführt wird.

### 8.2 E-Mail-Format-Validierung

```python
class RegisterBody(BaseModel):
    email: EmailStr  # Pydantic EmailStr: RFC-5322-konform
```

Ohne `EmailStr` könnten Nutzer beliebige Strings als E-Mail registrieren, was den Verifikations-Flow bricht und E-Mail-Injection ermöglicht (SMTP-Header-Injection über Newlines in der Adresse).

### 8.3 Rate Limiting

Zusätzlich zur Schema-Validierung sind folgende Endpunkte rate-limitiert (slowapi):

| Endpunkt | Limit | Schutz gegen |
|---|---|---|
| `POST /login` | 10/min | Brute Force |
| `POST /register` | 5/min | Account-Spam |
| `POST /auth/reset-request` | 3/h | E-Mail-Flooding |
| `GET/POST /garmin/link` | 5/h | Credential-Stuffing gegen Garmin API |
| `GET/POST /libre/link` | 5/h | Credential-Stuffing gegen LibreLink API |

### 8.4 Fehler-Responses ohne Daten-Leakage (WS-A)

Zwei globale Exception-Handler in [`api/src/main.py`](../api/src/main.py) normalisieren
**alle** JSON-Fehler auf die einheitliche Form `{error:{code,message,details?}}` (Details
siehe [`docs/api.md` → Error Format](api.md#error-format)). Sicherheitsrelevant:

- **Kein Echo gesendeter Werte (NEU-1).** Der `RequestValidationError`-Handler mappt pro
  Fehler nur `loc → field` und `msg` und verwirft Pydantics `input`/`ctx`. Der
  FastAPI-Default hätte den fehlerhaften Wert zurückgespiegelt — auf den Auth-POSTs
  (`/login`, `/register`, `/auth/reset/*`) ist das **das Klartext-Passwort**, und derselbe
  Wert wäre auch im Sentry-Event gelandet. Invariante: **kein vom Client gesendeter Wert
  verlässt den Server je über eine Fehler-Antwort.** Regressions-Schutz:
  `test_validation_error_does_not_leak_submitted_value` (Canary-Assert).
- **`debug=False`** (FastAPI-Default, kein `debug=True` in `main.py`) → keine Tracebacks im
  Response-Body. Die beiden Handler decken `RequestValidationError` und
  `HTTPException` ab; eine sonst unbehandelte Exception liefert Starlettes generische
  500-Antwort ohne Stacktrace/interne Details.
- **DSN nie geloggt (NEU-2).** Die DB-Verbindungs-URL ([`db/pool.py`](../api/src/db/pool.py))
  enthält das DB-Passwort im Klartext. `get_pool()` fängt Verbindungsfehler ab und loggt
  ausschließlich `reason=type(e).__name__` (nie den DSN), dann `raise`. Generell gilt:
  Exceptions werden mit `type(e).__name__` statt `str(e)` geloggt (z. B. `garmin.link.fail`).

---

## 9. Secrets Management

### 9.1 Secret-Übersicht

| Secret | Zweck | Scope | Rotation |
|---|---|---|---|
| `SESSION_SECRET` | Cookie-Signierung (HMAC), min. 32 Zeichen | API | Rotieren erzwingt alle User auszuloggen |
| `FERNET_KEY` | Token-Verschlüsselung at rest | API + Sync | Rotation erfordert Re-Encrypt aller Tokens |
| `DB_APP_PASSWORD` | DB-Verbindung (breite Rolle: Auth, Account-Löschung) | nur API | Standard DB-Rotation |
| `DB_SYNC_PASSWORD` | DB-Verbindung (Least-Privilege-Rolle, V24) | nur Sync | Standard DB-Rotation |
| `DB_ML_PASSWORD` | DB-Verbindung (read-only Health + write ml_predictions, V24) | nur ML | Standard DB-Rotation |
| `DB_PASSWORD` | DB-Admin (Migrations + Backup-Dump) | Flyway + Backup | Selten |
| `RESEND_API_KEY` | E-Mail-Versand | API | Bei Verdacht |
| age-Keypair | Backup-Verschlüsselung (Public am Server, Private **offsite**) | Backup | Unkritisch (s. 9.6) |

### 9.2 Secret-Isolation per Service

Jeder Service bekommt nur die Secrets die er braucht (Principle of Least Privilege):

```
env/.env       → nur db + flyway (DB_USER/PASSWORD Admin-Creds, HOST_IP)
env/.env.app   → api + sync + ml (FERNET_KEY + Per-Service-DB-Rollen V24:
                 DB_APP_* nur api, DB_SYNC_* nur sync, DB_ML_* nur ml — Least Privilege)
env/.env.api   → nur api (SESSION_SECRET, RESEND_API_KEY, APP_BASE_URL, ...)
env/.env.sync  → nur sync-service (SYNC_INTERVAL_HOURS, SYNC_LOOKBACK_DAYS, ...)
env/.env.ml    → nur ml-service (ML_INFER_HOUR — ml-service greift nie auf Tokens zu, kein FERNET_KEY nötig)
env/.env.backup → nur backup-Container (AGE_RECIPIENT, BACKUP_*; DB-Creds aus env/.env)
```

Admin-Credentials (`DB_USER`/`DB_PASSWORD`) sind nie im Prozess-Environment von api/sync/ml
sichtbar — kein Leak via `/proc/<pid>/environ` (H-11, W9). **Ausnahme:** der `backup`-Container
bekommt sie bewusst (pg_dump braucht Voll-Read). Least-Privilege-Härtung wäre eine dedizierte
`pg_read_all_data`-Backup-Rolle (Migration V27) statt der Admin-Rolle — dokumentiert vertagt.

Verifikation:
```bash
docker exec pulsebase-api  env | grep DB_USER        # → leer (nur DB_APP_USER vorhanden)
docker exec pulsebase-sync env | grep SESSION_SECRET # → leer (korrekt)
docker exec pulsebase-ml   env | grep SESSION_SECRET # → leer (korrekt)
```

### 9.3 Secret-Generierung

```bash
make gen-secrets    # SESSION_SECRET, FERNET_KEY, DB_APP/SYNC/ML_PASSWORD + age-keygen-Hinweis
```

Erzeugt mit `openssl rand` bzw. `Fernet.generate_key()` — kryptographisch starke Zufallszahlen
aus dem OS-CSPRNG. Das age-Backup-Keypair wird **nicht** hier erzeugt (der private Key soll nicht
am Server entstehen): `make gen-secrets` druckt nur den `age-keygen`-Hinweis für eine Offsite-Maschine.

### 9.4 Session-Secret-Rotation

`SESSION_SECRET` rotieren invalidiert alle aktiven Sessions sofort:
```bash
# Neues Secret generieren und in env/.env.api eintragen
make gen-secrets
make dashboard   # Container neu starten mit neuem Secret
```

**Wann rotieren:** Bei Verdacht auf Kompromittierung, oder präventiv nach Incident. Alle eingeloggten User werden automatisch ausgeloggt — das ist der gewünschte Effekt.

### 9.5 FERNET_KEY-Rotation

Komplexer als Session-Secret, da bestehende verschlüsselte Token re-encrypt werden müssen:

```python
# Ablauf:
# 1. Neuen Key generieren
new_key = Fernet.generate_key()

# 2. MultiFernet: dekodiert mit altem Key, kann mit neuem verschlüsseln
from cryptography.fernet import MultiFernet
f = MultiFernet([Fernet(new_key), Fernet(old_key)])

# 3. Alle Tokens in user_tokens re-encrypten
tokens = await conn.fetch("SELECT id, token_data FROM user_tokens")
for row in tokens:
    re_encrypted = f.rotate(row["token_data"])
    await conn.execute("UPDATE user_tokens SET token_data = $1 WHERE id = $2",
                       re_encrypted, row["id"])

# 4. Alten Key aus env entfernen, nur neuen Key stehen lassen
```

**Wichtig — zwei unabhängige Schlüssel nicht verwechseln:** `FERNET_KEY` (verschlüsselt
`user_tokens`) und das age-Backup-Keypair haben **verschiedene** Rotations-Konsequenzen (s. 9.6).

### 9.6 age-Backup-Key-Rotation

Das age-Keypair verschlüsselt die DB-Backups (Service `backup`). Asymmetrisch: der
**Public-Key** (`AGE_RECIPIENT` in `env/.env.backup`) liegt am Server und verschlüsselt nur;
der **private** Key bleibt offsite (Passwortmanager) und wird ausschließlich fürs Restore
gebraucht — ein kompromittierter Server kann seine eigenen Backups also **nicht** entschlüsseln.

- **Rotation unkritisch:** neuen `AGE_RECIPIENT` eintragen → gilt ab dem nächsten Backup. Alte
  Dumps brauchen weiterhin den alten privaten Key zum Restore → **beide privaten Keys
  aufbewahren**, bis die Retention (`BACKUP_RETENTION_DAYS`) der alten Dumps abgelaufen ist.
- **Kontrast zu `FERNET_KEY`:** dessen Rotation macht alle `user_tokens` unlesbar →
  betroffene Nutzer müssen **Garmin/LibreLink neu verknüpfen** (re-link). age-Rotation hat
  keine solche Nutzer-Auswirkung. Nur bei Verdacht auf Kompromittierung rotieren.

---

## 10. Infrastruktur-Sicherheit

### 10.1 Docker-Härtung

**Multi-Stage Builds:**
```dockerfile
FROM python:3.14-slim AS builder
# ... Build-Abhängigkeiten installieren ...

FROM python:3.14-slim AS runner
# Nur Runtime-Dateien kopieren, keine Build-Tools im finalen Image
COPY --from=builder /app /app
```

Warum: Kleineres Image = kleinere Angriffsfläche. Build-Tools (gcc, pip, etc.) sind nicht im laufenden Container.

**Non-root User:**
```dockerfile
RUN adduser --system --no-create-home appuser
USER appuser
```

Warum: Wenn ein Angreifer Code-Execution erlangt (z.B. durch eine FastAPI-Schwachstelle), läuft er als `appuser` ohne Schreibrechte auf das Dateisystem. Container-Escape via `root` wird deutlich schwerer.

**Digest-Pins für Base Images:**
```yaml
image: python:3.14-slim@sha256:abc123...
```

Warum: Ein `latest`-Tag kann sich über Nacht ändern. Ein kompromittierter Registry-Uploader könnte ein Backdoor-Image mit demselben Tag hochladen. Digest-Pins verhindern das.

### 10.2 Netzwerk-Isolation

```
┌─────────────────── internal (Docker-intern) ─────────────────┐
│  pulsebase-api  ←──→  pulsebase-db                                  │
│  pulsebase-sync ←──→  pulsebase-db                                  │
│  pulsebase-ml   ←──→  pulsebase-db                                  │
└───────────────────────────────────────────────────────────────┘
         │
         │ (nur pulsebase-api ist Mitglied beider Netze)
         ▼
┌─────── proxy (externe Docker-Netz) ──────┐
│  gateway-caddy  ←──→  pulsebase-api         │
└──────────────────────────────────────────┘
```

Die Datenbank ist **nie** direkt exponiert. Sync- und ML-Service kommunizieren nur intern. Kein Service bindet Ports auf `0.0.0.0`.

### 10.3 Container-Scanning mit Trivy

In der CI-Pipeline läuft Trivy gegen jedes gebaute Image:
```yaml
trivy image --severity CRITICAL,HIGH --exit-code 1 --ignore-unfixed pulsebase-api:latest
```

`--ignore-unfixed`: Findings ohne verfügbaren Fix werden ignoriert — der Developer kann diese nicht beheben, sie erhöhen nur den Lärm. `--exit-code 1` bricht den CI-Build ab wenn CRITICAL oder HIGH Findings mit verfügbarem Fix existieren.

### 10.4 Host-Härtung (Mac mini / Linux Server)

- SSH: Nur Key-Auth (`PasswordAuthentication no`)
- UFW: Nur 22, 80, 443 offen
- Automatische Security-Updates (`unattended-upgrades` auf Linux)
- `env/`-Dateien: `chmod 600` (nur Owner lesbar)

---

## 11. Supply Chain Security

### 11.1 Dependency-Management mit Renovate

Renovate erstellt automatisch PRs für veraltete Abhängigkeiten:

| Abhängigkeitstyp | Strategie | Begründung |
|---|---|---|
| devDependencies (patch) | Automerge | Patch-Updates sind fast immer sicher |
| Python-Pakete (minor/patch) | PR + manueller Review | Könnte Breaking Changes enthalten |
| Docker-Image-Digests | Automerge | Nur neuer Digest für gleiche Version |
| Docker-Image-Tags (major) | Manueller Review | Z.B. Python 3.14 → 3.15 |
| GitHub Actions | PR + Review | Actions können Code ausführen |

### 11.2 SAST (Static Application Security Testing)

**bandit** (per Pre-commit + CI):
```bash
bandit -r api/src/ sync-service/src/ -l -i
```
Scannt auf bekannte Python-Sicherheitsmuster: eval(), shell=True, hardcoded Passwörter, unsichere MD5-Nutzung, etc.

**semgrep** (nur CI):
```bash
semgrep --config=auto .
```
Cross-file Taint-Analyse — erkennt wenn User-Input einen gefährlichen Codepfad erreicht, auch über mehrere Dateien hinweg. Aufwändiger als bandit, läuft deshalb nur in CI (nicht pre-commit).

### 11.3 SCA (Software Composition Analysis)

**pip-audit** (CI):
```bash
uv export --frozen --no-hashes --directory api/ -o /tmp/req-api.txt
pip-audit -r /tmp/req-api.txt
```
`uv export --frozen` liest das eingefrorene `uv.lock` — deterministisch, kein Re-Resolve. Prüft gegen Python Packaging Advisory Database (GHSA + PyPI). Nicht Safety (veraltet, kommerziell).

### 11.4 Pre-commit Hook-Reihenfolge

```
gitleaks       ← Secrets-Scan zuerst (Commit mit Secret sofort verhindern)
pre-commit-hooks ← trailing-whitespace, check-yaml/json/toml, no-commit-to-branch
bandit         ← SAST (vor ruff — findet Security-Issues vor Code-Style-Korrekturen)
ruff           ← Lint + Fix
ruff-format    ← Format
detect-secrets ← Baseline-basierter Secret-Scan (ergänzt gitleaks)
mypy           ← Type Check (findet implizite None-Dereferenzierungen)
```

gitleaks läuft zuerst: Selbst wenn spätere Hooks fehlschlagen und der Commit abbricht, ist sichergestellt dass kein Secret committed wurde. bandit läuft vor ruff damit Security-Issues nicht durch Auto-Fixes überdeckt werden.

gitleaks läuft zuerst: Selbst wenn spätere Hooks fehlschlagen und der Commit abbricht, ist sichergestellt dass kein Secret committed wurde.

### 11.5 GitHub Actions: Digest-Pins

Alle Actions sind mit `@sha256:...` gepinnt, nicht mit `@v3` oder ähnlichem:
```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
```

Warum: Ein Angreifer könnte einen neuen Commit auf den `v3`-Tag pushen. SHA256-Digest ist unveränderlich.

---

## 12. Security im Entwicklungsprozess (SDLC)

### 12.1 Designphase

**Threat Modeling vor neuen Features:**
Für signifikante neue Features (neuer Datentyp, neuer externer Service, neue Auth-Methode) ein kurzes STRIDE-Modell erstellen:

| STRIDE | Frage | Mitigation |
|---|---|---|
| **S**poofing | Wer kann sich als jemand anderes ausgeben? | Starke Auth, Token-Binding |
| **T**ampering | Wer kann Daten manipulieren? | HMAC, Prepared Statements |
| **R**epudiation | Kann ein User Aktionen abstreiten? | Audit-Log |
| **I**nformation Disclosure | Welche Daten könnten leaken? | Least Privilege, Encryption |
| **D**enial of Service | Was kann den Service lahmlegen? | Rate Limiting, Input-Größen |
| **E**levation of Privilege | Wie kann jemand mehr Rechte bekommen? | Defense in Depth |

**ASVS 5.0 als Prüfrahmen:**
Neue Features gegen die relevanten ASVS-Chapters prüfen (V2 Auth, V3 Session, V4 Access Control, V5 Validation, V13 API).

### 12.2 Entwicklungsphase

**Checkliste vor jedem PR:**
- [ ] Kein `innerHTML` mit User-Daten (DOM XSS)
- [ ] Alle DB-Queries als Prepared Statements
- [ ] Neue POST-Endpunkte mit State-Change haben CSRF-Schutz
- [ ] Neue Eingabefelder haben Pydantic-Validierung mit `max_length`
- [ ] Keine Secrets in Logs oder Error-Responses
- [ ] Neue Endpunkte mit Auth haben `require_user()` als Dependency

### 12.3 CI/CD-Phase

```
Pre-commit:  gitleaks → bandit → mypy
CI Lint:     ruff (Python) + Biome (JS)
CI Security: gitleaks + pip-audit + bandit + semgrep
CI Type:     mypy (alle 3 Services)
CI Test:     pytest + Playwright E2E
CI Image:    Trivy (CRITICAL+HIGH, ignore-unfixed)
```

Ein `ci-ok`-All-Green-Gate-Job wurde in W3 ergänzt — security/lint/typecheck/test müssen grün sein bevor e2e läuft (H-06, ✅).

### 12.4 Deployment-Phase

Vor jedem Deployment auf Produktion:
```bash
make migrate    # Migrations anwenden (Flyway macht das automatisch beim Start)
make dashboard  # API neu bauen + starten
make analytics  # ML-Service neu bauen + starten
```

**Keine Zero-Downtime-Deployment derzeit:** `make dashboard` startet den Container neu — kurze Downtime (~5-10s). Dokumentierter Tech-Debt (CICD-M4).

**Rollback:**
```bash
# Docker-Tag des letzten funktionierenden Builds
docker compose up -d pulsebase-api:previous-tag
```

### 12.5 Betriebsphase

**Regelmäßige Aufgaben:**

| Frequenz | Aufgabe |
|---|---|
| Täglich | Sentry-Dashboard: neue Exceptions? |
| Wöchentlich | UptimeRobot-Report: Ausfälle? |
| Monatlich | Renovate-PRs mergen (Major-Updates nach Review) |
| Monatlich | Backup-Restore-Test (Dump in Test-Container einspielen) |
| Quartalsweise | pip-audit manuell laufen lassen, Dependencies prüfen |
| Jährlich | ASVS-Review: Hat sich die Bedrohungslage verändert? |

---

## 13. Security Testing

### 13.1 Was wird automatisch getestet?

| Test-Art | Tool | Was wird geprüft |
|---|---|---|
| Unit Tests (Auth) | pytest | Login/Lockout/Rate-Limit/E-Mail-Verifikation/Password-Reset — alle mit ~100% Coverage |
| E2E Smoke Tests | Playwright | Login-Flow, Dashboard, Settings, Metrics, Help, Account-Export/Delete |
| E2E Auth Flows | Playwright | Register, E-Mail-Verify (Token), Passwort-Reset (Token aus DB) |
| E2E Static Pages | Playwright | Privacy/Terms/Imprint/Accessibility + Epilepsie-Seite (mit/ohne Modus) |
| SAST | bandit + semgrep | Bekannte unsichere Python-Patterns |
| SCA | pip-audit | CVEs in Dependencies |
| Image-Scan | Trivy | CVEs in OS-Packages und Python-Paketen im Container |

### 13.2 Was wird nicht automatisch getestet?

| Lücke | Risiko | Mitigation |
|---|---|---|
| Manuelle Penetration | IDOR, Logic-Bugs | App-Eval mit ASVS-Fokus (dieser Report) |
| DAST (Dynamic Scanning) | Laufzeit-Injection | Kein OWASP ZAP in CI — manueller App-Eval (ASVS) als Ersatz |
| Fuzzing | Unerwartete Inputs | Pydantic-Validierung als Ersatz |
| E2E CSRF-Test | CSRF-Bypass | Manueller Test ausreichend |
| Auth-Flow E2E (Register, Verify, Reset) | Regressions in Auth | test_auth_flows.py ✅ (W9) |

### 13.3 Manueller Security-Test-Prozess

Für signifikante neue Features oder nach größeren Refactorings:

```bash
# 1. OWASP ZAP Baseline Scan (lokal, einmalig)
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t https://your-domain.com -r zap-report.html

# 2. Auth-Flow testen
# - Login mit falschen Credentials → 401, kein Timing-Leak?
# - 5x falsch → Lockout? E-Mail-Benachrichtigung?
# - Reset-Token nach Verwendung ungültig?

# 3. CSRF testen
# - POST /garmin/link ohne csrf_token → 403?
# - POST /account/delete von anderer Domain → geblockt?

# 4. IDOR testen
# - Als User A einloggen, Activity-ID eines User B abfragen → 404?
```

---

## 14. Incident Response

### 14.1 Erkennung

Sentry meldet Exceptions in Echtzeit. Folgende Events sollten sofortige Untersuchung auslösen:

- Ungewöhnlich viele `auth.login.fail`-Einträge (Brute-Force-Versuch)
- Unerwartete `500`-Fehler auf Auth-Endpunkten
- Sentry: `KeyError` oder `PermissionError` in db-Layer (möglicher IDOR-Versuch)
- UptimeRobot: Downtime-Alert

### 14.2 Sofortmaßnahmen

**Bei kompromittierter Session (Cookie-Theft/XSS):**
```bash
# SESSION_SECRET rotieren → alle Sessions sofort ungültig
make gen-secrets   # Neues Secret in env/.env.api
make dashboard     # Container neu starten
```

**Bei Verdacht auf kompromittierte Garmin/LibreLink-Credentials:**
```bash
# Betroffene User-IDs identifizieren
make db
# Im psql:
SELECT user_id, service, updated_at FROM user_tokens WHERE updated_at > NOW() - INTERVAL '24h';
# Betroffene Tokens löschen → User werden aufgefordert neu zu verknüpfen
DELETE FROM user_tokens WHERE user_id = <id>;
```

**Bei Verdacht auf Daten-Breach:**
1. App offline nehmen: `make down-public` (oder `caddy`-Service stoppen)
2. Logs sichern: `docker logs pulsebase-api > incident_$(date +%Y%m%d).log`
3. Audit-Log durchsuchen: Welche User-IDs, welche Endpunkte, welche IPs?
4. DSGVO-Meldepflicht prüfen: Bei Art. 9-Daten (Gesundheitsdaten) → Meldung an Datenschutzbehörde innerhalb 72h

### 14.3 Post-Incident

- Root Cause Analysis dokumentieren
- Falls offen: Finding in `review-open-items.md` ergänzen
- Wenn anwendbar: neuen Test schreiben der den Angriffspfad abdeckt
- Security-Kontrollen anpassen

---

## 15. DSGVO — Technische Umsetzung der Betroffenenrechte

| Recht | Endpunkt | Status | Anmerkung |
|---|---|---|---|
| Auskunft (Art. 15) | `GET /account/export` | ✅ | JSON-Download aller Daten außer `password_hash` |
| Löschung (Art. 17) | `POST /account/delete` | ✅ | E-Mail + Passwort als Bestätigung, atomar in TX |
| Datenportabilität (Art. 20) | `GET /account/export` | ✅ | Maschinenlesbares JSON-Format |
| Einwilligung (Art. 7, 9) | `/register` | ✅ | 3 Checkboxen (Gesundheitsdaten, AGB, Alter ≥16) + Audit-Log |
| Widerruf | Konto-Löschung = impliziter Widerruf | ✅ | Alle Nutzdaten werden gelöscht; Consent-Logs (user_consents, user_consent_events) bleiben pseudonymisiert erhalten (V30, SET NULL) |

**Wichtig:** Die Consent-Audit-Logs (`user_consents`, `user_consent_events`) werden bei Konto-Löschung **nicht** gelöscht, sondern pseudonymisiert: V30 ersetzte `ON DELETE CASCADE` durch `ON DELETE SET NULL` — beim Löschen der User-Zeile wird `user_id` auf NULL gesetzt, der Datensatz bleibt als anonymer Nachweis erhalten (Art. 5(2) Rechenschaftspflicht). Alle anderen Nutzdaten werden in derselben Transaktion gelöscht (`delete_user`, `api/src/db/users.py`).

---

## Anhang: ASVS-Coverage-Übersicht

Prüfrahmen: OWASP Application Security Verification Standard 5.0, Level 2.

| ASVS Chapter | Status | Offene Punkte |
|---|---|---|
| V2 Authentication | ✅ | — |
| V3 Session Management | ✅ | — |
| V4 Access Control | ✅ | — |
| V5 Validation & Encoding | ✅ | — |
| V7 Error Handling & Logging | 🟡 | Audit-Log noch nicht vollständig (3.5) |
| V8 Data Protection | ✅ | — |
| V9 Communication | ✅ | — |
| V13 API & Web Service | ✅ | — |
| V14 Configuration | ✅ | — |
