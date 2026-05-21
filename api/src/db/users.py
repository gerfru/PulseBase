from datetime import date

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
        "SELECT id, name, email, password_hash, garmin_linked, garmin_email FROM users WHERE email = $1",
        email,
    )
    return dict(row) if row else None


async def get_user_by_id(user_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, name, email, garmin_linked, garmin_email, libre_linked, libre_email,
               date_of_birth, sex, epilepsy_mode, spo2_enabled
        FROM users WHERE id = $1
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


async def update_password(user_id: int, password_hash: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET password_hash = $1 WHERE id = $2",
        password_hash,
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
