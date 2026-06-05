import asyncio
import json
import signal
import tempfile
import uuid
from datetime import date, timedelta
from pathlib import Path

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

from config import Settings
from scheduler import configure_scheduler
from crypto import (
    fernet_decrypt,
    fernet_encrypt,
    restore_token_dir,
    serialize_token_dir,
)
from garmin.client import GarminClient, garmin_call
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
from logging_config import configure_logging
from repositories.timescale import TimescaleRepository

configure_logging()
logger = structlog.get_logger(__name__)


async def _sync_activities(
    client: GarminClient,
    repo: TimescaleRepository,
    user_id: int,
    start: date,
    end: date,
) -> None:
    for raw in garmin_call(lambda: client.get_activities(start, end)):
        garmin_id = raw.get("activityId")
        if not garmin_id:
            continue
        activity = map_activity(raw, user_id)
        activity_db_id = await repo.save_activity(activity)
        if activity_db_id and not await repo.records_exist(activity_db_id):
            details = garmin_call(lambda: client.get_activity_details(garmin_id))
            activity.records = map_records(details)
            if activity.records:
                await repo.bulk_insert_records(activity_db_id, activity.records)


async def _sync_daily_summary_for_day(
    client: GarminClient, repo: TimescaleRepository, user_id: int, current: date
) -> None:
    try:
        summary_raw = garmin_call(lambda: client.get_daily_summary(current))
        await repo.upsert_daily(map_summary(summary_raw, user_id, current))
    except Exception as e:
        logger.warning("daily_summary.failed", date=str(current), error=str(e))


async def _sync_sleep_for_day(
    client: GarminClient, repo: TimescaleRepository, user_id: int, current: date
) -> None:
    try:
        sleep_raw = garmin_call(lambda: client.get_sleep(current))
        session = map_sleep(sleep_raw, user_id)
        if (
            session
            and session.garmin_sleep_id
            and not await repo.sleep_exists(session.garmin_sleep_id)
        ):
            await repo.save_sleep(session)
    except Exception as e:
        logger.warning("sleep.failed", date=str(current), error=str(e))


async def _sync_hrv_for_day(
    client: GarminClient, repo: TimescaleRepository, user_id: int, current: date
) -> None:
    try:
        hrv_raw = garmin_call(lambda: client.get_hrv(current))
        hrv = map_hrv(hrv_raw, user_id, current)
        if hrv:
            await repo.upsert_hrv(hrv)
    except Exception as e:
        logger.warning("hrv.failed", date=str(current), error=str(e))


async def _sync_body_battery_for_day(
    client: GarminClient, repo: TimescaleRepository, user_id: int, current: date
) -> None:
    try:
        bb_raw = garmin_call(lambda: client.get_body_battery(current))
        await repo.bulk_insert(
            "body_battery_intraday", user_id, map_body_battery(bb_raw, user_id)
        )
    except Exception as e:
        logger.warning("body_battery.failed", date=str(current), error=str(e))


async def _sync_stress_for_day(
    client: GarminClient, repo: TimescaleRepository, user_id: int, current: date
) -> None:
    try:
        stress_raw = garmin_call(lambda: client.get_stress(current))
        await repo.bulk_insert(
            "stress_intraday", user_id, map_stress(stress_raw, user_id)
        )
    except Exception as e:
        logger.warning("stress.failed", date=str(current), error=str(e))


async def _sync_training_status_for_day(
    client: GarminClient, repo: TimescaleRepository, user_id: int, current: date
) -> None:
    try:
        ts_raw = garmin_call(lambda: client.get_training_status(current))
        status = map_training_status(ts_raw)
        if status:
            await repo.upsert_training_status(user_id, current, status)
    except Exception as e:
        logger.warning("training_status.failed", date=str(current), error=str(e))


