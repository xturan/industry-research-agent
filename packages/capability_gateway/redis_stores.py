"""G2.3/G2.4 Redis-backed stores — 并发预算 + 熔断状态迁移到 Redis。

背景（2026-08-13）：系统已部署 Redis 但代码 0 处使用。capability_gateway 的
并发预算（provider_concurrency_leases）和熔断状态（provider_circuit_state）是
典型的短生命周期状态（lease 带 TTL、熔断丢失后回 CLOSED 安全默认），本质是
Redis 的菜（短 TTL + 原子 + 跨进程）。用户选定：优先把 budget + circuit 迁移
到 Redis，recorder（attempt 遥测，审计日志）保留 PG。

设计要点：
- **必须用同步 redis.Redis**：SearchCapabilityService/LLMCapabilityService 是 sync
  方法内部 asyncio.run（每次新建事件循环），redis.asyncio client 连接池绑定
  创建时 loop，跨 asyncio.run 复用会抛错。同步 client + asyncio.to_thread 与
  PostgresLeaseConcurrencyBudget 现状逐字节同构。
- **budget 用 Redis TIME 单一时钟**（Lua 脚本内调用，与 ZADD/ZCOUNT 同一原子
  单元），避免 Python↔Redis 时钟漂移。
- **circuit 沿用 CircuitBreaker 的 now_provider**（Python 墙钟，与现状 PG 一致），
  store 只做持久化，时间存 epoch ms。
- **降级策略**：budget acquire 遇 Redis 错误 → fail-closed 转抛
  ProviderCapacityExhaustedError（守"永不超限"契约）；release / circuit get/save
  → fail-open（吞错 + 日志，lease 留 TTL 自愈 / CLOSED 安全默认）。

Key 命名：`gw:budget:{pid}`（Sorted Set）+ `gw:circuit:{pid}`（Hash），加 `gw:`
前缀避免未来与任务队列/缓存共用 Redis 时碰撞。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from packages.capability_gateway.budget import (
    BudgetWaitCancelled,
    ProviderCapacityExhaustedError,
    ProviderConcurrencyPolicy,
    ProviderPermit,
)
from packages.capability_gateway.circuit import CircuitState, CircuitStateRecord

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11
    UTC = timezone.utc

LOGGER = logging.getLogger(__name__)

BUDGET_KEY = "gw:budget:{pid}"
CIRCUIT_KEY = "gw:circuit:{pid}"


def budget_key(provider_instance_id: str) -> str:
    return BUDGET_KEY.format(pid=provider_instance_id)


def circuit_key(provider_instance_id: str) -> str:
    return CIRCUIT_KEY.format(pid=provider_instance_id)


# ── 时间工具（epoch ms 存储，datetime ↔ ms 往返精确） ────────────────────────

def _now_ms_from_redis(client: Any) -> int:
    """Redis TIME 单一时钟源 → epoch ms。"""
    sec, usec = client.time()
    return int(sec) * 1000 + int(usec) // 1000


def _dt_from_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC)


def _ms_from_dt(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    return int(dt.timestamp() * 1000)


def _monotonic() -> float:
    return time.monotonic()


# ── 并发预算：RedisLeaseConcurrencyBudget ────────────────────────────────────

_LUA_ACQUIRE = """
-- KEYS[1] = gw:budget:{pid}
-- ARGV[1] = max_concurrency, ARGV[2] = lease_ttl_ms, ARGV[3] = lease_id
-- 返回 {1, now_ms, expires_ms} 授予；{0, now_ms} 满额
local t = redis.call('TIME')
local now_ms = t[1] * 1000 + math.floor(t[2] / 1000)
-- 清理严格过期（stale lease recovery，内存有界）
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', '(' .. now_ms)
-- 计数 >= now（对齐 PG expires_at >= now()）
local active = redis.call('ZCOUNT', KEYS[1], now_ms, '+inf')
if tonumber(active) >= tonumber(ARGV[1]) then
    return {0, now_ms}
end
local expires_ms = now_ms + tonumber(ARGV[2])
redis.call('ZADD', KEYS[1], expires_ms, ARGV[3])
return {1, now_ms, expires_ms}
"""


class RedisLeaseConcurrencyBudget:
    """Redis Sorted Set 版并发预算。与 PostgresLeaseConcurrencyBudget 语义等价：

    - member = lease_id，score = expires_at（epoch ms）。
    - acquire = 单个 Lua 脚本原子完成「TIME 取时钟 → 清理过期 → 计数 → ZADD」，
      等价 PG 短事务 + FOR UPDATE 串行化。
    - release = ZREM（fail-open：Redis 错误吞掉，lease 留 TTL 自愈）。
    - acquire 遇 Redis 错误 → fail-closed 转抛 ProviderCapacityExhaustedError。
    """

    def __init__(
        self,
        client: Any,
        policies: dict[str, ProviderConcurrencyPolicy],
        *,
        poll_interval_seconds: float = 0.05,
    ) -> None:
        self._client = client
        self._policies = policies
        self._poll_interval_seconds = poll_interval_seconds
        self._acquire_script = client.register_script(_LUA_ACQUIRE)

    def _policy(self, provider_instance_id: str) -> ProviderConcurrencyPolicy:
        return self._policies.get(
            provider_instance_id,
            ProviderConcurrencyPolicy(
                provider_instance_id=provider_instance_id, max_concurrency=1
            ),
        )

    async def acquire(
        self,
        *,
        provider_instance_id: str,
        route_execution_id: str,
        provider_call_id: str,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ProviderPermit:
        policy = self._policy(provider_instance_id)
        deadline = _monotonic() + policy.acquire_timeout_seconds
        while True:
            permit = await asyncio.to_thread(
                self._try_acquire_sync, policy, route_execution_id, provider_call_id
            )
            if permit is not None:
                return permit
            if should_cancel is not None and should_cancel():
                raise BudgetWaitCancelled()
            if _monotonic() >= deadline:
                raise ProviderCapacityExhaustedError(provider_instance_id)
            await asyncio.sleep(self._poll_interval_seconds)

    def _try_acquire_sync(
        self,
        policy: ProviderConcurrencyPolicy,
        route_execution_id: str,
        provider_call_id: str,
    ) -> ProviderPermit | None:
        lease_id = uuid.uuid4().hex
        try:
            res = self._acquire_script(
                keys=[budget_key(policy.provider_instance_id)],
                args=[
                    policy.max_concurrency,
                    int(policy.lease_ttl_seconds * 1000),
                    lease_id,
                ],
            )
        except (Exception, OSError) as exc:  # noqa: BLE001 - redis.RedisError 及其子类
            LOGGER.warning(
                "GATEWAY_REDIS_UNAVAILABLE acquire pid=%s err=%s",
                policy.provider_instance_id,
                exc,
            )
            # fail-closed：无法验证容量 → 不放行（守"永不超限"契约）。
            raise ProviderCapacityExhaustedError(policy.provider_instance_id) from exc

        if res[0] != 1:
            return None  # 满额，等待重试
        now_ms, expires_ms = int(res[1]), int(res[2])
        now = _dt_from_ms(now_ms)
        return ProviderPermit(
            lease_id=lease_id,
            provider_instance_id=policy.provider_instance_id,
            route_execution_id=route_execution_id,
            provider_call_id=provider_call_id,
            acquired_at=now,
            expires_at=_dt_from_ms(expires_ms),
        )

    async def release(self, permit: ProviderPermit) -> None:
        try:
            await asyncio.to_thread(
                self._client.zrem, budget_key(permit.provider_instance_id), permit.lease_id
            )
        except (Exception, OSError) as exc:  # noqa: BLE001 - fail-open
            LOGGER.warning(
                "GATEWAY_REDIS_RELEASE_FAILED lease=%s err=%s", permit.lease_id, exc
            )
        permit.released_at = datetime.now(UTC)

    def active_leases(self, provider_instance_id: str) -> int:
        try:
            now_ms = _now_ms_from_redis(self._client)
            return int(
                self._client.zcount(budget_key(provider_instance_id), now_ms, "+inf")
            )
        except (Exception, OSError):  # noqa: BLE001 - fail-open 观测
            return 0


# ── 熔断状态：RedisCircuitStateStore ─────────────────────────────────────────

class RedisCircuitStateStore:
    """Redis Hash 版熔断状态。与 PostgresCircuitStateStore 语义等价：

    - Hash `gw:circuit:{pid}` 存 state/failures/opened_at/next_probe_at/updated_at
      （全 epoch ms）。
    - get：HGETALL，缺失 → 默认 CLOSED（Redis 重启 / TTL 过期安全默认）。
    - save：HSET + PEXPIRE（record_ttl_seconds 默认 120 = 4× 默认 cooldown，
      保证 OPEN 记录完整覆盖 cooldown 窗口；probe 后再次 save 刷新）。
    - get/save 遇 Redis 错误 → fail-open（get 返 CLOSED、save 吞错日志）。
    """

    def __init__(
        self,
        client: Any,
        *,
        record_ttl_seconds: float = 120.0,
    ) -> None:
        self._client = client
        self._record_ttl_ms = int(record_ttl_seconds * 1000)

    def get(self, provider_instance_id: str) -> CircuitStateRecord:
        try:
            h = self._client.hgetall(circuit_key(provider_instance_id))
        except (Exception, OSError):  # noqa: BLE001 - fail-open
            return CircuitStateRecord(provider_instance_id=provider_instance_id)
        if not h:
            return CircuitStateRecord(provider_instance_id=provider_instance_id)
        state_raw = h.get("state")
        return CircuitStateRecord(
            provider_instance_id=provider_instance_id,
            state=CircuitState(state_raw) if state_raw else CircuitState.CLOSED,
            consecutive_failures=int(h.get("failures", 0) or 0),
            opened_at=_dt_from_ms(int(h["opened_at"])) if h.get("opened_at") else None,
            next_probe_at=_dt_from_ms(int(h["next_probe_at"]))
            if h.get("next_probe_at")
            else None,
            updated_at=_dt_from_ms(int(h["updated_at"])) if h.get("updated_at") else None,
        )

    def save(self, record: CircuitStateRecord) -> None:
        mapping = {
            "state": record.state.value,
            "failures": record.consecutive_failures,
            "opened_at": _ms_from_dt(record.opened_at) or "",
            "next_probe_at": _ms_from_dt(record.next_probe_at) or "",
            "updated_at": _ms_from_dt(record.updated_at) or "",
        }
        try:
            pipe = self._client.pipeline(transaction=True)
            pipe.hset(circuit_key(record.provider_instance_id), mapping=mapping)
            pipe.pexpire(circuit_key(record.provider_instance_id), self._record_ttl_ms)
            pipe.execute()
        except (Exception, OSError):  # noqa: BLE001 - fail-open
            LOGGER.warning(
                "GATEWAY_REDIS_CIRCUIT_SAVE_FAILED pid=%s", record.provider_instance_id
            )


__all__ = [
    "RedisCircuitStateStore",
    "RedisLeaseConcurrencyBudget",
    "budget_key",
    "circuit_key",
]
