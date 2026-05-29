from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "garmin"
    db_user: str
    db_password: str
    db_app_user: str
    db_app_password: str

    sync_hour: int = 6
    sync_lookback_days: int = 30
    sync_daily_days: int = 2  # days synced on daily run and manual button
    fernet_key: str
    sentry_dsn: str = ""
    token_base_dir: Path = Path("/app/tokens")

    @field_validator("fernet_key")
    @classmethod
    def fernet_key_must_not_be_empty(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "FERNET_KEY muss gesetzt sein. Generieren: "
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        return v

    @property
    def db_url(self) -> str:
        return f"postgresql://{self.db_app_user}:{self.db_app_password}@{self.db_host}:{self.db_port}/{self.db_name}"
