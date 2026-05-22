import asyncio
import json
import logging
import tempfile
from datetime import date, timedelta
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import Settings
from crypto import (
    fernet_decrypt,
    fernet_encrypt,
    restore_token_dir,
    serialize_token_dir,
)
from garmin.client import GarminClient
from libre.client import LibreAuthError, connect_with_token
from libre.client import get_recent_glucose
from libre.mapper import map_reading as map_glucose_reading
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


async def _sync_activities(
    client: GarminClient,
    repo: TimescaleRepository,
    user_id: int,
    start: date,
    end: date,
) -> None:
    for raw in client.get_activities(start, end):
        garmin_id = raw.get("activityId")
        if not garmin_id:
            continue
        activity = map_activity(raw, user_id)
        activity_db_id = await repo.save_activity(activity)
        if activity_db_id and not await repo.records_exist(activity_db_id):
            details = client.get_activity_details(garmin_id)
            activity.records = map_records(details)
            if activity.records:
                await repo.bulk_insert_records(activity_db_id, activity.records)


async def _sync_day(
    client: GarminClient, repo: TimescaleRepository, user_id: int, current: date
) -> None:
    """Sync all daily metrics for one date; each failure is logged but doesn't stop others."""
    try:
        summary_raw = client.get_daily_summary(current)
        await repo.upsert_daily(map_summary(summary_raw, user_id, current))
    except Exception as e:
        logger.warning(f"Daily summary {current} fehlgeschlagen: {e}")

    try:
        sleep_raw = client.get_sleep(current)
        session = map_sleep(sleep_raw, user_id)
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
        hrv = map_hrv(hrv_raw, user_id, current)
        if hrv:
            await repo.upsert_hrv(hrv)
    except Exception as e:
        logger.warning(f"HRV {current} fehlgeschlagen: {e}")

    try:
        bb_raw = client.get_body_battery(current)
        await repo.bulk_insert(
            "body_battery_intraday", user_id, map_body_battery(bb_raw, user_id)
        )
    except Exception as e:
        logger.warning(f"Body Battery {current} fehlgeschlagen: {e}")

    try:
        stress_raw = client.get_stress(current)
        await repo.bulk_insert(
            "stress_intraday", user_id, map_stress(stress_raw, user_id)
        )
    except Exception as e:
        logger.warning(f"Stress {current} fehlgeschlagen: {e}")

    try:
        ts_raw = client.get_training_status(current)
        status = map_training_status(ts_raw)
        if status:
            await repo.upsert_training_status(user_id, current, status)
    except Exception as e:
        logger.warning(f"Training status {current} fehlgeschlagen: {e}")


async def sync_user(
    user: dict, repo: TimescaleRepository, days: int, settings: Settings
) -> None:
    logger.info(f"Sync gestartet: {user['name']} ({days} Tage)")

    blob = await repo.get_user_token(user["id"], "garmin")
    if blob is None:
        file_dir = f"/app/tokens/{user['id']}"
        if Path(file_dir).exists():
            serialized = serialize_token_dir(file_dir)
            blob = (
                fernet_encrypt(serialized, settings.fernet_key)
                if settings.fernet_key
                else serialized
            )
            await repo.save_user_token(user["id"], "garmin", blob)
    if blob is None:
        logger.warning(f"Kein Garmin-Token für User {user['id']} — Sync übersprungen")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        raw = fernet_decrypt(blob, settings.fernet_key) if settings.fernet_key else blob
        restore_token_dir(raw, tmpdir)

        client = GarminClient(
            email=user["garmin_email"],
            password="",  # nosec B106 — intentionally empty; auth uses stored tokens
            token_dir=tmpdir,
        )
        client.connect()

        end = date.today()
        start = end - timedelta(days=days)

        await _sync_activities(client, repo, user["id"], start, end)

        current = start
        while current <= end:
            await _sync_day(client, repo, user["id"], current)
            current += timedelta(days=1)

        serialized = serialize_token_dir(tmpdir)
        encrypted = (
            fernet_encrypt(serialized, settings.fernet_key)
            if settings.fernet_key
            else serialized
        )
        await repo.save_user_token(user["id"], "garmin", encrypted)

    logger.info(f"Sync fertig: {user['name']}")


async def get_libre_users(repo: TimescaleRepository) -> list[dict]:
    async with repo._db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name FROM users WHERE libre_linked = true AND is_active = true"
        )
    return [dict(r) for r in rows]


