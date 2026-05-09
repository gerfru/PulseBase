"""Standalone entry point for manual energy history backfill.

Normally runs automatically on the first ML cycle after a sync (gap detection).
Use this only when you need to force a full recalculation (e.g. after formula changes).

Usage:
    make backfill-energy
    # or: docker compose exec ml-service python /app/src/backfill_energy.py
"""

import asyncio
import logging

from backfill import backfill_user
from config import Settings
from db import close_pool, get_pool, init_pool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    await init_pool(settings.db_url)
    try:
        users = await get_pool().fetch(
            "SELECT id FROM users WHERE is_active = true AND garmin_linked = true"
        )
        if not users:
            logger.warning("No active Garmin users found")
            return
        for user in users:
            n = await backfill_user(user["id"])
            if n == 0:
                logger.info(f"user={user['id']}: no gaps — already up to date")
        logger.info("Done. Trigger RF retraining: UPDATE users SET ml_requested = true")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
