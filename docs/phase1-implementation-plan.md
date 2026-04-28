# Garmin Dashboard — Phase 1 Implementation Plan

**Stand:** 2026-04-27
**Scope:** Docker-Setup, Datenmodell, Sync-Service, Basis-Grafana
**Ziel:** Laufende Instanz mit automatischem Garmin-Sync und erstem Dashboard

---

## Übersicht

```
Phase 1: Fundament (diese Phase)
  ├── 1.1  Projektstruktur & Docker Compose
  ├── 1.2  TimescaleDB Schema
  ├── 1.3  Sync-Service (garminconnect + APScheduler)
  └── 1.4  Grafana Basis-Dashboard

Phase 2: Dashboards & Auswertungen       [später]
Phase 3: GPS-Kartenansicht & Geo-Queries [später]
Phase 4: UI-Erweiterungen / Custom API   [später]
```

---

## 1.1 Projektstruktur

```
garmin-dev/
├── docker-compose.yml
├── .env                          ← Credentials (nie committen!)
├── .env.example                  ← Template für .env
├── docs/
│   └── phase1-implementation-plan.md
├── db/
│   └── init/
│       └── 01_schema.sql         ← TimescaleDB Schema
├── sync-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py               ← Einstiegspunkt + Scheduler
│       ├── config.py             ← Settings via Env-Vars
│       ├── domain/
│       │   └── models.py         ← Pydantic Domain Models
│       ├── repositories/
│       │   ├── base.py           ← Abstract Repository Interface
│       │   └── timescale.py      ← TimescaleDB Implementierung
│       └── garmin/
│           ├── client.py         ← garminconnect Wrapper
│           └── mapper.py         ← Garmin API → Domain Models
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── timescaledb.yml   ← Auto-Datasource Konfiguration
    │   └── dashboards/
    │       └── dashboards.yml    ← Dashboard Loader Config
    └── dashboards/
        └── activities.json       ← Basis-Dashboard (Aktivitäten)
```

---

## 1.2 Docker Compose

```yaml
# docker-compose.yml
version: '3.9'

services:

  db:
    image: timescale/timescaledb:latest-pg16
    container_name: garmin-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: garmin
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - timescale-data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d   # Schema beim ersten Start
    ports:
      - "5432:5432"                              # optional, für direkten DB-Zugriff
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d garmin"]
      interval: 10s
      timeout: 5s
      retries: 5

  sync-service:
    build: ./sync-service
    container_name: garmin-sync
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DB_HOST: db
      DB_PORT: 5432
      DB_NAME: garmin
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
      # User 1
      GARMIN_USER1_EMAIL: ${GARMIN_USER1_EMAIL}
      GARMIN_USER1_PASSWORD: ${GARMIN_USER1_PASSWORD}
      GARMIN_USER1_NAME: ${GARMIN_USER1_NAME}
      # User 2
      GARMIN_USER2_EMAIL: ${GARMIN_USER2_EMAIL}
      GARMIN_USER2_PASSWORD: ${GARMIN_USER2_PASSWORD}
      GARMIN_USER2_NAME: ${GARMIN_USER2_NAME}
      SYNC_HOUR: "6"                             # Sync täglich um 06:00
      SYNC_LOOKBACK_DAYS: "7"                    # Beim Start: letzte 7 Tage nachholen
    volumes:
      - garmin-tokens:/app/tokens                # Garmin Session Tokens cachen

  grafana:
    image: grafana/grafana:latest
    container_name: garmin-grafana
    restart: unless-stopped
    depends_on:
      - db
    environment:
      GF_SECURITY_ADMIN_USER: ${GRAFANA_ADMIN_USER}
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
    ports:
      - "3000:3000"                              # http://minipc-ip:3000
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards

volumes:
  timescale-data:
  grafana-data:
  garmin-tokens:
```

---

## 1.3 TimescaleDB Schema

