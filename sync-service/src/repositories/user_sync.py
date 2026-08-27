from typing import Protocol

import asyncpg


class UserSyncRepository(Protocol):
    async def get_active_users(self) -> list[dict]: ...

    async def get_sync_requested_users(self) -> list[dict]: ...

    async def get_libre_users(self) -> list[dict]: ...

    async def mark_sync_done(self, user_id: int) -> None: ...

    async def set_ml_requested(self, user_id: int) -> None: ...


class TimescaleUserSyncRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_active_users(self) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, garmin_email FROM users "
                "WHERE garmin_linked = true AND is_active = true"
            )
        return [dict(row) for row in rows]

    async def get_sync_requested_users(self) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, garmin_email FROM users "
                "WHERE garmin_linked = true AND is_active = true AND sync_requested = true"
            )
        return [dict(row) for row in rows]

    async def get_libre_users(self) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name FROM users WHERE libre_linked = true AND is_active = true"
            )
        return [dict(row) for row in rows]

    async def mark_sync_done(self, user_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET sync_requested = false, last_sync_at = NOW() WHERE id = $1",
                user_id,
            )

    async def set_ml_requested(self, user_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET ml_requested = true WHERE id = $1",
                user_id,
            )
            await conn.execute(
                """
                INSERT INTO service_events (event_type, user_id)
                VALUES ('ml_requested', $1)
                ON CONFLICT (event_type, user_id)
                WHERE status IN ('pending', 'processing') DO NOTHING
                """,
                user_id,
            )