async def _sync_day(
    client: GarminClient, repo: TimescaleRepository, user_id: int, current: date
) -> None:
    """Sync all daily metrics for one date; each failure is logged but doesn't stop others."""
    await _sync_daily_summary_for_day(client, repo, user_id, current)
    await _sync_sleep_for_day(client, repo, user_id, current)
    await _sync_hrv_for_day(client, repo, user_id, current)
    await _sync_body_battery_for_day(client, repo, user_id, current)
    await _sync_stress_for_day(client, repo, user_id, current)
    await _sync_training_status_for_day(client, repo, user_id, current)


async def _get_garmin_token(
    user: dict, repo: TimescaleRepository, settings: Settings
) -> bytes | None:
    blob = await repo.get_user_token(user["id"], "garmin")
    if blob is None:
        file_dir = str(settings.token_base_dir / str(user["id"]))
        if Path(file_dir).exists():
            serialized = serialize_token_dir(file_dir)
            blob = (
                fernet_encrypt(serialized, settings.fernet_key)
                if settings.fernet_key
                else serialized
            )
            await repo.save_user_token(user["id"], "garmin", blob)
    return blob


def _init_garmin_client(
    user: dict, blob: bytes, settings: Settings, tmpdir: str
) -> GarminClient:
    raw = fernet_decrypt(blob, settings.fernet_key) if settings.fernet_key else blob
    restore_token_dir(raw, tmpdir)
    client = GarminClient(
        email=user["garmin_email"],
        password="",  # nosec B106 — intentionally empty; auth uses stored tokens
        token_dir=tmpdir,
    )
    client.connect()
    return client


async def _sync_date_range(
    client: GarminClient, repo: TimescaleRepository, user_id: int, days: int
) -> None:
    end = date.today()
    start = end - timedelta(days=days)
    await _sync_activities(client, repo, user_id, start, end)
    current = start
    while current <= end:
        await _sync_day(client, repo, user_id, current)
        current += timedelta(days=1)


async def sync_user(
    user: dict, repo: TimescaleRepository, days: int, settings: Settings
) -> None:
    bind_contextvars(job_id=str(uuid.uuid4())[:8])
    try:
        logger.info("sync.started", user_id=user["id"], days=days)
        blob = await _get_garmin_token(user, repo, settings)
        if blob is None:
            logger.warning("sync.no_token", user_id=user["id"])
            return
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _init_garmin_client(user, blob, settings, tmpdir)
            await _sync_date_range(client, repo, user["id"], days)
            serialized = serialize_token_dir(tmpdir)
            encrypted = (
                fernet_encrypt(serialized, settings.fernet_key)
                if settings.fernet_key
                else serialized
            )
            await repo.save_user_token(user["id"], "garmin", encrypted)
        logger.info("sync.done", user_id=user["id"])
    finally:
        clear_contextvars()


async def sync_libre_user(
    user: dict, repo: TimescaleRepository, settings: Settings
) -> None:
    bind_contextvars(job_id=str(uuid.uuid4())[:8])
    try:
        blob = await repo.get_user_token(user["id"], "libre")
        if blob is None:
            file_path = (
                settings.token_base_dir / str(user["id"]) / "libre" / "libre_token.json"
            )
            if file_path.exists():
                raw = file_path.read_bytes()
                blob = (
                    fernet_encrypt(raw, settings.fernet_key)
                    if settings.fernet_key
                    else raw
                )
                await repo.save_user_token(user["id"], "libre", blob)
        if blob is None:
            raise LibreAuthError(
                "Kein LibreLinkUp-Token — Neu-Verknüpfung erforderlich"
            )

        raw = fernet_decrypt(blob, settings.fernet_key) if settings.fernet_key else blob
        token_data = json.loads(raw)
        client = connect_with_token(token_data["token"])
        readings = get_recent_glucose(client, hours=2)
        rows = [map_glucose_reading(r, user["id"]) for r in readings]
        await repo.bulk_insert_glucose(user["id"], rows)
        logger.info("libre_sync.done", user_id=user["id"], readings=len(rows))
    finally:
        clear_contextvars()


