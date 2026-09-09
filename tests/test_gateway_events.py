"""G1.4 RunEvent Timeline tests.

Verifies lifecycle events (RUN_CREATED/WORKER_CLAIMED/RUN_COMPLETED/RUN_FAILED),
stage events via the executor, sequence/order, after_sequence filtering,
append-only semantics, unknown-run 404, and fail-open (events don't affect Run).
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
from packages.research_gateway.events import RunEventRecorder
from packages.research_gateway.service import ResearchRunService
from packages.tasks.handlers import NonRetryableTaskError, TaskHandlers
from packages.tasks.service import TaskService


class FakeResearchExecutor:
    """Emits stage events like the real agent would (planner/search/editor)."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.run_id: int | None = None

    def run(self, *, query: str, run_id: int | None, strategy: str | None) -> dict:
        self.run_id = run_id
        rec = RunEventRecorder()
        rec.record(run_id=run_id, event_type="PLANNER_STARTED", stage="planning", status="started")
        rec.record(run_id=run_id, event_type="SEARCH_STARTED", stage="search", status="started")
        rec.record(run_id=run_id, event_type="SEARCH_COMPLETED", stage="search", status="completed",
                   payload={"source_count": 21})
        rec.record(run_id=run_id, event_type="EDITOR_COMPLETED", stage="editor", status="completed")
        if self.fail:
            raise NonRetryableTaskError("boom")
        return {"report": "ok", "evidence_count": 3}


def _make_engine(monkeypatch, tmp_path: Path):
    db_url = f"sqlite+pysqlite:///{(tmp_path / 'events.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    reset_db_session_state()
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def _create_and_run(
    engine, *, fail: bool = False
) -> tuple[ResearchRunService, int, FakeResearchExecutor]:
    svc = ResearchRunService(Session(engine))
    resp = svc.submit(
        ResearchAnalyzeRequest(query="测试合肥低空物流产业链", research_strategy="deep")
    )
    run_id = resp.run_id
    fake = FakeResearchExecutor(fail=fail)
    TaskService(Session(engine)).process_next(
        worker_id="w1", handlers=TaskHandlers(Session(engine), research_executor=fake)
    )
    return svc, run_id, fake


def _events(engine, run_id: int) -> list[RunEvent]:
    with Session(engine) as s:
        return list(
            s.scalars(
                select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.sequence.asc())
            )
        )


def test_create_emits_run_created(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    svc = ResearchRunService(Session(engine))
    resp = svc.submit(ResearchAnalyzeRequest(query="Q", research_strategy="deep"))
    evts = _events(engine, resp.run_id)
    assert [e.event_type for e in evts] == ["RUN_CREATED"]


def test_worker_claim_and_complete_events(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    _svc, run_id, _fake = _create_and_run(engine)
    types = [e.event_type for e in _events(engine, run_id)]
    assert "WORKER_CLAIMED" in types
    assert "RUN_COMPLETED" in types
    # stage events from the executor
    assert "SEARCH_COMPLETED" in types
    assert "EDITOR_COMPLETED" in types


def test_failure_emits_run_failed(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    _svc, run_id, _fake = _create_and_run(engine, fail=True)
    types = [e.event_type for e in _events(engine, run_id)]
    assert "RUN_FAILED" in types
    assert "RUN_COMPLETED" not in types


def test_sequence_is_monotonic_append_only(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    _svc, run_id, _fake = _create_and_run(engine)
    evts = _events(engine, run_id)
    seqs = [e.sequence for e in evts]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)  # unique, append-only
    # re-running the worker adds MORE events; original events are unchanged
    before = [e.event_type for e in evts]
    TaskService(Session(engine)).process_next(
        worker_id="w1",
        handlers=TaskHandlers(
            Session(engine), research_executor=FakeResearchExecutor()
        ),
    )
    after = _events(engine, run_id)
    assert before == [e.event_type for e in after[: len(before)]]


def test_payload_is_small_and_secret_free(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    _svc, run_id, _fake = _create_and_run(engine)
    for e in _events(engine, run_id):
        payload = e.payload_json or {}
        assert not any(k in payload for k in ("api_key", "prompt", "raw", "full_source", "secret"))
        assert len(json_dumps(payload)) < 2000


def json_dumps(payload: dict) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)


def test_events_do_not_affect_run_lifecycle(monkeypatch, tmp_path):
    engine = _make_engine(monkeypatch, tmp_path)
    _svc, run_id, _fake = _create_and_run(engine)
    with Session(engine) as s:
        run = s.get(Run, run_id)
        assert run.status == RunStatus.SUCCEEDED  # Run.status authoritative
    assert len(_events(engine, run_id)) > 0  # timeline exists alongside


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


def test_http_events_endpoint_and_after_sequence(http_client):
    payload = {"request": {"query": "研究2025年合肥低空物流产业链",
                           "research_strategy": "deep", "mode": "mock"}}
    created = http_client.post("/v1/research/runs", json=payload).json()
    run_id = created["run_id"]
    # initial events: RUN_CREATED
    ev1 = http_client.get(f"/v1/research/runs/{run_id}/events").json()
    assert ev1["run_id"] == run_id
    assert [e["event_type"] for e in ev1["events"]] == ["RUN_CREATED"]
    # after_sequence=1 -> empty
    ev2 = http_client.get(f"/v1/research/runs/{run_id}/events?after_sequence=1").json()
    assert ev2["events"] == []


def test_http_events_unknown_run_404(http_client):
    resp = http_client.get("/v1/research/runs/999999/events")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RUN_NOT_FOUND"
