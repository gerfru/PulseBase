import shutil
from datetime import date, datetime, timezone
from pathlib import Path

from .pool import get_pool


async def create_user(name: str, email: str, password_hash: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO users (name, email, password_hash)
        VALUES ($1, $2, $3)
        RETURNING id, name, email, garmin_linked, garmin_email
        """,
        name,
        email,
        password_hash,
    )
    if row is None:
        raise RuntimeError("create_user: INSERT RETURNING returned no row")
    return dict(row)


async def get_user_by_email(email: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, email, password_hash, garmin_linked, garmin_email,"
        " failed_login_attempts, locked_until, email_verified_at"
        " FROM users WHERE email = $1 AND is_active = true",
        email,
    )
    return dict(row) if row else None


async def get_user_by_id(user_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, name, email, garmin_linked, garmin_email, libre_linked, libre_email,
               date_of_birth, sex, epilepsy_mode, spo2_enabled
        FROM users WHERE id = $1 AND is_active = true
        """,
        user_id,
    )
    return dict(row) if row else None


async def update_user_profile(
    user_id: int,
    date_of_birth: date | None,
    sex: str | None,
) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET date_of_birth = $1, sex = $2 WHERE id = $3",
        date_of_birth,
        sex,
        user_id,
    )


async def update_epilepsy_mode(user_id: int, epilepsy_mode: bool) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET epilepsy_mode = $1 WHERE id = $2",
        epilepsy_mode,
        user_id,
    )


async def update_spo2_enabled(user_id: int, spo2_enabled: bool) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET spo2_enabled = $1 WHERE id = $2",
        spo2_enabled,
        user_id,
    )


async def set_garmin_linked(user_id: int, garmin_email: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET garmin_linked = true, garmin_email = $1 WHERE id = $2",
        garmin_email,
        user_id,
    )


async def set_garmin_unlinked(user_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET garmin_linked = false, garmin_email = null WHERE id = $1",
        user_id,
    )


async def set_libre_linked(user_id: int, libre_email: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET libre_linked = true, libre_email = $2 WHERE id = $1",
        user_id,
        libre_email,
    )


async def set_libre_unlinked(user_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE users SET libre_linked = false, libre_email = null WHERE id = $1",
                user_id,
            )
            await conn.execute(
                "DELETE FROM glucose_readings WHERE user_id = $1",
                user_id,
            )
            await conn.execute(
                "DELETE FROM user_tokens WHERE user_id = $1 AND service = 'libre'",
                user_id,
            )


async def update_password(user_id: int, password_hash: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET password_hash = $1 WHERE id = $2",
        password_hash,
        user_id,
    )


async def increment_failed_login(user_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET failed_login_attempts = failed_login_attempts + 1 WHERE id = $1",
        user_id,
    )


async def lock_user_until(user_id: int, until: datetime) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET locked_until = $1 WHERE id = $2",
        until,
        user_id,
    )


async def reset_failed_login(user_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = $1",
        user_id,
    )


async def set_email_verified(user_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET email_verified_at = NOW() WHERE id = $1",
        user_id,
    )


async def get_user_sex(user_id: int) -> str:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT sex FROM users WHERE id = $1", user_id)
    return str(row["sex"]) if row and row["sex"] else "male"


async def request_sync(user_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET sync_requested = true WHERE id = $1",
        user_id,
    )


async def get_sync_status(user_id: int) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT sync_requested, last_sync_at FROM users WHERE id = $1",
        user_id,
    )
    return {
        "pending": row["sync_requested"] if row else False,
        "last_sync_at": row["last_sync_at"].isoformat()
        if row and row["last_sync_at"]
        else None,
    }


async def get_ml_status(user_id: int) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT ml_requested, last_ml_at FROM users WHERE id = $1",
        user_id,
    )
    return {
        "pending": row["ml_requested"] if row else False,
        "last_ml_at": row["last_ml_at"].isoformat()
        if row and row["last_ml_at"]
        else None,
    }


