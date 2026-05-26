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

    # Embedding 服务（独立于 LLM 配置；通常对接 DashScope/SiliconFlow/智谱/OpenAI）。
    # 用 OpenAI 兼容协议 /v1/embeddings 端点；DashScope 的 compatible-mode 也走这个。
    # 留空时 concept_matcher 自动跳过路 4 embedding 召回，降级为路 1+2。
    embedding_api_base: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-v3"  # DashScope 默认；切提供方时改这里
    embedding_dim: int = 1024
    embedding_timeout_seconds: int = 30
    embedding_batch_size: int = 25  # DashScope 单请求上限 25，OpenAI 上限 2048

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="REG_ASSISTANT_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
