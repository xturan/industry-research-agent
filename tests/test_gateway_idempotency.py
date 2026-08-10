"""G1.2 Idempotent Run Submission tests.

Level 1 (unit, SQLite): first / replay / conflict / no-key.
HTTP: Idempotency-Key header -> replayed flag in response.
Concurrency smoke (SQLite, threads): same key -> exactly one Run + one Task.
"""

from __future__ import annotations

import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from apps.api.main import app
from packages.agents.schemas import ResearchAnalyzeRequest
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Run, TaskJob
from packages.db.models.enums import RunStatus
from packages.db.session import get_engine, reset_db_session_state
from packages.research_gateway.service import _canonical_request_hash
from packages.tasks.schemas import ResearchAnalyzeTaskSubmitRequest
from packages.tasks.service import IdempotencyConflictError, TaskService


def _req(query: str = "测试合肥低空物流产业链") -> ResearchAnalyzeRequest:
    return ResearchAnalyzeRequest(query=query, research_strategy="deep")


def _make_service(monkeypatch, tmp_path: Path):
    db_url = f"sqlite+pysqlite:///{(tmp_path / 'idem.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    reset_db_session_state()
    engine = get_engine()
    Base.metadata.create_all(engine)
    return Session(engine), TaskService(Session(engine)), engine


def test_no_key_creates_separate_runs(monkeypatch, tmp_path):
    _session, service, _engine = _make_service(monkeypatch, tmp_path)
    a, _ = service.submit_research(ResearchAnalyzeTaskSubmitRequest(request=_req()))
    b, _ = service.submit_research(ResearchAnalyzeTaskSubmitRequest(request=_req()))
    assert a.run_id != b.run_id


def test_same_key_same_payload_replays(monkeypatch, tmp_path):
    session, service, _engine = _make_service(monkeypatch, tmp_path)
    h = _canonical_request_hash(_req())
    first, replayed1 = service.submit_research(
        ResearchAnalyzeTaskSubmitRequest(request=_req()),
        run_idempotency_key="k1", run_idempotency_scope="default",
        run_idempotency_request_hash=h,
    )
    second, replayed2 = service.submit_research(
        ResearchAnalyzeTaskSubmitRequest(request=_req()),
        run_idempotency_key="k1", run_idempotency_scope="default",
        run_idempotency_request_hash=h,
    )
    assert replayed1 is False and replayed2 is True
    assert second.run_id == first.run_id
    # exactly one Run + one Task
    assert session.scalar(select(func.count()).select_from(Run)) == 1
    assert session.scalar(select(func.count()).select_from(TaskJob)) == 1


def test_same_key_different_payload_conflicts(monkeypatch, tmp_path):
    _session, service, _engine = _make_service(monkeypatch, tmp_path)
    h1 = _canonical_request_hash(_req("合肥"))
    service.submit_research(
        ResearchAnalyzeTaskSubmitRequest(request=_req("合肥")),
        run_idempotency_key="k2", run_idempotency_scope="default",
        run_idempotency_request_hash=h1,
    )
    h2 = _canonical_request_hash(_req("上海"))
    try:
        service.submit_research(
            ResearchAnalyzeTaskSubmitRequest(request=_req("上海")),
            run_idempotency_key="k2", run_idempotency_scope="default",
            run_idempotency_request_hash=h2,
        )
        raised = False
    except IdempotencyConflictError:
        raised = True
    assert raised


def test_replay_preserves_existing_run_state(monkeypatch, tmp_path):
    session, service, _engine = _make_service(monkeypatch, tmp_path)
    h = _canonical_request_hash(_req())
    first, _ = service.submit_research(
        ResearchAnalyzeTaskSubmitRequest(request=_req()),
        run_idempotency_key="k3", run_idempotency_scope="default",
        run_idempotency_request_hash=h,
    )
    # advance the run to RUNNING, then replay -> same run, still RUNNING
    run = session.get(Run, first.run_id)
    run.status = RunStatus.RUNNING
    session.commit()
    second, replayed = service.submit_research(
        ResearchAnalyzeTaskSubmitRequest(request=_req()),
        run_idempotency_key="k3", run_idempotency_scope="default",
        run_idempotency_request_hash=h,
    )
    assert replayed is True and second.run_id == first.run_id
    assert session.get(Run, first.run_id).status == RunStatus.RUNNING


def _submit_safe(service, request, key, h):
    payload = ResearchAnalyzeTaskSubmitRequest(request=request)
    for _ in range(6):
        try:
            return service.submit_research(
                payload, run_idempotency_key=key, run_idempotency_scope="default",
                run_idempotency_request_hash=h,
            )
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            time.sleep(0.05)
    raise RuntimeError("SQLite locked after retries")


def test_concurrent_same_key_single_run_and_task(monkeypatch, tmp_path):
    _session, service, engine = _make_service(monkeypatch, tmp_path)
    h = _canonical_request_hash(_req())

    def _submit(_i):
        with Session(engine) as s:
            svc = TaskService(s)
            accepted, _replayed = _submit_safe(svc, _req(), "conc-key", h)
            return accepted.run_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        run_ids = list(pool.map(_submit, range(8)))

    assert len(set(run_ids)) == 1
    with Session(engine) as s:
        run_count = s.scalar(select(func.count()).select_from(Run))
        task_count = s.scalar(select(func.count()).select_from(TaskJob))
    assert run_count == 1
    assert task_count == 1


@pytest.fixture()
def http_client(monkeypatch, tmp_path: Path) -> Generator[TestClient, None, None]:
    db_url = f"sqlite+pysqlite:///{(tmp_path / 'idem_http.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    reset_db_session_state()
    engine = get_engine()
    Base.metadata.create_all(engine)

    def _override() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db_session, None)


def _http_payload(query: str = "研究2025年合肥低空物流产业链") -> dict:
    return {"request": {"query": query, "research_strategy": "deep", "mode": "mock"}}


def test_http_idempotency_key_replays_same_run(http_client):
    headers = {"Idempotency-Key": "http-key-1"}
    first = http_client.post("/v1/research/runs", json=_http_payload(), headers=headers)
    second = http_client.post("/v1/research/runs", json=_http_payload(), headers=headers)
    assert first.status_code == 202 and second.status_code == 202
    assert first.json()["idempotency"]["replayed"] is False
    assert second.json()["idempotency"]["replayed"] is True
    assert second.json()["run_id"] == first.json()["run_id"]


def test_http_idempotency_key_conflict_on_different_payload(http_client):
    headers = {"Idempotency-Key": "http-key-2"}
    first = http_client.post("/v1/research/runs", json=_http_payload("合肥"), headers=headers)
    assert first.status_code == 202
    conflict = http_client.post("/v1/research/runs", json=_http_payload("上海"), headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_http_no_key_creates_new_runs(http_client):
    a = http_client.post("/v1/research/runs", json=_http_payload()).json()
    b = http_client.post("/v1/research/runs", json=_http_payload()).json()
    assert a["run_id"] != b["run_id"]
    assert a.get("idempotency") is None