async def sync_libre_user(
    user: dict, repo: TimescaleRepository, settings: Settings
) -> None:
    blob = await repo.get_user_token(user["id"], "libre")
    if blob is None:
        file_path = Path(f"/app/tokens/{user['id']}/libre/libre_token.json")
        if file_path.exists():
            raw = file_path.read_bytes()
            blob = (
                fernet_encrypt(raw, settings.fernet_key) if settings.fernet_key else raw
            )
            await repo.save_user_token(user["id"], "libre", blob)
    if blob is None:
        raise LibreAuthError(
            f"Kein LibreLinkUp-Token für User {user['id']} — Neu-Verknüpfung erforderlich"
        )

    raw = fernet_decrypt(blob, settings.fernet_key) if settings.fernet_key else blob
    token_data = json.loads(raw)
    client = connect_with_token(token_data["token"])
    readings = get_recent_glucose(client, hours=2)
    rows = [map_glucose_reading(r, user["id"]) for r in readings]
    await repo.bulk_insert_glucose(user["id"], rows)
    logger.info(f"Libre sync: user={user['id']} inserted {len(rows)} readings")


async def sync_all_libre(repo: TimescaleRepository, settings: Settings) -> None:
    users = await get_libre_users(repo)
    if not users:
        return
    for user in users:
        try:
            await sync_libre_user(user, repo, settings)
        except LibreAuthError as e:
            logger.warning(f"Libre auth error user={user['id']}: {e}")
        except Exception as e:
            logger.error(f"Libre sync failed user={user['id']}: {e}", exc_info=True)


async def get_active_users(repo: TimescaleRepository) -> list[dict]:
    async with repo._db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, garmin_email FROM users WHERE garmin_linked = true AND is_active = true"
        )
    return [dict(r) for r in rows]


async def get_sync_requested_users(repo: TimescaleRepository) -> list[dict]:
    async with repo._db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, garmin_email FROM users "
            "WHERE garmin_linked = true AND is_active = true AND sync_requested = true"
        )
    return [dict(r) for r in rows]


async def mark_sync_done(user_id: int, repo: TimescaleRepository) -> None:
    async with repo._db.acquire() as conn:
        await conn.execute(
            "UPDATE users SET sync_requested = false, last_sync_at = NOW() WHERE id = $1",
            user_id,
        )


async def set_ml_requested(user_id: int, repo: TimescaleRepository) -> None:
    async with repo._db.acquire() as conn:
        await conn.execute(
            "UPDATE users SET ml_requested = true WHERE id = $1",
            user_id,
        )


async def process_sync_requests(
    repo: TimescaleRepository, daily_days: int, settings: Settings
) -> None:
    users = await get_sync_requested_users(repo)
    for user in users:
        logger.info(f"Manueller Sync: {user['name']}")
        try:
            await sync_user(user, repo, days=daily_days, settings=settings)
        except Exception as e:
            logger.error(f"Manueller Sync Fehler {user['name']}: {e}", exc_info=True)
        finally:
            await set_ml_requested(user["id"], repo)
            await mark_sync_done(user["id"], repo)


async def sync_all_users(
    repo: TimescaleRepository, days: int, settings: Settings
) -> None:
    users = await get_active_users(repo)
    if not users:
        logger.info("Keine verknüpften Garmin-User gefunden — Sync übersprungen")
        return
    for user in users:
        try:
            await sync_user(user, repo, days=days, settings=settings)
        except Exception as e:
            logger.error(f"Sync Fehler {user['name']}: {e}", exc_info=True)
        finally:
            await mark_sync_done(user["id"], repo)


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    if not settings.fernet_key:
        logger.warning("FERNET_KEY not set — tokens stored unencrypted in DB")
    else:
        try:
            from cryptography.fernet import Fernet

            Fernet(settings.fernet_key.encode())
        except Exception:
            raise ValueError("FERNET_KEY invalid — must be 32-byte URL-safe base64")

    repo = TimescaleRepository(settings.db_url)
    await repo.init()

    logger.info(f"Initialer Sync: {settings.sync_lookback_days} Tage")
    await sync_all_users(repo, days=settings.sync_lookback_days, settings=settings)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        sync_all_users,
        CronTrigger(hour=settings.sync_hour, minute=0),
        args=[repo, settings.sync_daily_days, settings],
    )
    scheduler.add_job(
        process_sync_requests,
        "interval",
        minutes=1,
        args=[repo, settings.sync_daily_days, settings],
    )
    scheduler.add_job(
        sync_all_libre,
        "interval",
        minutes=5,
        args=[repo, settings],
        id="libre_sync",
    )
    scheduler.start()
    logger.info(
        f"Scheduler aktiv — täglicher Sync um {settings.sync_hour}:00 Uhr, manuelle Requests alle 60s"
    )

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
