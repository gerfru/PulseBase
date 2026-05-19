import json
from datetime import date, timedelta

from .pool import get_pool


async def get_ml_insights(user_id: int) -> dict:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT DISTINCT ON (model) model, value, metadata
        FROM ml_predictions
        WHERE user_id = $1
          AND (
              (model != 'model_meta_rf' AND date >= CURRENT_DATE - 1)
              OR model = 'model_meta_rf'
          )
        ORDER BY model, date DESC
        """,
        user_id,
    )
    result: dict = {}
    for row in rows:
        meta = json.loads(row["metadata"]) if row["metadata"] else {}
        result[row["model"]] = {"value": row["value"], **meta}
    return result


async def get_ml_history(
    user_id: int, days: int = 30, end_date: date | None = None
) -> dict:
    pool = await get_pool()
    end = end_date if end_date is not None else date.today()
    cutoff = end - timedelta(days=days)
    rows = await pool.fetch(
        """
        SELECT date, model, value, metadata
        FROM ml_predictions
        WHERE user_id = $1 AND date >= $2 AND date <= $3
        ORDER BY date ASC
        """,
        user_id,
        cutoff,
        end,
    )
    result: dict = {}
    for row in rows:
        meta = json.loads(row["metadata"]) if row["metadata"] else {}
        entry = {"date": str(row["date"]), "value": row["value"], **meta}
        result.setdefault(row["model"], []).append(entry)
    return result


async def get_ml_status(user_id: int) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT ml_requested, last_ml_at FROM users WHERE id = $1",
        user_id,
    )
    return {
        "pending": row["ml_requested"] if row else False,
        "last_ml_at": row["last_ml_at"].isoformat()
        if row and row["last_ml_at"]
        else None,
    }
