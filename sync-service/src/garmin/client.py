import logging
from datetime import date
from pathlib import Path
from typing import Any

import garminconnect

logger = logging.getLogger(__name__)


class GarminClient:
    def __init__(self, email: str, password: str, token_dir: str) -> None:
        self.email = email
        self.password = password
        self.token_dir = token_dir
        self._client: Any = None

    def connect(self) -> None:
        Path(self.token_dir).mkdir(parents=True, exist_ok=True)
        self._client = garminconnect.Garmin(email=self.email, password=self.password)
        if self.password:
            # Frischer Login (API-Service beim Garmin-Linking)
            try:
                self._client.login(self.token_dir)
                logger.info(f"Login via Token: {self.email}")
            except Exception as exc:
                logger.warning(
                    "Token-Login fehlgeschlagen (%s), versuche frischen Login", exc
                )
                self._client.login()
                self._client.garth.dump(self.token_dir)
                logger.info(f"Frischer Login: {self.email}")
        else:
            # Sync-Service: nur Token-Login, kein Passwort vorhanden
            self._client.login(self.token_dir)
            logger.info(f"Token-Login: {self.email}")

    def save_token(self) -> None:
        if self._client and hasattr(self._client, "garth"):
            self._client.garth.dump(self.token_dir)
            logger.debug("Garmin token auf Disk gespeichert")

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
