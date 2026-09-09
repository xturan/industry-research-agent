"""G4 Execution-Plane Load Acceptance（真实 PG，DB clock）。

在 G3 正确性验收之上，做 Execution Plane 的**高并发/持续负载**：

  E1 sustained_drain_load   200 tasks × 50 worker × cap5 → 持续 drain
                            max_observed==5、overshoot==0、全 succeeded；
                            worker 在 finalize 前 heartbeat（心跳负载）。
                            指标：drain 吞吐、claim p50/p95/p99。

  E2 recovery_storm         40 tasks 短 TTL，全部 claim 后集体过期，
                            8 线程并发 recover_expired → 每个 task 恰好恢复一次
                            （并发双处理 = 0）。回收后容量释放、可再 claim。

  E3 concurrent_fencing     30 tasks：claim(gen1) → 过期 → recover → claim(gen2)，
                            30 个 stale(gen1) 与 30 个 new(gen2) 并发 finalize →
                            stale 全部被拒、new 全部成功、无 stale artifact。

  E4 leak_check             leases 表清空、pool.checkedout()==0。

用法：
  GATEWAY_TEST_DATABASE_URL=postgresql+psycopg://... \
    python scripts/gateway_execution_load_acceptance.py
"""

from __future__ import annotations

import json
import os
import statistics
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

OUT_DIR = _REPO / "data" / "tmp" / "gateway_execution_load_acceptance"
DRAIN_TASKS = int(os.environ.get("G4E_DRAIN_TASKS", "200"))
DRAIN_WORKERS = int(os.environ.get("G4E_DRAIN_WORKERS", "50"))
DRAIN_CAP = int(os.environ.get("G4E_DRAIN_CAP", "5"))
STORM_TASKS = int(os.environ.get("G4E_STORM_TASKS", "40"))
STORM_RECOVER_THREADS = int(os.environ.get("G4E_STORM_RECOVER_THREADS", "8"))
FENCING_TASKS = int(os.environ.get("G4E_FENCING_TASKS", "30"))


def _pct(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    return round(float(statistics.quantiles(values, n=100, method="inclusive")[p - 1]), 3)


def _latency(times: list[float]) -> dict[str, float]:
    return {
        "count": len(times),
        "p50_ms": round(statistics.median(times) * 1000, 2),
        "p95_ms": round(_pct(times, 95) * 1000, 2),
        "p99_ms": round(_pct(times, 99) * 1000, 2),
        "max_ms": round(max(times) * 1000, 2),
    }


def _clean(sf) -> None:
    with sf() as s:
        s.execute(text("DELETE FROM task_execution_leases"))
        s.execute(text("DELETE FROM task_jobs"))
        s.execute(text("DELETE FROM runs"))
        s.commit()


def _seed_tasks(sf, n: int) -> None:
    with sf() as s:
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


def _count(sf, sql: str) -> int:
    with sf() as s:
        return int(s.execute(text(sql)).scalar() or 0)


# ── E1 sustained drain load ──────────────────────────────────────────────────

def e1_sustained_drain(sf, coord, *, workers: int, cap: int, total: int) -> dict:
    state = {"done": 0, "failed_finalize": 0, "lock": threading.Lock()}
    claim_times: list[float] = []
    max_observed = {"v": 0}
    stop = {"stop": False}

    def _observer() -> None:
        while not stop["stop"]:
            v = coord.active_leases()
            if v > max_observed["v"]:
                max_observed["v"] = v
            time.sleep(0.002)

    def _worker(wid: str) -> None:
        while state["done"] < total:
            t0 = time.perf_counter()
            claimed = coord.claim(wid, max_active_runs=cap)
            if claimed is None:
                time.sleep(0.005)
                continue
            claim_times.append(time.perf_counter() - t0)
            time.sleep(0.02)  # simulate a short piece of work
            coord.heartbeat(claimed.lease_id, ttl_seconds=2.0)  # heartbeat under load
            ok = coord.finalize(claimed, success=True, result_json={"wid": wid})
            with state["lock"]:
                state["done"] += 1
                if not ok:
                    state["failed_finalize"] += 1

    obs = threading.Thread(target=_observer, daemon=True)
    obs.start()
    t_wall0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_worker, f"w{i}") for i in range(workers)]
        for f in futures:
            f.result()
    t_wall = time.perf_counter() - t_wall0
    stop["stop"] = True
    obs.join(timeout=5)

    succeeded = _count(sf, "SELECT COUNT(*) FROM task_jobs WHERE status = 'succeeded'")
    active_after = coord.active_leases()
    overshoot = max_observed["v"] - cap
    ok = (
        succeeded == total
        and state["failed_finalize"] == 0
        and max_observed["v"] <= cap
        and active_after == 0
    )
    return {
        "PASS": ok,
        "workers": workers, "cap": cap, "total": total,
        "succeeded": succeeded,
        "failed_finalize": state["failed_finalize"],
        "max_observed_active_leases": max_observed["v"],
        "overshoot": overshoot,
        "active_leases_after": active_after,
        "drain_wall_seconds": round(t_wall, 3),
        "drain_throughput_tps": round(total / max(t_wall, 1e-9), 2),
        "claim_latency": _latency(claim_times),
    }


