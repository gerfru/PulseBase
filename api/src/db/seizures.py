from datetime import datetime

from .pool import get_pool


async def save_seizure(
    user_id: int,
    occurred_at: datetime,
    duration_seconds: int | None,
    type_: str,
    severity: int | None,
    notes: str | None,
) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO seizure_events
               (user_id, occurred_at, duration_seconds, type, severity, notes)
           VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
        user_id,
        occurred_at,
        duration_seconds,
        type_,
        severity,
        notes,
    )
    if row is None:
        raise RuntimeError("save_seizure: INSERT RETURNING returned no row")
    return int(row["id"])


async def get_seizures(user_id: int, days: int = 365) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT id, occurred_at, duration_seconds, type, severity, notes
           FROM seizure_events
           WHERE user_id = $1
             AND occurred_at >= NOW() - ($2 * INTERVAL '1 day')
           ORDER BY occurred_at DESC""",
        user_id,
        days,
    )
    result = []
    for r in rows:
        d = dict(r)
        d["occurred_at"] = d["occurred_at"].isoformat()
        result.append(d)
    return result


# ── Risk flag helpers ─────────────────────────────────────────────────────────
# Each helper returns (flags_to_append, severity_color).
# Threshold rationale: sleep debt >2h = amber (clinically meaningful partial deprivation),
# >5h = red (equivalent to total sleep deprivation risk).


def _check_sleep_debt(sleep_rows: list, sleep_debt_h: float) -> tuple[list[dict], str]:
    """Flag cumulative sleep debt over 7 nights; >5h = red, 2–5h = amber."""
    if sleep_debt_h > 5:
        return [
            {
                "label": "Schlafschuld",
                "detail": f"{sleep_debt_h:.1f}h in 7 Nächten",
                "color": "red",
            }
        ], "red"
    if sleep_debt_h > 2:
        return [
            {
                "label": "Schlafschuld",
                "detail": f"{sleep_debt_h:.1f}h in 7 Nächten",
                "color": "amber",
            }
        ], "amber"
    return [], "ok"


def _check_high_stress(avg_stress: int) -> tuple[list[dict], str]:
    """Flag average daily stress > 70 (Garmin stress scale 0–100)."""
    if avg_stress > 70:
        return [
            {
                "label": "Hoher Stress",
                "detail": f"Ø {avg_stress} gestern",
                "color": "amber",
            }
        ], "amber"
    return [], "ok"


def _check_hrv_drop(
    hrv_now: float | None, hrv_avg: float | None
) -> tuple[list[dict], str]:
    """Flag HRV drop > 20% below weekly average (autonomic nervous system stress)."""
    if hrv_now and hrv_avg and hrv_avg > 0 and hrv_now < hrv_avg * 0.8:
        drop_pct = round((1 - hrv_now / hrv_avg) * 100)
        return [
            {
                "label": "HRV-Einbruch",
                "detail": f"{hrv_now} ms (−{drop_pct}% vom Wochenschnitt)",
                "color": "amber",
            }
        ], "amber"
    return [], "ok"


def _check_low_body_battery(bb_low: float | None) -> tuple[list[dict], str]:
    """Flag body battery trough < 20 (critical energy depletion)."""
    if bb_low is not None and bb_low < 20:
        return [
            {
                "label": "Niedriger Body Battery",
                "detail": f"Tiefstwert {bb_low} gestern",
                "color": "amber",
            }
        ], "amber"
    return [], "ok"


def _check_intense_training(vigorous: int) -> tuple[list[dict], str]:
    """Flag >60 min vigorous intensity (overreaching risk in epilepsy context)."""
    if vigorous > 60:
        return [
            {
                "label": "Intensives Training",
                "detail": f"{vigorous} min vigorous gestern",
                "color": "amber",
            }
        ], "amber"
    return [], "ok"


def _check_resting_hr_spike(
    resting_hr: float | None, baseline: float | None
) -> tuple[list[dict], str]:
    """Flag resting HR > 10% above 30-day baseline (systemic stress marker)."""
    if resting_hr and baseline and resting_hr > float(baseline) * 1.1:
        return [
            {
                "label": "Erhöhte Ruheherzfrequenz",
                "detail": f"{resting_hr} bpm (Schnitt {int(baseline)} bpm)",
                "color": "amber",
            }
        ], "amber"
    return [], "ok"


def _merge_level(current: str, new: str) -> str:
    if new == "red" or current == "red":
        return "red"
    return new if new != "ok" else current


async def get_seizure_risk(user_id: int) -> dict:
    """Compute rule-based seizure risk from the last 7 days.

    Evaluates six risk factors: sleep debt, high stress, HRV drop, low body battery,
    intense training, and resting HR spike. Returns level ("ok"/"warning"/"red") + flags list.
    """
    pool = await get_pool()

    sleep_rows = await pool.fetch(
        """SELECT total_sleep_seconds FROM sleep_sessions
           WHERE user_id = $1 AND start_time >= NOW() - INTERVAL '8 days'
           ORDER BY start_time DESC LIMIT 7""",
        user_id,
    )
    sleep_debt_h = sum(
        max(0.0, 7.0 - (r["total_sleep_seconds"] or 0) / 3600.0) for r in sleep_rows
    )

    yesterday = await pool.fetchrow(
        """SELECT d.avg_stress, d.body_battery_low, d.resting_hr, d.intensity_vigorous,
                  h.hrv_last_night, h.hrv_weekly_avg
           FROM daily_summary d
           LEFT JOIN hrv_daily h ON h.user_id = d.user_id AND h.date = d.date
           WHERE d.user_id = $1
           ORDER BY d.date DESC LIMIT 1""",
        user_id,
    )

    flags: list[dict] = []
    level = "ok"

    new_flags, new_level = _check_sleep_debt(list(sleep_rows), sleep_debt_h)
    flags.extend(new_flags)
    level = _merge_level(level, new_level)

    if yesterday:
        for check_flags, check_level in [
            _check_high_stress(yesterday["avg_stress"] or 0),
            _check_hrv_drop(yesterday["hrv_last_night"], yesterday["hrv_weekly_avg"]),
            _check_low_body_battery(yesterday["body_battery_low"]),
            _check_intense_training(yesterday["intensity_vigorous"] or 0),
        ]:
            flags.extend(check_flags)
            level = _merge_level(level, check_level)

        if yesterday["resting_hr"]:
            hr_baseline_row = await pool.fetchrow(
                """SELECT ROUND(AVG(resting_hr)) AS baseline
                   FROM daily_summary
                   WHERE user_id = $1 AND resting_hr IS NOT NULL
                     AND date >= CURRENT_DATE - INTERVAL '30 days'
                     AND date < CURRENT_DATE""",
                user_id,
            )
            baseline = hr_baseline_row["baseline"] if hr_baseline_row else None
            hr_flags, hr_level = _check_resting_hr_spike(
                yesterday["resting_hr"], baseline
            )
            flags.extend(hr_flags)
            level = _merge_level(level, hr_level)

    return {"level": level, "flags": flags, "sleep_debt_h": round(sleep_debt_h, 1)}
