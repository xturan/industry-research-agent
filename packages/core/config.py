from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="invest-agent-api", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    worker_poll_interval_seconds: int = Field(default=5, alias="WORKER_POLL_INTERVAL_SECONDS")
    task_default_max_attempts: int = Field(default=3, alias="TASK_DEFAULT_MAX_ATTEMPTS")
    task_retry_backoff_seconds: int = Field(default=5, alias="TASK_RETRY_BACKOFF_SECONDS")
    task_worker_id: str = Field(default="worker-default", alias="TASK_WORKER_ID")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="invest_agent", alias="POSTGRES_DB")
    postgres_user: str = Field(default="invest", alias="POSTGRES_USER")
    postgres_password: str = Field(default="invest", alias="POSTGRES_PASSWORD")

    database_url: str = Field(
        default="postgresql+psycopg://invest:invest@localhost:5432/invest_agent",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    raw_storage_dir: str = Field(default="data/raw", alias="RAW_STORAGE_DIR")
    delivery_export_dir: str = Field(default="data/exports", alias="DELIVERY_EXPORT_DIR")
    delivery_enforce_policy_checks: bool = Field(
        default=False, alias="DELIVERY_ENFORCE_POLICY_CHECKS"
    )
    ingestion_max_chunk_chars: int = Field(default=1200, alias="INGESTION_MAX_CHUNK_CHARS")
    ingestion_request_timeout_seconds: int = Field(
        default=20, alias="INGESTION_REQUEST_TIMEOUT_SECONDS"
    )
    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        alias="DEEPSEEK_BASE_URL",
    )
    deepseek_research_model: str = Field(
        default="deepseek-chat",
        alias="DEEPSEEK_RESEARCH_MODEL",
    )
    deepseek_timeout_seconds: int = Field(default=180, alias="DEEPSEEK_TIMEOUT_SECONDS")
    deepseek_max_retries: int = Field(default=1, alias="DEEPSEEK_MAX_RETRIES")
    deepseek_max_tokens: int = Field(default=1200, alias="DEEPSEEK_MAX_TOKENS")
    deepseek_model_supervisor_intake: str | None = Field(
        default=None,
        alias="DEEPSEEK_MODEL_SUPERVISOR_INTAKE",
    )
    deepseek_model_thesis_builder: str | None = Field(
        default=None,
        alias="DEEPSEEK_MODEL_THESIS_BUILDER",
    )
    deepseek_model_opponent: str | None = Field(
        default=None,
        alias="DEEPSEEK_MODEL_OPPONENT",
    )
    deepseek_model_evidence_judge: str | None = Field(
        default=None,
        alias="DEEPSEEK_MODEL_EVIDENCE_JUDGE",
    )
    deepseek_model_risk_analyst: str | None = Field(
        default=None,
        alias="DEEPSEEK_MODEL_RISK_ANALYST",
    )
    deepseek_model_synthesize_memo: str | None = Field(
        default=None,
        alias="DEEPSEEK_MODEL_SYNTHESIZE_MEMO",
    )
    deepseek_enable_thinking: bool = Field(default=False, alias="DEEPSEEK_ENABLE_THINKING")
    deepseek_store_reasoning_content: bool = Field(
        default=False,
        alias="DEEPSEEK_STORE_REASONING_CONTENT",
    )
    source_http_timeout_seconds: int = Field(default=20, alias="SOURCE_HTTP_TIMEOUT_SECONDS")
    source_http_retry_count: int = Field(default=2, alias="SOURCE_HTTP_RETRY_COUNT")
    source_http_backoff_seconds: float = Field(default=0.3, alias="SOURCE_HTTP_BACKOFF_SECONDS")
    eia_api_key: str | None = Field(default=None, alias="EIA_API_KEY")
    sec_user_agent: str = Field(
        default="invest-agent/0.1 (research@local)",
        alias="SEC_USER_AGENT",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
