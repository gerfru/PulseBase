import asyncpg
import structlog

logger = structlog.get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool(db_url: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    logger.info("ml_service.db_pool_initialized")


async def close_pool() -> None:
    if _pool:
        await _pool.close()


def _pool_or_raise() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Pool not initialized")
    return _pool


def get_pool() -> asyncpg.Pool:
    return _pool_or_raise()
