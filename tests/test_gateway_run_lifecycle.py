"""G0.1 Run lifecycle tests — pure unit tests (SQLite + Fake executor).

Run lifecycle is owned by TaskService/Worker; the executor is a fake so no
DeepResearchAgent / Provider / network is imported or called. Fast (<2s).

Covers: queued / running / succeeded / failed / cancelled / enqueue failure /
same run identity / no duplicate Run.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.agents.schemas import ResearchAnalyzeRequest
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Run
from packages.db.models.enums import RunStatus
from packages.db.session import get_engine, reset_db_session_state
from packages.tasks.handlers import (
    NonRetryableTaskError,
    TaskHandlers,
)
from packages.tasks.schemas import ResearchAnalyzeTaskSubmitRequest
from packages.tasks.service import TaskService, TaskServiceError


class FakeResearchExecutor:
    """Records the run_id/strategy it was handed; never creates a Run."""

    def __init__(self, *, result: dict | None = None, fail: bool = False,
                 session_factory=None) -> None:
        self.result = result or {"ok": True}
        self.fail = fail
        self.session_factory = session_factory
        self.calls: list[dict] = []
        self.status_at_exec: RunStatus | None = None

    def run(self, *, query: str, run_id: int | None, strategy: str | None) -> dict:
        self.calls.append({"query": query, "run_id": run_id, "strategy": strategy})
        if self.session_factory is not None:
            with self.session_factory() as s:
                run = s.get(Run, run_id)
                self.status_at_exec = run.status if run is not None else None
        if self.fail:
            raise NonRetryableTaskError("boom")
        return dict(self.result)


def _make_service(monkeypatch, tmp_path: Path) -> tuple[Session, TaskService]:
    db_url = f"sqlite+pysqlite:///{(tmp_path / 'lifecycle.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    reset_db_session_state()
    engine = get_engine()
    Base.metadata.create_all(engine)
    session = Session(engine)
    return session, TaskService(session), engine


def _submit(service: TaskService, *, strategy: str = "deep", key: str | None = "k1"):
    return service.enqueue_research(
        ResearchAnalyzeTaskSubmitRequest(
            request=ResearchAnalyzeRequest(
                query="测试合肥低空物流产业链", research_strategy=strategy
            ),
            idempotency_key=key,
        )
    )


def test_enqueue_creates_queued_run_and_binds_task(monkeypatch, tmp_path):
    session, service, _engine = _make_service(monkeypatch, tmp_path)
    resp = _submit(service)
    assert resp.run_id is not None
    run = session.get(Run, resp.run_id)
    assert run is not None and run.status == RunStatus.QUEUED
    assert run.input_json.get("query") == "测试合肥低空物流产业链"
    task = service.get_task(resp.task_id)
    assert task.source_run_id == resp.run_id  # Task–Run binding
    session.close()


def test_worker_marks_running_then_succeeded(monkeypatch, tmp_path):
    session, service, _engine = _make_service(monkeypatch, tmp_path)
    resp = _submit(service)
    fake = FakeResearchExecutor(
        result={"pipeline": "deep_research_graph_v2"}, session_factory=lambda: Session(_engine)
    )
    service.process_next(worker_id="w1", handlers=TaskHandlers(session, research_executor=fake))
    # executor observed RUNNING mid-flight
    assert fake.status_at_exec == RunStatus.RUNNING
    assert fake.calls[0]["run_id"] == resp.run_id
    run = session.get(Run, resp.run_id)
    assert run.status == RunStatus.SUCCEEDED
    assert run.output_json.get("pipeline") == "deep_research_graph_v2"
    assert run.finished_at is not None
    # executor never created a second Run
    assert session.scalar(select(func.count()).select_from(Run)) == 1
    session.close()


def test_worker_marks_failed_and_persists_error(monkeypatch, tmp_path):
    session, service, _engine = _make_service(monkeypatch, tmp_path)
    resp = _submit(service)
    fake = FakeResearchExecutor(fail=True)
    service.process_next(worker_id="w1", handlers=TaskHandlers(session, research_executor=fake))
    run = session.get(Run, resp.run_id)
    assert run.status == RunStatus.FAILED
    assert "boom" in str(run.output_json.get("error", ""))
    assert run.finished_at is not None
    session.close()


def test_queued_cancel_marks_run_and_task_cancelled(monkeypatch, tmp_path):
    session, service, _engine = _make_service(monkeypatch, tmp_path)
    resp = _submit(service)
    result = service.cancel_research_run(resp.run_id)
    assert result["status"] == "cancelled"
    assert result["completed"] is True
    run = session.get(Run, resp.run_id)
    assert run.status == RunStatus.CANCELLED
    task = service.get_task(resp.task_id)
    assert task.status == "cancelled"
    session.close()


def test_cancel_unknown_run_raises(monkeypatch, tmp_path):
    _session, service, _engine = _make_service(monkeypatch, tmp_path)
    try:
        service.cancel_research_run(999999)
        raised = False
    except TaskServiceError:
        raised = True
    assert raised


def test_enqueue_failure_leaves_no_orphan_queued_run(monkeypatch, tmp_path):
    session, service, _engine = _make_service(monkeypatch, tmp_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("enqueue failed")

    monkeypatch.setattr(service, "_enqueue", _boom)
    try:
        _submit(service)
    except RuntimeError:
        pass
    # no Run should remain QUEUED (rolled back atomically or compensated to FAILED)
    queued = session.scalars(select(Run).where(Run.status == RunStatus.QUEUED)).all()
    assert len(queued) == 0
    session.close()


def test_idempotency_reuses_same_run(monkeypatch, tmp_path):
    _session, service, _engine = _make_service(monkeypatch, tmp_path)
    first = _submit(service, key="dup")
    second = _submit(service, key="dup")
    assert second.deduplicated is True
    assert second.run_id == first.run_id
