from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "MOCA API"
    project_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = Field(default="dev-secret-change-in-prod-32-bytes-min")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    enable_demo_auth: bool = True
    database_echo: bool = False
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "text-embedding-v4"
    embedding_dimensions: int = 1024
    embedding_batch_size: int = 10

    # LLM (GLM-5.1 via DashScope, per D-01)
    dashscope_api_key: str = Field(default="")
    llm_model: str = "glm-5.1"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 90
    session_memory_enabled: bool = True
    session_memory_ttl_seconds: int = 1800
    session_memory_summary_max_chars: int = 500
    session_memory_write_timeout_seconds: float = 0.5
    # Phase 15 owns enabling the active SLA scanner after replay/allocator gates pass.
    approval_sla_scanner_enabled: bool = Field(
        default=False,
        description="Backed by APPROVAL_SLA_SCANNER_ENABLED; false by default for Phase 13.",
    )

    @property
    def checkpointer_database_url(self) -> str:
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
