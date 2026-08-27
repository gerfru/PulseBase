import asyncpg


class TimescaleGlucoseRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def bulk_insert_glucose(self, user_id: int, rows: list[dict]) -> None:
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO glucose_readings (time, user_id, value_mgdl, trend, is_high, is_low)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id, time) DO NOTHING
                """,
                [
                    (
                        r["time"],
                        r["user_id"],
                        r["value_mgdl"],
                        r["trend"],
                        r["is_high"],
                        r["is_low"],
                    )
                    for r in rows
                ],
            )
