from .pool import get_pool


async def get_glucose_recent(user_id: int, hours: int = 24) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT time, value_mgdl, trend, is_high, is_low
        FROM glucose_readings
        WHERE user_id = $1
          AND time >= NOW() - ($2 * INTERVAL '1 hour')
        ORDER BY time DESC
        """,
        user_id,
        hours,
    )
    return [
        {
            "time": r["time"].isoformat(),
            "value_mgdl": r["value_mgdl"],
            "trend": r["trend"],
            "is_high": r["is_high"],
            "is_low": r["is_low"],
        }
        for r in rows
    ]


async def get_glucose_stats(user_id: int, days: int = 14) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT
            COUNT(*)                                                         AS total,
            ROUND(AVG(value_mgdl)::numeric, 1)                              AS avg_mgdl,
            MIN(value_mgdl)                                                  AS min_mgdl,
            MAX(value_mgdl)                                                  AS max_mgdl,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE value_mgdl BETWEEN 70 AND 180)
                / NULLIF(COUNT(*), 0)
            , 1)                                                             AS tir_pct,
            COUNT(*) FILTER (WHERE is_low  = true)                          AS count_low,
            COUNT(*) FILTER (WHERE is_high = true)                          AS count_high
        FROM glucose_readings
        WHERE user_id = $1
          AND time >= NOW() - ($2 * INTERVAL '1 day')
        """,
        user_id,
        days,
    )
    return dict(row) if row else {}
