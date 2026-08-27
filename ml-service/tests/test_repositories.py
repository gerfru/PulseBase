from datetime import date
from unittest.mock import AsyncMock, patch

from repositories.predictions import PredictionRepository
from repositories.users import UserMLRepository


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


async def test_user_repository_delegates_user_queries():
    repository = UserMLRepository()
    with (
        patch(
            "repositories.users.get_active_users",
            new_callable=AsyncMock,
            return_value=[{"id": 1}],
        ) as active,
        patch(
            "repositories.users.get_ml_requested_users",
            new_callable=AsyncMock,
            return_value=[{"id": 2}],
        ) as requested,
        patch(
            "repositories.users.get_user_profile",
            new_callable=AsyncMock,
            return_value={"has_profile": True},
        ) as profile,
        patch("repositories.users.mark_ml_done", new_callable=AsyncMock) as done,
    ):
        assert await repository.get_active() == [{"id": 1}]
        assert await repository.get_ml_requested() == [{"id": 2}]
        assert await repository.get_profile(2) == {"has_profile": True}
        await repository.mark_ml_done(2)

    active.assert_awaited_once_with()
    requested.assert_awaited_once_with()
    profile.assert_awaited_once_with(2)
    done.assert_awaited_once_with(2)
