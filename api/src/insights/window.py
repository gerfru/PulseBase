"""Kalendertag und Zeitgrenzen fuer den taeglichen Insights-Bericht."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

REPORT_ZONE = ZoneInfo("Europe/Vienna")


def current_period_end(now: datetime | None = None) -> date:
    local_now = (
        now.astimezone(REPORT_ZONE) if now is not None else datetime.now(REPORT_ZONE)
    )
    return local_now.date() - timedelta(days=1)


def window_bounds(period_end: date) -> tuple[datetime, datetime]:
    start = datetime.combine(
        period_end - timedelta(days=6), time.min, tzinfo=REPORT_ZONE
    )
    end = datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=REPORT_ZONE)
    return start.astimezone(UTC), end.astimezone(UTC)
