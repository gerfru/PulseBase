from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "garmin"
    db_app_user: str
    db_app_password: str

    model_dir: Path = Path("/app/models")
    ml_infer_hour: int = 7
    ml_train_weekday: int = 6  # Sunday (0=Monday)

    @property
    def db_url(self) -> str:
        return f"postgresql://{self.db_app_user}:{self.db_app_password}@{self.db_host}:{self.db_port}/{self.db_name}"
