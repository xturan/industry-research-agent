"""G1.1 Research Run API Contract — FastAPI integration tests.

Uses SQLite + FakeResearchExecutor (no LLM/search/provider). Verifies the full
chain: POST /v1/research/runs -> Run(QUEUED) -> fake worker -> SUCCEEDED -> result.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from apps.api.main import app
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.models import Run
from packages.db.models.enums import RunStatus
from packages.db.session import get_engine, reset_db_session_state
from packages.tasks.handlers import (
    NonRetryableTaskError,
    TaskHandlers,
)
from packages.tasks.service import TaskService


class FakeResearchExecutor:
    def __init__(self, *, result: dict | None = None, fail: bool = False) -> None:
        self.result = result or {"report": "ok", "evidence_count": 3}
        self.fail = fail
        self.calls: list[dict] = []

    def run(self, *, query: str, run_id: int | None, strategy: str | None) -> dict:
        self.calls.append({"query": query, "run_id": run_id, "strategy": strategy})
        if self.fail:
            raise NonRetryableTaskError("workflow exploded")
        return dict(self.result)


@pytest.fixture()
def client_engine(monkeypatch, tmp_path: Path) -> Generator[tuple[TestClient, object], None, None]:
    db_url = f"sqlite+pysqlite:///{(tmp_path / 'gw_api.db').as_posix()}"
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
        yield TestClient(app), engine
    finally:
        app.dependency_overrides.pop(get_db_session, None)


def _create_payload() -> dict:
    return {
        "request": {
            "query": "研究2025年合肥低空物流产业链",
            "research_strategy": "deep",
            "mode": "mock",
        }
    }


def test_create_run_returns_202_and_run_id(client_engine):
    client, _engine = client_engine
    resp = client.post("/v1/research/runs", json=_create_payload())
    assert resp.status_code == 202
    body = resp.json()
    assert body["run_id"] is not None
    assert body["status"] == "queued"
    assert body["links"]["self"].endswith(f"/runs/{body['run_id']}")


def test_get_run_queued(client_engine):
    client, _engine = client_engine
    created = client.post("/v1/research/runs", json=_create_payload()).json()
    resp = client.get(f"/v1/research/runs/{created['run_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["request"]["query"].startswith("研究2025年合肥")
    assert body["started_at"] is None


def test_result_before_completion_is_409(client_engine):
    client, _engine = client_engine
    created = client.post("/v1/research/runs", json=_create_payload()).json()
    resp = client.get(f"/v1/research/runs/{created['run_id']}/result")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "RUN_NOT_COMPLETED"


def test_unknown_run_is_404(client_engine):
    client, _engine = client_engine
    resp = client.get("/v1/research/runs/999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RUN_NOT_FOUND"


def test_full_chain_create_to_result(client_engine):
    client, engine = client_engine
    created = client.post("/v1/research/runs", json=_create_payload()).json()
    run_id = created["run_id"]

    # run the fake worker against the same DB
    fake = FakeResearchExecutor()
    with Session(engine) as session:
        TaskService(session).process_next(
            worker_id="w1", handlers=TaskHandlers(session, research_executor=fake)
        )

    # executor received the correct run identity
    assert fake.calls[0]["run_id"] == run_id

    run_resp = client.get(f"/v1/research/runs/{run_id}")
    assert run_resp.status_code == 200
    assert run_resp.json()["status"] == "succeeded"

    result_resp = client.get(f"/v1/research/runs/{run_id}/result")
    assert result_resp.status_code == 200
    assert result_resp.json()["status"] == "succeeded"
    assert result_resp.json()["result"]["evidence_count"] == 3


def test_failed_run_result_is_409_run_failed(client_engine):
    client, engine = client_engine
    created = client.post("/v1/research/runs", json=_create_payload()).json()
    fake = FakeResearchExecutor(fail=True)
    with Session(engine) as session:
        TaskService(session).process_next(
            worker_id="w1", handlers=TaskHandlers(session, research_executor=fake)
        )
    resp = client.get(f"/v1/research/runs/{created['run_id']}/result")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "RUN_FAILED"
    # GET run shows the failed status + error
    run_resp = client.get(f"/v1/research/runs/{created['run_id']}")
    assert run_resp.json()["status"] == "failed"
    assert "workflow exploded" in run_resp.json()["error"]["message"]


def test_run_status_enum_covers_all(client_engine):
    client, engine = client_engine
    # QUEUED -> RUNNING (durable) -> SUCCEEDED observed across states
    created = client.post("/v1/research/runs", json=_create_payload()).json()
    with Session(engine) as session:
        run = session.get(Run, created["run_id"])
        run.status = RunStatus.RUNNING
        session.commit()
    resp = client.get(f"/v1/research/runs/{created['run_id']}")
    assert resp.json()["status"] == "running"
