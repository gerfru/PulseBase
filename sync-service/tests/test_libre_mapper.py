import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from libre.mapper import map_reading


def _make_reading(
    value_mgdl: float = 95.0,
    timestamp: datetime | None = None,
    trend=3,
    is_high: bool | None = False,
    is_low: bool | None = False,
) -> MagicMock:
    r = MagicMock()
    r.value_in_mg_per_dl = value_mgdl
    r.timestamp = timestamp or datetime(2026, 4, 27, 8, 0, tzinfo=timezone.utc)
    r.trend_arrow = trend
    r.is_high = is_high
    r.is_low = is_low
    return r


class TestMapLibreReading:
    def test_maps_basic_fields(self):
        reading = _make_reading(value_mgdl=110.0, trend=2)
        result = map_reading(reading, user_id=5)
        assert result["user_id"] == 5
        assert result["value_mgdl"] == pytest.approx(110.0)
        assert result["trend"] == 2

    def test_timestamp_with_timezone_preserved(self):
        ts = datetime(2026, 4, 27, 12, 30, tzinfo=timezone.utc)
        result = map_reading(_make_reading(timestamp=ts), user_id=1)
        assert result["time"].tzinfo is not None
        assert result["time"] == ts

    def test_naive_timestamp_gets_utc(self):
        ts = datetime(2026, 4, 27, 12, 30)  # no tzinfo
        result = map_reading(_make_reading(timestamp=ts), user_id=1)
        assert result["time"].tzinfo == timezone.utc

    def test_is_high_and_is_low_mapped(self):
        result = map_reading(_make_reading(is_high=True, is_low=False), user_id=1)
        assert result["is_high"] is True
        assert result["is_low"] is False

    def test_none_is_high_is_low_preserved(self):
        result = map_reading(_make_reading(is_high=None, is_low=None), user_id=1)
        assert result["is_high"] is None
        assert result["is_low"] is None

    def test_trend_enum_value_extracted(self):
        trend_enum = SimpleNamespace(value=4)
        reading = _make_reading(trend=trend_enum)
        result = map_reading(reading, user_id=1)
        assert result["trend"] == 4

    def test_trend_int_passed_through(self):
        result = map_reading(_make_reading(trend=5), user_id=1)
        assert result["trend"] == 5
