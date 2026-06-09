import asyncpg
import structlog
from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = structlog.get_logger(__name__)


class Settings(BaseSettings):
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "garmin"
    db_app_user: str
    db_app_password: str
    session_secret: str
    https_only: bool = True
    trimp_lookback_days: int = 7
    trimp_forecast_days: int = 7
    resend_api_key: str = ""
    resend_from_email: str = "onboarding@resend.dev"
    app_base_url: str = ""
    fernet_key: str
    trusted_proxy_cidrs: list[str] = ["127.0.0.1/32"]
    sentry_dsn: str = ""  # SENTRY_DSN — empty = disabled
    db_pool_min: int = 1  # DB_POOL_MIN — asyncpg pool min_size
    db_pool_max: int = 5  # DB_POOL_MAX — asyncpg pool max_size

    @field_validator("fernet_key")
    @classmethod
    def fernet_key_must_not_be_empty(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "FERNET_KEY muss gesetzt sein. Generieren: "
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        return v

    @field_validator("session_secret")
    @classmethod
    def session_secret_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SESSION_SECRET must be at least 32 characters")
        return v

    @property
    def db_url(self) -> str:
        return f"postgresql://{self.db_app_user}:{self.db_app_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()  # type: ignore[call-arg]

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(
                settings.db_url,
                min_size=settings.db_pool_min,
                max_size=settings.db_pool_max,
            )
        except Exception as e:
            # db_url embeds the DB password — log only the exception type so the
            # DSN never reaches logs or a propagated trace, then re-raise.
            logger.error("db.pool.create_failed", reason=type(e).__name__)
            raise
    return _pool
