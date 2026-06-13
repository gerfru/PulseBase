from abc import ABC, abstractmethod
from typing import Any

from domain.models import Activity, DailySummary, HRVDaily, SleepSession


class ActivityRepository(ABC):
    @abstractmethod
    async def save_activity(self, activity: Activity) -> int | None: ...

    @abstractmethod
    async def records_exist(self, activity_id: int) -> bool: ...

    @abstractmethod
    async def get_activities_without_records(self, user_id: int) -> list[dict]: ...


class ActivityRecordRepository(ABC):
    @abstractmethod
    async def bulk_insert_records(self, activity_id: int, records: list) -> None: ...


class DailySummaryRepository(ABC):
    @abstractmethod
    async def upsert_daily(self, summary: DailySummary) -> None: ...


class SleepRepository(ABC):
    @abstractmethod
    async def save_sleep(self, session: SleepSession) -> int | None: ...

    @abstractmethod
    async def sleep_exists(self, garmin_sleep_id: int) -> bool: ...


class HRVRepository(ABC):
    @abstractmethod
    async def upsert_hrv(self, hrv: HRVDaily) -> None: ...


class IntradayRepository(ABC):
    @abstractmethod
    async def bulk_insert(
        self, table: str, user_id: int, readings: list[tuple[Any, ...]]
    ) -> None: ...
