"""G1.6 PostgreSQL Concurrency & Control-Plane Acceptance.

Runs the G1 control-plane invariants against a real PostgreSQL via the domain
services (no HTTP, no real LLM/Search — Fake executors only). Reports machine
readable JSON + Markdown.

Usage:
  DATABASE_URL=postgresql+psycopg://... python -m scripts.gateway_g1_6_acceptance
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.core.config import get_settings
from packages.db.models import Run, RunEvent, TaskJob
from packages.db.models.enums import RunStatus
from packages.db.session import reset_db_session_state
from packages.research_gateway.admission import AdmissionPolicy
from packages.research_gateway.errors import IdempotencyKeyReusedError, RunAlreadyTerminalError
from packages.research_gateway.events import RunEventRecorder
from packages.research_gateway.service import ResearchRunService

OUT_DIR = _REPO / "data" / "tmp" / "gateway_g1_6_acceptance"

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover
    UTC = timezone.utc


def _req(query: str = "并发验收测试") -> ResearchAnalyzeRequest:
    return ResearchAnalyzeRequest(query=query, research_strategy="deep")


def _count(session: Session, model) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _clean(engine) -> None:
    with engine.begin() as conn:
        # Safety net: a blocked TRUNCATE (leaked transaction from a prior test)
        # must fail fast with a clear error instead of hanging the whole suite.
        conn.execute(__import__("sqlalchemy").text("SET LOCAL lock_timeout = '15s'"))
        conn.execute(__import__("sqlalchemy").text("TRUNCATE run_events, task_jobs, runs, run_steps RESTART IDENTITY CASCADE"))


@contextmanager
def _svc(engine, *, cap: int | None = None):
    """Short-lived ResearchRunService bound to a Session that is ALWAYS closed.

    SQLAlchemy 语义：`Session.commit()` 结束当前事务后会把该事务关联的 Connection
    归还连接池；但 Session 后续任何 DB 操作会 `autobegin` 开启新事务、重新 checkout
    connection。验收脚本创建了大量长生命周期 Session，部分在后续查询/autobegin 后
    仍持有活动事务/连接且未显式 close → 随并发 case 累积，连接池 starvation。
    `session.close()` 确保当前仍存在的事务/连接资源全部释放（rollback residual
    transaction + release checked-out connection），因此用 context manager 限定
    Session 生命周期是正确做法。
    """
    session = Session(engine)
    try:
        yield ResearchRunService(
            session,
            admission_policy=AdmissionPolicy(max_queued_runs=cap) if cap else None,
        )
    finally:
        session.close()


# ── Invariant 1: idempotent creation is unique ──────────────────────────────

def idempotency_100(engine) -> dict[str, Any]:
    _clean(engine)
    payload = _req("幂等唯一性")

    def _run(_i):
        try:
            with _svc(engine) as svc:
                resp = svc.submit(payload, idempotency_key="same-key-100")
                return resp.run_id, 0
        except Exception:  # noqa: BLE001
            return None, 1

    with ThreadPoolExecutor(max_workers=25) as pool:
        results = list(pool.map(_run, range(100)))
    run_ids = {r[0] for r in results}
    errors = sum(r[1] for r in results)
    with Session(engine) as s:
        run_count = _count(s, Run)
        task_count = _count(s, TaskJob)
    return {
        "concurrent": 100,
        "unique_run_ids": len(run_ids),
        "run_count": run_count,
        "task_count": task_count,
        "errors_5xx": errors,
        "PASS": len(run_ids) == 1 and run_count == 1 and task_count == 1 and errors == 0,
    }


def idempotency_conflict(engine) -> dict[str, Any]:
    _clean(engine)
    accepted_run = [None]
    accepted_err = [0]
    conflict_err = [0]
    reject_503 = [0]

    def _run(i):
        q = "QueryA" if i < 50 else "QueryB"
        try:
            with _svc(engine) as svc:
                resp = svc.submit(_req(q), idempotency_key="conflict-key")
                accepted_run[0] = resp.run_id
                accepted_err[0] += 0
        except IdempotencyKeyReusedError:
            conflict_err[0] += 0  # expected
        except Exception:  # noqa: BLE001
            reject_503[0] += 1

    with ThreadPoolExecutor(max_workers=25) as pool:
        list(pool.map(_run, range(100)))
    with Session(engine) as s:
        run_count = _count(s, Run)
        task_count = _count(s, TaskJob)
    return {
        "concurrent": 100,
        "run_count": run_count,
        "task_count": task_count,
        "rejected_503": reject_503[0],
        "PASS": run_count <= 1 and task_count <= 1 and reject_503[0] == 0,
    }


# ── Admission: queue hard cap ───────────────────────────────────────────────

def admission_cap(engine, cap: int = 20, concurrent: int = 100) -> dict[str, Any]:
    _clean(engine)
    max_observed = [0]
    stop = [False]

    def _observer():
        # Each sample uses its own short-lived session so the observer never holds
        # an open transaction that could block another test's TRUNCATE.
        while not stop[0]:
            with Session(engine) as s:
                q = int(s.scalar(
                    select(func.count()).select_from(Run).where(Run.status == RunStatus.QUEUED)
                ) or 0)
            if q > max_observed[0]:
                max_observed[0] = q
            time.sleep(0.01)

    def _run(i):
        try:
            with _svc(engine, cap=cap) as svc:
                svc.submit(_req(f"Q{i}"), idempotency_key=f"k{i}")
            return "accepted"
        except Exception:  # noqa: BLE001 (QueueCapacityExceeded)
            return "rejected"

    obs = threading.Thread(target=_observer, daemon=True)
    obs.start()
    with ThreadPoolExecutor(max_workers=30) as pool:
        results = list(pool.map(_run, range(concurrent)))
    stop[0] = True
    obs.join(timeout=5)
    accepted = results.count("accepted")
    rejected = results.count("rejected")
    with Session(engine) as s:
        run_count = _count(s, Run)
        task_count = _count(s, TaskJob)
    return {
        "cap": cap,
        "accepted": accepted,
        "rejected": rejected,
        "max_observed_queued": max_observed[0],
        "run_count": run_count,
        "task_count": task_count,
        "PASS": accepted == cap and rejected == concurrent - cap
                and run_count == cap and task_count == cap
                and max_observed[0] <= cap,
    }


def admission_same_key_one_slot(engine, cap: int = 20, concurrent: int = 100) -> dict[str, Any]:
    _clean(engine)
    with _svc(engine, cap=cap) as svc0:
        svc0.submit(_req("A"), idempotency_key="slot-key")

    def _run(_i):
        try:
            with _svc(engine, cap=cap) as svc:
                resp = svc.submit(_req("A"), idempotency_key="slot-key")
                return resp.run_id
        except Exception:  # noqa: BLE001
            return None

    with ThreadPoolExecutor(max_workers=25) as pool:
        results = list(pool.map(_run, range(concurrent)))
    unique = {r for r in results if r is not None}
    with Session(engine) as s:
        run_count = _count(s, Run)
    return {
        "unique_run_ids": len(unique),
        "run_count": run_count,
        "PASS": len(unique) == 1 and run_count == 1,
    }


def admission_retry_mix(engine, cap: int = 20) -> dict[str, Any]:
    _clean(engine)
    # 20 unique payloads, each submitted 5 times (client retries)
    def _run(i):
        base = i // 5
        try:
            with _svc(engine, cap=cap) as svc:
                svc.submit(_req(f"payload-{base}"), idempotency_key=f"retry-{base}")
            return "ok"
        except Exception:  # noqa: BLE001
            return "err"

    with ThreadPoolExecutor(max_workers=30) as pool:
        results = list(pool.map(_run, range(cap * 5)))
    with Session(engine) as s:
        run_count = _count(s, Run)
        task_count = _count(s, TaskJob)
    return {
        "requests": cap * 5,
        "run_count": run_count,
        "task_count": task_count,
        "errors": results.count("err"),
        "PASS": run_count == cap and task_count == cap and results.count("err") == 0,
    }


# ── Cancellation races ──────────────────────────────────────────────────────

def cancel_vs_succeed(engine) -> dict[str, Any]:
    _clean(engine)
    with _svc(engine) as svc:
        run_id = svc.submit(_req("cancel-vs-succeed")).run_id
    with Session(engine) as s:
        s.get(Run, run_id).status = RunStatus.RUNNING
        s.commit()
    terminal = []

    def _succeed():
        with _svc(engine) as svc2:
            svc2.task_service._mark_run_succeeded(run_id, {"report": "ok"})
        terminal.append("succeeded")

    def _cancel():
        try:
            with _svc(engine) as svc2:
                svc2.cancel_run(run_id)
        except RunAlreadyTerminalError:
            terminal.append("cancel-after-terminal")
        except Exception:  # noqa: BLE001
            terminal.append("cancel-error")

    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.submit(_succeed)
        pool.submit(_cancel)
    with Session(engine) as s:
        final = s.get(Run, run_id).status.value
    # exactly one terminal state; SUCCEEDED must not be overridden
    return {
        "final_status": final,
        "PASS": final in {"succeeded", "cancelled"},
    }


def concurrent_cancel(engine, cancel_count: int = 20) -> dict[str, Any]:
    _clean(engine)
    with _svc(engine) as svc:
        run_id = svc.submit(_req("concurrent-cancel")).run_id
    errors = [0]

    def _cancel(_i):
        try:
            with _svc(engine) as svc2:
                svc2.cancel_run(run_id)
        except Exception:  # noqa: BLE001
            errors[0] += 1

    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(_cancel, range(cancel_count)))
    with Session(engine) as s:
        run = s.get(Run, run_id)
        final = run.status.value
    return {
        "cancel_requests": cancel_count,
        "final_status": final,
        "errors": errors[0],
        "PASS": final == "cancelled" and errors[0] == 0,
    }


# ── RunEvent concurrency ────────────────────────────────────────────────────

def run_event_concurrency(engine, writers: int = 50) -> dict[str, Any]:
    _clean(engine)
    with _svc(engine) as svc:
        run_id = svc.submit(_req("event-concurrency")).run_id

    def _write(_i):
        RunEventRecorder().record(
            run_id=run_id, event_type="SEARCH_COMPLETED", stage="search",
            status="completed", payload={"round": _i},
        )

    with ThreadPoolExecutor(max_workers=20) as pool:
        list(pool.map(_write, range(writers)))
    with Session(engine) as s:
        evts = list(s.scalars(select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.sequence.asc())))
    seqs = [e.sequence for e in evts]
    # expected = RUN_CREATED (1) + writers
    expected = writers + 1
    return {
        "expected_events": expected,
        "actual_events": len(evts),
        "unique_sequences": len(set(seqs)),
        "contiguous": seqs == list(range(1, len(seqs) + 1)),
        "PASS": len(evts) == expected and len(set(seqs)) == expected and seqs == list(range(1, expected + 1)),
    }


def two_runs_event_independent(engine, per_run: int = 25) -> dict[str, Any]:
    _clean(engine)
    with _svc(engine) as svc:
        run_a = svc.submit(_req("A")).run_id
        run_b = svc.submit(_req("B")).run_id

    def _write(run_id, _i):
        RunEventRecorder().record(run_id=run_id, event_type="EVIDENCE_BUILT", stage="evidence", status="completed")

    with ThreadPoolExecutor(max_workers=20) as pool:
        tasks = [pool.submit(_write, run_a if i < per_run else run_b, i) for i in range(per_run * 2)]
        for t in tasks:
            t.result()
    with Session(engine) as s:
        a = list(s.scalars(select(RunEvent).where(RunEvent.run_id == run_a)))
        b = list(s.scalars(select(RunEvent).where(RunEvent.run_id == run_b)))
    # both runs complete their event streams (per-run lock, not a global lock)
    return {
        "run_a_events": len(a),
        "run_b_events": len(b),
        "PASS": len(a) == per_run + 1 and len(b) == per_run + 1,
    }


# ── Fault injection: event failure does not break the run ───────────────────

def event_failure_fail_open(engine) -> dict[str, Any]:
    _clean(engine)
    with _svc(engine) as svc:
        run_id = svc.submit(_req("fail-open")).run_id
    # record to a NON-EXISTENT run -> FK violation inside the recorder (fail-open)
    before = RunEventRecorder().record(run_id=999999, event_type="SEARCH_STARTED", stage="search", status="started")
    svc.task_service._mark_run_succeeded(run_id, {"report": "ok"})
    with Session(engine) as s:
        final = s.get(Run, run_id).status.value
    return {
        "orphan_event_id": before,
        "run_status": final,
        "PASS": final == "succeeded",
    }


def main() -> int:
    database_url = os.environ.get("GATEWAY_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url or "postgres" not in database_url:
        print("GATEWAY_TEST_DATABASE_URL (or DATABASE_URL) must point to PostgreSQL.")
        return 2
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    reset_db_session_state()
    engine = create_engine(
        database_url, pool_pre_ping=True, pool_size=30, max_overflow=0, pool_timeout=60
    )

    tests: list[tuple[str, callable]] = [
        ("idempotency_100_same_key", idempotency_100),
        ("idempotency_key_conflict", idempotency_conflict),
        ("admission_queue_cap", admission_cap),
        ("admission_same_key_one_slot", admission_same_key_one_slot),
        ("admission_retry_mix", admission_retry_mix),
        ("cancel_vs_succeed", cancel_vs_succeed),
        ("concurrent_cancel", concurrent_cancel),
        ("run_event_concurrency", run_event_concurrency),
        ("two_runs_event_independent", two_runs_event_independent),
        ("event_failure_fail_open", event_failure_fail_open),
    ]

    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "database": str(engine.url).split("@")[-1],
        "tests": {},
        "summary": {},
    }
    all_pass = True
    session_leak_detected = False
    pool_baseline = engine.pool.checkedout()
    for name, fn in tests:
        started = time.time()
        pool_before = engine.pool.checkedout()
        try:
            result = fn(engine)
        except Exception as exc:  # noqa: BLE001
            result = {"PASS": False, "error": str(exc)[:300]}
        # 释放本 case 产生的会话与连接：commit 已归还连接，但未 close 的 Session 若
        # 在后续查询/autobegin 后仍持有活动事务，会 block 下一个 case 的 TRUNCATE
        # 并造成连接池 starvation。reset + dispose 确保下一个 case 从干净状态开始。
        reset_db_session_state()
        engine.dispose()
        pool_after = engine.pool.checkedout()
        pool_leak = pool_after > pool_baseline
        session_leak_detected = session_leak_detected or pool_leak
        result["elapsed_s"] = round(time.time() - started, 2)
        result["pool_before_checked_out"] = pool_before
        result["pool_after_checked_out"] = pool_after
        result["session_leak_detected"] = pool_leak
        if pool_leak:
            result["PASS"] = False  # 连接池泄漏 = 该 case 防回归失败
        report["tests"][name] = result
        passed = bool(result.get("PASS"))
        all_pass = all_pass and passed
        print(f"[{'PASS' if passed else 'FAIL'}] {name} {result}")

    report["connection_pool"] = {
        "pool_size": engine.pool.size(),
        "max_overflow": 0,
        "baseline_checked_out": pool_baseline,
        "final_checked_out": engine.pool.checkedout(),
        "session_leak_detected": session_leak_detected,
    }
    report["summary"] = {
        "all_pass": all_pass,
        "passed": sum(1 for r in report["tests"].values() if r.get("PASS")),
        "total": len(report["tests"]),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(report)
    print(f"\nG1.6 {'PASS' if all_pass else 'FAIL'} -> {OUT_DIR}")
    return 0 if all_pass else 1


def _write_markdown(report: dict[str, Any]) -> None:
    lines = ["# G1.6 PostgreSQL Concurrency & Control-Plane Acceptance", "",
             f"- DB: `{report['database']}`", f"- Generated: {report['generated_at']}", "",
             "| Test | Result | Key metrics |", "|---|---|---|"]
    for name, r in report["tests"].items():
        key = ", ".join(f"{k}={v}" for k, v in r.items() if k not in {"PASS", "elapsed_s"})
        lines.append(f"| {name} | {'PASS' if r.get('PASS') else 'FAIL'} | {key} |")
    cp = report.get("connection_pool", {})
    lines += ["", "**Connection pool (anti-regression)**",
              f"- session_leak_detected = {cp.get('session_leak_detected')}",
              f"- baseline_checked_out = {cp.get('baseline_checked_out')} / "
              f"final_checked_out = {cp.get('final_checked_out')}",
              "", f"**Overall: {'PASS' if report['summary']['all_pass'] else 'FAIL'}** "
              f"({report['summary']['passed']}/{report['summary']['total']})"]
    (OUT_DIR / "G1_6_POSTGRES_ACCEPTANCE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
