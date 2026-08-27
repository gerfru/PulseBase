from datetime import date
from unittest.mock import AsyncMock, patch

from repositories.predictions import PredictionRepository


async def test_prediction_repository_delegates_save():
    repository = PredictionRepository()
    with patch(
        "repositories.predictions.save_prediction", new_callable=AsyncMock
    ) as save:
        await repository.save(1, date(2026, 8, 27), "readiness_rf", 80.0, {"x": 1})

    save.assert_awaited_once_with(1, date(2026, 8, 27), "readiness_rf", 80.0, {"x": 1})


async def test_prediction_repository_delegates_reads():
    repository = PredictionRepository()
    with (
        patch(
            "repositories.predictions.get_yesterday_prediction",
            new_callable=AsyncMock,
            return_value=42.0,
        ) as yesterday,
        patch(
            "repositories.predictions.get_prediction_for_date",
            new_callable=AsyncMock,
            return_value=43.0,
        ) as for_date,
    ):
        assert await repository.get_yesterday(1, "body_battery_custom") == 42.0
        assert (
            await repository.get_for_date(1, date(2026, 8, 27), "body_battery_custom")
            == 43.0
        )

    yesterday.assert_awaited_once_with(1, "body_battery_custom")
    for_date.assert_awaited_once_with(1, date(2026, 8, 27), "body_battery_custom")
