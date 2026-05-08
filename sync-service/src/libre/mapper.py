from datetime import timezone
from typing import Any


def map_reading(reading: Any, user_id: int) -> dict:
    """Map a pylibrelinkup GlucoseReading to a DB row dict."""
    ts = reading.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    trend = reading.trend_arrow
    if hasattr(trend, "value"):
        trend = int(trend.value)
    elif trend is not None:
        trend = int(trend)

    return {
        "time": ts,
        "user_id": user_id,
        "value_mgdl": float(reading.value_in_mg_per_dl),
        "trend": trend,
        "is_high": bool(reading.is_high) if reading.is_high is not None else None,
        "is_low": bool(reading.is_low) if reading.is_low is not None else None,
    }
