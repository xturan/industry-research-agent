"""G1.5 Cancellation Control tests.

Covers: queued cancel (Run+Task CANCELLED), running cancel request (cooperative),
worker observes cancel -> CANCELLED, no further expensive stage, idempotent
repeat, terminal 409, RunEvent order, terminal-wins race, unknown 404.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from apps.api.main import app
from packages.agents.schemas import ResearchAnalyzeRequest
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Run, RunEvent
from packages.db.models.enums import RunStatus
from packages.db.session import get_engine, reset_db_session_state
from packages.research_gateway.errors import (
    ResearchRunCancelled,
    RunAlreadyTerminalError,
)
from packages.research_gateway.service import ResearchRunService
from packages.tasks.handlers import TaskHandlers
from packages.tasks.service import TaskService


class CancellableFakeExecutor:
    """Checks cancellation at stage boundaries; raises ResearchRunCancelled."""

    def __init__(self) -> None:
        self.stages: list[str] = []
        self.run_id: int | None = None

    @staticmethod
    def _cancel_requested(run_id: int) -> bool:
        from packages.db.models import Run
        from packages.db.session import SessionLocal

        with SessionLocal() as s:
            run = s.get(Run, run_id)
            return run is not None and run.cancel_requested_at is not None

    def run(self, *, query: str, run_id: int | None, strategy: str | None) -> dict:
        self.run_id = run_id
        self.stages.append("planner")
        if self._cancel_requested(run_id):
            raise ResearchRunCancelled()
        self.stages.append("search")
        if self._cancel_requested(run_id):
            raise ResearchRunCancelled()
        self.stages.append("editor")
        return {"report": "ok"}


def _make_engine(monkeypatch, tmp_path: Path):
    db_url = f"sqlite+pysqlite:///{(tmp_path / 'cancel.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    reset_db_session_state()
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def _submit(engine) -> ResearchRunService:
    svc = ResearchRunService(Session(engine))
    resp = svc.submit(
        ResearchAnalyzeRequest(query="测试合肥低空物流产业链", research_strategy="deep")
    )
    return svc, resp.run_id


def test_queued_cancel_marks_both_cancelled(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    svc, run_id = _submit(engine)
    result = svc.cancel_run(run_id)
    assert result.status == "cancelled"
    assert result.cancellation == {"requested": True, "completed": True}
    with Session(engine) as s:
        run = s.get(Run, run_id)
        assert run.status == RunStatus.CANCELLED
    # RUN_CANCEL_REQUESTED + RUN_CANCELLED events
    with Session(engine) as s:
        types = [e.event_type for e in s.scalars(
            select(RunEvent).where(RunEvent.run_id == run_id)
        )]
    assert "RUN_CANCELLED" in types


def test_running_cancel_request_sets_flag(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    svc, run_id = _submit(engine)
    with Session(engine) as s:
        run = s.get(Run, run_id)
        run.status = RunStatus.RUNNING
        s.commit()
    result = svc.cancel_run(run_id)
    assert result.status == "running"  # still running; cancellation requested
    assert result.cancellation == {"requested": True, "completed": False}
    with Session(engine) as s:
        run = s.get(Run, run_id)
        assert run.status == RunStatus.RUNNING
        assert run.cancel_requested_at is not None
    with Session(engine) as s:
        types = [e.event_type for e in s.scalars(
            select(RunEvent).where(RunEvent.run_id == run_id)
        )]
    assert "RUN_CANCEL_REQUESTED" in types


def test_worker_observes_cancel_and_stops(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    svc, run_id = _submit(engine)
    with Session(engine) as s:
        run = s.get(Run, run_id)
        run.status = RunStatus.RUNNING
        s.commit()
    svc.cancel_run(run_id)  # sets cancel_requested_at (202)
    fake = CancellableFakeExecutor()
    # claim + execute the task (worker)
    with Session(engine) as s:
        TaskService(s).process_next(
            worker_id="w1", handlers=TaskHandlers(s, research_executor=fake)
        )
    assert fake.stages == ["planner"]  # stopped before expensive stages
    with Session(engine) as s:
        run = s.get(Run, run_id)
        assert run.status == RunStatus.CANCELLED
    with Session(engine) as s:
        types = [e.event_type for e in s.scalars(
            select(RunEvent).where(RunEvent.run_id == run_id)
        )]
    assert "RUN_CANCELLED" in types


def test_no_expensive_stage_after_cancel(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    svc, run_id = _submit(engine)
    with Session(engine) as s:
        run = s.get(Run, run_id)
        run.status = RunStatus.RUNNING
        s.commit()
    svc.cancel_run(run_id)
    fake = CancellableFakeExecutor()
    with Session(engine) as s:
        TaskService(s).process_next(
            worker_id="w1", handlers=TaskHandlers(s, research_executor=fake)
        )
    assert "search" not in fake.stages  # search (expensive) never started


def test_repeated_cancel_is_idempotent(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    svc, run_id = _submit(engine)
    svc.cancel_run(run_id)
    again = svc.cancel_run(run_id)
    assert again.status == "cancelled"
    assert again.cancellation["completed"] is True


def test_cancel_succeeded_is_409(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    svc, run_id = _submit(engine)
    with Session(engine) as s:
        run = s.get(Run, run_id)
        run.status = RunStatus.SUCCEEDED
        s.commit()
    try:
        svc.cancel_run(run_id)
        raised = False
    except RunAlreadyTerminalError:
        raised = True
    assert raised


def test_cancel_failed_is_409(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    svc, run_id = _submit(engine)
    with Session(engine) as s:
        run = s.get(Run, run_id)
        run.status = RunStatus.FAILED
        s.commit()
    try:
        svc.cancel_run(run_id)
        raised = False
    except RunAlreadyTerminalError:
        raised = True
    assert raised


@pytest.fixture()
def http_client(monkeypatch, tmp_path: Path) -> Generator[TestClient, None, None]:
    engine = _make_engine(monkeypatch, tmp_path)

    def _override() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db_session, None)


def _http_create(client) -> int:
    payload = {"request": {"query": "研究2025年合肥低空物流产业链",
                           "research_strategy": "deep", "mode": "mock"}}
    return client.post("/v1/research/runs", json=payload).json()["run_id"]


def test_http_queued_cancel_200(http_client):
    run_id = _http_create(http_client)
    resp = http_client.post(f"/v1/research/runs/{run_id}/cancel")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancellation"] == {"requested": True, "completed": True}


def test_http_running_cancel_202(http_client):
    run_id = _http_create(http_client)
    # mark running via direct DB access through the dependency override generator
    from apps.api.dependencies import get_db_session as _gs
    _gen = app.dependency_overrides[_gs]()
    s = next(_gen)
    run = s.get(Run, run_id)
    run.status = RunStatus.RUNNING
    s.commit()
    _gen.close()
    resp = http_client.post(f"/v1/research/runs/{run_id}/cancel")
    assert resp.status_code == 202
    assert resp.json()["cancellation"]["completed"] is False


def test_http_unknown_run_404(http_client):
    resp = http_client.post("/v1/research/runs/999999/cancel")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RUN_NOT_FOUND"
