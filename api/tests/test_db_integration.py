"""Real-DB integration tests — verify SQL correctness without the HTTP layer.

Requires the test DB stack to be running. Skip unless DB_INT_TEST=true:
    make test-e2e  (sets up the stack and runs these automatically)
    or manually: DB_INT_TEST=true pytest api/tests/test_db_integration.py
"""

import os
import uuid
from datetime import datetime, timezone

import asyncpg
import bcrypt
import pytest

_skip = pytest.mark.skipif(
    os.getenv("DB_INT_TEST") != "true",
    reason="requires test DB stack (set DB_INT_TEST=true)",
)

_DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5434")),
    database=os.getenv("DB_NAME", "garmin_test"),
    user=os.getenv("DB_APP_USER", "garmin_app"),
    password=os.getenv("DB_APP_PASSWORD", ""),  # pragma: allowlist secret
)


async def _conn() -> asyncpg.Connection:
    return await asyncpg.connect(**_DB)


async def _insert_test_user(conn: asyncpg.Connection, suffix: str) -> int:
    email = f"inttest-{suffix}@int.local"
    pw_hash = bcrypt.hashpw(b"TestPass1234!", bcrypt.gensalt()).decode()
    user_id: int = await conn.fetchval(
        """
        INSERT INTO users (name, email, password_hash, email_verified_at, is_active)
        VALUES ($1, $2, $3, NOW(), TRUE)
        RETURNING id
        """,
        f"IntTest {suffix}",
        email,
        pw_hash,
    )
    return user_id


# ── get_user_by_id ────────────────────────────────────────────────────────────


@_skip
@pytest.mark.asyncio
async def test_get_user_by_id_returns_none_for_inactive_user():
    """Inactive users must never appear in require_user lookups."""
    conn = await _conn()
    suffix = uuid.uuid4().hex[:8]
    try:
        user_id = await _insert_test_user(conn, suffix)
        await conn.execute("UPDATE users SET is_active = FALSE WHERE id = $1", user_id)

        os.environ["DB_APP_USER"] = _DB["user"]
        os.environ["DB_APP_PASSWORD"] = _DB["password"]  # pragma: allowlist secret
        os.environ["DB_APP_HOST"] = _DB["host"]

        from src.db.users import get_user_by_id

        result = await get_user_by_id(user_id)
        assert result is None
    finally:
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)
        await conn.close()


# ── increment_session_version ─────────────────────────────────────────────────


@_skip
@pytest.mark.asyncio
async def test_increment_session_version_increases_by_one():
    """Password reset must bump version so all existing signed cookies are rejected."""
    conn = await _conn()
    suffix = uuid.uuid4().hex[:8]
    try:
        user_id = await _insert_test_user(conn, suffix)
        version_before: int = await conn.fetchval(
            "SELECT session_version FROM users WHERE id = $1", user_id
        )

        from src.db.users import increment_session_version

        await increment_session_version(user_id)

        version_after: int = await conn.fetchval(
            "SELECT session_version FROM users WHERE id = $1", user_id
        )
        assert version_after == version_before + 1
    finally:
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)
        await conn.close()


# ── cascade delete ────────────────────────────────────────────────────────────


@_skip
@pytest.mark.asyncio
async def test_delete_user_cascades_to_related_tables():
    """delete_user must remove all health data so no orphaned rows remain."""
    conn = await _conn()
    suffix = uuid.uuid4().hex[:8]
    try:
        user_id = await _insert_test_user(conn, suffix)
        await conn.execute(
            """
            INSERT INTO daily_summary (date, user_id, steps)
            VALUES (CURRENT_DATE, $1, 5000)
            ON CONFLICT DO NOTHING
            """,
            user_id,
        )

        from src.db.users import delete_user

        await delete_user(user_id)

        remaining = await conn.fetchval(
            "SELECT COUNT(*) FROM daily_summary WHERE user_id = $1", user_id
        )
        assert remaining == 0

        user_gone = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE id = $1", user_id
        )
        assert user_gone == 0
    finally:
        await conn.execute("DELETE FROM daily_summary WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)
        await conn.close()


# ── seizure IDOR filter ───────────────────────────────────────────────────────


@_skip
@pytest.mark.asyncio
async def test_seizure_patch_idor_filter():
    """PATCH /api/seizures/{id} must return False when seizure belongs to another user."""
    conn = await _conn()
    suffix_a = uuid.uuid4().hex[:8]
    suffix_b = uuid.uuid4().hex[:8]
    seizure_id: int | None = None
    user_a: int | None = None
    user_b: int | None = None
    try:
        user_a = await _insert_test_user(conn, suffix_a)
        user_b = await _insert_test_user(conn, suffix_b)
        await conn.execute(
            "UPDATE users SET epilepsy_mode = TRUE WHERE id = ANY($1::int[])",
            [user_a, user_b],
        )
        seizure_id = await conn.fetchval(
            """
            INSERT INTO seizure_events (user_id, occurred_at, type)
            VALUES ($1, NOW(), 'focal')
            RETURNING id
            """,
            user_a,
        )

        from src.db.seizures import update_seizure

        result = await update_seizure(
            user_id=user_b,
            seizure_id=seizure_id,
            occurred_at=datetime.now(timezone.utc),
            duration_seconds=None,
            type_="focal",
            severity=None,
            notes=None,
        )
        assert result is False
    finally:
        if seizure_id:
            await conn.execute("DELETE FROM seizure_events WHERE id = $1", seizure_id)
        if user_a:
            await conn.execute("DELETE FROM users WHERE id = $1", user_a)
        if user_b:
            await conn.execute("DELETE FROM users WHERE id = $1", user_b)
        await conn.close()


# ── get_seizures user filter ──────────────────────────────────────────────────


@_skip
@pytest.mark.asyncio
async def test_get_seizures_filters_by_user_id():
    """get_seizures must only return seizure_events belonging to the requesting user."""
    conn = await _conn()
    suffix_a = uuid.uuid4().hex[:8]
    suffix_b = uuid.uuid4().hex[:8]
    seizure_a: int | None = None
    seizure_b: int | None = None
    user_a: int | None = None
    user_b: int | None = None
    try:
        user_a = await _insert_test_user(conn, suffix_a)
        user_b = await _insert_test_user(conn, suffix_b)

        seizure_a = await conn.fetchval(
            "INSERT INTO seizure_events (user_id, occurred_at, type) VALUES ($1, NOW(), 'focal') RETURNING id",
            user_a,
        )
        seizure_b = await conn.fetchval(
            "INSERT INTO seizure_events (user_id, occurred_at, type) VALUES ($1, NOW(), 'focal') RETURNING id",
            user_b,
        )

        from src.db.seizures import get_seizures

        results_a = await get_seizures(user_id=user_a, days=30)
        ids_a = {r["id"] for r in results_a}
        assert seizure_a in ids_a
        assert seizure_b not in ids_a
    finally:
        for sid in [seizure_a, seizure_b]:
            if sid:
                await conn.execute("DELETE FROM seizure_events WHERE id = $1", sid)
        for uid in [user_a, user_b]:
            if uid:
                await conn.execute("DELETE FROM users WHERE id = $1", uid)
        await conn.close()
