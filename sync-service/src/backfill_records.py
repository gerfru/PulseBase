"""Backfill GPS/HR records for activities that were synced before records were stored.

Run once per deployment (or manually) to populate activity_records for all historical
activities that have no records yet. Safe to call repeatedly; skips activities that
already have records (via get_activities_without_records query).

Usage:
    docker compose exec sync-service python backfill_records.py
    # or via Makefile: make backfill-records
"""

import asyncio
import tempfile

import structlog

from config import Settings, require_fernet_key
from crypto import (
    fernet_decrypt,
    restore_token_dir,
    serialize_token_dir,
    fernet_encrypt,
)
from garmin.client import GarminClient, garmin_call_async
from garmin.mapper import map_records
from repositories.timescale import TimescaleRepository

logger = structlog.get_logger(__name__)

_RATE_LIMIT_SLEEP = 0.5  # seconds between Garmin API calls


async def backfill_records_for_user(
    user: dict,
    repo: TimescaleRepository,
    settings: Settings,
) -> int:
    blob = await repo.get_user_token(user["id"], "garmin")
    if blob is None:
        logger.warning("backfill_records.no_token", user_id=user["id"])
        return 0

    missing = await repo.get_activities_without_records(user["id"])
    if not missing:
        logger.info("backfill_records.nothing_to_do", user_id=user["id"])
        return 0

    logger.info("backfill_records.started", user_id=user["id"], count=len(missing))
    inserted = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        raw = fernet_decrypt(blob, require_fernet_key(settings))
        restore_token_dir(raw, tmpdir)
        client = GarminClient(
            email=user["garmin_email"],
            password="",  # nosec B106 — intentionally empty; auth uses stored tokens
            token_dir=tmpdir,
        )
        await asyncio.to_thread(client.connect)

        for act in missing:
            garmin_id = act["garmin_activity_id"]
            db_id = act["db_id"]
            try:
                details = await garmin_call_async(
                    lambda: client.get_activity_details(garmin_id)
                )
                records = map_records(details)
                if records:
                    await repo.bulk_insert_records(db_id, records)
                    inserted += len(records)
                    logger.info(
                        "backfill_records.activity_done",
                        garmin_id=garmin_id,
                        records=len(records),
                    )
                else:
                    logger.debug("backfill_records.no_records", garmin_id=garmin_id)
            except Exception:
                logger.warning(
                    "backfill_records.activity_failed",
                    garmin_id=garmin_id,
                    exc_info=True,
                )
            await asyncio.sleep(_RATE_LIMIT_SLEEP)

        serialized = serialize_token_dir(tmpdir)
        encrypted = fernet_encrypt(serialized, require_fernet_key(settings))
        await repo.save_user_token(user["id"], "garmin", encrypted)

    logger.info(
        "backfill_records.complete",
        user_id=user["id"],
        activities=len(missing),
        records_inserted=inserted,
    )
    return inserted


async def main() -> None:
    settings = Settings()
    repo = TimescaleRepository(settings.db_url)
    await repo.init()
    try:
        users = await repo.get_active_users()
        logger.info("backfill_records.users", count=len(users))
        total = 0
        for user in users:
            try:
                total += await backfill_records_for_user(user, repo, settings)
            except Exception:
                logger.error(
                    "backfill_records.user_failed",
                    user_id=user["id"],
                    exc_info=True,
                )
        logger.info("backfill_records.all_done", total_records=total)
    finally:
        await repo.close()


if __name__ == "__main__":
    asyncio.run(main())
