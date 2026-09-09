"""G1.3.1 Global Queue Admission & Backpressure tests.

Uses SQLite + explicit InProcessAdmissionGuard (test double, not a production
multi-instance guarantee). Global QUEUED capacity is the hard limit; RUNNING is
counted but not enforced (G3 handles scheduling).
"""

from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from apps.api.main import app
from packages.agents.schemas import ResearchAnalyzeRequest
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Run
from packages.db.models.enums import RunStatus
from packages.db.session import get_engine, reset_db_session_state
from packages.research_gateway.admission import AdmissionPolicy, InProcessAdmissionGuard
from packages.research_gateway.errors import QueueCapacityExceededError
from packages.research_gateway.service import ResearchRunService

_CAP = 2


def _req(query: str = "测试合肥低空物流产业链") -> ResearchAnalyzeRequest:
    return ResearchAnalyzeRequest(query=query, research_strategy="deep")


def _make_service(monkeypatch, tmp_path: Path):
    db_url = f"sqlite+pysqlite:///{(tmp_path / 'adm.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    reset_db_session_state()
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def _svc(engine) -> tuple[Session, ResearchRunService]:
    session = Session(engine)
    service = ResearchRunService(
        session,
        admission_policy=AdmissionPolicy(max_queued_runs=_CAP),
        admission_guard=InProcessAdmissionGuard(),
    )
    return session, service


def _submit(service: ResearchRunService, *, query: str = "测试合肥低空物流产业链",
            key: str | None = None):
    return service.submit(_req(query), idempotency_key=key)


def test_below_limit_accepts(monkeypatch, tmp_path):
    engine = _make_service(monkeypatch, tmp_path)
    session, service = _svc(engine)
    resp = _submit(service)
    assert resp.status == "queued"
    assert session.scalar(select(func.count()).select_from(Run)) == 1
    session.close()


def test_at_limit_rejects(monkeypatch, tmp_path):
    engine = _make_service(monkeypatch, tmp_path)
    session, service = _svc(engine)
    _submit(service, query="A")
    _submit(service, query="B")
    try:
        _submit(service, query="C")
        raised = False
    except QueueCapacityExceededError:
        raised = True
    assert raised
    assert session.scalar(select(func.count()).select_from(Run)) == _CAP
    session.close()


def test_terminal_statuses_excluded(monkeypatch, tmp_path):
    engine = _make_service(monkeypatch, tmp_path)
    session, service = _svc(engine)
    r1 = _submit(service, query="A")
    _submit(service, query="B")
    # fill the queue (CAP=2), then one succeeds -> only 1 QUEUED remains.
    run1 = session.get(Run, r1.run_id)
    run1.status = RunStatus.SUCCEEDED
    session.commit()
    resp = _submit(service, query="C")
    assert resp.status == "queued"
    session.close()


def test_running_excluded_from_queue(monkeypatch, tmp_path):
    engine = _make_service(monkeypatch, tmp_path)
    session, service = _svc(engine)
    r1 = _submit(service, query="A")
    _submit(service, query="B")
    run1 = session.get(Run, r1.run_id)
    run1.status = RunStatus.RUNNING
    session.commit()
    resp = _submit(service, query="C")
    assert resp.status == "queued"
    session.close()


def test_full_queue_replay_succeeds(monkeypatch, tmp_path):
    engine = _make_service(monkeypatch, tmp_path)
    session, service = _svc(engine)
    _submit(service, query="A", key="k1")
    _submit(service, query="B", key="k2")
    replay = _submit(service, query="A", key="k1")
    assert replay.idempotency == {"replayed": True}
    assert session.scalar(select(func.count()).select_from(Run)) == _CAP
    session.close()


def test_full_queue_key_conflict_is_409(monkeypatch, tmp_path):
    engine = _make_service(monkeypatch, tmp_path)
    session, service = _svc(engine)
    _submit(service, query="A", key="k1")
    _submit(service, query="B", key="k2")
    from packages.research_gateway.errors import IdempotencyKeyReusedError

    try:
        _submit(service, query="C", key="k1")
        raised = False
    except IdempotencyKeyReusedError:
        raised = True
    assert raised
    session.close()


def test_concurrent_different_keys_obey_hard_cap(monkeypatch, tmp_path):
    engine = _make_service(monkeypatch, tmp_path)

    def _run(i):
        session = Session(engine)
        svc = ResearchRunService(
            session,
            admission_policy=AdmissionPolicy(max_queued_runs=_CAP),
            admission_guard=InProcessAdmissionGuard(),
        )
        try:
            return svc.submit(_req(query=f"Q{i}"), idempotency_key=f"k{i}").run_id
        except QueueCapacityExceededError:
            return None
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(_run, range(10)))

    accepted = [r for r in results if r is not None]
    assert len(accepted) == _CAP
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(Run)) == _CAP


def test_concurrent_same_key_consumes_one_slot(monkeypatch, tmp_path):
    engine = _make_service(monkeypatch, tmp_path)

    def _run(_i):
        session = Session(engine)
        svc = ResearchRunService(
            session,
            admission_policy=AdmissionPolicy(max_queued_runs=_CAP),
            admission_guard=InProcessAdmissionGuard(),
        )
        try:
            resp = svc.submit(_req(), idempotency_key="same-key")
            return resp.run_id, resp.idempotency
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_run, range(8)))

    run_ids = {r[0] for r in results}
    assert len(run_ids) == 1
    assert any(r[1] == {"replayed": True} for r in results)
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(Run)) == 1


@pytest.fixture()
def http_client(monkeypatch, tmp_path: Path) -> Generator[TestClient, None, None]:
    db_url = f"sqlite+pysqlite:///{(tmp_path / 'adm_http.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("ADMISSION_MAX_QUEUED_RUNS", "1")
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


def test_http_queue_full_returns_503_retry_after(http_client):
    payload = {"request": {"query": "研究2025年合肥低空物流产业链",
                           "research_strategy": "deep", "mode": "mock"}}
    first = http_client.post("/v1/research/runs", json=payload)
    assert first.status_code == 202
    second = http_client.post("/v1/research/runs", json=payload)
    assert second.status_code == 503
    assert second.json()["error"]["code"] == "RESEARCH_QUEUE_CAPACITY_EXCEEDED"
    assert "retry-after" in {k.lower() for k in second.headers}
