"""Creates a CI test user directly in the test database.

Bypasses HTTP registration to avoid the email-verification requirement.
Requires asyncpg and bcrypt (both already in api/pyproject.toml dev deps).
"""

import asyncio
import os

import asyncpg
import bcrypt


async def main() -> None:
    email = os.environ["TEST_EMAIL"]
    password = os.environ["TEST_PASSWORD"]

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    conn = await asyncpg.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5433")),
        database=os.environ.get("DB_NAME", "garmin_test"),
        user=os.environ.get("DB_USER", "garmin"),
        password=os.environ.get("DB_PASSWORD", ""),
    )
    try:
        user_id = await conn.fetchval(
            """
            INSERT INTO users (name, email, password_hash, email_verified_at, is_active)
            VALUES ($1, $2, $3, NOW(), TRUE)
            ON CONFLICT (email) DO UPDATE
                SET password_hash   = EXCLUDED.password_hash,
                    email_verified_at = NOW(),
                    is_active         = TRUE
            RETURNING id
            """,
            "CI Test",
            email,
            pw_hash,
        )
        for consent_type in ("health_data", "terms", "age_16plus"):
            await conn.execute(
                """
                INSERT INTO user_consents
                    (user_id, consent_type, accepted, ip_address, privacy_policy_version)
                VALUES ($1, $2, TRUE, '127.0.0.1', '1.0')
                ON CONFLICT (user_id, consent_type) DO NOTHING
                """,
                user_id,
                consent_type,
            )
        print(f"CI user created: {email} (id={user_id})")
    finally:
        await conn.close()


asyncio.run(main())
