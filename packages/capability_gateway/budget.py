"""G2.3 Provider Concurrency Budget — 短事务 Lease，跨进程全局上限。

目标：无论多少 Run/Worker 并发，同一 Provider 的实际 inflight calls 永远
不超过它的并发预算（`max_concurrency`）。

三个身份：
- request_fingerprint    同类型请求指纹（RoutingPlan.request_fingerprint）
- route_execution_id     这一次 Capability Gateway invocation
- provider_call_id       这一次具体 Provider attempt（permit 绑定它）

关键设计：
- Lease 必须带 `expires_at`（Worker 崩溃后 TTL 过期 → 容量自动恢复）；
- acquire 用**短事务**：FOR UPDATE provider state → 清理过期 → count active →
  insert lease → commit。**绝不在 Provider 网络调用期间持有 DB transaction/connection**；
- 等待是有界的（acquire_timeout）→ 超时抛 `ProviderCapacityExhaustedError`；
- 等待期间支持业务取消（should_cancel）→ 抛 `BudgetWaitCancelled`，且不 invoke provider；
- CAPACITY_EXHAUSTED **不计** Provider health/circuit failure（不修改任何状态）；
- 本轮不做 RPM / quota / cost / circuit / runtime fallback。

实现：
- InProcessConcurrencyBudget（G2.3a：单进程语义验证；不是多进程生产保证）
- PostgresLeaseConcurrencyBudget（G2.3b：production shared lease）
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11
    UTC = timezone.utc


class ProviderCapacityExhaustedError(Exception):
    """预算等待超时仍未获得 permit（PROVIDER_CAPACITY_EXHAUSTED）。

    这是「我们自己不允许继续压 Provider」，不是 Provider 故障；不计入
    health/circuit failure。
    """

    def __init__(self, provider_instance_id: str) -> None:
        super().__init__(f"provider capacity exhausted: {provider_instance_id}")
        self.provider_instance_id = provider_instance_id


class BudgetWaitCancelled(Exception):
    """等待 permit 期间检测到业务取消（对应 G1 cancel_requested）。"""


@dataclass(frozen=True)
class ProviderConcurrencyPolicy:
    """单个 Provider 的并发预算配置（provisional，后续压测校准）。"""

    provider_instance_id: str
    max_concurrency: int
    acquire_timeout_seconds: float = 30.0
    lease_ttl_seconds: float = 90.0


@dataclass
class ProviderPermit:
    """一次 Provider attempt 的并发 Lease。绑定 provider_call_id。"""

    lease_id: str
    provider_instance_id: str
    route_execution_id: str
    provider_call_id: str
    acquired_at: datetime
    expires_at: datetime
    released_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.released_at is None and self.expires_at > datetime.now(UTC)


class ConcurrencyBudget(Protocol):
    """并发预算接口。acquire 拿到 permit；release 归还（任何路径都必须 release）。"""

    async def acquire(
        self,
        *,
        provider_instance_id: str,
        route_execution_id: str,
        provider_call_id: str,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ProviderPermit:
        ...

    async def release(self, permit: ProviderPermit) -> None:
        ...


def policy_from_instance(instance: Any) -> ProviderConcurrencyPolicy:
    """从 CapabilityInstance 的 limits.max_concurrency 派生 policy（provisional）。"""
    max_conc = int(instance.limits.get("max_concurrency", 0) or 0)
    if max_conc <= 0:
        max_conc = 1  # 未配置默认 1（保守）
    return ProviderConcurrencyPolicy(
        provider_instance_id=instance.instance_id, max_concurrency=max_conc
    )


def _now() -> datetime:
    return datetime.now(UTC)


# ── G2.3a: InProcessConcurrencyBudget（单进程语义验证） ───────────────────────

class InProcessConcurrencyBudget:
    """进程内 Lease 预算。G2.3a 验证语义用；**不是多进程生产保证**。

    用 per-provider 的 asyncio.Lock 保证短临界区原子性；Lease 带 expires_at，
    支持过期清理（stale lease recovery）——与 Postgres 版语义一致。
    """

    def __init__(
        self,
        policies: dict[str, ProviderConcurrencyPolicy],
        *,
        poll_interval_seconds: float = 0.01,
    ) -> None:
        self._policies = policies
        self._poll_interval_seconds = poll_interval_seconds
        self._active: dict[str, list[ProviderPermit]] = defaultdict(list)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _policy(self, provider_instance_id: str) -> ProviderConcurrencyPolicy:
        return self._policies.get(
            provider_instance_id,
            ProviderConcurrencyPolicy(provider_instance_id=provider_instance_id, max_concurrency=1),
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
            permit = await self._try_acquire(policy, route_execution_id, provider_call_id)
            if permit is not None:
                return permit
            if should_cancel is not None and should_cancel():
                raise BudgetWaitCancelled()
            if _monotonic() >= deadline:
                raise ProviderCapacityExhaustedError(provider_instance_id)
            await asyncio.sleep(self._poll_interval_seconds)

    async def _try_acquire(
        self, policy: ProviderConcurrencyPolicy, route_execution_id: str, provider_call_id: str
    ) -> ProviderPermit | None:
        now = _now()
        async with self._locks[policy.provider_instance_id]:
            leases = self._active[policy.provider_instance_id]
            # 清理过期/已释放 → stale lease recovery
            self._active[policy.provider_instance_id] = [
                lease for lease in leases
                if lease.released_at is None and lease.expires_at > now
            ]
            active = [
                lease for lease in self._active[policy.provider_instance_id]
                if lease.released_at is None
            ]
            if len(active) >= policy.max_concurrency:
                return None
            permit = ProviderPermit(
                lease_id=uuid.uuid4().hex,
                provider_instance_id=policy.provider_instance_id,
                route_execution_id=route_execution_id,
                provider_call_id=provider_call_id,
                acquired_at=now,
                expires_at=now + timedelta(seconds=policy.lease_ttl_seconds),
            )
            self._active[policy.provider_instance_id].append(permit)
            return permit

    async def release(self, permit: ProviderPermit) -> None:
        async with self._locks[permit.provider_instance_id]:
            permit.released_at = _now()

    def active_leases(self, provider_instance_id: str) -> int:
        now = _now()
        return sum(
            1 for lease in self._active.get(provider_instance_id, [])
            if lease.released_at is None and lease.expires_at > now
        )


def _monotonic() -> float:
    import time

    return time.monotonic()


# ── G2.3b: PostgresLeaseConcurrencyBudget（production shared lease） ─────────

DDL_LEASES = """
CREATE TABLE IF NOT EXISTS provider_concurrency_leases (
    lease_id TEXT PRIMARY KEY,
    provider_instance_id TEXT NOT NULL,
    route_execution_id TEXT NOT NULL,
    provider_call_id TEXT NOT NULL,
    acquired_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    released_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_pcl_provider
    ON provider_concurrency_leases(provider_instance_id);
"""

DDL_STATE = """
CREATE TABLE IF NOT EXISTS provider_concurrency_state (
    provider_instance_id TEXT PRIMARY KEY,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def create_concurrency_tables(engine_or_session: Any) -> None:
    """幂等建表（测试/验收/启动时调用）。engine 或 session 均可。"""
    if hasattr(engine_or_session, "begin"):
        with engine_or_session.begin() as conn:
            conn.execute(text(DDL_LEASES))
            conn.execute(text(DDL_STATE))
    else:
        conn = engine_or_session.connection()
        conn.execute(text(DDL_LEASES))
        conn.execute(text(DDL_STATE))


class PostgresLeaseConcurrencyBudget:
    """PostgreSQL 共享 Lease 预算（G2.3b，production）。

    acquire = 短事务：确保 provider state 行存在并 FOR UPDATE → 清理过期/已释放
    lease → count active → 若 < max 则 insert lease → commit。**DB connection 在
    commit 后即归还，Provider 网络调用期间不持有。**
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        policies: dict[str, ProviderConcurrencyPolicy],
        *,
        poll_interval_seconds: float = 0.05,
    ) -> None:
        self._session_factory = session_factory
        self._policies = policies
        self._poll_interval_seconds = poll_interval_seconds

    def _policy(self, provider_instance_id: str) -> ProviderConcurrencyPolicy:
        return self._policies.get(
            provider_instance_id,
            ProviderConcurrencyPolicy(provider_instance_id=provider_instance_id, max_concurrency=1),
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
        self, policy: ProviderConcurrencyPolicy, route_execution_id: str, provider_call_id: str
    ) -> ProviderPermit | None:
        with self._session_factory() as session:
            try:
                # 用 DB 时钟作为 lease 时间基准（免疫 Python↔DB 时钟漂移）：
                # expires_at 必须相对 DB 的 now()，否则 TTL 比较会失真。
                now = session.execute(text("SELECT now()")).scalar()
                session.execute(
                    text(
                        "INSERT INTO provider_concurrency_state (provider_instance_id) "
                        "VALUES (:pid) ON CONFLICT (provider_instance_id) DO NOTHING"
                    ),
                    {"pid": policy.provider_instance_id},
                )
                # 行锁锚点：per-provider 串行化申请
                session.execute(
                    text(
                        "SELECT provider_instance_id FROM provider_concurrency_state "
                        "WHERE provider_instance_id = :pid FOR UPDATE"
                    ),
                    {"pid": policy.provider_instance_id},
                )
                # 清理过期 / 已释放 lease（stale lease recovery）
                session.execute(
                    text(
                        "DELETE FROM provider_concurrency_leases "
                        "WHERE provider_instance_id = :pid "
                        "AND (released_at IS NOT NULL OR expires_at < now())"
                    ),
                    {"pid": policy.provider_instance_id},
                )
                active = int(
                    session.execute(
                        text(
                            "SELECT COUNT(*) FROM provider_concurrency_leases "
                            "WHERE provider_instance_id = :pid "
                            "AND released_at IS NULL AND expires_at >= now()"
                        ),
                        {"pid": policy.provider_instance_id},
                    ).scalar()
                    or 0
                )
                if active >= policy.max_concurrency:
                    session.rollback()
                    return None
                lease_id = uuid.uuid4().hex
                session.execute(
                    text(
                        "INSERT INTO provider_concurrency_leases "
                        "(lease_id, provider_instance_id, route_execution_id, "
                        " provider_call_id, acquired_at, expires_at) "
                        "VALUES (:lid, :pid, :rid, :cid, :a, :e)"
                    ),
                    {
                        "lid": lease_id,
                        "pid": policy.provider_instance_id,
                        "rid": route_execution_id,
                        "cid": provider_call_id,
                        "a": now,
                        "e": now + timedelta(seconds=policy.lease_ttl_seconds),
                    },
                )
                session.commit()
            except Exception:
                session.rollback()
                raise
        return ProviderPermit(
            lease_id=lease_id,
            provider_instance_id=policy.provider_instance_id,
            route_execution_id=route_execution_id,
            provider_call_id=provider_call_id,
            acquired_at=now,
            expires_at=now + timedelta(seconds=policy.lease_ttl_seconds),
        )

    async def release(self, permit: ProviderPermit) -> None:
        await asyncio.to_thread(self._release_sync, permit.lease_id)
        permit.released_at = _now()

    def _release_sync(self, lease_id: str) -> None:
        with self._session_factory() as session:
            session.execute(
                text("UPDATE provider_concurrency_leases SET released_at = now() "
                     "WHERE lease_id = :lid"),
                {"lid": lease_id},
            )
            session.commit()

    def active_leases(self, provider_instance_id: str) -> int:
        with self._session_factory() as session:
            return int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM provider_concurrency_leases "
                        "WHERE provider_instance_id = :pid "
                        "AND released_at IS NULL AND expires_at >= now()"
                    ),
                    {"pid": provider_instance_id},
                ).scalar()
                or 0
            )


__all__ = [
    "BudgetWaitCancelled",
    "ConcurrencyBudget",
    "InProcessConcurrencyBudget",
    "PostgresLeaseConcurrencyBudget",
    "ProviderCapacityExhaustedError",
    "ProviderConcurrencyPolicy",
    "ProviderPermit",
    "create_concurrency_tables",
    "policy_from_instance",
]
