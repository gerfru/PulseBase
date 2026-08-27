from typing import Any

import asyncpg


class TimescaleIntradayRepository:
    _allowed_tables = {"body_battery_intraday", "stress_intraday", "spo2_readings"}

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def bulk_insert(
        self, table: str, user_id: int, readings: list[tuple[Any, ...]]
    ) -> None:
        if not readings:
            return
        if table not in self._allowed_tables:
            raise ValueError(f"Unknown intraday table: {table}")
        async with self._pool.acquire() as conn:
            await conn.executemany(
                f"INSERT INTO {table} (time, user_id, value) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",
                [(timestamp, user_id, value) for timestamp, value in readings],
            )
