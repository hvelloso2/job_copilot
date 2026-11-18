from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = ""
    # Per-operation model, e.g. "extract_job=claude-haiku-5-5,extract_claims=claude-sonnet-5-5".
    # Operations not listed use ANTHROPIC_MODEL.
    anthropic_models: str = ""
    anthropic_fallbacks: str = ""
    database_url: str = "sqlite:///../data/job_copilot.db"

    def operation_models(self) -> dict[str, str]:
        """Parses ANTHROPIC_MODELS. Raises ValueError on a malformed entry."""
        result: dict[str, str] = {}
        for entry in self.anthropic_models.split(","):
            if not entry.strip():
                continue
            operation, sep, model = (part.strip() for part in entry.partition("="))
            if not sep or not operation or not model:
                raise ValueError(f"ANTHROPIC_MODELS inválido: {entry.strip()!r} (use operacao=modelo)")
            result[operation] = model
        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()
