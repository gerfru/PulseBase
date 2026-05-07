# Roadmap

## Current State

**Phase 7 complete** (May 2026):
- Extended sport type support: 13 types now correctly stored and displayed (walking, strength training, yoga, indoor cycling, trail running, open water swimming, cardio, elliptical, fitness equipment)
- Weekly overview card on dashboard: stacked bar chart of run/ride km per week
- Readiness score: rule-based 0–100 from HRV, sleep, body battery, and stress — no new DB schema

**Phase 6 complete** (May 2026):
- Activity detail page (`/activity/{id}`) with GPS track (Leaflet.js + OpenStreetMap),
  HR/pace/elevation/cadence charts, stat grid, and aerobic/anaerobic training effect bars
- Aerobic + anaerobic training effect stored and backfilled via upsert on every sync
- Dashboard activity table rows clickable

**Phase 5 complete** (May 2026):
- Mobile-first UI redesign with shared CSS design system and auto dark mode
- Hero stat row on dashboard (steps, sleep score, HRV, body battery)
- Responsive charts that zoom out on large time ranges
- Activity filter by actual date range (not just row count)

**Phase 4 complete:**
- Self-hosted HTTPS dashboard (Caddy via homelab-gateway + FastAPI)
- Multi-user registration and login
- Garmin Connect sync (activities, sleep, HRV, body battery, stress, SpO2)
- JSON API + Chart.js dashboard (no Grafana dependency)

---

## Historical Data Import

The sync-service pulls data from `SYNC_LOOKBACK_DAYS` back. For historical data
(e.g. 5 years of existing Garmin history) there are two approaches:

### Option A — Garmin Data Export (recommended)

Garmin allows a full account export from connect.garmin.com → Account → Data Export.
The ZIP contains CSV/JSON files for all activity types.

A one-time import script would parse these files and insert them via the same
`TimescaleRepository` used by the sync-service.

### Option B — Extended sync lookback

Set `SYNC_LOOKBACK_DAYS=1800` in `.env` and run `make sync`. This will make ~1800
individual API calls — slow and may hit Garmin's rate limits.

Option A is faster and more reliable for bulk historical import.

---

## ML / Analytics

With 5+ years of data (~1800 days per user), the dataset is large enough for meaningful
machine learning.

### Short-term (scikit-learn, ~3 months data minimum)

- **Readiness prediction**: Random Forest on `[hrv_last_night, sleep_score, resting_hr]`
  → predicted training quality score for the next day
- **Anomaly detection**: Flag days where resting HR is significantly above personal baseline
  (early indicator of overtraining or illness)
- **Correlation analysis**: Sleep score → next-day pace/HR efficiency

### Medium-term (1D-CNN, ~1 year data recommended)

- **Intraday pattern classification**: Body battery curve shape over the day as input to a
  1D-CNN → classify recovery type (fast recovery, slow recovery, disrupted)
- **Stress pattern recognition**: Detect characteristic stress patterns from intraday data

### Long-term (LSTM)

- **7-day sequence forecasting**: Given last 7 days of HRV + sleep + body battery, predict
  tomorrow's readiness score
- **Seasonal performance modeling**: Identify consistent seasonal patterns in running
  efficiency (pace/HR ratio) across multiple years

### Implementation notes

- Training data lives in TimescaleDB — can be exported directly with `psql COPY` to CSV
- scikit-learn / PyTorch can run as a separate container or standalone script
- Model outputs can be stored back in a new `ml_predictions` table and surfaced via a new
  `/api/readiness` endpoint

---

## Other Potential Features

### Correlation dashboard

A dedicated view showing cross-metric correlations:
- Sleep score → next-day average HR at same pace
- HRV trend → weekly training load
- Body battery start → activity quality rating

### Weekly digest

Automated weekly summary (email or on-screen) with narrative text:
- Total distance, time
- Best and worst sleep nights
- HRV trend direction
- Anomalies flagged

### ~~GPS map view~~ ✓ Done in Phase 6

`activity_records` stores `lat`/`lng` per second. Leaflet.js map is now live on the
activity detail page.

### Custom sport-type mapping

Garmin's `typeKey` values don't always map cleanly to the current `SportType` enum.
Extend the enum and mapper to cover more types (strength training, yoga, indoor cycling,
open water swimming, etc.).
