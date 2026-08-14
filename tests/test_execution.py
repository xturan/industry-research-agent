"""G3 Execution Plane — 8 个核心测试（InMemory coordinator）。

覆盖：Active cap / 唯一 owner / heartbeat / crash recovery / fencing /
cancel recovery / retry exhaustion / no lease leak。
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

from packages.execution import (
    InMemoryExecutionCoordinator,
    InMemoryExecutionLeaseStore,
)


def _task(tid, run_id=None, status="queued", attempts=0, max_attempts=3, generation=0):
    return {
        "id": tid, "status": status, "task_type": "RESEARCH_ANALYZE",
        "payload_json": {"q": f"q{tid}"}, "attempt_count": attempts,
        "max_attempts": max_attempts, "source_run_id": run_id,
        "execution_generation": generation,
    }


def _run(rid, status="queued", cancel_requested_at=None):
    return {"id": rid, "status": status, "cancel_requested_at": cancel_requested_at,
            "output_json": None}


class _Clock:
    def __init__(self):
        self.now = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self):
        return self.now


# ── 1. Active cap ────────────────────────────────────────────────────────────

def test_active_cap():
    tasks = {i: _task(i, run_id=i) for i in range(1, 11)}
    runs = {i: _run(i) for i in range(1, 11)}
    coord = InMemoryExecutionCoordinator(InMemoryExecutionLeaseStore(), tasks=tasks, runs=runs)

    claimed = [coord.claim(f"w{i}", max_active_runs=3) for i in range(10)]
    ok = sum(1 for c in claimed if c is not None)
    assert ok == 3  # 最多 3 个真正运行
    assert coord.active_leases() == 3
    running = sum(1 for t in tasks.values() if t["status"] == "running")
    assert running == 3


# ── 2. 唯一 owner（20 并发 claim） ───────────────────────────────────────────

def test_no_duplicate_owner():
    tasks = {1: _task(1, run_id=1)}
    runs = {1: _run(1)}
    coord = InMemoryExecutionCoordinator(InMemoryExecutionLeaseStore(), tasks=tasks, runs=runs)
    results = []

    def _claim(i):
        c = coord.claim(f"w{i}", max_active_runs=10)
        results.append(1 if c is not None else 0)

    threads = [threading.Thread(target=_claim, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(results) == 1  # exactly one owner
    assert coord.active_leases() == 1


# ── 3. Heartbeat 延长 expires_at ─────────────────────────────────────────────

def test_heartbeat_extends_expiry():
    clock = _Clock()
    store = InMemoryExecutionLeaseStore(clock=clock)
    coord = InMemoryExecutionCoordinator(
        store, tasks={1: _task(1, run_id=1)}, runs={1: _run(1)}
    )
    claimed = coord.claim("w1", max_active_runs=5)
    assert claimed is not None
    before = store.get(claimed.lease_id).expires_at
    clock.now += timedelta(seconds=30)
    assert coord.heartbeat(claimed.lease_id, ttl_seconds=60) is True
    after = store.get(claimed.lease_id).expires_at
    assert after > before  # heartbeat 续租


# ── 4. Crash recovery：A 消失 → lease 过期 → B reclaim ──────────────────────

def test_crash_recovery_and_fencing():
    clock = _Clock()
    store = InMemoryExecutionLeaseStore(clock=clock)
    tasks = {1: _task(1, run_id=1, max_attempts=3)}
    runs = {1: _run(1)}
    coord = InMemoryExecutionCoordinator(store, tasks=tasks, runs=runs)

    a = coord.claim("wA", max_active_runs=5)
    assert a is not None and a.execution_generation == 1
    # A 崩溃（不 finalize）；lease 过期 → claim loop 先 recovery requeue，再 reclaim
    clock.now += timedelta(seconds=120)
    coord.recover_expired()
    b = coord.claim("wB", max_active_runs=5)  # reclaim
    assert b is not None and b.execution_generation == 2
    # A 复活尝试写回 → 被 fence
    assert coord.finalize(a, success=True, result_json={"report": "stale"}) is False
    # B 正常 finalize → 成功
    assert coord.finalize(b, success=True, result_json={"report": "ok"}) is True
    assert tasks[1]["status"] == "succeeded"
    assert runs[1]["status"] == "succeeded"
    assert runs[1]["output_json"] == {"report": "ok"}


# ── 5. Fencing（stale worker 不能发布结果） ─────────────────────────────────

def test_fencing_rejects_stale_finalize():
    clock = _Clock()
    store = InMemoryExecutionLeaseStore(clock=clock)
    tasks = {1: _task(1, run_id=1, max_attempts=3)}
    runs = {1: _run(1)}
    coord = InMemoryExecutionCoordinator(store, tasks=tasks, runs=runs)

    a = coord.claim("wA", max_active_runs=5)
    clock.now += timedelta(seconds=120)
    coord.recover_expired()
    b = coord.claim("wB", max_active_runs=5)
    assert a.execution_generation == 1 and b.execution_generation == 2
    # stale A 不能发布最终业务结果
    assert coord.finalize(a, success=True, result_json={"report": "stale"}) is False
    assert runs[1].get("output_json") is None  # A 的结果没被发布


# ── 6. Cancel recovery ───────────────────────────────────────────────────────

def test_cancel_recovery():
    clock = _Clock()
    store = InMemoryExecutionLeaseStore(clock=clock)
    tasks = {1: _task(1, run_id=1, max_attempts=3)}
    runs = {1: _run(1, cancel_requested_at=datetime(2026, 1, 1, tzinfo=UTC))}
    coord = InMemoryExecutionCoordinator(store, tasks=tasks, runs=runs)
    coord.claim("wA", max_active_runs=5)
    clock.now += timedelta(seconds=120)
    recs = coord.recover_expired()
    assert recs[0].action == "cancelled"  # cancel_requested → CANCELLED，不 requeue
    assert tasks[1]["status"] == "cancelled"
    assert runs[1]["status"] == "cancelled"


# ── 7. Retry exhaustion ──────────────────────────────────────────────────────

def test_retry_exhaustion():
    clock = _Clock()
    store = InMemoryExecutionLeaseStore(clock=clock)
    tasks = {1: _task(1, run_id=1, attempts=3, max_attempts=3)}
    runs = {1: _run(1)}
    coord = InMemoryExecutionCoordinator(store, tasks=tasks, runs=runs)
    coord.claim("wA", max_active_runs=5)  # attempt_count -> 4
    clock.now += timedelta(seconds=120)
    recs = coord.recover_expired()
    assert recs[0].action == "failed"  # attempts 耗尽 → FAILED
    assert recs[0].reason == "WORKER_EXECUTION_RETRY_EXHAUSTED"
    assert tasks[1]["status"] == "failed"
    assert runs[1]["status"] == "failed"


# ── 8. No lease leak / Run 生命周期保持 QUEUED→RUNNING→TERMINAL ────────────

def test_no_lease_leak_and_run_lifecycle():
    clock = _Clock()
    store = InMemoryExecutionLeaseStore(clock=clock)
    tasks = {1: _task(1, run_id=1, max_attempts=3)}
    runs = {1: _run(1)}
    coord = InMemoryExecutionCoordinator(store, tasks=tasks, runs=runs)
    assert runs[1]["status"] == "queued"
    claimed = coord.claim("w1", max_active_runs=5)
    assert runs[1]["status"] == "running"  # 首次 claim → RUNNING
    assert coord.finalize(claimed, success=True, result_json={"r": 1}) is True
    assert runs[1]["status"] == "succeeded"  # RUNNING → SUCCEEDED（不回退 QUEUED）
    assert coord.active_leases() == 0  # 无 lease 泄漏

    # 崩溃残留的过期 lease 也能被 recovery 清掉
    tasks[2] = _task(2, run_id=2, max_attempts=3)
    runs[2] = _run(2)
    coord.claim("w2", max_active_runs=5)
    clock.now += timedelta(seconds=120)
    coord.recover_expired()
    assert coord.active_leases() == 0  # 过期 lease 已清
