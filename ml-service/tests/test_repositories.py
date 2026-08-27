from unittest.mock import AsyncMock, patch

from repositories.users import UserMLRepository


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
