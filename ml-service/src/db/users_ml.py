import json
from datetime import date
from typing import Any

from .pool import _pool_or_raise


async def count_energy_gaps(user_id: int) -> int:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT COUNT(*) AS gaps
        FROM daily_summary d
        WHERE d.user_id = $1
          AND d.date < CURRENT_DATE
          AND (
            NOT EXISTS (
              SELECT 1 FROM ml_predictions p
              WHERE p.user_id = d.user_id
                AND p.date    = d.date
                AND p.model   = 'energy_physical'
            )
            OR NOT EXISTS (
              SELECT 1 FROM ml_predictions p
              WHERE p.user_id = d.user_id
                AND p.date    = d.date
                AND p.model   = 'body_battery_custom'
            )
            OR NOT EXISTS (
              SELECT 1 FROM ml_predictions p
              WHERE p.user_id = d.user_id
                AND p.date    = d.date
                AND p.model   = 'stress_score_custom'
            )
          )
        """,
        user_id,
    )
    return int(row["gaps"]) if row else 0


async def get_active_users() -> list[dict[str, Any]]:
    rows = await _pool_or_raise().fetch(
        "SELECT id, name FROM users WHERE is_active = true AND garmin_linked = true"
    )
    return [dict(r) for r in rows]


async def get_ml_requested_users() -> list[dict[str, Any]]:
    rows = await _pool_or_raise().fetch(
        "SELECT id FROM users WHERE ml_requested = true AND is_active = true"
    )
    return [dict(r) for r in rows]


async def mark_ml_done(user_id: int) -> None:
    await _pool_or_raise().execute(
        "UPDATE users SET ml_requested = false, last_ml_at = NOW() WHERE id = $1",
        user_id,
    )


async def get_user_profile(user_id: int) -> dict[str, Any]:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT date_of_birth, sex,
               DATE_PART('year', AGE(date_of_birth))::int AS age
        FROM users WHERE id = $1
        """,
        user_id,
    )
    if not row or not row["sex"] or not row["date_of_birth"]:
        return {"has_profile": False, "age": None, "sex": None}
    return {
        "has_profile": True,
        "age": int(row["age"]),
        "sex": row["sex"],
        "date_of_birth": str(row["date_of_birth"]),
    }


async def get_yesterday_prediction(user_id: int, model: str) -> float | None:
    row = await _pool_or_raise().fetchrow(
        """
        SELECT value FROM ml_predictions
        WHERE user_id = $1 AND model = $2
        ORDER BY date DESC LIMIT 1
        """,
        user_id,
        model,
    )
    return float(row["value"]) if row and row["value"] is not None else None


async def get_prediction_for_date(
    user_id: int, pred_date: date, model: str
) -> float | None:
    row = await _pool_or_raise().fetchrow(
        "SELECT value FROM ml_predictions WHERE user_id=$1 AND date=$2 AND model=$3",
        user_id,
        pred_date,
        model,
    )
    return float(row["value"]) if row and row["value"] is not None else None


async def save_prediction(
    user_id: int,
    pred_date: date,
    model: str,
    value: float | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await _pool_or_raise().execute(
        """
        INSERT INTO ml_predictions (date, user_id, model, value, metadata)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (date, user_id, model) DO UPDATE SET
            value      = EXCLUDED.value,
            metadata   = EXCLUDED.metadata,
            created_at = NOW()
        """,
        pred_date,
        user_id,
        model,
        value,
        json.dumps(metadata) if metadata is not None else None,
    )