async def sync_all_libre(repo: TimescaleRepository, settings: Settings) -> None:
    users = await repo.get_libre_users()
    if not users:
        return
    for user in users:
        try:
            await sync_libre_user(user, repo, settings)
        except LibreAuthError as e:
            logger.warning("libre_sync.auth_error", user_id=user["id"], error=str(e))
        except Exception as e:
            logger.error(
                "libre_sync.failed", user_id=user["id"], error=str(e), exc_info=True
            )


async def process_sync_requests(
    repo: TimescaleRepository, daily_days: int, settings: Settings
) -> None:
    users = await repo.get_sync_requested_users()
    for user in users:
        logger.info("sync.manual.started", user_id=user["id"])
        try:
            await sync_user(user, repo, days=daily_days, settings=settings)
        except Exception as e:
            logger.error(
                "sync.manual.failed", user_id=user["id"], error=str(e), exc_info=True
            )
        finally:
            await repo.set_ml_requested(user["id"])
            await repo.mark_sync_done(user["id"])


async def sync_all_users(
    repo: TimescaleRepository, days: int, settings: Settings
) -> None:
    users = await repo.get_active_users()
    if not users:
        logger.info("sync.no_users")
        return
    for user in users:
        try:
            await sync_user(user, repo, days=days, settings=settings)
        except Exception as e:
            logger.error("sync.failed", user_id=user["id"], error=str(e), exc_info=True)
        finally:
            await repo.set_ml_requested(user["id"])
            await repo.mark_sync_done(user["id"])


async def _run_initial_sync(
    repo: TimescaleRepository, settings: Settings, shutdown_event: asyncio.Event
) -> bool:
    """Run the initial full sync as a cancellable task. Returns True if shutdown triggered."""
    logger.info("sync.initial", lookback_days=settings.sync_lookback_days)
    initial_task = asyncio.create_task(
        sync_all_users(repo, days=settings.sync_lookback_days, settings=settings)
    )
    await asyncio.wait(
        {initial_task, asyncio.create_task(shutdown_event.wait())},
        return_when=asyncio.FIRST_COMPLETED,
    )
    if shutdown_event.is_set():
        initial_task.cancel()
        await asyncio.gather(initial_task, return_exceptions=True)
        logger.info("shutdown.during_initial_sync")
        return True
    return False


async def main() -> None:  # pragma: no cover
    settings = Settings()  # type: ignore[call-arg]
    try:
        from cryptography.fernet import Fernet

        Fernet(settings.fernet_key.encode())
    except Exception:
        raise ValueError("FERNET_KEY invalid — must be 32-byte URL-safe base64")

    if settings.sentry_dsn:
        import os
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            send_default_pii=False,
            traces_sample_rate=0.1,
            environment=os.getenv("APP_ENV", "production"),
            release=os.getenv("APP_VERSION", "unknown"),
        )
        logger.info("sentry.initialized")
    else:
        logger.warning("sentry.disabled", reason="SENTRY_DSN not configured")

    repo = TimescaleRepository(settings.db_url)
    await repo.init()

    # SIGTERM handler registered BEFORE blocking work so make down responds immediately
    shutdown_event = asyncio.Event()

    def _on_sigterm() -> None:
        logger.info("shutdown.sigterm_received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, _on_sigterm)

    # Sentinel written at startup so the healthcheck passes during the initial sync
    Path("/tmp/sync_alive").touch()  # nosec B108

    if await _run_initial_sync(repo, settings, shutdown_event):
        await repo.close()
        return

    scheduler = configure_scheduler(
        repo,
        settings,
        sync_all_users_fn=sync_all_users,
        process_sync_requests_fn=process_sync_requests,
        sync_all_libre_fn=sync_all_libre,
    )
    await shutdown_event.wait()

    logger.info("shutdown.graceful_start")
    scheduler.shutdown(wait=True)
    logger.info("shutdown.complete")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
