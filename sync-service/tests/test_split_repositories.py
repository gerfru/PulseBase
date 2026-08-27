from unittest.mock import AsyncMock, MagicMock

from repositories.tokens import TimescaleTokenRepository
from repositories.user_sync import TimescaleUserSyncRepository


def make_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


async def test_token_repository_reads_and_writes_tokens():
    pool, conn = make_pool()
    repository = TimescaleTokenRepository(pool)
    conn.fetchrow.return_value = {"token_data": bytearray(b"token")}

    assert await repository.get_user_token(1, "garmin") == b"token"
    await repository.save_user_token(1, "garmin", b"new-token")

    conn.fetchrow.assert_awaited_once()
    conn.execute.assert_awaited_once()


async def test_user_sync_repository_writes_ml_event():
    pool, conn = make_pool()
    repository = TimescaleUserSyncRepository(pool)

    await repository.set_ml_requested(7)

    assert conn.execute.await_count == 2
    assert "service_events" in conn.execute.await_args_list[1].args[0]
