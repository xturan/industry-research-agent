from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="invest-agent-api", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    system_run_log_enabled: bool = Field(default=True, alias="SYSTEM_RUN_LOG_ENABLED")
    system_run_log_dir: str = Field(default="data/run_logs", alias="SYSTEM_RUN_LOG_DIR")
    system_run_log_max_value_chars: int = Field(
        default=240, alias="SYSTEM_RUN_LOG_MAX_VALUE_CHARS"
    )
    system_run_log_max_items: int = Field(default=8, alias="SYSTEM_RUN_LOG_MAX_ITEMS")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    worker_poll_interval_seconds: int = Field(default=5, alias="WORKER_POLL_INTERVAL_SECONDS")
    task_default_max_attempts: int = Field(default=3, alias="TASK_DEFAULT_MAX_ATTEMPTS")
    task_retry_backoff_seconds: int = Field(default=5, alias="TASK_RETRY_BACKOFF_SECONDS")
    task_worker_id: str = Field(default="worker-default", alias="TASK_WORKER_ID")

    # ── Pipeline feature flags (research-contract-refactor v1) ──
    # Shadow-safe: each toggles via .env without code change; default "legacy"
    # keeps current behavior until a phase flips its mode to primary.
    pipeline_planner_mode: str = Field(default="legacy", alias="PIPELINE_PLANNER_MODE")
    pipeline_evidence_mode: str = Field(default="legacy", alias="PIPELINE_EVIDENCE_MODE")
    pipeline_claim_mode: str = Field(default="legacy", alias="PIPELINE_CLAIM_MODE")
    pipeline_editor_mode: str = Field(default="legacy", alias="PIPELINE_EDITOR_MODE")
    pipeline_gate_mode: str = Field(default="legacy", alias="PIPELINE_GATE_MODE")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="invest_agent", alias="POSTGRES_DB")
    postgres_user: str = Field(default="invest", alias="POSTGRES_USER")
    postgres_password: str = Field(default="invest", alias="POSTGRES_PASSWORD")

    database_url: str = Field(
        default="postgresql+psycopg://invest:invest@localhost:5432/invest_agent",
        alias="DATABASE_URL",
    )
    # DB 连接池（G4 运维修复）：显式配置 + 环境可调。多进程（api+worker）各持一个
    # 池，pool_size+max_overflow 须满足 N_procs * (size+overflow) << PG max_connections。
    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    db_pool_max_overflow: int = Field(default=5, alias="DB_POOL_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=60, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=1800, alias="DB_POOL_RECYCLE")
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
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    tavily_api_keys: str | None = Field(default=None, alias="TAVILY_API_KEYS")
    tavily_search_depth: str = Field(default="basic", alias="TAVILY_SEARCH_DEPTH")
    tavily_topic: str = Field(default="general", alias="TAVILY_TOPIC")
    tavily_country: str = Field(default="china", alias="TAVILY_COUNTRY")
    tavily_max_results: int = Field(default=5, alias="TAVILY_MAX_RESULTS")
    tavily_auto_parameters: bool = Field(default=False, alias="TAVILY_AUTO_PARAMETERS")
    tavily_include_answer: bool = Field(default=False, alias="TAVILY_INCLUDE_ANSWER")
    tavily_include_raw_content: bool = Field(default=False, alias="TAVILY_INCLUDE_RAW_CONTENT")
    tavily_timeout_seconds: int = Field(default=60, alias="TAVILY_TIMEOUT_SECONDS")
    search_discovery_provider: str = Field(default="anysearch", alias="SEARCH_DISCOVERY_PROVIDER")
    search_discovery_fallback_provider: str | None = Field(
        default="tavily", alias="SEARCH_DISCOVERY_FALLBACK_PROVIDER"
    )
    search_discovery_fallback_enabled: bool = Field(
        default=True, alias="SEARCH_DISCOVERY_FALLBACK_ENABLED"
    )
    anysearch_api_key: str | None = Field(default=None, alias="ANYSEARCH_API_KEY")
    anysearch_endpoint: str = Field(
        default="https://api.anysearch.com/mcp", alias="ANYSEARCH_ENDPOINT"
    )
    anysearch_timeout_seconds: int = Field(default=60, alias="ANYSEARCH_TIMEOUT_SECONDS")
    anysearch_max_results: int = Field(default=5, alias="ANYSEARCH_MAX_RESULTS")
    # ── Retrieval LLM reranker (LLM-as-reranker via vLLM chat-completions endpoint) ──
    # Recommended adapter (handoff v6): Qwen/Qwen2.5-3B-Instruct base + LoRA
    #   data/rerank_cloud_train/output/rerank_3b_lora_v6_opd_clean/checkpoint-120
    # RERANK_MODEL must equal the `--lora-modules <name>=<checkpoint-120 path>` name
    # used at vLLM serve time (default "rerank-lora" matches scripts/_start_rerank.sh).
    rerank_endpoint: str = Field(
        default="http://localhost:8000/v1/chat/completions", alias="RERANK_ENDPOINT"
    )
    rerank_model: str = Field(default="rerank-lora", alias="RERANK_MODEL")
    # ── 2026-08-11：editor1 报告生成模式（空=单次调用；per_dimension=按维度分章节）──
    editor1_generation_mode: str = Field(default="", alias="EDITOR1_GENERATION_MODE")
    # ── G1.3.1 Research Gateway admission (global QUEUED-run capacity) ──
    admission_max_queued_runs: int = Field(
        default=200, ge=1, alias="ADMISSION_MAX_QUEUED_RUNS"
    )
    # ── Real embedding (vLLM OpenAI-compatible /embeddings) ──
    embedding_endpoint: str = Field(
        default="http://localhost:8001/v1/embeddings", alias="EMBEDDING_ENDPOINT"
    )
    embedding_model: str = Field(default="BAAI/bge-m3", alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1024, alias="EMBEDDING_DIMENSIONS")
    # B.3.3b: advisory gap backfill (shadow) flag + mode. Default OFF.
    advisory_gap_backfill_enabled: bool = Field(
        default=False, alias="ADVISORY_GAP_BACKFILL_ENABLED"
    )
    advisory_gap_backfill_mode: str = Field(
        default="shadow", alias="ADVISORY_GAP_BACKFILL_MODE"
    )
    # C.2: structured draft shadow (claim-constrained StructuredDraft) flag +
    # mode. Default OFF. Only "shadow" is accepted; "primary" is C.3.
    structured_draft_shadow_enabled: bool = Field(
        default=False, alias="STRUCTURED_DRAFT_SHADOW_ENABLED"
    )
    structured_draft_shadow_mode: str = Field(
        default="shadow", alias="STRUCTURED_DRAFT_SHADOW_MODE"
    )
    # C.3.1: Editor1 run mode. Allowed: legacy / structured_compare /
    # structured_primary_canary / structured_primary. Only "legacy" (formal) and
    # "structured_compare" (side-by-side shadow) are implemented now.
    editor1_mode: str = Field(default="legacy", alias="EDITOR1_MODE")
    structured_editor1_compare_enabled: bool = Field(
        default=False, alias="STRUCTURED_EDITOR1_COMPARE_ENABLED"
    )
    structured_editor1_max_retries: int = Field(
        default=1, alias="STRUCTURED_EDITOR1_MAX_RETRIES"
    )
    # B.3.3b: explicit provider fallback policy.
    #   fallback_allowed (default) -> anysearch error falls back to tavily.
    #   required                  -> if the configured provider needs a credential
    #                                and none is set, fail fast (no silent degrade).
    search_provider_policy: str = Field(
        default="fallback_allowed", alias="SEARCH_PROVIDER_POLICY"
    )
    eia_api_key: str | None = Field(default=None, alias="EIA_API_KEY")
    sec_user_agent: str = Field(
        default="invest-agent/0.1 (research@local)",
        alias="SEC_USER_AGENT",
    )


    # ── G2 Capability Gateway ──
    # 总开关默认 False：Gateway 完全不介入，行为完全 Legacy。
    # 每个 capability 有独立 mode（off/shadow/gateway），不用一个总开关切全部 Provider。
    capability_gateway_enabled: bool = Field(
        default=False, alias="CAPABILITY_GATEWAY_ENABLED"
    )
    # SEARCH: off(默认关闭时的行为=Legacy) / shadow(Gateway 只算不改) / gateway(G2.2b 接管)
    capability_gateway_search_mode: str = Field(
        default="shadow", alias="CAPABILITY_GATEWAY_SEARCH_MODE"
    )
    # LLM: off(默认) / shadow / gateway（G2.2b 之后再接）
    capability_gateway_llm_mode: str = Field(
        default="off", alias="CAPABILITY_GATEWAY_LLM_MODE"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