async def delete_user(user_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM ml_predictions WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM seizure_events WHERE user_id = $1", user_id)
            await conn.execute(
                "DELETE FROM glucose_readings WHERE user_id = $1", user_id
            )
            await conn.execute("DELETE FROM hrv_daily WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM sleep_sessions WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM daily_summary WHERE user_id = $1", user_id)
            await conn.execute(
                "DELETE FROM activity_records WHERE activity_id IN "
                "(SELECT id FROM activities WHERE user_id = $1)",
                user_id,
            )
            await conn.execute("DELETE FROM activities WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM users WHERE id = $1", user_id)
    # Token cleanup AFTER transaction — FS errors must not roll back the DB deletion
    token_dir = Path(f"/app/tokens/{user_id}")
    if token_dir.exists():
        shutil.rmtree(token_dir)


async def get_user_token(user_id: int, service: str) -> bytes | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT token_data FROM user_tokens WHERE user_id = $1 AND service = $2",
        user_id,
        service,
    )
    return bytes(row["token_data"]) if row else None


async def save_user_token(user_id: int, service: str, token_data: bytes) -> None:
    pool = await get_pool()
    await pool.execute(
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


async def save_reset_token(user_id: int, token_hash: str, expires_at: datetime) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET password_reset_token_hash = $2, password_reset_expires_at = $3 WHERE id = $1",
        user_id,
        token_hash,
        expires_at,
    )


async def get_reset_token_user_id(token_hash: str) -> int | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id FROM users WHERE password_reset_token_hash = $1 AND password_reset_expires_at > NOW()",
        token_hash,
    )
    return int(row["id"]) if row else None


async def clear_reset_token(user_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET password_reset_token_hash = NULL, password_reset_expires_at = NULL WHERE id = $1",
        user_id,
    )


async def save_consent(
    user_id: int,
    consent_type: str,
    accepted: bool,
    ip_address_hash: str | None,
    policy_version: str = "v1.0",
) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO user_consents
            (user_id, consent_type, accepted, ip_address_hash, privacy_policy_version)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id, consent_type) DO UPDATE
            SET accepted = $3, timestamp = NOW(), ip_address_hash = $4
        """,
        user_id,
        consent_type,
        accepted,
        ip_address_hash,
        policy_version,
    )


async def export_user_data(user_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, name, email, created_at, email_verified_at,
                      date_of_birth, sex, epilepsy_mode, spo2_enabled,
                      garmin_linked, garmin_email, libre_linked, libre_email
               FROM users WHERE id = $1""",
            user_id,
        )
        if row is None:
            raise RuntimeError(f"export_user_data: user {user_id} not found")
        user = dict(row)
        activities = [
            dict(r)
            for r in await conn.fetch(
                "SELECT * FROM activities WHERE user_id = $1 ORDER BY started_at",
                user_id,
            )
        ]
        sleep = [
            dict(r)
            for r in await conn.fetch(
                "SELECT * FROM sleep_sessions WHERE user_id = $1 ORDER BY start_time",
                user_id,
            )
        ]
        hrv = [
            dict(r)
            for r in await conn.fetch(
                "SELECT * FROM hrv_daily WHERE user_id = $1 ORDER BY date",
                user_id,
            )
        ]
        daily = [
            dict(r)
            for r in await conn.fetch(
                "SELECT * FROM daily_summary WHERE user_id = $1 ORDER BY date",
                user_id,
            )
        ]
        seizures = [
            dict(r)
            for r in await conn.fetch(
                "SELECT * FROM seizure_events WHERE user_id = $1 ORDER BY occurred_at",
                user_id,
            )
        ]
        glucose = [
            dict(r)
            for r in await conn.fetch(
                "SELECT * FROM glucose_readings WHERE user_id = $1 ORDER BY time",
                user_id,
            )
        ]
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "user": user,
        "activities": activities,
        "sleep_sessions": sleep,
        "hrv_daily": hrv,
        "daily_summary": daily,
        "seizure_events": seizures,
        "glucose_readings": glucose,
    }
