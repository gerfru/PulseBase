"""Real-DB integration tests — verify SQL correctness without the HTTP layer.

Requires the test DB stack to be running. Skip unless DB_INT_TEST=true:
    make test-e2e  (sets up the stack and runs these automatically)
    or manually: DB_INT_TEST=true pytest api/tests/test_db_integration.py
"""

import asyncio
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

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


@_skip
@pytest.mark.asyncio
async def test_insights_daily_jobs_claim_and_recovery_with_real_database():
    from src.db.insight_jobs import (
        claim_daily_jobs,
        complete_daily_job,
        enqueue_daily_jobs,
        get_daily_job_status,
        requeue_stale_daily_jobs,
    )

    conn = await _conn()
    pool = await asyncpg.create_pool(**_DB)
    user_id = None
    period_end = date(2036, 11, 15)
    try:
        user_id = await _insert_test_user(conn, uuid.uuid4().hex[:8])
        await conn.execute(
            "UPDATE users SET garmin_linked = TRUE WHERE id = $1", user_id
        )
        with patch("src.db.insight_jobs.get_pool", AsyncMock(return_value=pool)):
            assert await enqueue_daily_jobs(period_end) == 1
            assert await enqueue_daily_jobs(period_end) == 0

            claims = await asyncio.gather(claim_daily_jobs(), claim_daily_jobs())
            claimed = [job for batch in claims for job in batch]
            assert len(claimed) == 1
            assert claimed[0]["user_id"] == user_id
            assert claimed[0]["attempts"] == 1

            await conn.execute(
                "UPDATE insights_daily_jobs SET claimed_at = NOW() - INTERVAL '1 hour' "
                "WHERE user_id = $1 AND period_end = $2",
                user_id,
                period_end,
            )
            assert await requeue_stale_daily_jobs(lease_seconds=1) == 1
            assert await get_daily_job_status(user_id, period_end) == "pending"
            await conn.execute(
                "UPDATE insights_daily_jobs SET available_at = NOW() - INTERVAL '1 minute' "
                "WHERE user_id = $1 AND period_end = $2",
                user_id,
                period_end,
            )
            retry = await claim_daily_jobs()
            assert len(retry) == 1 and retry[0]["attempts"] == 2
            await complete_daily_job(user_id, period_end, retry[0]["attempts"])
            assert await get_daily_job_status(user_id, period_end) == "completed"

            published_end = period_end + timedelta(days=1)
            await conn.execute(
                "INSERT INTO weekly_insights "
                "(user_id, period_start, period_end, insight_obj, catalog_version) "
                "VALUES ($1, $2, $3, '{}'::jsonb, 'test')",
                user_id,
                published_end - timedelta(days=6),
                published_end,
            )
            await conn.execute(
                "INSERT INTO weekly_insight_texts "
                "(user_id, period_end, segment, body, generator) "
                "VALUES ($1, $2, 'report', 'Test', 'fallback_template')",
                user_id,
                published_end,
            )
            assert await enqueue_daily_jobs(published_end) == 0

            recovering_end = period_end + timedelta(days=2)
            assert await enqueue_daily_jobs(recovering_end) == 1
            recovery_claim = await claim_daily_jobs()
            assert len(recovery_claim) == 1
            await conn.execute(
                "INSERT INTO weekly_insights "
                "(user_id, period_start, period_end, insight_obj, catalog_version) "
                "VALUES ($1, $2, $3, '{}'::jsonb, 'test')",
                user_id,
                recovering_end - timedelta(days=6),
                recovering_end,
            )
            await conn.execute(
                "INSERT INTO weekly_insight_texts "
                "(user_id, period_end, segment, body, generator) "
                "VALUES ($1, $2, 'report', 'Test', 'fallback_template')",
                user_id,
                recovering_end,
            )
            await conn.execute(
                "UPDATE insights_daily_jobs SET claimed_at = NOW() - INTERVAL '1 hour' "
                "WHERE user_id = $1 AND period_end = $2",
                user_id,
                recovering_end,
            )
            assert await requeue_stale_daily_jobs(lease_seconds=1) == 1
            status = await conn.fetchrow(
                "SELECT status, finished_at, last_error FROM insights_daily_jobs "
                "WHERE user_id = $1 AND period_end = $2",
                user_id,
                recovering_end,
            )
            assert status["status"] == "completed"
            assert status["finished_at"] is not None
            assert status["last_error"] is None
    finally:
        if user_id is not None:
            await conn.execute("DELETE FROM users WHERE id = $1", user_id)
        await pool.close()
        await conn.close()


@_skip
@pytest.mark.asyncio
async def test_insights_latest_report_is_scoped_and_published_only_once():
    from src.db.weekly_insights import (
        TextRecord,
        get_latest_weekly_insight,
        get_weekly_insight,
        save_weekly_insight,
    )
    from src.insights.models import WeeklyInsight

    conn = await _conn()
    pool = await asyncpg.create_pool(**_DB)
    user_id = None
    other_user_id = None
    period_end = date(2036, 11, 14)
    try:
        user_id = await _insert_test_user(conn, uuid.uuid4().hex[:8])
        other_user_id = await _insert_test_user(conn, uuid.uuid4().hex[:8])
        insight = WeeklyInsight(
            period_start=period_end - timedelta(days=6),
            period_end=period_end,
            metrics=[],
            flags=[],
            evidence=[],
            catalog_version="test",
        )
        with patch("src.db.weekly_insights.get_pool", AsyncMock(return_value=pool)):
            await save_weekly_insight(
                user_id,
                insight,
                TextRecord("Erster Bericht", "fallback_template", None),
            )
            await save_weekly_insight(
                user_id,
                insight,
                TextRecord("Ueberschrieben", "fallback_template", None),
            )
            latest = await get_latest_weekly_insight(
                user_id, period_end + timedelta(days=1)
            )
            assert latest is not None
            assert latest.insight.period_end == period_end
            assert latest.text.body == "Erster Bericht"
            assert (
                await get_weekly_insight(user_id, period_end + timedelta(days=1))
                is None
            )
            assert await get_latest_weekly_insight(user_id, period_end) is None
            assert (
                await get_latest_weekly_insight(
                    other_user_id, period_end + timedelta(days=1)
                )
                is None
            )
    finally:
        for test_user_id in (user_id, other_user_id):
            if test_user_id is not None:
                await conn.execute("DELETE FROM users WHERE id = $1", test_user_id)
        await pool.close()
        await conn.close()


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
