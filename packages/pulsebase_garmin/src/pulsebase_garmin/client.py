from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import garminconnect
import structlog

logger = structlog.get_logger(__name__)


class GarminClient:
    def __init__(
        self,
        email: str,
        password: str,
        token_dir: str,
        *,
        token_only: bool | None = None,
    ) -> None:
        self.email = email
        self.password = password
        self.token_dir = token_dir
        self._client: Any = None
        self.token_only = token_only if token_only is not None else not bool(password)

    def connect(self) -> None:
        Path(self.token_dir).mkdir(parents=True, exist_ok=True)
        self._client = garminconnect.Garmin(email=self.email, password=self.password)

        if self.token_only or not self.password:
            self._client.login(self.token_dir)
            logger.info("garmin.connect.token_only")
            return

        try:
            self._client.login(self.token_dir)
            logger.info("garmin.connect.token_login")
        except Exception:
            logger.warning("garmin.connect.failed", reason="retrying_fresh_login")
            self._client.login()
            self._client.garth.dump(self.token_dir)
            logger.info("garmin.connect.fresh_login")

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
