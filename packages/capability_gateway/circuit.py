"""G2.4a Provider Failure Taxonomy + Circuit Breaker。

先统一 Failure 分类，再决定是否计入 Provider outage：

- **Provider Availability Failure**（可计入 circuit）：NETWORK / TIMEOUT / RATE_LIMIT /
  PROVIDER_5XX。
- **Local Control Failure**：CAPACITY_EXHAUSTED（我们自己的 Gateway 不允许继续压，
  Provider 可能完全健康 → 不计 circuit，是否 fallback 由 FallbackPolicy 决定）。
- **Business / Quality Failure**：OUTPUT_INVALID / BUSINESS_VALIDATION（不是 Provider 挂了，
  不计 circuit，第一版也不 fallback）。

Circuit 状态机（CLOSED → OPEN → HALF_OPEN → CLOSED/OPEN）：
- OPEN 的 Provider 不得产生 transport call；
- cooldown 后进入 HALF_OPEN，只放行受控 probe；
- 只按 `provider_instance_id` 管理（不是 provider 名）。

Runtime state 与 CapabilityRegistry 分离（Registry = 静态 metadata）。
Circuit check/update 均为短事务；Provider 网络调用期间不持 DB transaction。

DB 时钟单源：所有 deadline/next_probe_at 用同一 clock（Postgres 用 DB now()）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Protocol

from sqlalchemy import text

from packages.capability_gateway.schemas import CircuitState

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11
    UTC = timezone.utc


# ── Failure Taxonomy ─────────────────────────────────────────────────────────

class ProviderFailureClass(StrEnum):
    NETWORK = "network"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"  # 429
    PROVIDER_5XX = "provider_5xx"
    CAPACITY_EXHAUSTED = "capacity_exhausted"
    AUTH = "auth"
    QUOTA = "quota"
    OUTPUT_INVALID = "output_invalid"
    BUSINESS_VALIDATION = "business_validation"
    CANCELLED = "cancelled"


# 只有这 4 类计入 Provider availability failure（会影响 circuit）。
AVAILABILITY_FAILURES = {
    ProviderFailureClass.NETWORK,
    ProviderFailureClass.TIMEOUT,
    ProviderFailureClass.RATE_LIMIT,
    ProviderFailureClass.PROVIDER_5XX,
}


def _from_status_code(status: int | None) -> ProviderFailureClass:
    if status == 429:
        return ProviderFailureClass.RATE_LIMIT
    if status is not None and 500 <= status < 600:
        return ProviderFailureClass.PROVIDER_5XX
    if status in {401, 403}:
        return ProviderFailureClass.AUTH
    if status is not None and 400 <= status < 500:
        return ProviderFailureClass.QUOTA
    return ProviderFailureClass.NETWORK


class FailureClassifier:
    """把 Provider / Adapter / Budget 的错误统一映射为 ProviderFailureClass。"""

    def classify(self, failure: Any) -> ProviderFailureClass:
        from packages.capability_gateway.budget import (
            BudgetWaitCancelled,
            ProviderCapacityExhaustedError,
        )

        # Budget / 取消
        if isinstance(failure, ProviderCapacityExhaustedError):
            return ProviderFailureClass.CAPACITY_EXHAUSTED
        if isinstance(failure, BudgetWaitCancelled):
            return ProviderFailureClass.CANCELLED
        if isinstance(failure, asyncio.CancelledError):
            return ProviderFailureClass.CANCELLED
        if isinstance(failure, (asyncio.TimeoutError, TimeoutError)):
            return ProviderFailureClass.TIMEOUT

        # CapabilityResult（adapter 已返回结构化失败）
        if hasattr(failure, "success") and not getattr(failure, "success", True):
            explicit = getattr(failure, "failure_class", None)
            if explicit is not None:
                return explicit
            return ProviderFailureClass.OUTPUT_INVALID

        # 常见 Provider 错误类型（按类名 + 属性推断）
        cls_name = type(failure).__name__
        detail = getattr(failure, "detail", None) or {}
        status = detail.get("status_code") if isinstance(detail, dict) else None
        if isinstance(detail, dict) and status is not None:
            return _from_status_code(status)

        if cls_name in {"ProviderRetryableError", "SourceTavilyError", "SourceAnySearchError"}:
            # retryable 无明确 status → 网络/超时类
            return ProviderFailureClass.NETWORK
        if cls_name in {"ProviderAuthError", "AuthenticationError"}:
            return ProviderFailureClass.AUTH
        if cls_name in {"ProviderParseError", "ProviderRequestError"}:
            return ProviderFailureClass.OUTPUT_INVALID
        if "Quota" in cls_name or "RateLimit" in cls_name:
            return (
                ProviderFailureClass.QUOTA
                if "Quota" in cls_name
                else ProviderFailureClass.RATE_LIMIT
            )
        if cls_name in {"ConnectionError", "URLError", "APIConnectionError", "OSError"}:
            return ProviderFailureClass.NETWORK

        # 连接类基类
        if isinstance(failure, ConnectionError):
            return ProviderFailureClass.NETWORK
        return ProviderFailureClass.OUTPUT_INVALID


# ── Circuit State ────────────────────────────────────────────────────────────
# CircuitState 定义在 schemas（G2.1 contract），此处复用同一枚举（CLOSED/OPEN/HALF_OPEN）。

@dataclass
class CircuitStateRecord:
    provider_instance_id: str
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at: datetime | None = None
    next_probe_at: datetime | None = None
    updated_at: datetime | None = None


class CircuitStateStore(Protocol):
    def get(self, provider_instance_id: str) -> CircuitStateRecord: ...
    def save(self, record: CircuitStateRecord) -> None: ...


class InMemoryCircuitStateStore:
    """进程内 circuit state（G2.4a 测试用；非多进程生产保证）。"""

    def __init__(self) -> None:
        self._records: dict[str, CircuitStateRecord] = {}

    def get(self, provider_instance_id: str) -> CircuitStateRecord:
        return self._records.get(
            provider_instance_id, CircuitStateRecord(provider_instance_id=provider_instance_id)
        )

    def save(self, record: CircuitStateRecord) -> None:
        self._records[record.provider_instance_id] = record


DDL_CIRCUIT = """
CREATE TABLE IF NOT EXISTS provider_circuit_state (
    provider_instance_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    consecutive_failures INT NOT NULL DEFAULT 0,
    opened_at TIMESTAMPTZ,
    next_probe_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def create_circuit_tables(engine_or_session: Any) -> None:
    if hasattr(engine_or_session, "begin"):
        with engine_or_session.begin() as conn:
            conn.execute(text(DDL_CIRCUIT))
    else:
        conn = engine_or_session.connection()
        conn.execute(text(DDL_CIRCUIT))


class PostgresCircuitStateStore:
    """PostgreSQL circuit state（G2.4a production；短事务读写）。"""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    def get(self, provider_instance_id: str) -> CircuitStateRecord:
        with self._session_factory() as session:
            row = session.execute(
                text(
                    "SELECT provider_instance_id, state, consecutive_failures, "
                    "opened_at, next_probe_at, updated_at "
                    "FROM provider_circuit_state WHERE provider_instance_id = :pid"
                ),
                {"pid": provider_instance_id},
            ).fetchone()
        if row is None:
            return CircuitStateRecord(provider_instance_id=provider_instance_id)
        return CircuitStateRecord(
            provider_instance_id=row[0],
            state=CircuitState(row[1]),
            consecutive_failures=int(row[2]),
            opened_at=row[3],
            next_probe_at=row[4],
            updated_at=row[5],
        )

    def save(self, record: CircuitStateRecord) -> None:
        with self._session_factory() as session:
            session.execute(
                text(
                    "INSERT INTO provider_circuit_state "
                    "(provider_instance_id, state, consecutive_failures, opened_at, "
                    " next_probe_at, updated_at) "
                    "VALUES (:pid, :state, :failures, :opened, :probe, now()) "
                    "ON CONFLICT (provider_instance_id) DO UPDATE SET "
                    "state = EXCLUDED.state, "
                    "consecutive_failures = EXCLUDED.consecutive_failures, "
                    "opened_at = EXCLUDED.opened_at, "
                    "next_probe_at = EXCLUDED.next_probe_at, "
                    "updated_at = now()"
                ),
                {
                    "pid": record.provider_instance_id,
                    "state": record.state.value,
                    "failures": record.consecutive_failures,
                    "opened": record.opened_at,
                    "probe": record.next_probe_at,
                },
            )
            session.commit()


def _now() -> datetime:
    return datetime.now(UTC)


class CircuitBreaker:
    """CLOSED / OPEN / HALF_OPEN 状态机。只按 provider_instance_id 管理。

    - 只有 AVAILABILITY_FAILURES 计入 circuit（capacity/quality/cancel 不影响）。
    - OPEN → allow() 返回 False（不产生 transport call）；cooldown 后 → HALF_OPEN
      受控 probe；probe 成功 → CLOSED，失败 → OPEN。
    - 单一时钟源：now_provider 注入（Postgres 场景传 DB now()，避免时钟漂移）。
    """

    def __init__(
        self,
        store: CircuitStateStore,
        *,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._now = now_provider or _now

    def allow(self, provider_instance_id: str) -> bool:
        """Provider 调用前检查。返回 False = 该 Provider 当前不允许调用（OPEN）。"""
        rec = self._store.get(provider_instance_id)
        now = self._now()
        if rec.state == CircuitState.CLOSED:
            return True
        if rec.state == CircuitState.OPEN:
            if rec.next_probe_at is not None and now >= rec.next_probe_at:
                rec.state = CircuitState.HALF_OPEN
                rec.updated_at = now
                self._store.save(rec)
                return True  # 受控 probe
            return False
        if rec.state == CircuitState.HALF_OPEN:
            return True  # probe
        return False

    def record_success(self, provider_instance_id: str) -> None:
        rec = self._store.get(provider_instance_id)
        now = self._now()
        if rec.state == CircuitState.HALF_OPEN:
            rec.state = CircuitState.CLOSED  # probe 成功 → 恢复
        rec.consecutive_failures = 0
        rec.opened_at = None
        rec.next_probe_at = None
        rec.updated_at = now
        self._store.save(rec)

    def record_failure(
        self, provider_instance_id: str, failure_class: ProviderFailureClass
    ) -> None:
        if failure_class not in AVAILABILITY_FAILURES:
            return  # capacity/quality/cancel 不污染 circuit
        rec = self._store.get(provider_instance_id)
        now = self._now()
        if rec.state == CircuitState.HALF_OPEN:
            # probe 失败 → 立刻回 OPEN
            rec.state = CircuitState.OPEN
            rec.opened_at = now
            rec.next_probe_at = now + timedelta(seconds=self._cooldown_seconds)
        else:
            rec.consecutive_failures += 1
            if rec.consecutive_failures >= self._failure_threshold:
                rec.state = CircuitState.OPEN
                rec.opened_at = now
                rec.next_probe_at = now + timedelta(seconds=self._cooldown_seconds)
        rec.updated_at = now
        self._store.save(rec)


__all__ = [
    "AVAILABILITY_FAILURES",
    "CircuitBreaker",
    "CircuitState",
    "CircuitStateRecord",
    "CircuitStateStore",
    "FailureClassifier",
    "InMemoryCircuitStateStore",
    "PostgresCircuitStateStore",
    "ProviderFailureClass",
    "create_circuit_tables",
]