```sql
-- db/init/01_schema.sql

-- Extension aktivieren
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ── USERS ────────────────────────────────────────────────────────────────────

CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── SUMMARY TABLES ───────────────────────────────────────────────────────────

CREATE TABLE activities (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    garmin_activity_id  BIGINT NOT NULL UNIQUE,    -- Deduplication
    started_at          TIMESTAMPTZ NOT NULL,
    duration_seconds    INTEGER,
    sport_type          TEXT NOT NULL,             -- running | cycling | swimming | ...
    distance_meters     FLOAT,
    calories            INTEGER,
    avg_hr              SMALLINT,
    max_hr              SMALLINT,
    avg_pace_sec_per_km FLOAT,                     -- Sekunden pro km
    avg_cadence         SMALLINT,
    avg_power           SMALLINT,                  -- Watt (Radfahren)
    elevation_gain      FLOAT,                     -- Meter
    avg_speed_kmh       FLOAT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_activities_user_started ON activities (user_id, started_at DESC);

CREATE TABLE daily_summary (
    date            DATE NOT NULL,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    steps           INTEGER,
    calories_total  INTEGER,
    avg_stress      SMALLINT,
    max_stress      SMALLINT,
    avg_spo2        SMALLINT,
    min_spo2        SMALLINT,
    body_battery_high SMALLINT,
    body_battery_low  SMALLINT,
    resting_hr      SMALLINT,
    PRIMARY KEY (date, user_id)
);

CREATE TABLE sleep_sessions (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    garmin_sleep_id     BIGINT UNIQUE,
    start_time          TIMESTAMPTZ NOT NULL,
    end_time            TIMESTAMPTZ NOT NULL,
    total_sleep_seconds INTEGER,
    deep_sleep_seconds  INTEGER,
    light_sleep_seconds INTEGER,
    rem_sleep_seconds   INTEGER,
    awake_seconds       INTEGER,
    sleep_score         SMALLINT                   -- 0-100 Garmin Score
);

CREATE INDEX idx_sleep_user_start ON sleep_sessions (user_id, start_time DESC);

CREATE TABLE hrv_daily (
    date            DATE NOT NULL,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    hrv_last_night  SMALLINT,                      -- ms
    hrv_weekly_avg  SMALLINT,                      -- ms
    hrv_status      TEXT,                          -- balanced | unbalanced | poor
    PRIMARY KEY (date, user_id)
);

-- ── TIMESERIES HYPERTABLES ───────────────────────────────────────────────────

CREATE TABLE activity_records (
    time            TIMESTAMPTZ NOT NULL,
    activity_id     INTEGER NOT NULL REFERENCES activities(id),
    user_id         INTEGER NOT NULL,
    heart_rate      SMALLINT,
    pace_sec_per_km FLOAT,
    cadence         SMALLINT,
    power           SMALLINT,
    elevation       FLOAT,
    distance        FLOAT,
    lat             DOUBLE PRECISION,
    lng             DOUBLE PRECISION
);

SELECT create_hypertable('activity_records', 'time');
CREATE INDEX idx_activity_records_activity ON activity_records (activity_id, time DESC);

-- Komprimierung nach 7 Tagen (10x Platzersparnis)
ALTER TABLE activity_records SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'activity_id'
);
SELECT add_compression_policy('activity_records', INTERVAL '7 days');


CREATE TABLE body_battery_intraday (
    time    TIMESTAMPTZ NOT NULL,
    user_id INTEGER NOT NULL,
    value   SMALLINT NOT NULL              -- 0-100
);

SELECT create_hypertable('body_battery_intraday', 'time');
ALTER TABLE body_battery_intraday SET (timescaledb.compress);
SELECT add_compression_policy('body_battery_intraday', INTERVAL '30 days');


CREATE TABLE stress_intraday (
    time    TIMESTAMPTZ NOT NULL,
    user_id INTEGER NOT NULL,
    value   SMALLINT NOT NULL              -- 0-100
);

SELECT create_hypertable('stress_intraday', 'time');
ALTER TABLE stress_intraday SET (timescaledb.compress);
SELECT add_compression_policy('stress_intraday', INTERVAL '30 days');


CREATE TABLE spo2_readings (
    time    TIMESTAMPTZ NOT NULL,
    user_id INTEGER NOT NULL,
    value   SMALLINT NOT NULL              -- Prozent
);

SELECT create_hypertable('spo2_readings', 'time');


CREATE TABLE sleep_levels (
    time             TIMESTAMPTZ NOT NULL,
    sleep_session_id INTEGER NOT NULL REFERENCES sleep_sessions(id),
    user_id          INTEGER NOT NULL,
    level            TEXT NOT NULL          -- deep | light | rem | awake
);

SELECT create_hypertable('sleep_levels', 'time');
```

---

## 1.4 Sync-Service

### Repository Pattern

