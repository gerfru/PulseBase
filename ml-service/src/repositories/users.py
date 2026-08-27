from typing import Any

from db.users_ml import (
    get_active_users,
    get_ml_requested_users,
    get_user_profile,
    mark_ml_done,
)


class UserMLRepository:
    async def get_active(self) -> list[dict[str, Any]]:
        return await get_active_users()

    async def get_ml_requested(self) -> list[dict[str, Any]]:
        return await get_ml_requested_users()

    async def get_profile(self, user_id: int) -> dict[str, Any]:
        return await get_user_profile(user_id)

    async def mark_ml_done(self, user_id: int) -> None:
        await mark_ml_done(user_id)
