"""G2.8 Gateway Production Runtime Wiring — 把 G2.3 budget / G2.4 circuit /
G2.5 recorder 一次性装配成进程级单例，供 workflow 的 search/LLM 注入点使用。

背景（2026-08-12 审计结论）：
- 网关的 G2.1-G2.5 能力全部就绪，但所有生产调用点（real_nodes.py:184、
  advisory_backfill_live.py:80、lane_execution.py:737/1068/1399、
  search_assisted_domestic.py:339、deep_research.py:411/757、llm_agents.py:187）
  都以零参数构造 build_gateway_aware_search_provider /
  build_gateway_aware_llm_client，导致 budget/recorder/circuit 恒为 None，
  G2.3/G2.5 在真实 workflow 里从不生效。
- 本模块提供唯一装配入口：`build_gateway_runtime()`。按 database_url 方言选择
  store：Postgres → 跨进程共享（PostgresLease / PostgresCircuit / PostgresRecorder）；
  SQLite/dev → 进程内（InProcess / InMemory / InMemory），保证 dev/test 不崩。

安全边界：
- Postgres 三 store 的构造签名都是 `session_factory: Callable[[], Session]`，
  内部各自 `with session_factory() as session:` 开短事务（telemetry.py:186、
  circuit.py:194、budget.py:296/374/383）。绝不能把 runner.session（长期持有）
  传进来——budget.acquire 用 asyncio.to_thread 跨线程新建连接，与 runner 的
  session 生命周期冲突。
- DDL：生产以 alembic 三迁移（a1b2c3d4e5f6/a2b3c4d5e6f7/a3b4c5d6e7f8）为唯一
  正式来源；本模块只做幂等兜底 create_*_tables，绝不替代 alembic。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from packages.core.config import Settings, get_settings
from packages.db.session import get_session_factory

LOGGER = logging.getLogger(__name__)


def _is_postgres(database_url: str) -> bool:
    """方言判断：仅 postgresql(+driver) 使用共享 DB store。"""
    return str(database_url or "").strip().lower().startswith("postgres")


def _redis_enabled(settings: Settings) -> bool:
    """Redis-backed budget/circuit 是否启用：显式开关 + REDIS_URL 已配置。"""
    return bool(settings.capability_gateway_redis_enabled) and bool(settings.redis_url)


def _redis_client(settings: Settings) -> Any:
    """同步 redis.Redis client（短超时保证故障时快速降级）。

    用同步版：SearchCapabilityService/LLMCapabilityService 是 sync 方法内部
    asyncio.run，redis.asyncio client 连接池绑定创建时 loop，跨 asyncio.run 复用
    会抛错。同步 client + asyncio.to_thread 与 PostgresLease 现状同构。
    """
    import redis

    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=0.5,
        socket_connect_timeout=0.5,
        retry_on_timeout=False,
    )


def _budget_policies() -> dict[str, Any]:
    """从 default_registry() 的 instance.limits.max_concurrency 派生 budget policies。

    未配置（<=0）的 instance 用默认 1（保守）；生产 registry 已给 anysearch=20 /
    tavily=10 / deepseek=10 / openrouter=5 / ollama=1。
    """
    from packages.capability_gateway.budget import policy_from_instance
    from packages.capability_gateway.registry import default_registry

    registry = default_registry()
    return {
        instance.instance_id: policy_from_instance(instance)
        for instance in registry.all()
    }


def build_gateway_runtime(
    settings: Settings | None = None,
    *,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """装配网关运行期保护组件（budget / circuit / recorder）。

    Args:
        settings: 应用配置；None → get_settings()。
        session_factory: 返回新 Session 的 callable（SessionLocal /
            get_session_factory()）；仅 Postgres 方言需要。None → 从
            get_session_factory() 取进程级 sessionmaker。

    Returns:
        {"budget": ConcurrencyBudget, "circuit": CircuitBreaker|None,
         "recorder": ProviderAttemptRecorder}
    """
    app = settings or get_settings()
    sf = session_factory or get_session_factory()

    from packages.capability_gateway.budget import (
        InProcessConcurrencyBudget,
        PostgresLeaseConcurrencyBudget,
    )
    from packages.capability_gateway.circuit import (
        CircuitBreaker,
        InMemoryCircuitStateStore,
        PostgresCircuitStateStore,
    )
    from packages.capability_gateway.telemetry import (
        InMemoryProviderAttemptRecorder,
        PostgresProviderAttemptRecorder,
    )

    policies = _budget_policies()

    # ── 三分支：Redis → Postgres → InProcess/InMemory ──────────────────────
    # G2.8 迁移（2026-08-13）：显式开关 CAPABILITY_GATEWAY_REDIS_ENABLED 控制
    # budget/circuit 后端。recorder 独立选型（遥测审计日志始终留 PG/SQLite）。
    budget = None
    circuit = None
    if _redis_enabled(app):
        client = _redis_client(app)
        try:
            if not client.ping():
                raise ConnectionError("redis ping failed")
        except (Exception, OSError) as exc:  # noqa: BLE001 - 启动 sanity check
            LOGGER.warning(
                "GATEWAY_REDIS_BOOTSTRAP_FAILED fallback_to_pg err=%s", exc
            )
            client = None
        if client is not None:
            from packages.capability_gateway.redis_stores import (
                RedisCircuitStateStore,
                RedisLeaseConcurrencyBudget,
            )

            budget = RedisLeaseConcurrencyBudget(client, policies)
            circuit = CircuitBreaker(
                RedisCircuitStateStore(client, record_ttl_seconds=120.0)
            )

    if budget is None and _is_postgres(app.database_url):
        budget = PostgresLeaseConcurrencyBudget(sf, policies)
        circuit = CircuitBreaker(PostgresCircuitStateStore(sf))
    if budget is None:
        # SQLite / dev / test / Redis 降级后：进程内语义验证。
        budget = InProcessConcurrencyBudget(policies)
        circuit = CircuitBreaker(InMemoryCircuitStateStore())

    recorder = (
        PostgresProviderAttemptRecorder(sf)
        if _is_postgres(app.database_url)
        else InMemoryProviderAttemptRecorder()
    )

    return {
        "budget": budget,
        "circuit": circuit,
        "recorder": recorder,
    }


@lru_cache(maxsize=4)
def get_gateway_runtime_cached(
    database_url: str | None = None,
    redis_url: str | None = None,
    capability_gateway_redis_enabled: bool | None = None,
) -> dict[str, Any]:
    """进程级单例网关运行时（按 database_url + redis 配置缓存）。

    生产（api + worker 两个进程）各持一个单例；budget 靠 Postgres lease / Redis
    zset 跨进程保证真实全局上限，recorder 靠 Postgres 表共享 attempt 记录。

    缓存 key 含 redis_url + enabled 开关——否则进程内切换 Redis 配置会拿到旧单例。
    """
    app = get_settings()
    return build_gateway_runtime(app, session_factory=get_session_factory())


def ensure_gateway_tables(engine_or_session: Any, *, settings: Settings | None = None) -> None:
    """幂等兜底建表（gateway 三表）。生产正式来源是 alembic；此处只保证
    跳过/落后 alembic 的新环境能启动。IF NOT EXISTS，可安全重复调用。

    仅 Postgres 方言调用：三张表的原始 DDL（telemetry.py:128-157、
    circuit.py:166-175、budget.py:212-231）含多语句 + TIMESTAMPTZ/now()，
    SQLite 不支持；且 SQLite 方言走 InMemory store，本就不需要建表。
    """
    app = settings or get_settings()
    if not _is_postgres(app.database_url):
        return  # SQLite/dev：InMemory store 不依赖 DB 表

    from packages.capability_gateway.budget import create_concurrency_tables
    from packages.capability_gateway.circuit import create_circuit_tables
    from packages.capability_gateway.telemetry import create_attempt_tables

    create_concurrency_tables(engine_or_session)
    create_circuit_tables(engine_or_session)
    create_attempt_tables(engine_or_session)


__all__ = [
    "build_gateway_runtime",
    "ensure_gateway_tables",
    "get_gateway_runtime_cached",
]