```python
# sync-service/src/repositories/base.py
from abc import ABC, abstractmethod
from typing import List
from domain.models import Activity, DailySummary, SleepSession, HRVDaily

class ActivityRepository(ABC):
    @abstractmethod
    async def save(self, activity: Activity) -> int: ...

    @abstractmethod
    async def exists(self, garmin_activity_id: int) -> bool: ...

    @abstractmethod
    async def get_by_user(self, user_id: int, days: int) -> List[Activity]: ...

class DailySummaryRepository(ABC):
    @abstractmethod
    async def upsert(self, summary: DailySummary) -> None: ...

class SleepRepository(ABC):
    @abstractmethod
    async def save(self, session: SleepSession) -> int: ...

    @abstractmethod
    async def exists(self, garmin_sleep_id: int) -> bool: ...

class HRVRepository(ABC):
    @abstractmethod
    async def upsert(self, hrv: HRVDaily) -> None: ...
```

### Domain Models

```python
# sync-service/src/domain/models.py
from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional, List
from enum import Enum

class SportType(str, Enum):
    RUNNING  = "running"
    CYCLING  = "cycling"
    SWIMMING = "swimming"
    HIKING   = "hiking"
    OTHER    = "other"

class ActivityRecord(BaseModel):
    time:            datetime
    heart_rate:      Optional[int]
    pace_sec_per_km: Optional[float]
    cadence:         Optional[int]
    power:           Optional[int]
    elevation:       Optional[float]
    distance:        Optional[float]
    lat:             Optional[float]
    lng:             Optional[float]

class Activity(BaseModel):
    garmin_activity_id:  int
    user_id:             int
    started_at:          datetime
    duration_seconds:    Optional[int]
    sport_type:          SportType
    distance_meters:     Optional[float]
    calories:            Optional[int]
    avg_hr:              Optional[int]
    max_hr:              Optional[int]
    avg_pace_sec_per_km: Optional[float]
    avg_cadence:         Optional[int]
    avg_power:           Optional[int]
    elevation_gain:      Optional[float]
    records:             List[ActivityRecord] = []

class DailySummary(BaseModel):
    date:              date
    user_id:           int
    steps:             Optional[int]
    calories_total:    Optional[int]
    avg_stress:        Optional[int]
    max_stress:        Optional[int]
    avg_spo2:          Optional[int]
    min_spo2:          Optional[int]
    body_battery_high: Optional[int]
    body_battery_low:  Optional[int]
    resting_hr:        Optional[int]

class SleepSession(BaseModel):
    garmin_sleep_id:     Optional[int]
    user_id:             int
    start_time:          datetime
    end_time:            datetime
    total_sleep_seconds: Optional[int]
    deep_sleep_seconds:  Optional[int]
    light_sleep_seconds: Optional[int]
    rem_sleep_seconds:   Optional[int]
    awake_seconds:       Optional[int]
    sleep_score:         Optional[int]

class HRVDaily(BaseModel):
    date:           date
    user_id:        int
    hrv_last_night: Optional[int]
    hrv_weekly_avg: Optional[int]
    hrv_status:     Optional[str]
```

### Garmin Client Wrapper

```python
# sync-service/src/garmin/client.py
import garminconnect
from datetime import date, timedelta
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class GarminClient:
    def __init__(self, email: str, password: str, token_dir: str):
        self.email     = email
        self.password  = password
        self.token_dir = token_dir
        self._client   = None

    def connect(self) -> None:
        self._client = garminconnect.Garmin(
            email=self.email,
            password=self.password,
            is_cn=False,
            prompt_mfa=None
        )
        try:
            self._client.login(self.token_dir)          # Token aus Cache
            logger.info(f"Login via Token: {self.email}")
        except Exception:
            self._client.login()                         # Frischer Login
            self._client.garth.dump(self.token_dir)      # Token cachen
            logger.info(f"Frischer Login: {self.email}")

    def get_activities(self, start: date, end: date) -> List[Dict[str, Any]]:
        return self._client.get_activities_by_date(
            start.isoformat(), end.isoformat()
        )

    def get_activity_details(self, activity_id: int) -> Dict[str, Any]:
        return self._client.get_activity_details(activity_id)

    def get_daily_summary(self, day: date) -> Dict[str, Any]:
        return self._client.get_stats(day.isoformat())

    def get_sleep(self, day: date) -> Dict[str, Any]:
        return self._client.get_sleep_data(day.isoformat())

    def get_hrv(self, day: date) -> Dict[str, Any]:
        return self._client.get_hrv_data(day.isoformat())

    def get_body_battery(self, day: date) -> List[Dict]:
        return self._client.get_body_battery(day.isoformat(), day.isoformat())

    def get_stress(self, day: date) -> List[Dict]:
        return self._client.get_stress_data(day.isoformat())
```

### Scheduler

