"""Tests fuer das datierte Glukosefenster des Insights-Berichts."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from src.db.glucose import get_glucose_tir_for_window


async def test_glucose_tir_uses_exact_user_and_exclusive_window():
    pool = AsyncMock()
    pool.fetchrow.return_value = {"tir_pct": Decimal("75.0")}
    start_at = datetime(2026, 3, 22, 23, tzinfo=timezone.utc)
    end_at = datetime(2026, 3, 29, 22, tzinfo=timezone.utc)

    with patch("src.db.glucose.get_pool", AsyncMock(return_value=pool)):
        result = await get_glucose_tir_for_window(9, start_at, end_at)

    assert result == Decimal("75.0")
    query, user_id, start, end = pool.fetchrow.await_args.args
    assert "user_id = $1" in query
    assert "time >= $2 AND time < $3" in query
    assert (user_id, start, end) == (9, start_at, end_at)


async def test_glucose_tir_without_readings_is_unavailable():
    pool = AsyncMock()
    pool.fetchrow.return_value = {"tir_pct": None}

    with patch("src.db.glucose.get_pool", AsyncMock(return_value=pool)):
        result = await get_glucose_tir_for_window(
            9,
            datetime(2026, 3, 22, 23, tzinfo=timezone.utc),
            datetime(2026, 3, 29, 22, tzinfo=timezone.utc),
        )

    assert result is None
