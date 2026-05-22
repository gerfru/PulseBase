import asyncpg
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "garmin"
    db_user: str
    db_password: str
    db_app_user: str
    db_app_password: str
    session_secret: str
    https_only: bool = True
    trimp_lookback_days: int = 7
    trimp_forecast_days: int = 7
    resend_api_key: str = ""
    resend_from_email: str = "onboarding@resend.dev"
    app_base_url: str = "https://garmin.home.lab"
    fernet_key: str = ""  # FERNET_KEY — empty = no encryption (startup warning)

    @property
    def db_url(self) -> str:
        return f"postgresql://{self.db_app_user}:{self.db_app_password}@{self.db_host}:{self.db_port}/{self.db_name}"


_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = Settings()  # type: ignore[call-arg]
        _pool = await asyncpg.create_pool(settings.db_url, min_size=1, max_size=5)
    return _pool
