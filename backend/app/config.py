from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = ""
    anthropic_fallbacks: str = ""
    database_url: str = "sqlite:///../data/job_copilot.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
