"""G3 ExecutionCoordinator — 增强现有 Persistent Task + Worker（不新建 Queue）。

能力：
- **Global Active Run Capacity**：active 数量以 non-expired lease 为准（跨进程）。
- **Claim = 短原子事务**：capacity check → claim queued task（SKIP LOCKED）→
  execution_generation += 1 → 创建 lease → Task RUNNING → Run 首次 RUNNING → commit。
  **Agent 长任务期间不持 DB transaction/connection。**
- **Heartbeat**：独立续租（DB clock）。
- **Fencing**：finalize 用 `execution_generation` 条件 UPDATE；stale worker 写 0 行。
- **Crash recovery**：expired lease → cancel_requested→CANCELLED /
  attempts 剩余→requeue / attempts 耗尽→FAILED。
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc


@dataclass
class ClaimedExecution:
    lease_id: str
    task_id: int
    run_id: int | None
    worker_id: str
    execution_generation: int
    task_type: str
    payload_json: dict[str, Any]
    max_attempts: int
    attempt_count: int


@dataclass
class RecoveryResult:
    task_id: int
    run_id: int | None
    action: str  # cancelled | requeued | failed
    reason: str


class ExecutionCoordinator(Protocol):
    def claim(self, worker_id: str, *, max_active_runs: int) -> ClaimedExecution | None: ...
    def heartbeat(self, lease_id: str, ttl_seconds: float) -> bool: ...
    def finalize(self, claimed: ClaimedExecution, *, success: bool,
                 result_json: dict[str, Any] | None = None, error: str | None = None) -> bool: ...
    def recover_expired(self) -> list[RecoveryResult]: ...
    def active_leases(self) -> int: ...


# ── InMemory（G3 单进程语义验证 + 8 核心测试） ────────────────────────────────

class InMemoryExecutionCoordinator:
    def __init__(self, lease_store: Any, *, tasks: dict[int, dict] | None = None,
                 runs: dict[int, dict] | None = None, lease_ttl_seconds: float = 60.0) -> None:
        self._lease = lease_store
        self._tasks = tasks if tasks is not None else {}
        self._runs = runs if runs is not None else {}
        self._lock = threading.Lock()
        self._ttl = lease_ttl_seconds

    def _run(self, run_id: int | None) -> dict | None:
        return self._runs.get(run_id) if run_id is not None else None

    def claim(self, worker_id: str, *, max_active_runs: int) -> ClaimedExecution | None:
        with self._lock:
            if self._lease.active_count() >= max_active_runs:
                return None
            task_id = next(
                (tid for tid, t in self._tasks.items()
                 if t["status"] == "queued"),
                None,
            )
            if task_id is None:
                return None
            task = self._tasks[task_id]
            task["execution_generation"] = int(task.get("execution_generation", 0)) + 1
            task["attempt_count"] = int(task.get("attempt_count", 0)) + 1
            task["status"] = "running"
            task["locked_by"] = worker_id
            lease = self._lease.create(
                task_id=task_id, run_id=task.get("source_run_id"), worker_id=worker_id,
                execution_generation=task["execution_generation"],
                ttl_seconds=self._ttl,
            )
            run = self._run(task.get("source_run_id"))
            if run is not None and run.get("status") == "queued":
                run["status"] = "running"
            return ClaimedExecution(
                lease_id=lease.lease_id, task_id=task_id, run_id=task.get("source_run_id"),
                worker_id=worker_id, execution_generation=task["execution_generation"],
                task_type=task["task_type"], payload_json=dict(task.get("payload_json") or {}),
                max_attempts=int(task.get("max_attempts", 3)),
                attempt_count=int(task.get("attempt_count", 0)),
            )

    def heartbeat(self, lease_id: str, ttl_seconds: float) -> bool:
        return self._lease.heartbeat(lease_id, ttl_seconds)

    def finalize(self, claimed: ClaimedExecution, *, success: bool,
                 result_json: dict[str, Any] | None = None, error: str | None = None) -> bool:
        with self._lock:
            task = self._tasks.get(claimed.task_id)
            if task is None or (
                int(task.get("execution_generation", 0)) != claimed.execution_generation
            ):
                return False  # fencing：stale worker 失去所有权
            task["status"] = "succeeded" if success else "failed"
            task["result_json"] = result_json
            task["error_message"] = error
            self._lease.release(claimed.lease_id)
            run = self._run(claimed.run_id)
            if run is not None:
                run["status"] = "succeeded" if success else "failed"
                if success and result_json is not None:
                    run["output_json"] = dict(result_json)
            return True

    def recover_expired(self) -> list[RecoveryResult]:
        results: list[RecoveryResult] = []
        with self._lock:
            for lease in self._lease.list_expired():
                task = self._tasks.get(lease.task_id)
                if task is None or task.get("status") != "running":
                    self._lease.release(lease.lease_id)
                    continue
                run = self._run(lease.run_id)
                if run is not None and run.get("cancel_requested_at"):
                    task["status"] = "cancelled"
                    run["status"] = "cancelled"
                    results.append(RecoveryResult(
                        task["id"], lease.run_id, "cancelled", "cancel_requested",
                    ))
                elif int(task.get("attempt_count", 0)) >= int(task.get("max_attempts", 3)):
                    task["status"] = "failed"
                    if run is not None:
                        run["status"] = "failed"
                    results.append(RecoveryResult(
                        task["id"], lease.run_id, "failed",
                        "WORKER_EXECUTION_RETRY_EXHAUSTED",
                    ))
                else:
                    task["status"] = "queued"  # 下个 claim 会 bump generation
                    results.append(RecoveryResult(
                        task["id"], lease.run_id, "requeued", "lease_expired",
                    ))
                self._lease.release(lease.lease_id)
        return results

    def active_leases(self) -> int:
        return self._lease.active_count()


# ── PostgreSQL（production，DB clock） ───────────────────────────────────────

class PostgresExecutionCoordinator:
    def __init__(self, session_factory: Any, lease_store: Any,
                 *, lease_ttl_seconds: float = 60.0) -> None:
        self._sf = session_factory
        self._lease = lease_store
        self._ttl = lease_ttl_seconds

    def claim(self, worker_id: str, *, max_active_runs: int) -> ClaimedExecution | None:
        import uuid as _uuid

        from sqlalchemy import text as _text

        # 快速路径（非原子，仅减少无效事务）
        if self._lease.active_count() >= max_active_runs:
            return None
        lease_id = _uuid.uuid4().hex
        with self._sf() as s:
            # 全局串行化 claim：capacity 检查 + claim + lease 创建必须在同一短事务，
            # 否则并发 worker 会同时通过检查 → overshoot。
            s.execute(_text("SELECT pg_advisory_xact_lock(71400001)"))
            active = int(
                s.execute(
                    _text(
                        "SELECT COUNT(*) FROM task_execution_leases "
                        "WHERE released_at IS NULL AND expires_at > now()"
                    )
                ).scalar()
                or 0
            )
            if active >= max_active_runs:
                s.rollback()
                return None
            row = s.execute(
                _text(
                    "SELECT id, task_type, payload_json, source_run_id, "
                    "attempt_count, max_attempts "
                    "FROM task_jobs WHERE status = 'queued' "
                    "AND available_at <= now() ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED"
                )
            ).fetchone()
            if row is None:
                s.rollback()
                return None
            task_id, task_type, payload_json, run_id, attempt_count, max_attempts = row
            # generation += 1（fencing token）
            new_gen = s.execute(
                _text(
                    "UPDATE task_jobs SET execution_generation = execution_generation + 1, "
                    "attempt_count = attempt_count + 1, status = 'running', locked_by = :wid "
                    "WHERE id = :tid RETURNING execution_generation"
                ),
                {"wid": worker_id, "tid": task_id},
            ).scalar_one()
            # 创建 lease（同一 session/事务内）
            s.execute(
                _text(
                    "INSERT INTO task_execution_leases "
                    "(lease_id, task_id, run_id, worker_id, execution_generation, "
                    " acquired_at, heartbeat_at, expires_at) "
                    "VALUES (:lid, :tid, :rid, :wid, :gen, now(), now(), "
                    " now() + make_interval(secs => :ttl))"
                ),
                {
                    "lid": lease_id, "tid": task_id, "rid": run_id,
                    "wid": worker_id, "gen": int(new_gen), "ttl": self._ttl,
                },
            )
            # Run 首次 RUNNING（QUEUED → RUNNING）
            if run_id is not None:
                s.execute(
                    _text(
                        "UPDATE runs SET status = 'running' "
                        "WHERE id = :rid AND status = 'queued'"
                    ),
                    {"rid": run_id},
                )
            s.commit()
        return ClaimedExecution(
            lease_id=lease_id, task_id=task_id, run_id=run_id, worker_id=worker_id,
            execution_generation=int(new_gen), task_type=task_type,
            payload_json=dict(payload_json or {}), max_attempts=int(max_attempts),
            attempt_count=int(attempt_count) + 1,
        )

    def heartbeat(self, lease_id: str, ttl_seconds: float) -> bool:
        return self._lease.heartbeat(lease_id, ttl_seconds)

    def finalize(self, claimed: ClaimedExecution, *, success: bool,
                 result_json: dict[str, Any] | None = None, error: str | None = None) -> bool:
        from sqlalchemy import text as _text

        with self._sf() as s:
            rows = s.execute(
                _text(
                    "UPDATE task_jobs SET status = :st, "
                    "result_json = CAST(:rj AS jsonb), error_message = :err, locked_by = NULL "
                    "WHERE id = :tid AND execution_generation = :gen"
                ),
                {
                    "st": "succeeded" if success else "failed",
                    "rj": json.dumps(result_json) if result_json is not None else None,
                    "err": error,
                    "tid": claimed.task_id, "gen": claimed.execution_generation,
                },
            ).rowcount
            if rows == 0:
                s.rollback()
                return False  # fencing：stale worker 写 0 行
            if claimed.run_id is not None:
                if success:
                    s.execute(
                        _text(
                            "UPDATE runs SET status = 'succeeded', "
                            "output_json = CAST(:oj AS jsonb), "
                            "finished_at = now() WHERE id = :rid"
                        ),
                        {
                            "oj": json.dumps(result_json) if result_json is not None else None,
                            "rid": claimed.run_id,
                        },
                    )
                else:
                    s.execute(
                        _text(
                            "UPDATE runs SET status = 'failed', "
                            "output_json = jsonb_build_object('error', :err), "
                            "finished_at = now() WHERE id = :rid"
                        ),
                        {"err": error, "rid": claimed.run_id},
                    )
            s.commit()
        self._lease.release(claimed.lease_id)
        return True

    def recover_expired(self) -> list[RecoveryResult]:
        """Recover expired leases. Concurrency-safe: the state transition uses a
        conditional UPDATE (`WHERE status='running'`) so that under a recovery
        storm exactly one worker wins per task (rowcount 1); losers rollback and
        just release the lease — no double recovery."""
        from sqlalchemy import text as _text

        results: list[RecoveryResult] = []
        for lease in self._lease.list_expired():
            with self._sf() as s:
                task = s.execute(
                    _text(
                        "SELECT attempt_count, max_attempts, source_run_id "
                        "FROM task_jobs WHERE id = :tid"
                    ),
                    {"tid": lease.task_id},
                ).fetchone()
                if task is None:
                    s.rollback()
                    self._lease.release(lease.lease_id)
                    continue
                run = s.execute(
                    _text(
                        "SELECT cancel_requested_at FROM runs WHERE id = :rid"
                    ),
                    {"rid": lease.run_id},
                ).fetchone() if lease.run_id else None
                cancel_requested = bool(run is not None and run[0] is not None)
                attempt_count, max_attempts = int(task[0]), int(task[1])
                if cancel_requested:
                    rows = s.execute(
                        _text(
                            "UPDATE task_jobs SET status = 'cancelled' "
                            "WHERE id = :tid AND status = 'running'"
                        ),
                        {"tid": lease.task_id},
                    ).rowcount
                    if not rows:
                        s.rollback()
                        self._lease.release(lease.lease_id)
                        continue
                    if lease.run_id:
                        s.execute(
                            _text(
                                "UPDATE runs SET status = 'cancelled', finished_at = now() "
                                "WHERE id = :rid AND status IN ('queued', 'running')"
                            ),
                            {"rid": lease.run_id},
                        )
                    s.commit()
                    results.append(RecoveryResult(
                        lease.task_id, lease.run_id, "cancelled", "cancel_requested",
                    ))
                elif attempt_count >= max_attempts:
                    rows = s.execute(
                        _text(
                            "UPDATE task_jobs SET status = 'failed', "
                            "error_message = 'WORKER_EXECUTION_RETRY_EXHAUSTED' "
                            "WHERE id = :tid AND status = 'running'"
                        ),
                        {"tid": lease.task_id},
                    ).rowcount
                    if not rows:
                        s.rollback()
                        self._lease.release(lease.lease_id)
                        continue
                    if lease.run_id:
                        s.execute(
                            _text(
                                "UPDATE runs SET status = 'failed', "
                                "output_json = jsonb_build_object('error', "
                                "'WORKER_EXECUTION_RETRY_EXHAUSTED'), finished_at = now() "
                                "WHERE id = :rid AND status IN ('queued', 'running')"
                            ),
                            {"rid": lease.run_id},
                        )
                    s.commit()
                    results.append(RecoveryResult(
                        lease.task_id, lease.run_id, "failed",
                        "WORKER_EXECUTION_RETRY_EXHAUSTED",
                    ))
                else:
                    rows = s.execute(
                        _text(
                            "UPDATE task_jobs SET status = 'queued' "
                            "WHERE id = :tid AND status = 'running'"
                        ),
                        {"tid": lease.task_id},
                    ).rowcount
                    if not rows:
                        s.rollback()
                        self._lease.release(lease.lease_id)
                        continue
                    s.commit()
                    results.append(RecoveryResult(
                        lease.task_id, lease.run_id, "requeued", "lease_expired",
                    ))
            self._lease.release(lease.lease_id)
        return results

    def active_leases(self) -> int:
        return self._lease.active_count()


__all__ = [
    "ClaimedExecution",
    "ExecutionCoordinator",
    "InMemoryExecutionCoordinator",
    "PostgresExecutionCoordinator",
    "RecoveryResult",
]
