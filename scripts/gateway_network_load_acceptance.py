"""G4 Network-Layer Load Acceptance（真实 HTTP + 真实 PostgreSQL）。

范围：只打 **network layer** —— FastAPI `/v1/research/runs` 控制面在并发下的
行为：admission 边界、幂等并发去重、GET/events 读放大、cancel 突发、
容量回收、连接池健康与泄漏。不执行研究（G3 worker / provider 已有独立验收）。

做法：脚本拉起 uvicorn 子进程（独立测试库 + 小 admission cap），用 httpx async
并发打真实 socket。输出 `data/tmp/gateway_network_load_acceptance/`。

场景：
  S1 solo baseline        1 POST → 202，GET → queued，量延迟
  S2 burst submission     cap=40，60 并发 POST → 恰好 40×202 / 20×503，无 5xx
  S3 idempotency replay   同 key 20 并发 POST → 恰好 1 run，全 202 同 run_id
  S4 poll storm           40 run_ids × 5 并发 GET /runs/{id}+/events → 全 200
  S5 cancel burst         10 并发 cancel QUEUED → 全 200，capacity -10
  S6 capacity reclaim     cap=40，当前 queued=30 → 15 并发 → 恰好 10×202 / 5×503
  S7 leak & integrity     pool.checkedout()==0，无孤儿 lease，幂等无重复

PASS 条件：
  - 无 5xx / 连接超时 / session 泄漏
  - admission 精确守界（accepted==cap，rejected==burst-cap）
  - 幂等并发 exactly-once
  - poll/cancel 100% 成功
  - S6 回收后边界仍精确
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from packages.db.base import Base
from packages.execution.execution_lease import create_execution_tables

OUT_DIR = _REPO / "data" / "tmp" / "gateway_network_load_acceptance"
PORT = int(os.environ.get("GATEWAY_LOAD_PORT", "8101"))
ADMISSION_CAP = int(os.environ.get("GATEWAY_LOAD_ADMISSION_CAP", "40"))
BURST_N = int(os.environ.get("GATEWAY_LOAD_BURST_N", "60"))


def _db_url() -> str:
    url = os.environ.get("GATEWAY_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url or "postgres" not in url:
        raise SystemExit(
            "GATEWAY_TEST_DATABASE_URL (or DATABASE_URL) must point to PostgreSQL."
        )
    return url


def _clean(engine, sf) -> None:
    with sf() as s:
        s.execute(text("DELETE FROM task_execution_leases"))
        s.execute(text("DELETE FROM task_jobs"))
        s.execute(text("DELETE FROM run_events"))
        s.execute(text("DELETE FROM runs"))
        s.commit()


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    return round(float(statistics.quantiles(values, n=100, method="inclusive")[int(p) - 1]), 3)


def _latency_metrics(times: list[float], *, wall_seconds: float | None = None) -> dict[str, float]:
    wall = wall_seconds if wall_seconds is not None else max(sum(times), 1e-9)
    return {
        "count": len(times),
        "p50_ms": round(statistics.median(times) * 1000, 2),
        "p95_ms": round(_pct(times, 95) * 1000, 2),
        "p99_ms": round(_pct(times, 99) * 1000, 2),
        "max_ms": round(max(times) * 1000, 2),
        "wall_seconds": round(wall, 3),
        "throughput_rps": round(len(times) / max(wall, 1e-9), 2),
    }


def _payload(query: str) -> dict[str, Any]:
    return {"request": {"query": query, "research_strategy": "deep"}}


# ── DB connection sampler (side-channel, observes app->DB pool pressure) ─────

class _ConnSampler:
    def __init__(self, url: str) -> None:
        self._url = url
        self._stop = threading.Event()
        self.max_connections = 0
        self.samples = 0

    def _run(self) -> None:
        try:
            eng = create_engine(self._url, pool_size=1, max_overflow=0)
        except Exception:
            return
        while not self._stop.is_set():
            try:
                with eng.connect() as c:
                    n = c.execute(
                        text(
                            "SELECT count(*) FROM pg_stat_activity "
                            "WHERE datname = current_database()"
                        )
                    ).scalar() or 0
                self.max_connections = max(self.max_connections, int(n))
                self.samples += 1
            except Exception:
                pass
            self._stop.wait(0.05)
        eng.dispose()

    def start(self) -> None:
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        self._thread = t

    def stop(self) -> None:
        self._stop.set()
        if hasattr(self, "_thread"):
            self._thread.join(timeout=3)


# ── scenarios ────────────────────────────────────────────────────────────────

async def _solo_baseline(client: httpx.AsyncClient, sf) -> dict[str, Any]:
    t0 = time.perf_counter()
    r = await client.post("/v1/research/runs", json=_payload("S1 基线研究"))
    submit_ms = (time.perf_counter() - t0) * 1000
    body = r.json()
    run_id = body.get("run_id")
    t1 = time.perf_counter()
    g = await client.get(f"/v1/research/runs/{run_id}")
    get_ms = (time.perf_counter() - t1) * 1000
    with sf() as s:
        status = s.execute(
            text("SELECT status FROM runs WHERE id = :rid"), {"rid": run_id}
        ).scalar()
    # cancel the solo run to leave admission empty for S2
    c = await client.post(f"/v1/research/runs/{run_id}/cancel")
    cancel_body = c.json()
    cancel_completed = bool((cancel_body.get("cancellation") or {}).get("completed"))
    ok = (
        r.status_code == 202 and g.status_code == 200 and status == "queued"
        and c.status_code == 200 and cancel_completed
    )
    return {
        "PASS": ok,
        "submit_status": r.status_code,
        "get_status": g.status_code,
        "submit_ms": round(submit_ms, 2),
        "get_ms": round(get_ms, 2),
        "cancel_completed": cancel_completed,
        "run_status": status,
    }


async def _burst_submission(client, sf, sampler) -> dict[str, Any]:
    sampler.start()
    async def _one(i: int) -> tuple[int, float, dict[str, Any]]:
        t0 = time.perf_counter()
        r = await client.post(
            "/v1/research/runs",
            json=_payload(f"S2 并发压测 query {i}"),
            headers={"Idempotency-Key": f"load-burst-{i}"},
        )
        return r.status_code, time.perf_counter() - t0, r.json()

    t_wall0 = time.perf_counter()
    results = await asyncio.gather(*[_one(i) for i in range(BURST_N)])
    t_wall = time.perf_counter() - t_wall0
    sampler.stop()
    codes = [c for c, _, _ in results]
    accepted = [b for c, _, b in results if c == 202]
    times = [t for _, t, _ in results]
    run_ids = [b.get("run_id") for b in accepted]
    with sf() as s:
        queued = s.execute(
            text("SELECT count(*) FROM runs WHERE status = 'queued'")
        ).scalar() or 0
    # 503 is the *expected* admission rejection (queue full); only flag true
    # server errors (500/502/504) as failures.
    ok = (
        codes.count(202) == ADMISSION_CAP
        and codes.count(503) == BURST_N - ADMISSION_CAP
        and not any(c in (500, 501, 502, 504) for c in codes)
        and queued == ADMISSION_CAP
        and len(set(run_ids)) == ADMISSION_CAP
    )
    return {
        "PASS": ok,
        "burst_n": BURST_N,
        "cap": ADMISSION_CAP,
        "accepted_202": codes.count(202),
        "rejected_503": codes.count(503),
        "unexpected_status": {c: codes.count(c) for c in set(codes) if c not in (202, 503)},
        "db_queued": queued,
        "peak_db_connections": sampler.max_connections,
        "latency": _latency_metrics(times, wall_seconds=t_wall),
        "run_ids": run_ids,
    }


async def _idempotency_replay(client, sf) -> dict[str, Any]:
    async def _one() -> tuple[int, dict[str, Any]]:
        r = await client.post(
            "/v1/research/runs",
            json=_payload("S3 幂等并发同一请求"),
            headers={"Idempotency-Key": "load-idem-same"},
        )
        return r.status_code, r.json()

    results = await asyncio.gather(*[_one() for _ in range(20)])
    codes = [c for c, _ in results]
    bodies = [b for _, b in results]
    run_ids = {b.get("run_id") for b in bodies}
    replayed_true = sum(1 for b in bodies if (b.get("idempotency") or {}).get("replayed") is True)
    replayed_false = sum(1 for b in bodies if (b.get("idempotency") or {}).get("replayed") is False)
    with sf() as s:
        rows = s.execute(
            text(
                "SELECT idempotency_key FROM runs "
                "WHERE idempotency_key = 'load-idem-same'"
            )
        ).fetchall()
    ok = (
        len(codes) == 20
        and all(c == 202 for c in codes)
        and len(run_ids) == 1
        and replayed_true == 19
        and replayed_false == 1
        and len(rows) == 1
    )
    return {
        "PASS": ok,
        "responses": len(codes),
        "distinct_run_ids": len(run_ids),
        "run_id": next(iter(run_ids), None),
        "replayed_true": replayed_true,
        "replayed_false": replayed_false,
        "db_rows_with_key": len(rows),
    }


async def _poll_storm(client, run_ids: list[int]) -> dict[str, Any]:
    ids = list(run_ids)
    async def _one(idx: int) -> tuple[int, float, str]:
        rid = ids[idx % len(ids)]
        kind = "/events" if idx % 4 == 0 else ""
        t0 = time.perf_counter()
        r = await client.get(f"/v1/research/runs/{rid}{kind}")
        return r.status_code, time.perf_counter() - t0, kind or "/runs"

    total = len(ids) * 5
    t_wall0 = time.perf_counter()
    results = await asyncio.gather(*[_one(i) for i in range(total)])
    t_wall = time.perf_counter() - t_wall0
    codes = [c for c, _, _ in results]
    times = [t for _, t, _ in results]
    ok = len(codes) == total and all(c == 200 for c in codes)
    return {
        "PASS": ok,
        "requests": total,
        "all_200": all(c == 200 for c in codes),
        "status_counts": {c: codes.count(c) for c in set(codes)},
        "latency": _latency_metrics(times, wall_seconds=t_wall),
    }


async def _cancel_burst(client, run_ids: list[int]) -> dict[str, Any]:
    ids = run_ids[:10]
    async def _one(rid: int) -> tuple[int, dict[str, Any]]:
        r = await client.post(f"/v1/research/runs/{rid}/cancel")
        return r.status_code, r.json()

    results = await asyncio.gather(*[_one(rid) for rid in ids])
    codes = [c for c, _ in results]
    bodies = [b for _, b in results]
    completed = sum(1 for b in bodies if (b.get("cancellation") or {}).get("completed") is True)
    requested = sum(1 for b in bodies if (b.get("cancellation") or {}).get("requested") is True)
    ok = len(ids) == 10 and all(c in (200, 202) for c in codes) and completed == 10
    return {
        "PASS": ok,
        "targets": len(ids),
        "status_200": codes.count(200),
        "cancellation_completed": completed,
        "cancellation_requested": requested,
    }


async def _capacity_reclaim(client, sf) -> dict[str, Any]:
    async def _one(i: int) -> tuple[int, dict[str, Any]]:
        r = await client.post(
            "/v1/research/runs",
            json=_payload(f"S6 回收后新请求 {i}"),
            headers={"Idempotency-Key": f"load-reclaim-{i}"},
        )
        return r.status_code, r.json()

    with sf() as s:
        queued_before = s.execute(
            text("SELECT count(*) FROM runs WHERE status = 'queued'")
        ).scalar() or 0
    results = await asyncio.gather(*[_one(i) for i in range(15)])
    codes = [c for c, _ in results]
    accepted = codes.count(202)
    rejected = codes.count(503)
    with sf() as s:
        queued_after = s.execute(
            text("SELECT count(*) FROM runs WHERE status = 'queued'")
        ).scalar() or 0
    expected_accepted = ADMISSION_CAP - queued_before
    expected_rejected = 15 - expected_accepted
    ok = (
        accepted == expected_accepted
        and rejected == expected_rejected
        and queued_after == ADMISSION_CAP
        and not any(c in (500, 501, 502, 504) for c in codes)
    )
    return {
        "PASS": ok,
        "queued_before": queued_before,
        "cap": ADMISSION_CAP,
        "accepted_202": accepted,
        "rejected_503": rejected,
        "expected_accepted": expected_accepted,
        "expected_rejected": expected_rejected,
        "queued_after": queued_after,
    }


async def _leak_and_integrity(engine, sf) -> dict[str, Any]:
    with sf() as s:
        runs = s.execute(text("SELECT count(*) FROM runs")).scalar() or 0
        queued = s.execute(text("SELECT count(*) FROM runs WHERE status = 'queued'")).scalar() or 0
        cancelled = s.execute(
            text("SELECT count(*) FROM runs WHERE status = 'cancelled'")
        ).scalar() or 0
        leases = s.execute(text("SELECT count(*) FROM task_execution_leases")).scalar() or 0
        dup_keys = s.execute(
            text(
                "SELECT count(*) FROM (SELECT idempotency_key FROM runs "
                "WHERE idempotency_key IS NOT NULL GROUP BY idempotency_key "
                "HAVING count(*) > 1) t"
            )
        ).scalar() or 0
        run_events = s.execute(text("SELECT count(*) FROM run_events")).scalar() or 0
    checkedout = engine.pool.checkedout()
    ok = (
        checkedout == 0
        and leases == 0
        and dup_keys == 0
        and queued + cancelled == runs
    )
    return {
        "PASS": ok,
        "pool_checkedout": checkedout,
        "total_runs": runs,
        "queued": queued,
        "cancelled": cancelled,
        "orphan_leases": leases,
        "duplicate_idempotency_keys": dup_keys,
        "run_events": run_events,
    }


# ── main ─────────────────────────────────────────────────────────────────────

def _wait_ready(base: str, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base}/readyz", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


async def main() -> int:
    url = _db_url()
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    create_execution_tables(engine)
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    _clean(engine, sf)

    base = f"http://127.0.0.1:{PORT}"
    env = dict(os.environ)
    env["DATABASE_URL"] = url
    env["ADMISSION_MAX_QUEUED_RUNS"] = str(ADMISSION_CAP)
    env["LOG_LEVEL"] = "WARNING"
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "apps.api.main:app",
            "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning",
        ],
        cwd=str(_REPO),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_ready(base):
            print("server did not become ready")
            return 2
        print(f"[server] ready at {base} (admission cap={ADMISSION_CAP})")

        sampler = _ConnSampler(url)
        async with httpx.AsyncClient(
            base_url=base, timeout=30.0,
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
        ) as client:
            results: dict[str, Any] = {}
            results["solo_baseline"] = await _solo_baseline(client, sf)
            print("S1 solo_baseline:", results["solo_baseline"]["PASS"])

            burst = await _burst_submission(client, sf, sampler)
            results["burst_submission"] = burst
            print(
                f"S2 burst: accepted={burst['accepted_202']} rejected={burst['rejected_503']} "
                f"peak_db={burst['peak_db_connections']} "
                f"p95={burst['latency']['p95_ms']}ms"
            )

            run_ids = burst["run_ids"]
            results["cancel_burst"] = await _cancel_burst(client, run_ids)
            print("S5 cancel:", results["cancel_burst"]["PASS"])

            results["idempotency_replay"] = await _idempotency_replay(client, sf)
            print("S3 idempotency:", results["idempotency_replay"]["PASS"])

            results["capacity_reclaim"] = await _capacity_reclaim(client, sf)
            print("S6 reclaim:", results["capacity_reclaim"]["PASS"])

            results["poll_storm"] = await _poll_storm(client, run_ids)
            poll = results["poll_storm"]
            print(
                f"S4 poll: {poll['requests']} req all_200={poll['all_200']} "
                f"p95={poll['latency']['p95_ms']}ms"
            )

            results["leak_check"] = await _leak_and_integrity(engine, sf)
            print("S7 leak:", results["leak_check"]["PASS"])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        engine.dispose()

    all_pass = all(v["PASS"] for v in results.values())
    report = {
        "g4_network_layer": results,
        "status": "PASS" if all_pass else "FAIL",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "network_load_acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nG4 Network-layer Load {'PASS' if all_pass else 'FAIL'} -> {OUT_DIR}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
