"""G3 Execution Lease — Worker 对 Task 的执行所有权（Lease + Heartbeat + TTL）。

- Lease：这个 Worker 现在拥有任务。
- Heartbeat：证明我还活着（独立续租）。
- TTL：多久没 heartbeat 就视为死亡。
- Generation：即使旧 Worker 复活，也不能再写结果（fencing token）。

**所有 lease 时间用 PostgreSQL DB clock**（G2.3 经验：Python clock vs DB clock
漂移会导致 TTL 判断失真）。
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from sqlalchemy import column, func, select, table, text, update
from sqlalchemy.orm import Session

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc


@dataclass
class TaskExecutionLease:
    lease_id: str
    task_id: int
    run_id: int | None
    worker_id: str
    execution_generation: int
    acquired_at: datetime
    heartbeat_at: datetime | None = None
    expires_at: datetime | None = None
    released_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.released_at is None and (
            self.expires_at is None or self.expires_at > datetime.now(UTC)
        )

    @property
    def is_expired(self) -> bool:
        return self.released_at is None and (
            self.expires_at is not None and self.expires_at <= datetime.now(UTC)
        )


class ExecutionLeaseStore(Protocol):
    def create(
        self, *, task_id, run_id, worker_id, execution_generation, ttl_seconds
    ) -> TaskExecutionLease: ...
    def heartbeat(self, lease_id: str, ttl_seconds: float) -> bool: ...
    def release(self, lease_id: str) -> None: ...
    def active_count(self) -> int: ...
    def get(self, lease_id: str) -> TaskExecutionLease | None: ...
    def list_expired(self) -> list[TaskExecutionLease]: ...


# ── InMemory（G3 单进程语义验证） ─────────────────────────────────────────────

class InMemoryExecutionLeaseStore:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._leases: dict[str, TaskExecutionLease] = {}
        self._lock = threading.Lock()
        self._now = clock or (lambda: datetime.now(UTC))

    def create(
        self, *, task_id, run_id, worker_id, execution_generation, ttl_seconds
    ) -> TaskExecutionLease:
        now = self._now()
        lease = TaskExecutionLease(
            lease_id=uuid.uuid4().hex, task_id=task_id, run_id=run_id,
            worker_id=worker_id, execution_generation=execution_generation,
            acquired_at=now, heartbeat_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        with self._lock:
            self._leases[lease.lease_id] = lease
        return lease

    def heartbeat(self, lease_id: str, ttl_seconds: float) -> bool:
        now = self._now()
        with self._lock:
            lease = self._leases.get(lease_id)
            if lease is None or lease.released_at is not None:
                return False
            lease.heartbeat_at = now
            lease.expires_at = now + timedelta(seconds=ttl_seconds)
            return True

    def release(self, lease_id: str) -> None:
        with self._lock:
            lease = self._leases.get(lease_id)
            if lease is not None:
                lease.released_at = self._now()

    def active_count(self) -> int:
        now = self._now()
        with self._lock:
            return sum(
                1 for lease in self._leases.values()
                if lease.released_at is None
                and (lease.expires_at is None or lease.expires_at > now)
            )

    def get(self, lease_id: str) -> TaskExecutionLease | None:
        with self._lock:
            return self._leases.get(lease_id)

    def list_expired(self) -> list[TaskExecutionLease]:
        now = self._now()
        with self._lock:
            return [
                lease for lease in self._leases.values()
                if lease.released_at is None
                and lease.expires_at is not None and lease.expires_at <= now
            ]


# ── PostgreSQL（production，DB clock 单源） ─────────────────────────────────

_LEASES = table(
    "task_execution_leases",
    column("lease_id"), column("task_id"), column("run_id"), column("worker_id"),
    column("execution_generation"), column("acquired_at"), column("heartbeat_at"),
    column("expires_at"), column("released_at"),
)

DDL_EXECUTION_LEASES = """
CREATE TABLE IF NOT EXISTS task_execution_leases (
    lease_id TEXT PRIMARY KEY,
    task_id BIGINT NOT NULL,
    run_id BIGINT,
    worker_id TEXT NOT NULL,
    execution_generation INT NOT NULL,
    acquired_at TIMESTAMPTZ NOT NULL,
    heartbeat_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    released_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_tel_active
    ON task_execution_leases(run_id, released_at);
"""


def create_execution_tables(engine_or_session: Any) -> None:
    if hasattr(engine_or_session, "begin"):
        with engine_or_session.begin() as conn:
            conn.execute(text(DDL_EXECUTION_LEASES))
    else:
        engine_or_session.connection().execute(text(DDL_EXECUTION_LEASES))


class PostgresExecutionLeaseStore:
    """PostgreSQL lease store。所有时间用 DB clock（func.now()）。"""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._sf = session_factory

    def _interval(self, ttl_seconds: float) -> Any:
        return text(f"make_interval(secs => {ttl_seconds})")

    def create(
        self, *, task_id, run_id, worker_id, execution_generation, ttl_seconds
    ) -> TaskExecutionLease:
        lease_id = uuid.uuid4().hex
        with self._sf() as s:
            row = s.execute(
                _LEASES.insert().values(
                    lease_id=lease_id, task_id=task_id, run_id=run_id,
                    worker_id=worker_id, execution_generation=execution_generation,
                    acquired_at=func.now(), heartbeat_at=func.now(),
                    expires_at=func.now() + self._interval(ttl_seconds),
                ).returning(_LEASES.c.lease_id, _LEASES.c.acquired_at, _LEASES.c.expires_at)
            ).one()
            s.commit()
        return TaskExecutionLease(
            lease_id=row[0], task_id=task_id, run_id=run_id, worker_id=worker_id,
            execution_generation=execution_generation, acquired_at=row[1],
            heartbeat_at=row[1], expires_at=row[2],
        )

    def heartbeat(self, lease_id: str, ttl_seconds: float) -> bool:
        with self._sf() as s:
            result = s.execute(
                update(_LEASES).where(
                    _LEASES.c.lease_id == lease_id, _LEASES.c.released_at.is_(None)
                ).values(
                    heartbeat_at=func.now(), expires_at=func.now() + self._interval(ttl_seconds)
                )
            )
            s.commit()
            return result.rowcount > 0

    def release(self, lease_id: str) -> None:
        with self._sf() as s:
            s.execute(
                update(_LEASES).where(_LEASES.c.lease_id == lease_id).values(released_at=func.now())
            )
            s.commit()

    def active_count(self) -> int:
        with self._sf() as s:
            return int(
                s.scalar(
                    select(func.count()).select_from(_LEASES).where(
                        _LEASES.c.released_at.is_(None), _LEASES.c.expires_at > func.now()
                    )
                )
                or 0
            )

    def get(self, lease_id: str) -> TaskExecutionLease | None:
        with self._sf() as s:
            row = s.execute(
                select(_LEASES).where(_LEASES.c.lease_id == lease_id)
            ).mappings().first()
        if row is None:
            return None
        return TaskExecutionLease(
            lease_id=row["lease_id"], task_id=row["task_id"], run_id=row["run_id"],
            worker_id=row["worker_id"], execution_generation=row["execution_generation"],
            acquired_at=row["acquired_at"], heartbeat_at=row["heartbeat_at"],
            expires_at=row["expires_at"], released_at=row["released_at"],
        )

    def list_expired(self) -> list[TaskExecutionLease]:
        with self._sf() as s:
            rows = s.execute(
                select(_LEASES).where(
                    _LEASES.c.released_at.is_(None), _LEASES.c.expires_at < func.now()
                )
            ).mappings().all()
        return [
            TaskExecutionLease(
                lease_id=r["lease_id"], task_id=r["task_id"], run_id=r["run_id"],
                worker_id=r["worker_id"], execution_generation=r["execution_generation"],
                acquired_at=r["acquired_at"], heartbeat_at=r["heartbeat_at"],
                expires_at=r["expires_at"], released_at=r["released_at"],
            )
            for r in rows
        ]


__all__ = [
    "DDL_EXECUTION_LEASES",
    "ExecutionLeaseStore",
    "InMemoryExecutionLeaseStore",
    "PostgresExecutionLeaseStore",
    "TaskExecutionLease",
    "create_execution_tables",
]
