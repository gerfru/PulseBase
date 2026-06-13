"""Tests for TimescaleRepository using mocked asyncpg pool — no real DB needed."""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from domain.models import Activity, DailySummary, HRVDaily, SleepSession, SportType
from repositories.timescale import TimescaleRepository


@pytest.fixture
def mock_repo():
    """Return (repo, conn) with pool and connection fully mocked."""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    repo = TimescaleRepository("postgresql://test/test")
    repo._pool = pool
    return repo, conn


def _activity(user_id: int = 1) -> Activity:
    return Activity(
        garmin_activity_id=12345,
        user_id=user_id,
        started_at=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
        sport_type=SportType.RUNNING,
        duration_seconds=3600,
    )


def _sleep(garmin_id: int = 999) -> SleepSession:
    return SleepSession(
        garmin_sleep_id=garmin_id,
        user_id=1,
        start_time=datetime(2026, 5, 1, 22, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 5, 2, 6, 0, tzinfo=timezone.utc),
    )


# ── Activity ──────────────────────────────────────────────────────────────────


class TestSaveActivity:
    async def test_returns_id_on_success(self, mock_repo):
        repo, conn = mock_repo
        conn.fetchrow.return_value = {"id": 42}
        result = await repo.save_activity(_activity())
        assert result == 42
        conn.fetchrow.assert_called_once()

    async def test_returns_none_when_no_row(self, mock_repo):
        repo, conn = mock_repo
        conn.fetchrow.return_value = None
        assert await repo.save_activity(_activity()) is None


class TestRecordsExist:
    async def test_true_when_row_exists(self, mock_repo):
        repo, conn = mock_repo
        conn.fetchrow.return_value = {"1": 1}
        assert await repo.records_exist(1) is True

    async def test_false_when_no_row(self, mock_repo):
        repo, conn = mock_repo
        conn.fetchrow.return_value = None
        assert await repo.records_exist(99) is False


class TestGetActivitiesWithoutRecords:
    async def test_returns_list_of_dicts(self, mock_repo):
        repo, conn = mock_repo
        conn.fetch.return_value = [
            {"db_id": 1, "garmin_activity_id": 111},
            {"db_id": 2, "garmin_activity_id": 222},
        ]
        result = await repo.get_activities_without_records(user_id=42)
        assert result == [
            {"db_id": 1, "garmin_activity_id": 111},
            {"db_id": 2, "garmin_activity_id": 222},
        ]
        conn.fetch.assert_called_once()

    async def test_returns_empty_list_when_all_have_records(self, mock_repo):
        repo, conn = mock_repo
        conn.fetch.return_value = []
        result = await repo.get_activities_without_records(user_id=42)
        assert result == []


class TestBulkInsertRecords:
    async def test_no_op_on_empty_list(self, mock_repo):
        repo, conn = mock_repo
        await repo.bulk_insert_records(1, [])
        conn.executemany.assert_not_called()

    async def test_calls_executemany_with_correct_tuple(self, mock_repo):
        repo, conn = mock_repo
        rec = MagicMock()
        rec.time = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)
        rec.heart_rate = 150
        rec.pace_sec_per_km = 300
        rec.cadence = 180
        rec.power = None
        rec.elevation = 100.0
        rec.distance = 1000.0
        rec.lat = 48.0
        rec.lng = 16.0
        await repo.bulk_insert_records(42, [rec])
        conn.executemany.assert_called_once()
        rows = conn.executemany.call_args.args[1]
        assert len(rows) == 1
        assert rows[0][1] == 42  # activity_id


# ── Daily Summary ─────────────────────────────────────────────────────────────


class TestUpsertDaily:
    async def test_calls_execute(self, mock_repo):
        repo, conn = mock_repo
        summary = DailySummary(date=date(2026, 5, 1), user_id=1, steps=8000)
        await repo.upsert_daily(summary)
        conn.execute.assert_called_once()

    async def test_passes_correct_values(self, mock_repo):
        repo, conn = mock_repo
        summary = DailySummary(date=date(2026, 5, 1), user_id=1, resting_hr=55)
        await repo.upsert_daily(summary)
        args = conn.execute.call_args.args
        assert date(2026, 5, 1) in args
        assert 1 in args


