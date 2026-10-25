from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore", hide_input_in_errors=True)
    ml_benchmark_path: Path = Path(__file__).resolve().parents[2] / 'docs/ml/experiment-results.json'
    ml_dataset_dir: Path = Path(__file__).resolve().parents[2] / 'data/external/cuad'
    ml_artifacts_dir: Path = Path(__file__).resolve().parents[2] / 'artifacts/ml'
    corplex_llm_api_key: str = Field(default='', repr=False)
    corplex_llm_model: str = 'gpt-4.1-mini'
    corplex_access_token: str = Field(default='', repr=False)
    corplex_review_token: str = Field(default='', repr=False)
    allowed_hosts: list[str] = ['localhost', '127.0.0.1', 'testserver', 'backend']
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://corplex:corplex_local@localhost:5432/corplex"
    cors_origins: list[str] = ["http://localhost:5173"]


    @model_validator(mode='after')
    def production_safety(self):
        if self.app_env == 'production':
            if len(self.corplex_access_token) < 32 or len(self.corplex_review_token) < 32 or self.corplex_access_token == self.corplex_review_token:
                raise ValueError('Production requires distinct access/reviewer tokens of at least 32 characters.')
            if 'corplex_local' in self.database_url or '*' in self.cors_origins or '*' in self.allowed_hosts:
                raise ValueError('Production requires a non-default database credential and explicit CORS origins.')
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