```python
# sync-service/src/main.py
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import Settings
from garmin.client import GarminClient
from repositories.timescale import TimescaleRepository
from datetime import date, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()

USERS = [
    {"id": 1, "name": settings.user1_name,
     "email": settings.user1_email, "password": settings.user1_password},
    {"id": 2, "name": settings.user2_name,
     "email": settings.user2_email, "password": settings.user2_password},
]

async def sync_user(user: dict, days: int = 1) -> None:
    logger.info(f"Sync gestartet: {user['name']} ({days} Tage)")
    client = GarminClient(user["email"], user["password"], f"/app/tokens/{user['id']}")
    repo   = TimescaleRepository(settings.db_url)

    client.connect()
    end   = date.today()
    start = end - timedelta(days=days)

    # Aktivitäten
    raw_activities = client.get_activities(start, end)
    for raw in raw_activities:
        garmin_id = raw.get("activityId")
        if not await repo.activity_exists(garmin_id):
            activity = map_activity(raw, user["id"])
            # Rohdaten inkl. GPS
            details = client.get_activity_details(garmin_id)
            activity.records = map_records(details)
            await repo.save_activity(activity)

    # Tages-Loop
    current = start
    while current <= end:
        summary = client.get_daily_summary(current)
        await repo.upsert_daily_summary(map_summary(summary, user["id"], current))

        sleep = client.get_sleep(current)
        if sleep:
            await repo.save_sleep(map_sleep(sleep, user["id"]))

        hrv = client.get_hrv(current)
        if hrv:
            await repo.upsert_hrv(map_hrv(hrv, user["id"], current))

        current += timedelta(days=1)

    logger.info(f"Sync fertig: {user['name']}")

async def daily_sync() -> None:
    for user in USERS:
        try:
            await sync_user(user, days=2)           # 2 Tage: heute + gestern (Sicherheit)
        except Exception as e:
            logger.error(f"Sync Fehler {user['name']}: {e}")

async def main() -> None:
    # Beim Start: Rückwirkend sync
    for user in USERS:
        await sync_user(user, days=settings.sync_lookback_days)

    # Täglicher Sync 06:00
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        daily_sync,
        CronTrigger(hour=settings.sync_hour, minute=0)
    )
    scheduler.start()
    logger.info(f"Scheduler läuft — täglicher Sync um {settings.sync_hour}:00 Uhr")

    await asyncio.Event().wait()                     # Läuft bis Container stoppt

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 1.5 Grafana Datasource Provisioning

```yaml
# grafana/provisioning/datasources/timescaledb.yml
apiVersion: 1
datasources:
  - name: TimescaleDB
    type: postgres
    url: db:5432
    database: garmin
    user: ${DB_USER}
    secureJsonData:
      password: ${DB_PASSWORD}
    jsonData:
      sslmode: disable
      timescaledb: true
    isDefault: true
```

---

## 1.6 .env Template

```bash
# .env.example — kopieren nach .env und befüllen

# Datenbank
DB_USER=garmin
DB_PASSWORD=changeme

# Garmin Accounts
GARMIN_USER1_EMAIL=gerald@example.com
GARMIN_USER1_PASSWORD=changeme
GARMIN_USER1_NAME=Gerald

GARMIN_USER2_EMAIL=freundin@example.com
GARMIN_USER2_PASSWORD=changeme
GARMIN_USER2_NAME=Freundin

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=changeme

# Sync-Einstellungen
SYNC_HOUR=6
SYNC_LOOKBACK_DAYS=7
```

---

## Phase 1 — Implementierungs-Reihenfolge

```
Schritt 1: Projektstruktur anlegen + .env befüllen
Schritt 2: docker-compose.yml + db/init/01_schema.sql
Schritt 3: `docker compose up db` → Schema prüfen
Schritt 4: sync-service/requirements.txt + Dockerfile
Schritt 5: Domain Models + Repository Interface
Schritt 6: TimescaleDB Repository Implementierung
Schritt 7: Garmin Client + Mapper
Schritt 8: Scheduler + main.py
Schritt 9: `docker compose up` → erster Sync-Lauf
Schritt 10: Grafana Datasource + erstes Dashboard
```

---

## requirements.txt (Sync-Service)

```
garminconnect>=0.2.22
asyncpg>=0.29.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
apscheduler>=3.10.0
```

---

## Offene Punkte für Phase 2

- [ ] Grafana Dashboards: Aktivitäten, Schlaf, HRV, Body Battery, Stress, SpO2
- [ ] GPS Track Visualisierung (Grafana Geomap Panel)
- [ ] User-Vergleichs-Dashboard (Gerald vs. Freundin)
- [ ] Wochen/Monats-Aggregationen als Materialized Views
- [ ] Alerting (z.B. HRV unter Schwellwert)
