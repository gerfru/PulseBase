from datetime import date
from typing import Any

from db.users_ml import (
    get_prediction_for_date,
    get_yesterday_prediction,
    save_prediction,
)


class PredictionRepository:
    async def get_yesterday(self, user_id: int, model: str) -> float | None:
        return await get_yesterday_prediction(user_id, model)

    async def get_for_date(
        self, user_id: int, prediction_date: date, model: str
    ) -> float | None:
        return await get_prediction_for_date(user_id, prediction_date, model)

    async def save(
        self,
        user_id: int,
        prediction_date: date,
        model: str,
        value: float | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await save_prediction(user_id, prediction_date, model, value, metadata)
