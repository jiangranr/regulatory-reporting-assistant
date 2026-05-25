from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "监管规则变更智能落地助手"
    database_url: str = "sqlite:///./data/app.db"
    upload_dir: Path = Path("./data/uploads")
    mock_ai: bool = True
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-5.4"
    llm_fallback_model: str = "gpt-5.3-codex"
    llm_timeout_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="REG_ASSISTANT_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