# ── E2 recovery storm ────────────────────────────────────────────────────────

def _force_expire(sf) -> None:
    """SQL 强制把所有活动 lease 置为已过期（DB clock），消除时序脆弱性。"""
    with sf() as s:
        s.execute(text(
            "UPDATE task_execution_leases SET expires_at = now() - interval '2 second' "
            "WHERE released_at IS NULL"
        ))
        s.commit()


def e2_recovery_storm(sf, coord, *, tasks: int, recover_threads: int) -> dict:
    _clean(sf)
    _seed_tasks(sf, tasks)
    claims = [coord.claim(f"claimer-{i}", max_active_runs=tasks) for i in range(tasks)]
    assert all(c is not None for c in claims), "should be able to claim all tasks"
    assert coord.active_leases() == tasks
    _force_expire(sf)  # 全部 lease 立刻过期（DB clock）

    recovered_lists = []
    lock = threading.Lock()

    def _recover() -> None:
        recs = coord.recover_expired()
        with lock:
            recovered_lists.append(recs)

    t_wall0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=recover_threads) as pool:
        futures = [pool.submit(_recover) for _ in range(recover_threads)]
        for f in futures:
            f.result()
    t_wall = time.perf_counter() - t_wall0

    all_recs = [r for lst in recovered_lists for r in lst]
    by_task: dict[int, list] = {}
    for r in all_recs:
        by_task.setdefault(r.task_id, []).append(r)
    duplicates = sum(1 for k, v in by_task.items() if len(v) > 1)
    actions = {r.action for r in all_recs}
    recovered_tasks = len(by_task)

    # 回收后容量释放，能重新 claim
    re = coord.claim("reclaimer", max_active_runs=2)
    reclaim_ok = re is not None
    if re is not None:
        coord.finalize(re, success=True, result_json={"ok": True})

    active_after = coord.active_leases()
    ok = (
        recovered_tasks == tasks
        and duplicates == 0
        and actions == {"requeued"}
        and reclaim_ok
        and active_after == 0
    )
    return {
        "PASS": ok,
        "tasks": tasks, "recover_threads": recover_threads,
        "recovered_tasks": recovered_tasks,
        "duplicate_recovered_tasks": duplicates,
        "actions": sorted(actions),
        "recover_wall_seconds": round(t_wall, 3),
        "reclaim_after_recovery": reclaim_ok,
        "active_leases_after": active_after,
    }


# ── E3 concurrent fencing storm ──────────────────────────────────────────────

