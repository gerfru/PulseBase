from .pool import get_pool

# Modelle, fuer die Item-Level-Feedback (👍/👎) erfasst wird. Whitelist gegen
# beliebige Strings (vgl. service-Whitelist in users.save_user_token).
FEEDBACK_MODELS = ("readiness_rf", "anomaly_hr")


async def save_ml_feedback(user_id: int, model: str, helpful: bool) -> None:
    """Upsert binary feedback for today's prediction of a given model.

    prediction_date is stamped server-side (CURRENT_DATE). The UNIQUE constraint
    on (user_id, model, prediction_date) makes this idempotent and toggleable —
    a later 👎 overwrites an earlier 👍 for the same day.
    """
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO ml_feedback (user_id, model, prediction_date, helpful)
           VALUES ($1, $2, CURRENT_DATE, $3)
           ON CONFLICT (user_id, model, prediction_date)
           DO UPDATE SET helpful = EXCLUDED.helpful, updated_at = NOW()""",
        user_id,
        model,
        helpful,
    )


async def get_ml_feedback(user_id: int) -> dict[str, bool]:
    """Return today's feedback per model ({model: helpful}) for button state."""
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT model, helpful FROM ml_feedback
           WHERE user_id = $1 AND prediction_date = CURRENT_DATE""",
        user_id,
    )
    return {r["model"]: r["helpful"] for r in rows}
