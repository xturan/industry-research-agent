from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app
from packages.core.config import get_settings
from packages.db.base import Base
from packages.db.session import get_engine, reset_db_session_state
from packages.tasks.worker import TaskWorker


def _setup_ops_api_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "ops_registry_api.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("RAW_STORAGE_DIR", str((tmp_path / "raw").as_posix()))
    monkeypatch.setenv("DELIVERY_EXPORT_DIR", str((tmp_path / "exports").as_posix()))
    monkeypatch.setenv("TASK_RETRY_BACKOFF_SECONDS", "0")
    get_settings.cache_clear()
    reset_db_session_state()
    engine = get_engine()
    Base.metadata.create_all(engine)


def test_registry_ops_and_smoke_eval_api(monkeypatch, tmp_path: Path) -> None:
    _setup_ops_api_db(monkeypatch, tmp_path)

    with TestClient(app) as client:
        templates = client.get("/registry/templates")
        assert templates.status_code == 200
        templates_payload = templates.json()
        assert len(templates_payload["templates"]) >= 3

        policies = client.get("/registry/policies")
        assert policies.status_code == 200
        policies_payload = policies.json()
        assert any(
            item["policy_id"] == "content_guardrail_v1"
            for item in policies_payload["policies"]
        )

        smoke = client.post(
            "/evals/run-smoke",
            json={
                "query": "lithium pricing outlook",
                "top_k": 6,
                "bootstrap_sample": True,
            },
        )
        assert smoke.status_code == 200
        smoke_payload = smoke.json()
        assert smoke_payload["eval_run_id"] > 0
        assert smoke_payload["summary"]["case_count"] > 0

        eval_run = client.get(f"/evals/runs/{smoke_payload['eval_run_id']}")
        assert eval_run.status_code == 200
        eval_payload = eval_run.json()
        assert len(eval_payload["items"]) > 0

        bad_task = client.post(
            "/tasks/content/generate",
            json={
                "idempotency_key": "ops-bad-task-1",
                "max_attempts": 1,
                "request": {
                    "research_run_id": 999999,
                    "content_types": ["wechat_article"],
                    "mode": "mock",
                },
            },
        )
        assert bad_task.status_code == 200
        assert (
            TaskWorker(worker_id="ops-api-test-worker", poll_interval_seconds=1).run_once()
            is True
        )

        readiness = client.get("/ops/readiness-report")
        assert readiness.status_code == 200
        readiness_payload = readiness.json()
        assert readiness_payload["status"] in {"ready", "degraded"}
        assert "database" in readiness_payload["checks"]
        assert "failure_counts" in readiness_payload

        recent_failures = client.get("/ops/failures/recent")
        assert recent_failures.status_code == 200
        failures_payload = recent_failures.json()
        assert any(item["failure_type"] == "task_job" for item in failures_payload["items"])