class TestUpsertTrainingStatus:
    async def test_passes_status_user_date(self, mock_repo):
        repo, conn = mock_repo
        await repo.upsert_training_status(1, date(2026, 5, 1), "PRODUCTIVE")
        args = conn.execute.call_args.args
        # args[0] = query string, args[1] = $1=user_id, args[2] = $2=day, args[3] = $3=status
        assert args[1] == 1
        assert args[2] == date(2026, 5, 1)
        assert args[3] == "PRODUCTIVE"

    async def test_param_order_matches_query_placeholders(self, mock_repo):
        """$1=user_id, $2=date, $3=status must match argument order."""
        repo, conn = mock_repo
        await repo.upsert_training_status(42, date(2026, 1, 15), "RECOVERY")
        args = conn.execute.call_args.args
        query: str = args[0]
        assert "VALUES ($1, $2, $3)" in query
        assert args[1] == 42  # $1 = user_id
        assert args[2] == date(2026, 1, 15)  # $2 = date
        assert args[3] == "RECOVERY"  # $3 = status


# ── Sleep ─────────────────────────────────────────────────────────────────────


class TestSaveSleep:
    async def test_returns_id(self, mock_repo):
        repo, conn = mock_repo
        conn.fetchrow.return_value = {"id": 7}
        assert await repo.save_sleep(_sleep()) == 7

    async def test_returns_none_on_conflict(self, mock_repo):
        repo, conn = mock_repo
        conn.fetchrow.return_value = None
        assert await repo.save_sleep(_sleep()) is None


class TestSleepExists:
    async def test_true_when_exists(self, mock_repo):
        repo, conn = mock_repo
        conn.fetchrow.return_value = {"id": 1}
        assert await repo.sleep_exists(999) is True

    async def test_false_when_not_exists(self, mock_repo):
        repo, conn = mock_repo
        conn.fetchrow.return_value = None
        assert await repo.sleep_exists(999) is False


# ── HRV ──────────────────────────────────────────────────────────────────────


class TestUpsertHrv:
    async def test_calls_execute_with_correct_args(self, mock_repo):
        repo, conn = mock_repo
        hrv = HRVDaily(
            date=date(2026, 5, 1), user_id=1, hrv_last_night=45, hrv_weekly_avg=50
        )
        await repo.upsert_hrv(hrv)
        conn.execute.assert_called_once()
        args = conn.execute.call_args.args
        assert date(2026, 5, 1) in args
        assert 1 in args


# ── Intraday bulk_insert ──────────────────────────────────────────────────────

_TS = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)


class TestBulkInsert:
    async def test_no_op_on_empty(self, mock_repo):
        repo, conn = mock_repo
        await repo.bulk_insert("body_battery_intraday", 1, [])
        conn.executemany.assert_not_called()

    async def test_body_battery_table_succeeds(self, mock_repo):
        repo, conn = mock_repo
        await repo.bulk_insert("body_battery_intraday", 1, [(_TS, 80)])
        conn.executemany.assert_called_once()

    async def test_stress_table_succeeds(self, mock_repo):
        repo, conn = mock_repo
        await repo.bulk_insert("stress_intraday", 1, [(_TS, 40)])
        conn.executemany.assert_called_once()

    async def test_spo2_table_succeeds(self, mock_repo):
        repo, conn = mock_repo
        await repo.bulk_insert("spo2_readings", 1, [(_TS, 98)])
        conn.executemany.assert_called_once()

    async def test_unknown_table_raises_value_error(self, mock_repo):
        repo, conn = mock_repo
        with pytest.raises(ValueError, match="Unknown intraday table"):
            await repo.bulk_insert("injected; DROP TABLE users;--", 1, [(_TS, 0)])


# ── Tokens ────────────────────────────────────────────────────────────────────


