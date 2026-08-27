from typing import Protocol

import asyncpg


class TokenRepository(Protocol):
    async def get_user_token(self, user_id: int, service: str) -> bytes | None: ...

    async def save_user_token(
        self, user_id: int, service: str, token_data: bytes
    ) -> None: ...


class TimescaleTokenRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_user_token(self, user_id: int, service: str) -> bytes | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT token_data FROM user_tokens WHERE user_id = $1 AND service = $2",
                user_id,
                service,
            )
        return bytes(row["token_data"]) if row else None

    async def save_user_token(
        self, user_id: int, service: str, token_data: bytes
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_tokens (user_id, service, token_data)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, service) DO UPDATE
                    SET token_data = $3, updated_at = NOW()
                """,
                user_id,
                service,
                token_data,
            )
