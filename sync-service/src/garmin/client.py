from collections.abc import Callable
import asyncio
from datetime import date
from pathlib import Path
from typing import Any, TypeVar

import garminconnect
import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential
from resilience import CircuitBreaker

logger = structlog.get_logger(__name__)

_T = TypeVar("_T")


def garmin_call(fn: Callable[[], _T], breaker: CircuitBreaker | None = None) -> _T:
    """Call a synchronous Garmin API function with up to 3 retries and exponential backoff."""
    for attempt in Retrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    ):
        with attempt:
            return breaker.call(fn) if breaker else fn()
    raise RuntimeError(
        "unreachable: tenacity reraises on exhaustion"
    )  # pragma: no cover


async def garmin_call_async(
    fn: Callable[[], _T], breaker: CircuitBreaker | None = None
) -> _T:
    return await asyncio.to_thread(garmin_call, fn, breaker)


class GarminClient:
    def __init__(self, email: str, password: str, token_dir: str) -> None:
        self.email = email
        self.password = password
        self.token_dir = token_dir
        self._client: Any = None
        self._breaker = CircuitBreaker()

    @property
    def breaker(self) -> CircuitBreaker:
        return self._breaker

    def connect(self) -> None:
        Path(self.token_dir).mkdir(parents=True, exist_ok=True)
        self._client = garminconnect.Garmin(email=self.email, password=self.password)
        if self.password:
            # Frischer Login (API-Service beim Garmin-Linking)
            try:
                self._client.login(self.token_dir)
                logger.info("garmin.connect.token_login")
            except Exception:
                logger.warning("garmin.connect.failed", reason="retrying_fresh_login")
                self._client.login()
                self._client.garth.dump(self.token_dir)
                logger.info("garmin.connect.fresh_login")
        else:
            # Sync-Service: nur Token-Login, kein Passwort vorhanden
            self._client.login(self.token_dir)
            logger.info("garmin.connect.token_only")

    def save_token(self) -> None:
        if self._client and hasattr(self._client, "garth"):
            self._client.garth.dump(self.token_dir)
            logger.debug("garmin.token.saved")

    def get_activities(self, start: date, end: date) -> list[dict[str, Any]]:
        return (
            self._client.get_activities_by_date(start.isoformat(), end.isoformat())
            or []
        )

    def get_activity_details(self, activity_id: int) -> dict[str, Any]:
        return self._client.get_activity_details(activity_id) or {}

    def get_daily_summary(self, day: date) -> dict[str, Any]:
        return self._client.get_stats(day.isoformat()) or {}

    def get_sleep(self, day: date) -> dict[str, Any]:
        return self._client.get_sleep_data(day.isoformat()) or {}

    def get_hrv(self, day: date) -> dict[str, Any]:
        return self._client.get_hrv_data(day.isoformat()) or {}

    def get_body_battery(self, day: date) -> list[dict]:
        return self._client.get_body_battery(day.isoformat(), day.isoformat()) or []

    def get_stress(self, day: date) -> dict[str, Any]:
        return self._client.get_stress_data(day.isoformat()) or {}

    def get_training_status(self, day: date) -> dict[str, Any]:
        return self._client.get_training_status(day.isoformat()) or {}
