import asyncio
import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import Settings
from garmin.client import GarminClient
from garmin.mapper import (
    map_activity,
    map_body_battery,
    map_hrv,
    map_records,
    map_sleep,
    map_stress,
    map_summary,
    map_training_status,
)
from logging_config import setup_logging
from repositories.timescale import TimescaleRepository

setup_logging()
logger = logging.getLogger(__name__)


async def sync_user(user: dict, repo: TimescaleRepository, days: int = 1) -> None:
    logger.info(f"Sync gestartet: {user['name']} ({days} Tage)")
    client = GarminClient(
        email=user["garmin_email"],
        password="",  # nosec B106 — intentionally empty; auth uses stored tokens
        token_dir=f"/app/tokens/{user['id']}",
    )
    client.connect()

    end = date.today()
    start = end - timedelta(days=days)

    raw_activities = client.get_activities(start, end)
    for raw in raw_activities:
        garmin_id = raw.get("activityId")
        if not garmin_id:
            continue
        activity = map_activity(raw, user["id"])
        activity_db_id = await repo.save_activity(activity)
        if activity_db_id and not await repo.records_exist(activity_db_id):
            details = client.get_activity_details(garmin_id)
            activity.records = map_records(details)
            if activity.records:
                await repo.bulk_insert_records(activity_db_id, activity.records)

    current = start
    while current <= end:
        try:
            summary_raw = client.get_daily_summary(current)
            await repo.upsert_daily(map_summary(summary_raw, user["id"], current))
        except Exception as e:
            logger.warning(f"Daily summary {current} fehlgeschlagen: {e}")

        try:
            sleep_raw = client.get_sleep(current)
            session = map_sleep(sleep_raw, user["id"])
            if (
                session
                and session.garmin_sleep_id
                and not await repo.sleep_exists(session.garmin_sleep_id)
            ):
                await repo.save_sleep(session)
        except Exception as e:
            logger.warning(f"Sleep {current} fehlgeschlagen: {e}")

        try:
            hrv_raw = client.get_hrv(current)
            hrv = map_hrv(hrv_raw, user["id"], current)
            if hrv:
                await repo.upsert_hrv(hrv)
        except Exception as e:
            logger.warning(f"HRV {current} fehlgeschlagen: {e}")

        try:
            bb_raw = client.get_body_battery(current)
            readings = map_body_battery(bb_raw, user["id"])
            await repo.bulk_insert("body_battery_intraday", user["id"], readings)
        except Exception as e:
            logger.warning(f"Body Battery {current} fehlgeschlagen: {e}")

        try:
            stress_raw = client.get_stress(current)
            readings = map_stress(stress_raw, user["id"])
            await repo.bulk_insert("stress_intraday", user["id"], readings)
        except Exception as e:
            logger.warning(f"Stress {current} fehlgeschlagen: {e}")

        try:
            ts_raw = client.get_training_status(current)
            status = map_training_status(ts_raw)
            if status:
                await repo.upsert_training_status(user["id"], current, status)
        except Exception as e:
            logger.warning(f"Training status {current} fehlgeschlagen: {e}")

        current += timedelta(days=1)

    logger.info(f"Sync fertig: {user['name']}")


async def get_active_users(repo: TimescaleRepository) -> list[dict]:
    async with repo._pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, garmin_email FROM users WHERE garmin_linked = true AND is_active = true"
        )
    return [dict(r) for r in rows]


async def get_sync_requested_users(repo: TimescaleRepository) -> list[dict]:
    async with repo._pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, garmin_email FROM users "
            "WHERE garmin_linked = true AND is_active = true AND sync_requested = true"
        )
    return [dict(r) for r in rows]


async def mark_sync_done(user_id: int, repo: TimescaleRepository) -> None:
    async with repo._pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET sync_requested = false, last_sync_at = NOW() WHERE id = $1",
            user_id,
        )


async def process_sync_requests(repo: TimescaleRepository) -> None:
    users = await get_sync_requested_users(repo)
    for user in users:
        logger.info(f"Manueller Sync: {user['name']}")
        try:
            await sync_user(user, repo, days=2)
        except Exception as e:
            logger.error(f"Manueller Sync Fehler {user['name']}: {e}", exc_info=True)
        finally:
            await mark_sync_done(user["id"], repo)


async def sync_all_users(repo: TimescaleRepository, days: int = 2) -> None:
    users = await get_active_users(repo)
    if not users:
        logger.info("Keine verknüpften Garmin-User gefunden — Sync übersprungen")
        return
    for user in users:
        try:
            await sync_user(user, repo, days=days)
        except Exception as e:
            logger.error(f"Sync Fehler {user['name']}: {e}", exc_info=True)
        finally:
            await mark_sync_done(user["id"], repo)


async def main() -> None:
    settings = Settings()
    repo = TimescaleRepository(settings.db_url)
    await repo.init()

    logger.info(f"Initialer Sync: {settings.sync_lookback_days} Tage")
    await sync_all_users(repo, days=settings.sync_lookback_days)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        sync_all_users,
        CronTrigger(hour=settings.sync_hour, minute=0),
        args=[repo, 2],
    )
    scheduler.add_job(
        process_sync_requests,
        "interval",
        minutes=1,
        args=[repo],
    )
    scheduler.start()
    logger.info(
        f"Scheduler aktiv — täglicher Sync um {settings.sync_hour}:00 Uhr, manuelle Requests alle 60s"
    )

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
