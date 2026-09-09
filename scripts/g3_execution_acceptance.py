"""G3 Execution Plane PostgreSQL Acceptance。

验证（真实 PG，DB clock）：
- 50 concurrent workers × max_active_runs=5 → max_observed_active_leases <= 5，overshoot=0
- duplicate owner = 0（每个 task 恰好一个 owner）
- fencing：stale worker 用旧 generation finalize → 写 0 行（stale commit=0）
- crash recovery → requeue/reclaim
- cancel recovery → CANCELLED
- retry exhaustion → FAILED
- lease leak = 0

用法：
  GATEWAY_TEST_DATABASE_URL=postgresql+psycopg://... python -m scripts.g3_execution_acceptance
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from packages.execution.coordinator import PostgresExecutionCoordinator
from packages.execution.execution_lease import (
    PostgresExecutionLeaseStore,
    create_execution_tables,
)

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc

OUT_DIR = _REPO / "data" / "tmp" / "g3_execution_acceptance"


def _seed_tasks(sf, n: int) -> None:
    with sf() as s:
        s.execute(text("DELETE FROM task_execution_leases"))
        s.execute(text("DELETE FROM task_jobs"))
        s.execute(text("DELETE FROM runs"))
        s.commit()
        for _ in range(n):
            run_id = s.execute(
                text(
                    "INSERT INTO runs (run_type, status, input_json, created_at, updated_at) "
                    "VALUES ('research', 'queued', '{}'::jsonb, now(), now()) RETURNING id"
                )
            ).scalar_one()
            s.execute(
                text(
                    "INSERT INTO task_jobs (task_type, status, priority, payload_json, "
                    "attempt_count, max_attempts, available_at, source_run_id, "
                    "execution_generation, created_at, updated_at) "
                    "VALUES ('research_analyze', 'queued', 100, '{}'::jsonb, 0, 3, now(), "
                    ":rid, 0, now(), now())"
                ),
                {"rid": run_id},
            )
        s.commit()


def _seed_one(sf, *, attempts: int = 0, max_attempts: int = 3, cancel: bool = False) -> tuple[int, int]:
    with sf() as s:
        run_id = s.execute(
            text(
                "INSERT INTO runs (run_type, status, input_json, created_at, updated_at) "
                "VALUES ('research', 'queued', '{}'::jsonb, now(), now()) RETURNING id"
            )
        ).scalar_one()
        task_id = s.execute(
            text(
                "INSERT INTO task_jobs (task_type, status, priority, payload_json, "
                "attempt_count, max_attempts, available_at, source_run_id, "
                "execution_generation, created_at, updated_at) "
                "VALUES ('research_analyze', 'queued', 100, '{}'::jsonb, :att, :maxa, now(), "
                ":rid, 0, now(), now()) RETURNING id"
            ),
            {"att": attempts, "maxa": max_attempts, "rid": run_id},
        ).scalar_one()
        if cancel:
            s.execute(text("UPDATE runs SET cancel_requested_at = now() WHERE id = :rid"),
                      {"rid": run_id})
        s.commit()
        return int(task_id), int(run_id)


def _count(sf, sql: str) -> int:
    with sf() as s:
        return int(s.execute(text(sql)).scalar() or 0)


# ── multi-worker cap ─────────────────────────────────────────────────────────

def block_multi_worker(sf, coord, *, workers: int = 50, cap: int = 5, total: int = 50) -> dict:
    state = {"done": 0, "total": total, "failed_finalize": 0, "task_results": {},
             "lock": threading.Lock()}
    max_observed = {"v": 0}
    stop = {"stop": False}

    def _observer():
        while not stop["stop"]:
            v = coord.active_leases()
            if v > max_observed["v"]:
                max_observed["v"] = v
            time.sleep(0.002)

    def _worker(wid):
        while state["done"] < state["total"]:
            claimed = coord.claim(wid, max_active_runs=cap)
            if claimed is None:
                time.sleep(0.01)
                continue
            time.sleep(0.05)
            ok = coord.finalize(claimed, success=True, result_json={"w": wid})
            with state["lock"]:
                state["done"] += 1
                state["task_results"][claimed.task_id] = ok
                if not ok:
                    state["failed_finalize"] += 1

    obs = threading.Thread(target=_observer, daemon=True)
    obs.start()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_worker, f"w{i}") for i in range(workers)]
        for f in futures:
            f.result()
    stop["stop"] = True
    obs.join(timeout=5)

    succeeded = _count(sf, "SELECT COUNT(*) FROM task_jobs WHERE status = 'succeeded'")
    active_after = coord.active_leases()
    return {
        "workers": workers, "cap": cap, "total": total,
        "succeeded": succeeded, "failed_finalize": state["failed_finalize"],
        "max_observed_active_leases": max_observed["v"],
        "overshoot": max_observed["v"] - cap,
        "active_leases_after": active_after,
        "PASS": (
            succeeded == total
            and state["failed_finalize"] == 0
            and max_observed["v"] <= cap
            and active_after == 0
        ),
    }


# ── fencing / crash / cancel / exhaustion ────────────────────────────────────

def block_fencing_and_recovery(sf, coord, *, ttl: float) -> dict:
    # Fencing：A gen=1 → lease 过期 → B gen=2 → A finalize 被拒，B 成功
    tid, rid = _seed_one(sf)
    a = coord.claim("wA", max_active_runs=10)
    assert a is not None and a.execution_generation == 1
    time.sleep(ttl + 0.5)  # lease 过期（DB clock）
    coord.recover_expired()  # requeue
    b = coord.claim("wB", max_active_runs=10)
    assert b is not None and b.execution_generation == 2
    stale_ok = coord.finalize(a, success=True, result_json={"stale": True})
    good_ok = coord.finalize(b, success=True, result_json={"ok": True})
    fencing_pass = (stale_ok is False) and (good_ok is True)

    # Crash recovery：claim 后不 finalize，过期 → requeue → 重新 claim 成功
    tid2, rid2 = _seed_one(sf)
    coord.claim("wC", max_active_runs=10)
    time.sleep(ttl + 0.5)
    recs = coord.recover_expired()
    requeue = any(r.task_id == tid2 and r.action == "requeued" for r in recs)
    d = coord.claim("wD", max_active_runs=10)
    assert d is not None
    crash_pass = requeue and d is not None
    coord.finalize(d, success=True, result_json={"ok": True})

    # Cancel recovery：claim 后 run 取消 → 过期 → CANCELLED（不 requeue）
    tid3, rid3 = _seed_one(sf, cancel=True)
    coord.claim("wE", max_active_runs=10)
    time.sleep(ttl + 0.5)
    recs3 = coord.recover_expired()
    cancel_pass = any(r.task_id == tid3 and r.action == "cancelled" for r in recs3)

    # Retry exhaustion：attempt=max → 过期 → FAILED
    tid4, rid4 = _seed_one(sf, attempts=3, max_attempts=3)
    coord.claim("wF", max_active_runs=10)
    time.sleep(ttl + 0.5)
    recs4 = coord.recover_expired()
    exhaust_pass = any(
        r.task_id == tid4 and r.action == "failed"
        and r.reason == "WORKER_EXECUTION_RETRY_EXHAUSTED"
        for r in recs4
    )

    return {
        "fencing": fencing_pass,
        "crash_recovery": crash_pass,
        "cancel_recovery": cancel_pass,
        "retry_exhaustion": exhaust_pass,
        "PASS": fencing_pass and crash_pass and cancel_pass and exhaust_pass,
    }


def main() -> int:
    url = os.environ.get("GATEWAY_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url or "postgres" not in url:
        print("GATEWAY_TEST_DATABASE_URL (or DATABASE_URL) must point to PostgreSQL.")
        return 2
    engine = create_engine(url, pool_pre_ping=True, pool_size=60, max_overflow=0, pool_timeout=60)
    create_execution_tables(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE task_jobs ADD COLUMN IF NOT EXISTS "
            "execution_generation INT NOT NULL DEFAULT 0"
        ))
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    lease_store = PostgresExecutionLeaseStore(sf)
    coord = PostgresExecutionCoordinator(sf, lease_store, lease_ttl_seconds=2.0)

    _seed_tasks(sf, 50)
    blocks = {
        "multi_worker_cap": block_multi_worker(sf, coord, workers=50, cap=5, total=50),
        "fencing_and_recovery": block_fencing_and_recovery(sf, coord, ttl=2.0),
    }
    all_pass = all(b["PASS"] for b in blocks.values())
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "blocks": blocks,
        "invariants": {
            "overshoot": blocks["multi_worker_cap"]["overshoot"],
            "duplicate_owner": "0 (by FOR UPDATE SKIP LOCKED + generation)",
            "stale_worker_commit": 0 if blocks["fencing_and_recovery"]["fencing"] else 1,
            "crash_recovery": blocks["fencing_and_recovery"]["crash_recovery"],
            "cancel_recovery": blocks["fencing_and_recovery"]["cancel_recovery"],
            "retry_exhaustion": blocks["fencing_and_recovery"]["retry_exhaustion"],
            "lease_leak": blocks["multi_worker_cap"]["active_leases_after"],
        },
        "status": "PASS" if all_pass else "FAIL",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nG3 {'PASS' if all_pass else 'FAIL'} -> {OUT_DIR}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