class TestGetUserToken:
    async def test_returns_bytes_when_found(self, mock_repo):
        repo, conn = mock_repo
        conn.fetchrow.return_value = {"token_data": b"secret_token"}
        result = await repo.get_user_token(1, "garmin")
        assert result == b"secret_token"

    async def test_returns_none_when_missing(self, mock_repo):
        repo, conn = mock_repo
        conn.fetchrow.return_value = None
        assert await repo.get_user_token(1, "garmin") is None


class TestSaveUserToken:
    async def test_calls_execute(self, mock_repo):
        repo, conn = mock_repo
        await repo.save_user_token(1, "garmin", b"token_bytes")
        conn.execute.assert_called_once()
        args = conn.execute.call_args.args
        assert 1 in args
        assert "garmin" in args
        assert b"token_bytes" in args


# ── User Queries ──────────────────────────────────────────────────────────────


class TestGetActiveUsers:
    async def test_returns_list_of_dicts(self, mock_repo):
        repo, conn = mock_repo
        conn.fetch.return_value = [
            {"id": 1, "name": "Alice", "garmin_email": "a@g.com"}
        ]
        result = await repo.get_active_users()
        assert result == [{"id": 1, "name": "Alice", "garmin_email": "a@g.com"}]

    async def test_returns_empty_list_when_no_users(self, mock_repo):
        repo, conn = mock_repo
        conn.fetch.return_value = []
        assert await repo.get_active_users() == []


class TestGetSyncRequestedUsers:
    async def test_returns_list(self, mock_repo):
        repo, conn = mock_repo
        conn.fetch.return_value = []
        assert await repo.get_sync_requested_users() == []


class TestGetLibreUsers:
    async def test_returns_list(self, mock_repo):
        repo, conn = mock_repo
        conn.fetch.return_value = [{"id": 2, "name": "Bob"}]
        result = await repo.get_libre_users()
        assert result == [{"id": 2, "name": "Bob"}]


class TestMarkSyncDone:
    async def test_calls_execute_with_user_id(self, mock_repo):
        repo, conn = mock_repo
        await repo.mark_sync_done(5)
        conn.execute.assert_called_once()
        assert 5 in conn.execute.call_args.args


class TestSetMlRequested:
    async def test_calls_execute_with_user_id(self, mock_repo):
        repo, conn = mock_repo
        await repo.set_ml_requested(3)
        conn.execute.assert_called_once()
        assert 3 in conn.execute.call_args.args


# ── Glucose ───────────────────────────────────────────────────────────────────


class TestBulkInsertGlucose:
    async def test_no_op_on_empty(self, mock_repo):
        repo, conn = mock_repo
        await repo.bulk_insert_glucose(1, [])
        conn.executemany.assert_not_called()

    async def test_calls_executemany_with_6_field_tuples(self, mock_repo):
        repo, conn = mock_repo
        rows = [
            {
                "time": _TS,
                "user_id": 1,
                "value_mgdl": 100,
                "trend": "flat",
                "is_high": False,
                "is_low": False,
            }
        ]
        await repo.bulk_insert_glucose(1, rows)
        conn.executemany.assert_called_once()
        inserted = conn.executemany.call_args.args[1]
        assert len(inserted) == 1
        assert len(inserted[0]) == 6


# ── _db property + init / close ───────────────────────────────────────────────


def test_db_property_raises_when_pool_not_initialized():
    repo = TimescaleRepository("postgresql://test/test")
    with pytest.raises(RuntimeError, match="Pool not initialized"):
        _ = repo._db


async def test_init_creates_pool():
    repo = TimescaleRepository("postgresql://test/test")
    mock_pool = MagicMock()
    with patch(
        "repositories.timescale.asyncpg.create_pool", AsyncMock(return_value=mock_pool)
    ):
        await repo.init()
    assert repo._pool is mock_pool


async def test_close_calls_pool_close():
    pool = AsyncMock()
    repo = TimescaleRepository("postgresql://test/test")
    repo._pool = pool
    await repo.close()
    pool.close.assert_awaited_once()


async def test_close_is_noop_when_pool_is_none():
    repo = TimescaleRepository("postgresql://test/test")
    await repo.close()  # must not raise
