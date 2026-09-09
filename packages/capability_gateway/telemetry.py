"""G2.5a Provider Attempt Telemetry — 每次 Provider attempt 的可追踪事实记录。

一次 Gateway invocation（route_execution_id）可以对应多次 Provider attempt
（provider_call_id）。每个 attempt 独立一条记录，append-only，绝不 UPDATE 覆盖：

    Route R1
    ├── C1 DeepSeek TIMEOUT（transport_invoked=true, outcome=failed）
    └── C2 OpenRouter SUCCESS（transport_invoked=true, outcome=success）

覆盖完整 attempt 生命周期：circuit_rejected / capacity_exhausted / no_adapter /
success / failed / cancelled。其中 circuit/capacity 未真正调用 Provider →
`transport_invoked=false`。

安全边界：**禁止记录 raw prompt / raw response / API key / full source**，
只记录 token/result 用量与 schema/task_type/model 等元数据。

`ProviderAttemptRecorder` 是 best-effort / fail-open：telemetry 写失败不得影响
业务调用（PROVIDER_CALL_METRIC_PERSIST_FAILED 日志）。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy import text

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Python < 3.11
    UTC = timezone.utc

LOGGER = logging.getLogger(__name__)


# Attempt outcome 常量（可解释、可查询）。
OUTCOME_SUCCESS = "success"
OUTCOME_FAILED = "failed"
OUTCOME_CIRCUIT_REJECTED = "circuit_rejected"
OUTCOME_CAPACITY_EXHAUSTED = "capacity_exhausted"
OUTCOME_NO_ADAPTER = "no_adapter"
OUTCOME_CANCELLED = "cancelled"


@dataclass
class ProviderAttemptRecord:
    """一次真实 Provider attempt 到底发生了什么（append-only 事实）。"""

    provider_call_id: str
    route_execution_id: str
    provider_instance_id: str
    outcome: str
    transport_invoked: bool
    started_at: datetime
    finished_at: datetime | None = None
    latency_ms: float | None = None
    attempt_index: int = 0
    fallback_used: bool = False
    fallback_index: int | None = None
    failure_class: str | None = None
    request_fingerprint: str | None = None
    run_id: str | None = None
    capability: str | None = None
    task_type: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_count: int | None = None
    result_count: int | None = None
    cost_estimate: float | None = None
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_call_id": self.provider_call_id,
            "route_execution_id": self.route_execution_id,
            "provider_instance_id": self.provider_instance_id,
            "outcome": self.outcome,
            "transport_invoked": self.transport_invoked,
            "attempt_index": self.attempt_index,
            "fallback_used": self.fallback_used,
            "fallback_index": self.fallback_index,
            "failure_class": self.failure_class,
            "request_fingerprint": self.request_fingerprint,
            "run_id": self.run_id,
            "capability": self.capability,
            "task_type": self.task_type,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "request_count": self.request_count,
            "result_count": self.result_count,
            "cost_estimate": self.cost_estimate,
        }


class ProviderAttemptRecorder(Protocol):
    def record(self, attempt: ProviderAttemptRecord) -> None: ...
    def recent(
        self, *, provider_instance_id: str | None = None, limit: int = 1000
    ) -> list[ProviderAttemptRecord]: ...


class InMemoryProviderAttemptRecorder:
    """进程内 recorder（G2.5a 测试 + 单进程）。"""

    def __init__(self) -> None:
        self._records: list[ProviderAttemptRecord] = []

    def record(self, attempt: ProviderAttemptRecord) -> None:
        self._records.append(attempt)

    def recent(
        self, *, provider_instance_id: str | None = None, limit: int = 1000
    ) -> list[ProviderAttemptRecord]:
        recs = [
            r for r in self._records
            if provider_instance_id is None or r.provider_instance_id == provider_instance_id
        ]
        return recs[-limit:]

    def all(self) -> list[ProviderAttemptRecord]:
        return list(self._records)


DDL_ATTEMPTS = """
CREATE TABLE IF NOT EXISTS provider_attempt_records (
    provider_call_id TEXT PRIMARY KEY,
    route_execution_id TEXT NOT NULL,
    request_fingerprint TEXT,
    run_id TEXT,
    provider_instance_id TEXT NOT NULL,
    capability TEXT,
    task_type TEXT,
    attempt_index INT NOT NULL,
    transport_invoked BOOLEAN NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    latency_ms DOUBLE PRECISION,
    outcome TEXT NOT NULL,
    failure_class TEXT,
    fallback_used BOOLEAN NOT NULL DEFAULT false,
    fallback_index INT,
    input_tokens INT,
    output_tokens INT,
    request_count INT,
    result_count INT,
    cost_estimate DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_par_route
    ON provider_attempt_records(route_execution_id);
CREATE INDEX IF NOT EXISTS ix_par_provider_created
    ON provider_attempt_records(provider_instance_id, created_at);
"""


def create_attempt_tables(engine_or_session: Any) -> None:
    if hasattr(engine_or_session, "begin"):
        with engine_or_session.begin() as conn:
            conn.execute(text(DDL_ATTEMPTS))
    else:
        conn = engine_or_session.connection()
        conn.execute(text(DDL_ATTEMPTS))


_INSERT_COLS = (
    "provider_call_id, route_execution_id, request_fingerprint, run_id, "
    "provider_instance_id, capability, task_type, attempt_index, transport_invoked, "
    "started_at, finished_at, latency_ms, outcome, failure_class, fallback_used, "
    "fallback_index, input_tokens, output_tokens, request_count, result_count, "
    "cost_estimate"
)


class PostgresProviderAttemptRecorder:
    """PostgreSQL attempt recorder（G2.5a production）。fail-open。"""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    def record(self, attempt: ProviderAttemptRecord) -> None:
        try:
            with self._session_factory() as session:
                session.execute(
                    text(
                        f"INSERT INTO provider_attempt_records ({_INSERT_COLS}) "
                        "VALUES (:provider_call_id, :route_execution_id, :request_fingerprint, "
                        ":run_id, :provider_instance_id, :capability, :task_type, :attempt_index, "
                        ":transport_invoked, :started_at, :finished_at, :latency_ms, :outcome, "
                        ":failure_class, :fallback_used, :fallback_index, :input_tokens, "
                        ":output_tokens, :request_count, :result_count, :cost_estimate)"
                    ),
                    {
                        "provider_call_id": attempt.provider_call_id,
                        "route_execution_id": attempt.route_execution_id,
                        "request_fingerprint": attempt.request_fingerprint,
                        "run_id": attempt.run_id,
                        "provider_instance_id": attempt.provider_instance_id,
                        "capability": attempt.capability,
                        "task_type": attempt.task_type,
                        "attempt_index": attempt.attempt_index,
                        "transport_invoked": attempt.transport_invoked,
                        "started_at": attempt.started_at,
                        "finished_at": attempt.finished_at,
                        "latency_ms": attempt.latency_ms,
                        "outcome": attempt.outcome,
                        "failure_class": attempt.failure_class,
                        "fallback_used": attempt.fallback_used,
                        "fallback_index": attempt.fallback_index,
                        "input_tokens": attempt.input_tokens,
                        "output_tokens": attempt.output_tokens,
                        "request_count": attempt.request_count,
                        "result_count": attempt.result_count,
                        "cost_estimate": attempt.cost_estimate,
                    },
                )
                session.commit()
        except Exception:  # noqa: BLE001 - telemetry fail-open
            LOGGER.warning(
                "PROVIDER_CALL_METRIC_PERSIST_FAILED provider_call_id=%s",
                attempt.provider_call_id,
                exc_info=True,
            )

    def recent(
        self, *, provider_instance_id: str | None = None, limit: int = 1000
    ) -> list[ProviderAttemptRecord]:
        sql = (
            "SELECT provider_call_id, route_execution_id, request_fingerprint, run_id, "
            "provider_instance_id, capability, task_type, attempt_index, transport_invoked, "
            "started_at, finished_at, latency_ms, outcome, failure_class, fallback_used, "
            "fallback_index, input_tokens, output_tokens, request_count, result_count, "
            "cost_estimate FROM provider_attempt_records "
        )
        params: dict[str, Any] = {}
        if provider_instance_id is not None:
            sql += "WHERE provider_instance_id = :pid "
            params["pid"] = provider_instance_id
        sql += "ORDER BY started_at DESC LIMIT :limit"
        params["limit"] = limit
        with self._session_factory() as session:
            rows = session.execute(text(sql), params).fetchall()
        return [_row_to_record(row) for row in rows]


def _row_to_record(row: Any) -> ProviderAttemptRecord:
    return ProviderAttemptRecord(
        provider_call_id=row[0],
        route_execution_id=row[1],
        request_fingerprint=row[2],
        run_id=row[3],
        provider_instance_id=row[4],
        capability=row[5],
        task_type=row[6],
        attempt_index=int(row[7]),
        transport_invoked=bool(row[8]),
        started_at=row[9],
        finished_at=row[10],
        latency_ms=float(row[11]) if row[11] is not None else None,
        outcome=row[12],
        failure_class=row[13],
        fallback_used=bool(row[14]),
        fallback_index=int(row[15]) if row[15] is not None else None,
        input_tokens=int(row[16]) if row[16] is not None else None,
        output_tokens=int(row[17]) if row[17] is not None else None,
        request_count=int(row[18]) if row[18] is not None else None,
        result_count=int(row[19]) if row[19] is not None else None,
        cost_estimate=float(row[20]) if row[20] is not None else None,
    )


__all__ = [
    "OUTCOME_CANCELLED",
    "OUTCOME_CAPACITY_EXHAUSTED",
    "OUTCOME_CIRCUIT_REJECTED",
    "OUTCOME_FAILED",
    "OUTCOME_NO_ADAPTER",
    "OUTCOME_SUCCESS",
    "InMemoryProviderAttemptRecorder",
    "PostgresProviderAttemptRecorder",
    "ProviderAttemptRecord",
    "ProviderAttemptRecorder",
    "create_attempt_tables",
]
