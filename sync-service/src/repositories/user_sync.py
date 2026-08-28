from typing import Protocol

import asyncpg


class UserSyncRepository(Protocol):
    async def get_active_users(self) -> list[dict]: ...

    async def get_sync_requested_users(self) -> list[dict]: ...

    async def get_sync_user(self, user_id: int) -> dict | None: ...

    async def get_libre_users(self) -> list[dict]: ...

    async def mark_sync_done(self, user_id: int) -> None: ...

    async def clear_sync_requested(self, user_id: int) -> None: ...

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

    async def get_sync_user(self, user_id: int) -> dict | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, name, garmin_email FROM users "
                "WHERE id = $1 AND garmin_linked = true AND is_active = true",
                user_id,
            )
        return dict(row) if row else None

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

    async def clear_sync_requested(self, user_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET sync_requested = false WHERE id = $1",
                user_id,
            )

    async def set_ml_requested(self, user_id: int) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE users SET ml_requested = true WHERE id = $1",
                    user_id,
                )
                await conn.execute(
                    """
                    INSERT INTO service_events (event_type, user_id, payload)
                    VALUES (
                        'ml_requested',
                        $1,
                        jsonb_build_object(
                            'schema_version', 1,
                            'correlation_id', gen_random_uuid()::text,
                            'cause', 'sync_completed'
                        )
                    )
                    ON CONFLICT (event_type, user_id)
                    WHERE status IN ('pending', 'processing') DO UPDATE
                    SET generation = service_events.generation + 1,
                        payload = EXCLUDED.payload
                    """,
                    user_id,
                )
