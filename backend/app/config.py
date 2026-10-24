from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    ml_dataset_dir: Path = Path(__file__).resolve().parents[2] / 'data/external/cuad'
    ml_artifacts_dir: Path = Path(__file__).resolve().parents[2] / 'artifacts/ml'
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://corplex:corplex_local@localhost:5432/corplex"
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