def e3_concurrent_fencing(sf, coord, *, tasks: int) -> dict:
    _clean(sf)
    _seed_tasks(sf, tasks)
    stale = [coord.claim(f"stale-{i}", max_active_runs=tasks) for i in range(tasks)]
    assert all(c is not None and c.execution_generation == 1 for c in stale)
    _force_expire(sf)
    coord.recover_expired()  # requeue
    new = [coord.claim(f"new-{i}", max_active_runs=tasks) for i in range(tasks)]
    assert all(c is not None and c.execution_generation == 2 for c in new)

    stale_results = [False] * tasks
    new_results = [False] * tasks
    lock = threading.Lock()

    def _stale_finalize(i: int) -> None:
        ok = coord.finalize(stale[i], success=True, result_json={"stale": True})
        with lock:
            stale_results[i] = ok

    def _new_finalize(i: int) -> None:
        ok = coord.finalize(new[i], success=True, result_json={"fresh": True})
        with lock:
            new_results[i] = ok

    with ThreadPoolExecutor(max_workers=40) as pool:
        futs = [
            pool.submit(_stale_finalize, i) for i in range(tasks)
        ] + [pool.submit(_new_finalize, i) for i in range(tasks)]
        for f in futs:
            f.result()

    succeeded = _count(sf, "SELECT COUNT(*) FROM task_jobs WHERE status = 'succeeded'")
    # 没有任何 stale artifact 落库
    stale_artifacts = _count(
        sf,
        "SELECT COUNT(*) FROM task_jobs WHERE status = 'succeeded' "
        "AND result_json::text LIKE '%stale%'",
    )
    ok = (
        all(not r for r in stale_results)
        and all(r for r in new_results)
        and succeeded == tasks
        and stale_artifacts == 0
    )
    return {
        "PASS": ok,
        "tasks": tasks,
        "stale_rejected": sum(1 for r in stale_results if not r),
        "new_accepted": sum(1 for r in new_results if r),
        "succeeded": succeeded,
        "stale_artifact_publish": stale_artifacts,
    }


def e4_leak(sf, engine) -> dict:
    # lease 表是 append-only（已 release 的行保留）；只数「未释放」的孤儿 lease。
    leases = _count(
        sf, "SELECT COUNT(*) FROM task_execution_leases WHERE released_at IS NULL"
    )
    checkedout = engine.pool.checkedout()
    return {
        "PASS": leases == 0 and checkedout == 0,
        "orphan_leases": leases,
        "pool_checkedout": checkedout,
    }


def main() -> int:
    url = os.environ.get("GATEWAY_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url or "postgres" not in url:
        print("GATEWAY_TEST_DATABASE_URL (or DATABASE_URL) must point to PostgreSQL.")
        return 2
    engine = create_engine(url, pool_pre_ping=True, pool_size=80, max_overflow=0, pool_timeout=60)
    create_execution_tables(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE task_jobs ADD COLUMN IF NOT EXISTS "
            "execution_generation INT NOT NULL DEFAULT 0"
        ))
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    coord = PostgresExecutionCoordinator(sf, PostgresExecutionLeaseStore(sf), lease_ttl_seconds=2.0)

    _clean(sf)
    _seed_tasks(sf, DRAIN_TASKS)
    blocks: dict = {}
    blocks["sustained_drain_load"] = e1_sustained_drain(
        sf, coord, workers=DRAIN_WORKERS, cap=DRAIN_CAP, total=DRAIN_TASKS
    )
    print("E1 sustained_drain:", blocks["sustained_drain_load"]["PASS"],
          f"overshoot={blocks['sustained_drain_load']['overshoot']} "
          f"tps={blocks['sustained_drain_load']['drain_throughput_tps']}")

    blocks["recovery_storm"] = e2_recovery_storm(
        sf, coord, tasks=STORM_TASKS, recover_threads=STORM_RECOVER_THREADS
    )
    print("E2 recovery_storm:", blocks["recovery_storm"]["PASS"],
          f"dup={blocks['recovery_storm']['duplicate_recovered_tasks']}")

    blocks["concurrent_fencing"] = e3_concurrent_fencing(sf, coord, tasks=FENCING_TASKS)
    print("E3 concurrent_fencing:", blocks["concurrent_fencing"]["PASS"],
          f"stale_rejected={blocks['concurrent_fencing']['stale_rejected']} "
          f"stale_artifacts={blocks['concurrent_fencing']['stale_artifact_publish']}")

    blocks["leak_check"] = e4_leak(sf, engine)
    print("E4 leak:", blocks["leak_check"]["PASS"])

    all_pass = all(b["PASS"] for b in blocks.values())
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "g4_execution_plane_load": blocks,
        "status": "PASS" if all_pass else "FAIL",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "execution_load_acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nG4 Execution-plane Load {'PASS' if all_pass else 'FAIL'} -> {OUT_DIR}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
