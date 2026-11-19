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

    # Job alert emails (IMAP). With Gmail: IMAP on and an app password (not the account password).
    imap_host: str = "imap.gmail.com"
    imap_user: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    # Only emails from these domains are read (job alerts of each site)
    alert_senders: str = "linkedin.com,indeed.com,gupy.io,catho.com.br,infojobs.com.br,vagas.com.br,glassdoor.com"
    alert_days: int = 14         # how far back to look
    alert_max_emails: int = 20   # new emails read per check (each one is a Claude call)

    def alert_sender_list(self) -> list[str]:
        return [s.strip().lower() for s in self.alert_senders.split(",") if s.strip()]

    @property
    def imap_configured(self) -> bool:
        return bool(self.imap_host and self.imap_user and self.imap_password)

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
